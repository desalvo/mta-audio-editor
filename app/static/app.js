
function controlName(el){
  const explicit=el.getAttribute('aria-label')||el.dataset.tooltip||el.getAttribute('data-label');
  if(explicit)return explicit.trim();
  if(el.matches('input[type="file"]'))return '';
  const text=(el.innerText||el.textContent||'').replace(/\s+/g,' ').trim();
  if(text)return text.replace(/^[^\p{L}\p{N}]+/u,'').trim()||text;
  const value=(el.value||'').trim();
  return value;
}
function ensureControlTooltips(root=document){
  root.querySelectorAll('button,a.nav-item,a.header-link,label.nav-item,.new-project,.tool,.toolbar-action,.tiny-btn,.dock-tab,.format-option,.analysis-btn,.preview-master').forEach(el=>{
    if(!el.getAttribute('title')){
      const name=controlName(el);
      if(name)el.setAttribute('title',name);
    }
    if(!el.getAttribute('aria-label')){
      const name=controlName(el);
      if(name && !el.textContent.trim())el.setAttribute('aria-label',name);
    }
  });
}
const tooltipObserver=new MutationObserver(records=>{
  for(const record of records){
    for(const node of record.addedNodes){
      if(node.nodeType===1){
        if(node.matches?.('button,a,label'))ensureControlTooltips(node.parentElement||document);
        else ensureControlTooltips(node);
      }
    }
  }
});
document.addEventListener('DOMContentLoaded',()=>{
  ensureControlTooltips();
  tooltipObserver.observe(document.body,{childList:true,subtree:true});
});

let current=null, currentUser=null, pluginInfo={inserts:{},schemas:{},custom:{},stem_splitter:{available:false}}, pxPerSec=70;
let sel={a:0,b:0}, dragging=false, audioCtx=null, playAudio=null, selectedTrackId=null, exportFormat='mta';
let autosaveTimer=null, autosaveBusy=false, autosaveQueued=false, autosaveEnabled=true, projectDirty=false, stemPollTimer=null, activeStemJob=null, activeStemProjectId=null;
let undoStack=[],redoStack=[],historyProjectId=null,lastHistoryState=null,timelineClipboard=null;
let playCursorMs=0, playRaf=null, mediaProgressTimer=null;
let uiState={trackTop:0,timelineTop:0,timelineLeft:0,mixerLeft:0};
let waveformJobs={}, trackPlaybacks=[], meterRaf=null, meterRunToken=0, playbackToken=0, masterMeterAnalysers=null, masterPlaybackGainNode=null;
let lastSelectedAudioFile=null, playbackPaused=false, mixerMetaTab='lyrics', pendingExportConfig=null, pendingNewProjectPath=null;
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const TRACK_COLORS=['#2f81f7','#28b463','#f0a52b','#8a58db','#e9506c','#8395a7','#24b8d4','#b26ff2','#e67e22','#16a085','#d35400','#7f8c8d'];

function mobilePlatform(){
  try{return window.MtaMobile?.getPlatform?.()||''}catch(e){return ''}
}
function isMobileClient(){return ['android','ios'].includes(mobilePlatform())}
function nativeApi(){return window.pywebview?.api||null}
function isNativeDesktop(){return !!nativeApi()||!!currentUser?.native_single_user}
let nativeBridgeReadyPromise=null;
function waitForPywebviewReadyEvent(timeoutMs){
  if(nativeApi())return Promise.resolve(nativeApi());
  if(!nativeBridgeReadyPromise){
    nativeBridgeReadyPromise=new Promise(resolve=>{
      let settled=false;
      const finish=()=>{if(settled)return;settled=true;resolve(nativeApi())};
      window.addEventListener('pywebviewready',finish,{once:true});
      setTimeout(finish,timeoutMs);
    }).finally(()=>{nativeBridgeReadyPromise=null});
  }
  return nativeBridgeReadyPromise;
}
async function waitForNativeApi(timeoutMs=15000){
  if(nativeApi())return nativeApi();
  if(!currentUser?.native_single_user)return null;
  const deadline=Date.now()+timeoutMs;
  // pywebview on macOS/ARM can finish injecting js_api after the HTTP UI is
  // already interactive. Listen for its readiness event and also poll because
  // some WebKit versions can dispatch the event before this bundle attaches.
  while(Date.now()<deadline){
    const bridge=nativeApi();
    if(bridge)return bridge;
    await Promise.race([
      waitForPywebviewReadyEvent(Math.min(1000,Math.max(1,deadline-Date.now()))),
      new Promise(resolve=>setTimeout(resolve,100)),
    ]);
  }
  return nativeApi();
}

function setMobileBusy(value){try{window.MtaMobile?.setBusy?.(!!value)}catch(e){}}
function mobileSaveRemoteFile(url,filename,mime='application/octet-stream',share=false){
  if(!isMobileClient())return false;
  try{
    if(share&&window.MtaMobile?.shareRemoteFile)window.MtaMobile.shareRemoteFile(url,filename,mime);
    else window.MtaMobile?.saveRemoteFile?.(url,filename,mime);
    return true;
  }catch(e){toast('Filesystem mobile non disponibile: '+e.message);return false}
}

async function api(url,opt={}){opt.headers=opt.headers||{};if((opt.method||'GET').toUpperCase()!=='GET')opt.headers['X-MTA-Request']='1';const r=await fetch(url,opt);if(!r.ok)throw new Error(await r.text());const ct=r.headers.get('content-type')||'';return ct.includes('json')?r.json():r}
function esc(s){return String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function toast(s){const t=$('#toast');t.textContent=s;t.style.display='block';clearTimeout(t._timer);t._timer=setTimeout(()=>t.style.display='none',4200)}
function fmtTime(sec,ms=false){sec=Math.max(0,sec);const m=Math.floor(sec/60),s=sec-m*60;return ms?`${String(m).padStart(2,'0')}:${String(Math.floor(s)).padStart(2,'0')}.${String(Math.floor((s%1)*1000)).padStart(3,'0')}`:`${m}:${String(Math.floor(s)).padStart(2,'0')}`}
function projectEnd(){let e=10000;for(const t of current?.tracks||[])for(const c of t.clips||[])e=Math.max(e,c.timeline_start_ms+(c.source_end_ms-c.source_start_ms));return e}
function widthPx(){return Math.max(980,projectEnd()/1000*pxPerSec+180)}
function trackById(id){return current?.tracks?.find(t=>t.id===id)}
function selectedTrack(){return trackById(selectedTrackId)||current?.tracks?.[0]||null}
function selectedTrackIds(){return $$('.track-check:checked').map(x=>x.value)}
function linesToText(a,b){return(a||[]).map(x=>`${(x.time_ms/1000).toFixed(3)}\t${x[b]}`).join('\n')}
function textToLines(v,key){return v.split(/\n/).map(x=>x.trim()).filter(Boolean).map(line=>{const [t,...rest]=line.split(/\t|\s{2,}/);return{time_ms:Math.max(0,Math.round(parseFloat(t)*1000)||0),[key]:rest.join(' ').trim()}})}

async function init(){if(isMobileClient())document.body.classList.add('mobile-client');try{currentUser=await api('/api/session');const a=$('#adminNav');if(a)a.hidden=!!currentUser.native_single_user||currentUser.role!=='admin';if(currentUser.native_single_user){document.body.classList.add('native-single-user');const b=$('#nativeSettingsButton');if(b)b.hidden=false}}catch(e){}if(currentUser?.native_single_user){const bridge=await waitForNativeApi();if(bridge?.get_native_settings){try{const cfg=await bridge.get_native_settings();autosaveEnabled=cfg.autosave_enabled!==false}catch(e){}}}try{pluginInfo=await api('/api/plugins')}catch(e){}await refresh()}

function toggleEditingToolsPanel(){
  const panel=$('#editingToolsPanel');if(!panel)return;
  const collapsed=panel.classList.toggle('collapsed');
  $('#editingToolsChevron').textContent=collapsed?'▸':'▾';
  panel.querySelector('.sidebar-tools-toggle')?.setAttribute('aria-expanded',String(!collapsed));
}
function toggleProjectToolsPanel(){
  const panel=$('#projectToolsPanel');if(!panel)return;
  const collapsed=panel.classList.toggle('collapsed');
  $('#projectToolsChevron').textContent=collapsed?'▸':'▾';
  panel.querySelector('.sidebar-tools-toggle')?.setAttribute('aria-expanded',String(!collapsed));
}

function toggleMobileSidebar(){
  const sidebar=$('.sidebar');if(!sidebar)return;
  const expanded=sidebar.classList.toggle('mobile-expanded');
  document.body.classList.toggle('mobile-nav-expanded',expanded);
  const button=$('#mobileSidebarToggle');
  if(button){button.setAttribute('aria-expanded',String(expanded));button.querySelector('.mobile-menu-label').textContent=expanded?'Chiudi menu':'Menu'}
}
function closeCurrentProject(){
  if(!current)return toast('Nessun progetto aperto');
  if(activeStemJob&&activeStemProjectId===current.id)return toast('Attendi il completamento della separazione prima di chiudere il progetto.');
  stopPlayback();
  clearTimeout(autosaveTimer);autosaveTimer=null;
  current=null;selectedTrackId=null;pendingExportConfig=null;playCursorMs=0;
  if($('#headerProjectName'))$('#headerProjectName').textContent='No project loaded';
  if($('#transportTime'))$('#transportTime').textContent='00:00.000';
  render();refresh();
  toast('Progetto chiuso');
}

function toggleProjectsPanel(){
  const panel=$('#projectsPanel');if(!panel)return;
  const collapsed=panel.classList.toggle('collapsed');
  $('#projectsChevron').textContent=collapsed?'▸':'▾';
  panel.querySelector('.projects-toggle')?.setAttribute('aria-expanded',String(!collapsed));
}
async function refresh(){
  const ps=await api('/api/projects');
  $('#projects').innerHTML=ps.map(p=>{
    const shared=currentUser&&p.owner_user_id&&p.owner_user_id!==currentUser.id;
    return `<div class="project-row ${current&&p.id===current.id?'active':''}" data-project="${p.id}">
      <button class="project-open" data-open-project="${p.id}" title="Apri ${esc(p.title)}">${shared?'⌘ ':''}<span>${esc(p.title)}</span><small>${shared?'shared · ':''}${p.target}</small></button>
      <button class="project-mini" data-download-project="${p.id}" title="Salva progetto localmente">⬇</button>
      ${!shared?`<button class="project-mini danger" data-delete-project="${p.id}" data-project-title="${encodeURIComponent(p.title)}" title="Elimina progetto">×</button>`:''}
    </div>`;
  }).join('');
  $$('[data-open-project]').forEach(el=>el.addEventListener('click',()=>openP(el.dataset.openProject)));
  $$('[data-download-project]').forEach(el=>el.addEventListener('click',()=>downloadProjectArchive(el.dataset.downloadProject)));
  $$('[data-delete-project]').forEach(el=>el.addEventListener('click',()=>deleteProjectFromWorkspace(el.dataset.deleteProject,decodeURIComponent(el.dataset.projectTitle||''))));
}
async function newProject(){
  if(activeStemJob)return toast('Attendi il completamento della separazione prima di creare un altro progetto.');
  pendingNewProjectPath=null;
  const nativePathRow=currentUser?.native_single_user?`
      <div class="workflow-field">
        <span>Percorso di salvataggio</span>
        <div class="native-path-row">
          <input id="newProjectPath" value="" placeholder="Scegli dove salvare il progetto…" readonly>
          <button class="utility-btn secondary" type="button" onclick="chooseNewProjectPath()">Scegli…</button>
        </div>
      </div>`:'';
  showUtilityModal('Nuovo progetto',`
    <div class="stem-workflow">
      <label class="workflow-field"><span>Nome progetto</span><input id="newProjectTitle" maxlength="200" value="Nuovo progetto" autofocus></label>
      <label class="workflow-field"><span>Tipo progetto</span><select id="newProjectTarget"><option value="MTA8">MTA8</option><option value="MTA16">MTA16</option></select></label>
      ${nativePathRow}
      <div class="utility-actions">
        <button class="utility-btn primary" type="button" onclick="createProjectFromDialog()">Crea progetto</button>
        <button class="utility-btn secondary" type="button" onclick="closeUtilityModal()">Annulla</button>
      </div>
    </div>`);
}
async function chooseNewProjectPath(){
  if(!currentUser?.native_single_user)return toast('La scelta del percorso è disponibile nell’app desktop nativa');
  const apiBridge=await waitForNativeApi();
  if(!apiBridge?.choose_project_save_path)return toast('Bridge nativo non ancora disponibile. Riprova tra un istante.');
  const title=$('#newProjectTitle')?.value?.trim()||'Nuovo progetto';
  try{
    const chosen=await apiBridge.choose_project_save_path(title);
    if(!chosen?.ok)return;
    pendingNewProjectPath=chosen.path;
    if($('#newProjectPath'))$('#newProjectPath').value=chosen.path;
  }catch(e){toast('Scelta destinazione progetto fallita: '+e.message)}
}
async function createProjectFromDialog(){
  const title=$('#newProjectTitle')?.value?.trim()||'';
  const target=$('#newProjectTarget')?.value||'MTA8';
  if(!title)return toast('Inserisci un nome per il progetto');
  if(currentUser?.native_single_user){
    if(!pendingNewProjectPath){
      await chooseNewProjectPath();
      if(!pendingNewProjectPath)return;
    }
  }
  try{
    const created=await api('/api/projects?title='+encodeURIComponent(title)+'&target='+encodeURIComponent(target),{method:'POST'});
    if(currentUser?.native_single_user&&pendingNewProjectPath&&window.pywebview?.api?.bind_project_path){
      await window.pywebview.api.bind_project_path(created.id,pendingNewProjectPath);
    }
    current=created;
    selectedTrackId=null;resetSessionHistory();
    closeUtilityModal();render();await refresh();
    toast(currentUser?.native_single_user?`Progetto ${target} creato in ${pendingNewProjectPath}`:`Progetto ${target} creato e salvato nel workspace`);
    pendingNewProjectPath=null;
  }catch(e){toast(e.message)}
}
async function openP(id){
  if(activeStemJob&&activeStemProjectId&&id!==activeStemProjectId){
    return toast('La separazione è in corso: resta nel progetto corrente fino al completamento.');
  }
  await flushAutosave();stopPlayback();uiState={trackTop:0,timelineTop:0,timelineLeft:0,mixerLeft:0};
  current=await api('/api/projects/'+id);selectedTrackId=current.tracks[0]?.id||null;resetSessionHistory();render();refresh();
}
function downloadProjectArchive(id){window.location.href=`/api/projects/${id}/archive`}
async function saveAsProject(){
  if(!current)return toast('Apri prima un progetto');
  await flushAutosave();
  const suggested=(current.title||'project').replace(/[^A-Za-z0-9._ -]+/g,'_');
  if(currentUser?.native_single_user&&window.pywebview?.api?.save_project_copy){
    try{
      const result=await window.pywebview.api.save_project_copy(current.id,suggested);
      if(result?.ok)toast(`Copia del progetto salvata in ${result.path}`);
      return;
    }catch(e){toast('Save as fallito: '+e.message);return}
  }
  window.location.href=`/api/projects/${current.id}/archive`;
}

async function saveProjectLocal(){
  if(!current)return toast('Apri prima un progetto');
  await flushAutosave();
  if(currentUser?.native_single_user&&window.pywebview?.api?.save_project){
    try{
      const suggested=(current.title||'project').replace(/[^A-Za-z0-9._ -]+/g,'_');
      const result=await window.pywebview.api.save_project(current.id,suggested);
      if(result?.ok)toast(`Progetto salvato in ${result.path}`);return;
    }catch(e){toast('Salvataggio nativo fallito: '+e.message);return}
  }
  window.location.href=`/api/projects/${current.id}/archive`;
}
async function openProjectArchive(){
  if(currentUser?.native_single_user&&window.pywebview?.api?.open_project){
    try{
      const result=await window.pywebview.api.open_project();
      if(!result?.ok)return;
      current=result.project;selectedTrackId=current.tracks[0]?.id||null;render();await refresh();toast('Progetto aperto dal filesystem');return;
    }catch(e){toast('Apertura progetto fallita: '+e.message);return}
  }
  $('#projectArchiveFile')?.click();
}
async function deleteProjectFromWorkspace(id,title){
  if(activeStemJob&&activeStemProjectId===id)return toast('Non puoi eliminare il progetto mentre è in corso la separazione.');
  if(!confirm(`Sei sicuro di voler eliminare il progetto "${title}" e tutti i file contenuti?`))return;
  if(!confirm(`Questa operazione è irreversibile. Eliminare definitivamente "${title}"?`))return;
  try{
    stopPlayback();
    await api(`/api/projects/${id}`,{method:'DELETE'});
    if(current?.id===id){current=null;selectedTrackId=null;render()}
    await refresh();toast('Progetto e relativi file eliminati dal workspace');
  }catch(e){toast(e.message)}
}

function captureUiState(){
  const tc=$('#trackColumn'),tp=$('#timelinePane'),mx=$('#mixer');
  if(tc)uiState.trackTop=tc.scrollTop;
  if(tp){uiState.timelineTop=tp.scrollTop;uiState.timelineLeft=tp.scrollLeft}
  if(mx)uiState.mixerLeft=mx.scrollLeft;
}
function restoreUiState(){
  requestAnimationFrame(()=>{
    const tc=$('#trackColumn'),tp=$('#timelinePane'),mx=$('#mixer');
    if(tc)tc.scrollTop=uiState.trackTop||0;
    if(tp){tp.scrollTop=uiState.timelineTop||0;tp.scrollLeft=uiState.timelineLeft||0}
    if(mx)mx.scrollLeft=uiState.mixerLeft||0;
  });
}
function render(){
  if(current){pxPerSec=Number(current.timeline_zoom_px_per_sec||70);mixerMetaTab=current.mixer_meta_tab||'lyrics';exportFormat=current.export_format||'mta';}
  captureUiState();
  if(!current){$('#emptyState').classList.remove('hidden');$('#editor').hidden=true;$('#mixerDock').hidden=true;return}
  $('#emptyState').classList.add('hidden');$('#editor').hidden=false;$('#mixerDock').hidden=false;
  $('#headerProjectName').textContent=current.title;
  $('#transportBpm').textContent=Number(current.bpm||120).toFixed(1);
  if($('#transportBpmInput'))$('#transportBpmInput').value=Number(current.bpm||120).toFixed(1);
  if($('#transportPitchInput'))$('#transportPitchInput').value=Number(current.pitch_semitones||0).toFixed(1);
  $('#topZoom').value=pxPerSec;
  updateTransportToggleButtons();
  if(!selectedTrackId||!trackById(selectedTrackId))selectedTrackId=current.tracks[0]?.id||null;
  const W=widthPx(),trackWidth=Math.max(160,Math.min(520,Number(current.track_panel_width_px)||225));
  $('#editor').innerHTML=`
    ${toolbarHtml()}
    <div class="editor-grid" id="editorGrid" style="--track-column-width:${trackWidth}px">
      <div class="track-column" id="trackColumn"><div class="track-column-head">TRACKS</div>${current.tracks.map((t,i)=>trackHead(t,i)).join('')}</div>
      <div class="track-resizer" id="trackResizer" title="Ridimensiona Tracks"></div>
      <div class="timeline-pane" id="timelinePane"><div class="ruler"><canvas id="ruler" width="${W}" height="30"></canvas></div><div class="lanes" id="lanes" style="width:${W}px">${current.tracks.map((t,i)=>lane(t,W,i)).join('')}<div class="selection" id="selection" style="display:none"></div><div class="playhead" id="playhead" style="left:${playCursorMs/1000*pxPerSec}px"></div></div></div>
      ${inspectorHtml()}
    </div>`;
  $('#mixerDock').innerHTML=mixerHtml();
  updateMixerDockLayout();updatePanelMenuButtons();
  drawRuler();bindTimeline();bindTrackTimelineScroll();bindTrackResizer();
  current.tracks.forEach(drawWave);ensureWaveforms();updateSel();bindModelInputs();updateMuteSoloVisuals();restoreUiState();ensureSessionHistory();updateEditActionState();
}
async function createMetronomeTrack(){
  if(!current)return toast('Apri prima un progetto');
  if(!current.tracks.length)return toast('Importa almeno una traccia audio per definire la durata del progetto');
  try{
    await flushAutosave();
    const result=await api(`/api/projects/${current.id}/metronome-track`,{method:'POST'});
    current=result.project;
    selectedTrackId=result.track.id;
    render();
    await refresh();
    toast(`Traccia metronomo creata a ${Number(current.bpm).toFixed(1)} BPM`);
  }catch(e){toast(e.message)}
}

function toolbarHtml(){
  const refs=current.tracks.map(t=>`<option value="${t.id}">${esc(t.name)}</option>`).join('');
  const stem=pluginInfo.stem_splitter||{};
  return `<div class="editor-toolbar">
    <button class="tool active"><strong>➤</strong>Select</button><button class="tool"><strong>✂</strong>Split</button><button class="tool active"><strong>▭</strong>Range</button><button class="tool"><strong>↔</strong>Ripple</button>
    <div class="toolbar-sep"></div><div class="toolbar-group"><label>Snap</label><select><option>Bars</option><option>Beats</option><option>Off</option></select></div>
    <button class="toolbar-action emphasis" onclick="openStemWorkflow()">▥ Import &amp; Separate</button>
    <button class="toolbar-action" onclick="createMetronomeTrack()" title="Crea una traccia click per tutta la durata corrente del progetto">♩ Metronomo</button>
    <div class="toolbar-group"><input id="newTrackFile" type="file" accept=".mp3,.wav,.flac,.m4a,audio/*" onchange="addTrack()"><select id="newSync"><option value="manual">Manual sync</option><option value="auto">Auto sync</option></select><input id="newOffset" type="number" value="0" title="Offset ms" style="width:72px"><select id="newRef" style="max-width:115px">${refs}</select><button class="toolbar-action" onclick="addTrack()">♫ Import Audio Track</button></div>
    <div class="toolbar-sep"></div><button id="undoBtn" class="toolbar-action" onclick="undoEdit()">↶ Undo</button><button id="redoBtn" class="toolbar-action" onclick="redoEdit()">↷ Redo</button><button class="toolbar-action" onclick="cutTimelineSelection()">✂ Cut</button><button class="toolbar-action" onclick="copyTimelineSelection()">⧉ Copy</button><button id="pasteBtn" class="toolbar-action" onclick="pasteTimelineSelection()">▣ Paste</button><button class="toolbar-action danger" onclick="removeTimelineSelection()">⌫ Remove</button> <div class="toolbar-grow"></div><span class="selection-info" id="selectionInfo">0.000 → 0.000 s</span><button class="toolbar-action danger" onclick="deleteSelection(false)">Delete tracks</button><label class="hint"><input id="ripple" type="checkbox"> ripple</label><button class="toolbar-action danger" onclick="deleteSelection(true)">Delete song segment</button>
  </div>`
}

function trackHead(t,i){
  const color=t.color||TRACK_COLORS[i%TRACK_COLORS.length],anySolo=current.tracks.some(x=>x.solo),inaudible=t.mute||(anySolo&&!t.solo);
  const audioMode=t.channels===2?'STEREO':(t.channels===1?'MONO':(t.channel_layout?String(t.channel_layout).toUpperCase():''));
  return `<div class="track-head ${t.id===selectedTrackId?'selected':''} ${inaudible?'audibly-muted':''}" id="head-${t.id}" style="--track-color:${color}" onclick="selectTrack('${t.id}')" oncontextmenu="openTrackContextMenu(event,'${t.id}')">
    <div class="track-color"></div>
    <div class="track-num">${i+1}</div>
    <div class="track-info">
      <div class="track-title-row">
        <input class="track-name model-input" data-i="${i}" data-k="name" value="${esc(t.name)}" title="Rinomina traccia" onchange="renameTrackInline('${t.id}',this.value)">
        <span class="track-type">${esc(t.type)}${audioMode?` · ${esc(audioMode)}`:''}</span>
      </div>
      <div class="track-buttons">
        <button class="tiny-btn" title="Rinomina traccia" onclick="event.stopPropagation();renameTrack('${t.id}')">✎</button>
        <button data-mute-track="${t.id}" class="tiny-btn mute ${t.mute?'on':''}" onclick="event.stopPropagation();toggleBool(this,'${t.id}','mute')">M</button>
        <button data-solo-track="${t.id}" class="tiny-btn solo ${t.solo?'on':''}" onclick="event.stopPropagation();toggleBool(this,'${t.id}','solo')">S</button>
        <button class="tiny-btn preview" onclick="event.stopPropagation();previewTrack('${t.id}')">▶</button>
        <input class="track-mini-slider track-volume-range" data-volume-track="${t.id}" type="range" min="-60" max="12" step="0.5" value="${t.volume_db}" oninput="setTrackVolume('${t.id}',this.value)">
        <input class="track-db-input volume-number" id="db-${t.id}" data-volume-number="${t.id}" type="number" min="-60" max="12" step="0.1" value="${Number(t.volume_db).toFixed(1)}" oninput="setTrackVolume('${t.id}',this.value)" aria-label="Volume ${esc(t.name)} in dB" title="Volume in dB">
      </div>
    </div>
    <label class="track-select-wrap" title="Seleziona traccia" onclick="event.stopPropagation()"><input class="track-check" type="checkbox" value="${t.id}"></label>
  </div>`;
}
function closeTrackContextMenu(){
  const menu=$('#trackContextMenu');
  if(menu)menu.remove();
}
function openTrackContextMenu(event,id){
  event.preventDefault();event.stopPropagation();closeTrackContextMenu();
  const track=trackById(id);if(!track)return;
  selectedTrackId=id;
  $$('.track-head').forEach(el=>el.classList.toggle('selected',el.id===`head-${id}`));
  const stem=pluginInfo.stem_splitter||{};
  const disabled=stem.available?'':'disabled';
  const menu=document.createElement('div');
  menu.id='trackContextMenu';
  menu.className='track-context-menu';
  menu.innerHTML=`
    <button type="button" onclick="closeTrackContextMenu();renameTrack('${id}')">✎ <span>Rinomina</span></button>
    <button type="button" ${disabled} onclick="closeTrackContextMenu();startTrackStemSplit('${id}')">▥ <span>Separa</span></button>
    <button type="button" class="danger" onclick="closeTrackContextMenu();deleteTracksByIds(['${id}'])">× <span>Rimuovi</span></button>
  `;
  document.body.appendChild(menu);
  const pad=8,r=menu.getBoundingClientRect();
  menu.style.left=`${Math.max(pad,Math.min(event.clientX,window.innerWidth-r.width-pad))}px`;
  menu.style.top=`${Math.max(pad,Math.min(event.clientY,window.innerHeight-r.height-pad))}px`;
}
async function startTrackStemSplit(id){
  if(!current)return;
  const track=trackById(id);if(!track)return toast('Traccia non trovata');
  const stem=pluginInfo.stem_splitter||{};
  if(!stem.available)return toast('Demucs non è disponibile in questo runtime');
  const model=stem.recommended_model||(stem.models||['htdemucs_6s'])[0];
  await flushAutosave();
  try{
    const job=await api(`/api/projects/${current.id}/tracks/${id}/stem-jobs?model=${encodeURIComponent(model)}`,{method:'POST'});
    activeStemJob=job.id;
    activeStemProjectId=job.project_id;
    showStemProgress(job);
    pollStemJob(job.id);
  }catch(e){toast(e.message)}
}
function renameTrackInline(id,value){const t=trackById(id);if(!t)return;const v=String(value||'').trim();if(!v)return;t.name=v.slice(0,200);markDirty()}
function renameTrack(id){const t=trackById(id);if(!t)return;const value=prompt('Nome traccia',t.name);if(value===null)return;const v=value.trim();if(!v)return toast('Il nome non può essere vuoto');t.name=v.slice(0,200);render();markDirty(100)}
function lane(t,W,i){const color=t.color||TRACK_COLORS[i%TRACK_COLORS.length];const anySolo=current.tracks.some(x=>x.solo);const inaudible=t.mute||(anySolo&&!t.solo);return `<div class="lane ${inaudible?'audibly-muted':''}" id="lane-${t.id}" data-track="${t.id}" style="width:${W}px;--track-color:${color}" oncontextmenu="openTrackContextMenu(event,'${t.id}')"><canvas class="wave" id="wave-${t.id}" width="${W}" height="78"></canvas><div class="waveform-progress ${t.waveform_peaks?.length?'hidden':''}" id="wave-progress-${t.id}"><div class="waveform-progress-bar" id="wave-progress-bar-${t.id}" style="width:2%"></div><span id="wave-progress-label-${t.id}">Waveform…</span></div>${(t.clips||[]).map((c,j)=>{const l=c.timeline_start_ms/1000*pxPerSec,w=(c.source_end_ms-c.source_start_ms)/1000*pxPerSec;return `<div class="clip-block" style="left:${l}px;width:${Math.max(2,w)}px"><span class="clip-label">${esc(t.name)}_${String(j+1).padStart(2,'0')}</span></div>`}).join('')}</div>`}

function inspectorHtml(){const t=selectedTrack();if(!t)return `<aside class="inspector"><div class="inspector-tabs"><button class="inspector-tab active">Inspector</button><button class="inspector-tab">Stems</button><button class="inspector-tab">Metadata</button></div><div class="inspector-body"><p class="hint">Import a track to open the inspector.</p></div></aside>`;const i=current.tracks.indexOf(t);return `<aside class="inspector" id="inspector"><div class="inspector-tabs"><button class="inspector-tab active">Inspector</button><button class="inspector-tab">Stems</button><button class="inspector-tab">Metadata</button></div><div class="inspector-body"><div class="inspector-track-title"><span>◉</span>${esc(t.name)}<label class="tool" style="margin-left:auto;min-width:auto;height:28px">Replace<input type="file" accept="audio/*,.mp3,.wav" hidden onchange="replaceTrack('${t.id}',this)"></label></div><div class="inspector-row"><label>Volume</label><input class="track-volume-range" data-volume-track="${t.id}" type="range" min="-60" max="12" step="0.5" value="${t.volume_db}" oninput="setTrackVolume('${t.id}',this.value)"><input class="valuebox volume-number" id="ins-db-${t.id}" data-volume-number="${t.id}" type="number" min="-60" max="12" step="0.1" value="${Number(t.volume_db).toFixed(1)}" oninput="setTrackVolume('${t.id}',this.value)" aria-label="Volume ${esc(t.name)} in dB" title="Volume in dB"></div><div class="inspector-row"><label>Pan</label><input type="range" min="-1" max="1" step="0.01" value="${t.pan||0}" oninput="setTrackPan('${t.id}',this.value)"><div class="valuebox" id="pan-${t.id}">${Number(t.pan||0).toFixed(2)}</div></div><div class="inspector-row"><label>Type</label><select class="model-input" data-i="${i}" data-k="type">${['drums','bass','guitars','keyboards','orchestra','winds','melody','click','choirs','other'].map(x=>`<option ${x===t.type?'selected':''}>${x}</option>`).join('')}</select><div class="valuebox">${t.duration_ms?fmtTime(t.duration_ms/1000):'--'}</div></div>${insertPanelHtml(t,false)}<div class="panel-section"><div class="section-title">Track export</div><div class="track-export-actions"><button onclick="exportTrack('${t.id}','wav')">WAV</button><button onclick="exportTrack('${t.id}','mp3')">MP3</button><button onclick="exportTrack('${t.id}','flac')">FLAC</button></div></div><div class="panel-section"><div class="collapsed-row">› Send</div><div class="collapsed-row">› Track Automation</div><div class="collapsed-row">› Advanced</div></div></div></aside>`}

function insertPanelHtml(owner,isMaster){const inserts=owner.inserts||owner.master_inserts||[];return `<div class="panel-section"><div class="panel-section-title"><span>⌄ Inserts</span><span>${inserts.length}/16</span></div><div class="insert-list">${inserts.map((x,n)=>insertHtml(x,n,isMaster)).join('')||'<div class="hint" style="padding:7px">No inserts configured.</div>'}</div>${insertAddHtml(isMaster)}</div>`}
function pluginLabel(x){return x.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase())}
function insertHtml(x,n,isMaster,trackId=''){
  const presets=pluginInfo.inserts?.[x.plugin]||['default'];
  const all=(x.params&&Object.keys(x.params).length&&!presets.includes(x.preset))?[...presets,x.preset]:presets;
  const icons={normalizer:'↕',compressor:'◫',limiter:'│',delay:'↝',reverb_lexicon:'◌',room_ambience:'⌂',graphic_eq_32:'▥',amplify:'＋',stereo_imager:'↔',maximizer_loudness:'▲',mastering_wizard:'✦',denoise:'≈',crackle_cleaner:'⌁'};
  const tid=trackId||'';
  return `<div class="insert">
    <div class="insert-icon">${icons[x.plugin]||'◇'}</div>
    <div><div class="insert-name">${n+1} · ${esc(pluginLabel(x.plugin))}</div>
      <select onchange="changeInsertPreset(${isMaster},'${x.id}',this.value,'${tid}')">${all.map(p=>`<option ${p===x.preset?'selected':''}>${esc(p)}</option>`).join('')}</select>
    </div>
    <button class="insert-edit" title="Configura" onclick="openInsertEditor(${isMaster},'${x.id}','${tid}')">⚙</button>
    <button class="insert-power ${x.enabled?'':'off'}" title="Attiva/disattiva" onclick="toggleInsert(${isMaster},'${x.id}','${tid}')">⏻</button>
    <button class="insert-remove" title="Rimuovi insert" onclick="removeInsert(${isMaster},'${x.id}','${tid}')">×</button>
  </div>`;
}
function insertAddHtml(isMaster,trackId=''){
  const kinds=Object.keys(pluginInfo.inserts||{});
  const suffix=isMaster?'master':(trackId?`mix-${trackId}`:'track');
  return `<div class="insert-add">
    <select id="${suffix}PluginType" onchange="refreshPresetSelect(${isMaster},'${trackId}')">${kinds.map(x=>`<option value="${x}">${esc(pluginLabel(x))}</option>`).join('')}</select>
    <select id="${suffix}PluginPreset"></select>
    <button onclick="addInsert(${isMaster},'${trackId}')">＋</button>
  </div>`;
}
function insertArray(isMaster,trackId=''){
  if(isMaster)return current.master_inserts;
  const t=trackId?trackById(trackId):selectedTrack();
  return t?.inserts||[];
}
function insertControlPrefix(isMaster,trackId=''){return isMaster?'master':(trackId?`mix-${trackId}`:'track')}
const insertWaveformTimers={};
function queueInsertWaveformRefresh(trackId){
  if(!trackId||!current)return;
  clearTimeout(insertWaveformTimers[trackId]);
  insertWaveformTimers[trackId]=setTimeout(async()=>{
    delete insertWaveformTimers[trackId];
    const track=trackById(trackId);if(!track)return;
    try{
      await flushAutosave();
      track.waveform_peaks=[];
      track.waveform_revision='';
      updateWaveProgress(trackId,3,'Ricalcolo waveform dopo modifica insert…');
      const job=await api(`/api/projects/${current.id}/tracks/${trackId}/waveform-jobs?force=true`,{method:'POST'});
      if(job.status==='completed'&&job.result){
        track.waveform_peaks=job.result.peaks||[];
        track.waveform_revision=job.result.revision||'';
        drawWave(track);
        $(`#wave-progress-${trackId}`)?.classList.add('hidden');
        return;
      }
      waveformJobs[trackId]=job.id;
      pollWaveformJob(trackId,job.id);
    }catch(e){
      updateWaveProgress(trackId,0,'Ricalcolo waveform fallito');
    }
  },180);
}

function refreshPresetSelect(isMaster,trackId=''){
  const pre=insertControlPrefix(isMaster,trackId),kind=$(`#${pre}PluginType`)?.value,el=$(`#${pre}PluginPreset`);
  if(!el)return;
  el.innerHTML=(pluginInfo.inserts?.[kind]||['default']).map(x=>`<option>${esc(x)}</option>`).join('');
}
function addInsert(isMaster,trackId=''){
  const pre=insertControlPrefix(isMaster,trackId),kind=$(`#${pre}PluginType`)?.value,preset=$(`#${pre}PluginPreset`)?.value||'default',arr=insertArray(isMaster,trackId);
  if(!kind)return toast('Seleziona un insert');
  if(!arr||arr.length>=16)return toast('Maximum 16 inserts per chain');
  arr.push({id:crypto.randomUUID().replaceAll('-','').slice(0,10),plugin:kind,preset,enabled:true,params:{}});
  markDirty(100);
  if(!isMaster)queueInsertWaveformRefresh(trackId||selectedTrack()?.id||'');
  if(trackId||isMaster)openMixerInsertManager(trackId||'master');else render();
}
function removeInsert(isMaster,id,trackId=''){
  const arr=insertArray(isMaster,trackId);if(!arr)return;
  const idx=arr.findIndex(x=>x.id===id);if(idx<0)return;
  arr.splice(idx,1);markDirty(100);
  if(!isMaster)queueInsertWaveformRefresh(trackId||selectedTrack()?.id||'');
  if(trackId||isMaster)openMixerInsertManager(trackId||'master');else render();
}
function toggleInsert(isMaster,id,trackId=''){
  const x=insertArray(isMaster,trackId)?.find(p=>p.id===id);if(!x)return;
  x.enabled=!x.enabled;markDirty(100);
  if(!isMaster)queueInsertWaveformRefresh(trackId||selectedTrack()?.id||'');
  if(trackId||isMaster)openMixerInsertManager(trackId||'master');else render();
}
function changeInsertPreset(isMaster,id,preset,trackId=''){
  const x=insertArray(isMaster,trackId)?.find(p=>p.id===id);if(!x)return;
  x.preset=preset;x.params={};markDirty(100);
  if(!isMaster)queueInsertWaveformRefresh(trackId||selectedTrack()?.id||'');
  if(playAudio||trackPlaybacks.length){
    const pos=playCursorMs;stopPlayback();setPlayCursor(pos);setTimeout(()=>previewMaster(),140);
  }
}
function editorPresetChanged(isMaster,id,preset,trackId=''){
  changeInsertPreset(isMaster,id,preset,trackId);
  setTimeout(()=>openInsertEditor(isMaster,id,trackId),30);
}
function defaultPluginParams(kind){const schema=pluginInfo.schemas?.[kind]||{};return Object.fromEntries(Object.entries(schema).map(([k,v])=>[k,Number(v.default??0)]))}
function graphicEqEditorFields(schema,params){
  return `<div class="geq-editor">
    <div class="geq-scale"><span>+12</span><span>0</span><span>-12</span></div>
    <div class="geq-bands">${Object.entries(schema).map(([k,v])=>{
      const freq=k.slice(1),value=Number(params[k]??v.default);
      return `<label class="geq-band" title="${freq} Hz · ${value.toFixed(1)} dB">
        <span class="geq-value" id="geq-val-${k}">${value.toFixed(1)}</span>
        <input class="plugin-param geq-slider" data-key="${k}" type="range" min="${v.min}" max="${v.max}" step="${v.step}" value="${value}" oninput="$('#geq-val-${k}').textContent=Number(this.value).toFixed(1)">
        <span class="geq-freq">${Number(freq)>=1000?(Number(freq)/1000).toFixed(Number(freq)%1000?1:0)+'k':freq}</span>
      </label>`;
    }).join('')}</div>
  </div>`;
}
function openInsertEditor(isMaster,id,trackId=''){
  const x=insertArray(isMaster,trackId)?.find(p=>p.id===id);if(!x)return;
  const schema=pluginInfo.schemas?.[x.plugin]||{},custom=x.preset.startsWith('user:')?pluginInfo.custom?.[x.plugin]?.[x.preset.slice(5)]:null;
  const presets=pluginInfo.inserts?.[x.plugin]||['default'];
  const params=Object.keys(x.params||{}).length?x.params:(custom||defaultPluginParams(x.plugin));
  const fields=x.plugin==='graphic_eq_32'
    ?graphicEqEditorFields(schema,params)
    :Object.entries(schema).map(([k,v])=>`<label class="plugin-field"><span>${esc(k.replaceAll('_',' '))}</span><input class="plugin-param" data-key="${k}" type="number" min="${v.min}" max="${v.max}" step="${v.step}" value="${Number(params[k]??v.default)}"><small>${v.min} … ${v.max}</small></label>`).join('');
  const editorHtml=`<label class="plugin-preset-row"><span>Preset</span><select onchange="editorPresetChanged(${isMaster},'${id}',this.value,'${trackId}')">${presets.map(p=>`<option value="${esc(p)}" ${p===x.preset?'selected':''}>${esc(p)}</option>`).join('')}</select></label><p class="hint">Il preset selezionato viene applicato realmente alla catena audio. I controlli sotto servono per creare una configurazione custom.</p><p class="hint">${x.plugin==='graphic_eq_32'?'Trascina graficamente i 32 fader di banda.':'Custom values are validated server-side.'}</p><div class="${x.plugin==='graphic_eq_32'?'':'plugin-param-grid'}">${fields||'<p class="hint">This processor currently exposes factory presets only.</p>'}</div><label class="preset-save-name"><span>Custom preset name</span><input id="customPresetName" maxlength="80" placeholder="My preset"></label><div class="modal-actions"><button onclick="applyInsertConfig(${isMaster},'${id}',false,'${trackId}')">Apply custom</button><button onclick="applyInsertConfig(${isMaster},'${id}',true,'${trackId}')">Save preset & apply</button><button onclick="${trackId||isMaster?`openMixerInsertManager('${trackId||'master'}')`:'closeExportMapping()'}">Cancel</button></div>`;
  if(trackId||isMaster){
    showUtilityModal(`${pluginLabel(x.plugin)} configuration`,editorHtml);
  }else{
    const m=$('#exportMapModal');if(!m)return;
    m.innerHTML=`<h3>${esc(pluginLabel(x.plugin))} configuration</h3>${editorHtml}`;m.classList.remove('hidden');
  }
}
async function applyInsertConfig(isMaster,id,savePreset,trackId=''){
  const x=insertArray(isMaster,trackId)?.find(p=>p.id===id);if(!x)return;
  const params={};$$('.plugin-param').forEach(el=>params[el.dataset.key]=Number(el.value));
  if(savePreset){
    const name=$('#customPresetName')?.value?.trim();if(!name)return toast('Enter a custom preset name');
    try{const r=await api('/api/presets',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({plugin:x.plugin,name,params})});pluginInfo=await api('/api/plugins');x.preset=r.preset;x.params={};toast('Custom preset saved')}catch(e){return toast(e.message)}
  }else{x.preset='custom';x.params=params}
  closeExportMapping();markDirty(100);
  if(!isMaster)queueInsertWaveformRefresh(trackId||selectedTrack()?.id||'');
  if(trackId||isMaster)openMixerInsertManager(trackId||'master');else render();
}
function openMixerInsertManager(owner){
  if(!current)return;
  const isMaster=owner==='master',track=isMaster?null:trackById(owner);
  if(!isMaster&&!track)return;
  const arr=isMaster?current.master_inserts:(track.inserts||[]);
  const title=isMaster?'MASTER inserts':`${track.name} · Inserts`;
  showUtilityModal(title,`<div class="mixer-insert-manager">
    <div class="insert-list">${arr.map((x,n)=>insertHtml(x,n,isMaster,isMaster?'':track.id)).join('')||'<div class="hint" style="padding:8px">No inserts configured.</div>'}</div>
    ${insertAddHtml(isMaster,isMaster?'':track.id)}
    <div class="utility-actions"><button class="utility-btn secondary" onclick="closeUtilityModal()">Chiudi</button></div>
  </div>`);
  requestAnimationFrame(()=>refreshPresetSelect(isMaster,isMaster?'':track.id));
}
function mixerHtml(){
  const limit=current.target==='MTA8'?8:16,over=current.tracks.length>limit;
  const exportPane=current.export_panel_visible?exportPaneHtml(limit,over):'';
  const metaPane=current.metadata_panel_visible?metaPaneHtml():'';
  return `<div class="mixer-pane" id="mixer">
    <div class="dock-tabs"><button class="dock-tab active">Mixer</button><button class="dock-tab">Master / Preview</button><button id="realtimeBtn" class="dock-tab realtime-toggle ${current.realtime_meter_enabled?'active':''}" onclick="toggleRealtimeMeters()">RealTime</button>
      <button class="dock-tab" onclick="toggleMuteAll()">${current.tracks.length&&current.tracks.every(t=>t.mute)?'Unmute all':'Mute all'}</button><button class="dock-tab" onclick="toggleSoloAll()">${current.tracks.length&&current.tracks.every(t=>t.solo)?'Unsolo all':'Solo all'}</button><button class="dock-tab" onclick="toggleAllPlugins()">${[...(current.master_inserts||[]),...current.tracks.flatMap(t=>t.inserts||[])].some(x=>x.enabled)?'Bypass all FX':'Enable all FX'}</button>
      <div class="automix-control"><label class="switch"><input type="checkbox" ${current.auto_mix_enabled?'checked':''} onchange="setAutoMix(this.checked)"><span></span></label><b>Auto Mix</b><select id="autoMixStyle" onchange="changeAutoMixStyle(this.value)"><option value="balanced" ${current.auto_mix_style==='balanced'?'selected':''}>Balanced</option><option value="studio" ${current.auto_mix_style==='studio'?'selected':''}>Studio</option><option value="live" ${current.auto_mix_style==='live'?'selected':''}>Live</option><option value="gentle" ${current.auto_mix_style==='gentle'?'selected':''}>Gentle</option></select><button onclick="showAutoMixInfo()">?</button></div>
      <span class="capacity-badge ${over?'over':''}">${current.tracks.length} project tracks · ${limit} ${current.target} output slots</span>
    </div>
    <div class="channels">${current.tracks.map((t,i)=>channelHtml(t,i)).join('')}<div class="master-divider" aria-hidden="true"></div>${masterChannelHtml()}</div>
  </div>${exportPane}${metaPane}<div id="exportMapModal" class="modal-card export-map-modal hidden"></div>`;
}
function exportPaneHtml(limit,over){
  return `<div class="export-pane" id="exportPane"><div class="dock-tabs"><button class="dock-tab active">Export</button><button class="dock-tab">Single Track Export</button><button class="dock-close" onclick="toggleMixerPanel('export')" title="Nascondi Export">×</button></div><div class="export-content"><div class="export-title">Final output</div>${over?`<div class="export-warning">Project has more tracks than ${current.target}. MTA export will ask how to merge tracks into ${limit} output slots.</div>`:''}<div class="format-option ${exportFormat==='mta'?'selected':''}" onclick="selectExport('mta')"><span>▧ MTA (${current.target})</span><span>›</span></div><div class="format-option ${exportFormat==='wav'?'selected':''}" onclick="selectExport('wav')"><span>♫ WAV (24 bit, 44.1 kHz)</span><span>›</span></div><div class="format-option ${exportFormat==='mp3'?'selected':''}" onclick="selectExport('mp3')"><span>♫ MP3 (320 kbps)</span><span>›</span></div><div class="format-option ${exportFormat==='flac'?'selected':''}" onclick="selectExport('flac')"><span>♫ FLAC (lossless)</span><span>›</span></div><div class="export-actions"><button onclick="doExport('mta')">Export MTA</button><button onclick="doExport('wav')">WAV</button><button onclick="doExport('mp3')">MP3</button><button onclick="doExport('flac')">FLAC</button></div><button class="preview-master" onclick="previewMaster()">▶ Render &amp; Preview Master</button><button class="analysis-btn" onclick="showMtaAnalysis()">⌁ MTA reverse analysis</button></div></div>`;
}
function metaPaneHtml(){
  const config={lyrics:['text','Lyrics'],chords:['chord','Chords'],markers:['label','Markers']},[key,label]=config[mixerMetaTab]||config.lyrics,rows=current[mixerMetaTab]||[];
  return `<div class="meta-pane" id="metaPane"><div class="dock-tabs"><button class="dock-tab ${mixerMetaTab==='lyrics'?'active':''}" onclick="showMetaPanel('lyrics')">Lyrics</button><button class="dock-tab ${mixerMetaTab==='chords'?'active':''}" onclick="showMetaPanel('chords')">Chords</button><button class="dock-tab ${mixerMetaTab==='markers'?'active':''}" onclick="showMetaPanel('markers')">Markers</button><button class="dock-close" onclick="toggleMixerPanel('meta')" title="Nascondi Lyrics/Chords/Markers">×</button></div><div class="meta-tabs-content"><div class="meta-list">${rows.map(x=>`<div class="meta-line"><time>${fmtTime(x.time_ms/1000)}</time><span>${esc(x[key])}</span></div>`).join('')||`<div class="hint">No synchronized ${label.toLowerCase()} yet.</div>`}</div><div class="meta-actions"><button class="tool" onclick="editTimed('${mixerMetaTab}')">Edit ${label.toLowerCase()}</button></div><textarea id="lyrics" hidden>${esc(linesToText(current.lyrics,'text'))}</textarea><textarea id="chords" hidden>${esc(linesToText(current.chords,'chord'))}</textarea><textarea id="markers" hidden>${esc(linesToText(current.markers,'label'))}</textarea></div></div>`;
}
function updateMixerDockLayout(){
  const dock=$('#mixerDock');if(!dock||!current)return;
  const exp=!!current.export_panel_visible,meta=!!current.metadata_panel_visible;
  dock.classList.toggle('export-hidden',!exp);
  dock.classList.toggle('meta-hidden',!meta);
  dock.classList.toggle('sidepanels-hidden',!exp&&!meta);
  dock.style.gridTemplateColumns=exp&&meta
    ?'minmax(0,1fr) 350px 320px'
    :exp
      ?'minmax(0,1fr) 350px'
      :meta
        ?'minmax(0,1fr) 320px'
        :'minmax(0,1fr)';
  const mixer=$('#mixer');
  if(mixer)mixer.style.width='100%';
}
function updatePanelMenuButtons(){
  $('#exportPanelMenuBtn')?.classList.toggle('panel-hidden',!current?.export_panel_visible);
  $('#metaPanelMenuBtn')?.classList.toggle('panel-hidden',!current?.metadata_panel_visible);
}
function toggleMixerPanel(which){
  if(!current)return;
  if(which==='export')current.export_panel_visible=!current.export_panel_visible;
  else current.metadata_panel_visible=!current.metadata_panel_visible;
  render();
  requestAnimationFrame(()=>{
    updateMixerDockLayout();
    $('#mixer')?.scrollIntoView({block:'nearest'});
  });
  markDirty(100);
  focusMixer();
}
function showMetaPanel(kind='lyrics'){
  if(!current)return;mixerMetaTab=kind;
  current.mixer_meta_tab=kind;
  current.metadata_panel_visible=true;render();markDirty(100);focusMixer();
}
function effectiveTrackChannels(t){
  if(Number(t?.channels)===1){
    const stereoFx=(t.inserts||[]).some(x=>x.enabled&&x.plugin==='stereo_imager');
    return stereoFx?2:1;
  }
  return 2;
}
function clampPan(v){const n=Number(v);return Number.isFinite(n)?Math.max(-1,Math.min(1,n)):0}
function panLabel(v){const n=clampPan(v);if(Math.abs(n)<0.005)return 'C';return n<0?`L${Math.round(Math.abs(n)*100)}`:`R${Math.round(n*100)}`}
function updatePanUi(id,value){
  const n=clampPan(value),angle=n*55;
  const knob=$(`#pan-knob-${id}`),input=$(`#pan-input-${id}`),label=$(`#pan-label-${id}`);
  if(knob)knob.style.setProperty('--pan-angle',`${angle}deg`);
  if(input&&document.activeElement!==input)input.value=n.toFixed(2);
  if(label)label.textContent=panLabel(n);
}
function startPanDrag(event,id){
  if(event.button!==0&&event.pointerType!=='touch')return;
  event.preventDefault();event.stopPropagation();
  const t=trackById(id);if(!t)return;
  const startX=event.clientX,start=clampPan(t.pan);
  const move=ev=>setTrackPan(id,start+(ev.clientX-startX)/70);
  const up=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',up);markDirty(100)};
  window.addEventListener('pointermove',move);window.addEventListener('pointerup',up,{once:true});
}
function resetTrackPan(id){setTrackPan(id,0)}

function channelHtml(t,i){
  const anySolo=current.tracks.some(x=>x.solo),inaudible=t.mute||(anySolo&&!t.solo);
  const color=t.color||TRACK_COLORS[i%TRACK_COLORS.length],pan=clampPan(t.pan),angle=pan*55;
  const staticLevel=Math.max(4,Math.min(100,(Number(t.volume_db)+60)/72*100));
  const outChannels=effectiveTrackChannels(t),stereoByFx=Number(t.channels)===1&&outChannels===2;
  return `<div class="channel ${inaudible?'audibly-muted':''}" data-channel-track="${t.id}" style="--track-color:${color}">
    <div class="channel-name">${esc(t.name)}</div>
    <div class="pan-control">
      <div id="pan-knob-${t.id}" class="pan-knob interactive" style="--pan-angle:${angle}deg" title="Pan ${pan.toFixed(2)} · trascina, doppio click = center" onpointerdown="startPanDrag(event,'${t.id}')" ondblclick="resetTrackPan('${t.id}')" role="slider" tabindex="0" aria-valuemin="-1" aria-valuemax="1" aria-valuenow="${pan.toFixed(2)}"></div>
      <input id="pan-input-${t.id}" class="pan-value-input" type="number" min="-1" max="1" step="0.01" value="${pan.toFixed(2)}" oninput="setTrackPan('${t.id}',this.value)" aria-label="Pan ${esc(t.name)}">
      <span id="pan-label-${t.id}" class="pan-label">${panLabel(pan)}</span>
    </div>
    <div class="channel-buttons"><button data-mute-track="${t.id}" class="${t.mute?'on':''}" onclick="toggleBool(this,'${t.id}','mute')">M</button><button data-solo-track="${t.id}" class="${t.solo?'on':''}" onclick="toggleBool(this,'${t.id}','solo')">S</button><button class="channel-fx ${t.inserts?.length?'active':''}" onclick="openMixerInsertManager('${t.id}')" title="Gestisci insert">FX${t.inserts?.length?` ${t.inserts.length}`:''}</button></div>
    <div class="channel-mode">${outChannels===1?'MONO':(stereoByFx?'STEREO · FX':'STEREO')}</div>
    <div class="channel-fader-area"><input class="v-fader track-volume-range" data-volume-track="${t.id}" type="range" min="-60" max="12" step="0.5" value="${t.volume_db}" oninput="setTrackVolume('${t.id}',this.value)">
      <div class="meter-pair"><div class="meter meter-static" title="Volume impostato"><span style="height:${staticLevel}%"></span></div>${outChannels===1?`<div class="meter meter-realtime ${current.realtime_meter_enabled?'':'hidden'}" title="VU mono"><span id="vu-${t.id}-M" style="height:0%"></span><em>M</em></div>`:`<div class="meter meter-realtime ${current.realtime_meter_enabled?'':'hidden'}" title="VU Left"><span id="vu-${t.id}-L" style="height:0%"></span><em>L</em></div><div class="meter meter-realtime ${current.realtime_meter_enabled?'':'hidden'}" title="VU Right"><span id="vu-${t.id}-R" style="height:0%"></span><em>R</em></div>`}</div>
    </div>
    <input class="channel-value volume-number" id="mix-db-${t.id}" data-volume-number="${t.id}" type="number" min="-60" max="12" step="0.1" value="${Number(t.volume_db).toFixed(1)}" oninput="setTrackVolume('${t.id}',this.value)" aria-label="Volume ${esc(t.name)} in dB" title="Volume in dB">
  </div>`;
}
function masterChannelHtml(){
  const v=current.master_volume_db||0,fx=current.master_inserts||[];
  return `<div class="channel master" style="--track-color:#644ce5"><div class="channel-name">MASTER</div><div class="pan-knob"></div><div class="channel-buttons"><button class="channel-fx master-fx ${fx.length?'active':''}" onclick="openMixerInsertManager('master')" title="Gestisci insert Master">FX${fx.length?` ${fx.length}`:''}</button></div><div class="channel-fader-area"><input id="master-volume-range" class="v-fader" type="range" min="-60" max="12" step="0.5" value="${v}" oninput="setMasterVolume(this.value)"><div class="meter-pair master-meter-pair"><div class="meter meter-static" title="Volume master impostato"><span style="height:${Math.max(4,Math.min(100,(Number(v)+60)/72*100))}%"></span></div><div class="meter meter-realtime ${current.realtime_meter_enabled?'':'hidden'}" title="Master Left"><span id="vu-master-L" style="height:0%"></span><em>L</em></div><div class="meter meter-realtime ${current.realtime_meter_enabled?'':'hidden'}" title="Master Right"><span id="vu-master-R" style="height:0%"></span><em>R</em></div></div></div><input class="channel-value volume-number" id="master-db" type="number" min="-60" max="12" step="0.1" value="${Number(v).toFixed(1)}" oninput="setMasterVolume(this.value)" aria-label="Master volume in dB" title="Master volume in dB"></div>`;
}
async function setAutoMix(enabled){if(!current)return;try{collect();await api('/api/projects/'+current.id,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(current)});const style=$('#autoMixStyle')?.value||current.auto_mix_style||'balanced';current=await api(`/api/projects/${current.id}/auto-mix`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({enabled,style})});render();toast(enabled?'Auto Mix applied. Toggle off to restore your previous mix.':'Auto Mix removed; previous mix restored.')}catch(e){toast(e.message);render()}}
async function changeAutoMixStyle(style){current.auto_mix_style=style;if(current.auto_mix_enabled)await setAutoMix(true)}
function showAutoMixInfo(){alert('Auto Mix is reversible. It snapshots the current mix, applies conservative type-based headroom, panning, EQ/dynamics/space rules and a master preparation chain. Turning it off restores the snapshot. Always audition the result before export.')}

function bindModelInputs(){$$('.model-input').forEach(el=>el.addEventListener('change',()=>{const t=current.tracks[+el.dataset.i];if(t){t[el.dataset.k]=el.value;markDirty()}}));refreshPresetSelect(false);refreshPresetSelect(true)}
function collect(){if(!current)return;$$('.model-input').forEach(el=>{const t=current.tracks[+el.dataset.i];if(t)t[el.dataset.k]=el.value});if($('#lyrics'))current.lyrics=textToLines($('#lyrics').value,'text');if($('#chords'))current.chords=textToLines($('#chords').value,'chord');if($('#markers'))current.markers=textToLines($('#markers').value,'label')}
function projectSnapshot(){return current?JSON.parse(JSON.stringify(current)):null}
function resetSessionHistory(){undoStack=[];redoStack=[];historyProjectId=current?.id||null;lastHistoryState=projectSnapshot();timelineClipboard=null;updateEditActionState()}
function ensureSessionHistory(){if((current?.id||null)!==historyProjectId)resetSessionHistory();else if(!lastHistoryState&&current)lastHistoryState=projectSnapshot()}
function checkpointHistory(){if(!current)return;ensureSessionHistory();if(JSON.stringify(current)!==JSON.stringify(lastHistoryState)){undoStack.push(lastHistoryState);if(undoStack.length>100)undoStack.shift();redoStack=[];lastHistoryState=projectSnapshot();updateEditActionState()}}
async function persistCurrentProject(showToast=false){if(!current)return;collect();const saved=await api('/api/projects/'+current.id,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(current)});if(current&&current.id===saved.id)current=saved;projectDirty=false;lastHistoryState=projectSnapshot();$('#headerProjectName').textContent=current?.title||'—';await syncNativeProjectFile(saved.id);if(showToast)toast('Progetto salvato')}
async function restoreHistorySnapshot(snapshot,label){if(!snapshot||!current)return;current=JSON.parse(JSON.stringify(snapshot));selectedTrackId=current.tracks.some(t=>t.id===selectedTrackId)?selectedTrackId:(current.tracks[0]?.id||null);projectDirty=true;render();await persistCurrentProject(false);lastHistoryState=projectSnapshot();updateEditActionState();toast(label)}
async function undoEdit(){ensureSessionHistory();checkpointHistory();if(!undoStack.length)return toast('Nessuna operazione da annullare');const target=undoStack.pop();redoStack.push(projectSnapshot());await restoreHistorySnapshot(target,'Undo')}
async function redoEdit(){ensureSessionHistory();if(!redoStack.length)return toast('Nessuna operazione da ripristinare');undoStack.push(projectSnapshot());const target=redoStack.pop();await restoreHistorySnapshot(target,'Redo')}
function editTrackIds(){let ids=selectedTrackIds();if(!ids.length&&selectedTrackId)ids=[selectedTrackId];return ids}
function selectionBounds(){return[Math.round(Math.min(sel.a,sel.b)),Math.round(Math.max(sel.a,sel.b))]}
function clipId(){return'clip_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,9)}
function selectedClipFragments(){if(!current)return[];const[a,b]=selectionBounds();if(b-a<2)return[];const ids=new Set(editTrackIds()),out=[];for(const t of current.tracks){if(!ids.has(t.id))continue;for(const c of t.clips||[]){const cs=c.timeline_start_ms,ce=cs+(c.source_end_ms-c.source_start_ms),is=Math.max(a,cs),ie=Math.min(b,ce);if(ie>is)out.push({track_id:t.id,offset_ms:is-a,source_start_ms:c.source_start_ms+(is-cs),source_end_ms:c.source_start_ms+(ie-cs)})}}return out}
function removeRangeFromTracks(a,b,trackIds){const ids=new Set(trackIds);for(const t of current.tracks){if(!ids.has(t.id))continue;const next=[];for(const c of t.clips||[]){const cs=c.timeline_start_ms,ce=cs+(c.source_end_ms-c.source_start_ms);if(ce<=a||cs>=b){next.push(c);continue}if(cs<a)next.push({...c,id:clipId(),source_end_ms:c.source_start_ms+(a-cs)});if(ce>b)next.push({...c,id:clipId(),source_start_ms:c.source_start_ms+(b-cs),timeline_start_ms:b})}t.clips=next}}
function copyTimelineSelection(){const[a,b]=selectionBounds(),parts=selectedClipFragments();if(b-a<2)return toast('Seleziona prima un intervallo nella timeline');if(!parts.length)return toast('La selezione non contiene audio nelle tracce selezionate');timelineClipboard={duration_ms:b-a,parts};updateEditActionState();toast('Selezione copiata')}
function cutTimelineSelection(){const[a,b]=selectionBounds(),ids=editTrackIds(),parts=selectedClipFragments();if(b-a<2)return toast('Seleziona prima un intervallo nella timeline');if(!ids.length||!parts.length)return toast('La selezione non contiene audio nelle tracce selezionate');checkpointHistory();timelineClipboard={duration_ms:b-a,parts};removeRangeFromTracks(a,b,ids);projectDirty=true;render();markDirty();updateEditActionState();toast('Selezione tagliata')}
function pasteTimelineSelection(){if(!current||!timelineClipboard?.parts?.length)return toast('Clipboard timeline vuota');checkpointHistory();const dest=Math.max(0,Math.round(playCursorMs||Math.min(sel.a,sel.b)||0));for(const x of timelineClipboard.parts){const t=trackById(x.track_id);if(!t)continue;t.clips=t.clips||[];t.clips.push({id:clipId(),source_start_ms:x.source_start_ms,source_end_ms:x.source_end_ms,timeline_start_ms:dest+x.offset_ms});t.clips.sort((a,b)=>a.timeline_start_ms-b.timeline_start_ms)}projectDirty=true;render();markDirty();toast('Selezione incollata')}
function removeTimelineSelection(){if(!current)return;const[a,b]=selectionBounds(),ids=editTrackIds();if(b-a<2)return toast('Seleziona prima un intervallo nella timeline');if(!ids.length)return toast('Seleziona almeno una traccia');checkpointHistory();removeRangeFromTracks(a,b,ids);projectDirty=true;render();markDirty();toast('Parte di traccia rimossa')}
function updateEditActionState(){const set=(id,v)=>{const e=$(id);if(e)e.disabled=!!v};set('#undoBtn',!undoStack.length);set('#redoBtn',!redoStack.length);set('#pasteBtn',!timelineClipboard?.parts?.length)}
function markDirty(delay=650){
  if(!current)return;ensureSessionHistory();checkpointHistory();projectDirty=true;clearTimeout(autosaveTimer);if(!autosaveEnabled){updateEditActionState();return}autosaveTimer=setTimeout(()=>flushAutosave(false),delay);
}
async function syncNativeProjectFile(projectId){
  if(!projectId||!currentUser?.native_single_user||!window.pywebview?.api?.sync_project)return;
  try{await window.pywebview.api.sync_project(projectId)}catch(e){console.warn('Native project sync failed',e)}
}
async function flushAutosave(showToast=false){
  clearTimeout(autosaveTimer);autosaveTimer=null;
  if(!current)return;
  if(autosaveBusy){autosaveQueued=true;return}
  autosaveBusy=true;
  try{
    await persistCurrentProject(showToast);
  }catch(e){if(showToast)toast(e.message);else toast('Autosave fallito: '+e.message)}
  finally{
    autosaveBusy=false;
    if(autosaveQueued){autosaveQueued=false;markDirty(50)}
  }
}
async function save(){
  if(!current)return toast('Nessun progetto aperto');
  clearTimeout(autosaveTimer);autosaveTimer=null;
  while(autosaveBusy)await new Promise(r=>setTimeout(r,25));
  collect();
  autosaveBusy=true;
  try{
    await persistCurrentProject(false);
    await syncNativeProjectFile(current.id);
    await refresh();
    toast('Progetto salvato manualmente');
  }catch(e){toast('Salvataggio fallito: '+e.message);throw e}
  finally{autosaveBusy=false}
}
function selectTrack(id){captureUiState();selectedTrackId=id;render()}
function toggleBool(btn,id,k){const t=trackById(id);if(!t)return;t[k]=!t[k];updateMuteSoloVisuals();markDirty();toast(k==='mute'?(t[k]?'Mute attivato':'Mute disattivato'):(t[k]?'Solo attivato':'Solo disattivato'))}
function toggleMuteAll(){
  if(!current?.tracks?.length)return;
  const next=!current.tracks.every(t=>t.mute);
  current.tracks.forEach(t=>{t.mute=next});updateMuteSoloVisuals();markDirty();render();toast(next?'Mute attivato su tutte le tracce':'Mute rimosso da tutte le tracce');
}
function toggleSoloAll(){
  if(!current?.tracks?.length)return;
  const next=!current.tracks.every(t=>t.solo);
  current.tracks.forEach(t=>{t.solo=next});updateMuteSoloVisuals();markDirty();render();toast(next?'Solo attivato su tutte le tracce':'Solo rimosso da tutte le tracce');
}
function toggleAllPlugins(){
  if(!current)return;
  const plugins=[...(current.master_inserts||[]),...current.tracks.flatMap(t=>t.inserts||[])];
  if(!plugins.length)return toast('Nessun plugin configurato');
  const enable=!plugins.some(x=>x.enabled);
  plugins.forEach(x=>{x.enabled=enable});
  for(const t of current.tracks){if(t.inserts?.length)queueInsertWaveformRefresh(t.id)}
  markDirty(100);render();toast(enable?'Tutti i plugin abilitati':'Bypass di tutti i plugin attivato');
}
function updateMuteSoloVisuals(){
  if(!current)return;const anySolo=current.tracks.some(t=>t.solo);
  for(const t of current.tracks){
    const inaudible=t.mute||(anySolo&&!t.solo);
    $(`#head-${t.id}`)?.classList.toggle('audibly-muted',inaudible);
    $(`#lane-${t.id}`)?.classList.toggle('audibly-muted',inaudible);
    const ch=$(`[data-channel-track="${t.id}"]`);ch?.classList.toggle('audibly-muted',inaudible);
    $$(`[data-mute-track="${t.id}"]`).forEach(b=>b.classList.toggle('on',!!t.mute));
    $$(`[data-solo-track="${t.id}"]`).forEach(b=>b.classList.toggle('on',!!t.solo));
  }
}
function normalizeVolume(v){const n=Number(v);if(!Number.isFinite(n))return null;return Math.max(-60,Math.min(12,n))}
function setTrackVolume(id,v){
  const t=trackById(id),n=normalizeVolume(v);if(!t||n===null)return;
  t.volume_db=n;
  const item=trackPlaybacks.find(x=>x.trackId===id);
  if(item?.gainNode)item.gainNode.gain.setValueAtTime(dbToGain(n+Number(current?.master_volume_db||0)),audioCtx?.currentTime||0);
  $$(`[data-volume-track="${id}"]`).forEach(el=>{if(Number(el.value)!==n)el.value=n});
  $$(`[data-volume-number="${id}"]`).forEach(el=>{if(document.activeElement!==el||String(el.value)!==String(v))el.value=n.toFixed(1)});
  markDirty();
}
function dbToGain(db){return Math.pow(10,Number(db||0)/20)}
function updatePlaybackGains(){
  for(const item of trackPlaybacks){
    const track=trackById(item.trackId);if(!track||!item.gainNode)continue;
    const totalDb=Number(track.volume_db||0)+Number(current?.master_volume_db||0);
    item.gainNode.gain.setValueAtTime(dbToGain(totalDb),audioCtx?.currentTime||0);
  }
}
function setMasterVolume(v){
  const n=normalizeVolume(v);if(!current||n===null)return;
  current.master_volume_db=n;
  if($('#master-volume-range')&&Number($('#master-volume-range').value)!==n)$('#master-volume-range').value=n;
  if($('#master-db')&&document.activeElement!==$('#master-db'))$('#master-db').value=n.toFixed(1);
  updatePlaybackGains();
  if(masterPlaybackGainNode)masterPlaybackGainNode.gain.setValueAtTime(dbToGain(n),audioCtx?.currentTime||0);
  markDirty();
}
function setTrackPan(id,v){
  const t=trackById(id);if(!t)return;
  const n=clampPan(v);t.pan=n;updatePanUi(id,n);
  const item=trackPlaybacks.find(x=>x.trackId===id);
  if(item?.panner)item.panner.pan.setValueAtTime(n,audioCtx?.currentTime||0);
  markDirty(120);
}


function bindTrackTimelineScroll(){
  const tracks=$('#trackColumn'),timeline=$('#timelinePane');if(!tracks||!timeline)return;
  let syncing=false;
  tracks.onscroll=()=>{if(syncing)return;syncing=true;timeline.scrollTop=tracks.scrollTop;uiState.trackTop=uiState.timelineTop=tracks.scrollTop;requestAnimationFrame(()=>syncing=false)};
  timeline.onscroll=()=>{uiState.timelineLeft=timeline.scrollLeft;if(syncing)return;syncing=true;tracks.scrollTop=timeline.scrollTop;uiState.trackTop=uiState.timelineTop=timeline.scrollTop;requestAnimationFrame(()=>syncing=false)};
}
function bindTrackResizer(){
  const handle=$('#trackResizer'),grid=$('#editorGrid');if(!handle||!grid)return;
  handle.onmousedown=e=>{
    e.preventDefault();const startX=e.clientX,startWidth=Number(current.track_panel_width_px)||225;
    document.body.classList.add('resizing-tracks');
    const move=ev=>{const width=Math.max(160,Math.min(520,startWidth+ev.clientX-startX));current.track_panel_width_px=Math.round(width);grid.style.setProperty('--track-column-width',`${width}px`)};
    const up=()=>{window.removeEventListener('mousemove',move);window.removeEventListener('mouseup',up);document.body.classList.remove('resizing-tracks');markDirty(150)};
    window.addEventListener('mousemove',move);window.addEventListener('mouseup',up);
  };
}
function drawWave(t){
  const c=$('#wave-'+t.id);if(!c)return;
  const ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);
  const peaks=t.waveform_peaks||[];if(!peaks.length)return;
  const color=t.color||'#2f81f7';ctx.strokeStyle=color;ctx.globalAlpha=.9;ctx.lineWidth=1;
  const sourceDuration=Math.max(1,t.duration_ms||1);
  for(const clip of t.clips||[]){
    const tl=clip.timeline_start_ms/1000*pxPerSec,tw=(clip.source_end_ms-clip.source_start_ms)/1000*pxPerSec;
    const x0=Math.max(0,Math.floor(tl)),x1=Math.min(c.width,Math.ceil(tl+tw));
    ctx.beginPath();
    for(let x=x0;x<x1;x++){
      const frac=(x-tl)/Math.max(1,tw);
      const srcMs=clip.source_start_ms+frac*(clip.source_end_ms-clip.source_start_ms);
      const idx=Math.max(0,Math.min(peaks.length-1,Math.floor(srcMs/sourceDuration*peaks.length)));
      const amp=Number(peaks[idx]||0);
      ctx.moveTo(x+.5,39-amp*29);ctx.lineTo(x+.5,39+amp*29);
    }
    ctx.stroke();
  }
}
function updateWaveProgress(trackId,pct,message){
  const box=$(`#wave-progress-${trackId}`),bar=$(`#wave-progress-bar-${trackId}`),label=$(`#wave-progress-label-${trackId}`);
  if(!box)return;box.classList.remove('hidden');if(bar)bar.style.width=`${Math.max(2,Math.min(100,Number(pct)||0))}%`;if(label)label.textContent=message||'Waveform…';
}
async function ensureWaveforms(){
  // Persisted peaks are drawn immediately, then the server validates their revision.
  // This keeps project opening fast while guaranteeing stale/missing waveforms are regenerated and saved.
  for(const t of current?.tracks||[]){
    if(t.waveform_peaks?.length)drawWave(t);
    if(waveformJobs[t.id])continue;
    try{
      const job=await api(`/api/projects/${current.id}/tracks/${t.id}/waveform-jobs`,{method:'POST'});
      if(job.status==='completed'&&job.result){t.waveform_peaks=job.result.peaks||[];t.waveform_revision=job.result.revision||'';drawWave(t);$(`#wave-progress-${t.id}`)?.classList.add('hidden');continue}
      waveformJobs[t.id]=job.id;pollWaveformJob(t.id,job.id);
    }catch(e){if(!t.waveform_peaks?.length)updateWaveProgress(t.id,0,'Waveform non disponibile')}
  }
}
async function pollWaveformJob(trackId,jobId){
  try{
    const job=await api(`/api/media-jobs/${jobId}`);updateWaveProgress(trackId,job.progress,job.message);
    if(job.status==='completed'){
      const t=trackById(trackId);if(t&&job.result){t.waveform_peaks=job.result.peaks||[];t.waveform_revision=job.result.revision||'';drawWave(t)}
      delete waveformJobs[trackId];$(`#wave-progress-${trackId}`)?.classList.add('hidden');return;
    }
    if(job.status==='failed'){delete waveformJobs[trackId];updateWaveProgress(trackId,0,'Waveform fallita');return}
    setTimeout(()=>pollWaveformJob(trackId,jobId),450);
  }catch(e){setTimeout(()=>pollWaveformJob(trackId,jobId),1000)}
}

function drawRuler(){const c=$('#ruler');if(!c)return;const x=c.getContext('2d');x.clearRect(0,0,c.width,c.height);x.fillStyle='#0b141e';x.fillRect(0,0,c.width,c.height);x.strokeStyle='#334b5e';x.fillStyle='#8298aa';x.font='9px sans-serif';const end=c.width/pxPerSec,step=end>300?30:end>120?10:end>60?5:1;for(let s=0;s<=end;s+=step){const p=s*pxPerSec;x.beginPath();x.moveTo(p,18);x.lineTo(p,30);x.stroke();x.fillText(fmtTime(s),p+3,12)}}
function setPlayCursor(ms){
  playCursorMs=Math.max(0,Math.round(ms));
  const playheadX=playCursorMs/1000*pxPerSec;
  if($('#playhead'))$('#playhead').style.left=playheadX+'px';
  followPlayhead(playheadX);
  if($('#transportTime'))$('#transportTime').textContent=fmtTime(playCursorMs/1000,true);
}
function bindTimeline(){
  const el=$('#lanes'),pane=$('#timelinePane'),ruler=$('#ruler');
  if(!el||!pane)return;
  let downX=0,downMs=0,moved=false;
  el.onmousedown=e=>{
    if(e.button!==0)return;
    const r=pane.getBoundingClientRect();
    downX=e.clientX; moved=false;
    downMs=Math.max(0,(e.clientX-r.left+pane.scrollLeft)/pxPerSec*1000);
    dragging=true;sel.a=sel.b=downMs;updateSel();
  };
  window.onmousemove=e=>{
    if(!dragging||!$('#lanes'))return;
    const r=pane.getBoundingClientRect();
    if(Math.abs(e.clientX-downX)>3)moved=true;
    sel.b=Math.max(0,(e.clientX-r.left+pane.scrollLeft)/pxPerSec*1000);updateSel();
  };
  window.onmouseup=e=>{
    if(!dragging)return;
    dragging=false;
    if(!moved){sel={a:0,b:0};updateSel();setPlayCursor(downMs)}
  };
  if(ruler)ruler.onclick=e=>{
    const r=pane.getBoundingClientRect();
    setPlayCursor(Math.max(0,(e.clientX-r.left+pane.scrollLeft)/pxPerSec*1000));
  };
}
function updateSel(){const a=Math.min(sel.a,sel.b),b=Math.max(sel.a,sel.b),s=$('#selection');if(s){s.style.display=Math.abs(b-a)>2?'block':'none';s.style.left=`${a/1000*pxPerSec}px`;s.style.width=`${Math.max(1,(b-a)/1000*pxPerSec)}px`}if($('#selectionInfo'))$('#selectionInfo').textContent=`${(a/1000).toFixed(3)} → ${(b/1000).toFixed(3)} s`}

async function deleteTracksByIds(ids){
  if(!current||!ids?.length)return;
  const names=ids.map(id=>trackById(id)?.name).filter(Boolean);
  if(!confirm(`Eliminare ${ids.length===1?'la traccia':'le tracce'} ${names.join(', ')} dal progetto?`))return;
  await save();
  current=await api(`/api/projects/${current.id}/delete-tracks`,{
    method:'POST',
    headers:{'content-type':'application/json'},
    body:JSON.stringify(ids)
  });
  if(selectedTrackId&&!current.tracks.some(t=>t.id===selectedTrackId))selectedTrackId=current.tracks[0]?.id||null;
  render();await refresh();toast(ids.length===1?'Traccia eliminata':'Tracce eliminate');
}

async function deleteSelection(wholeSong){
  if(!current)return;
  if(!wholeSong){
    let ids=selectedTrackIds();
    if(!ids.length&&selectedTrackId)ids=[selectedTrackId];
    if(!ids.length)return toast('Seleziona almeno una traccia');
    await deleteTracksByIds(ids);
    return;
  }
  const a=Math.round(Math.min(sel.a,sel.b)),b=Math.round(Math.max(sel.a,sel.b));
  if(b-a<2)return toast('Seleziona prima un intervallo nella timeline');
  await save();
  current=await api(`/api/projects/${current.id}/delete-range`,{
    method:'POST',
    headers:{'content-type':'application/json'},
    body:JSON.stringify({start_ms:a,end_ms:b,track_ids:null,ripple:true})
  });
  sel={a:0,b:0};render();toast('Segmento del brano eliminato con ripple globale');
}

function showMediaProgress(title,pct,message,detail=''){
  const p=Math.max(0,Math.min(100,Number(pct)||0));
  setMobileBusy(p<100);
  showUtilityModal(title,`<div class="stem-progress-card"><div class="stem-progress-head"><b>${esc(title)}</b><span>${p}%</span></div><div class="stem-progress"><div class="stem-progress-fill" style="width:${p}%"></div></div><div class="stem-progress-message">${esc(message||'')}</div>${detail?`<div class="workflow-note">${esc(detail)}</div>`:''}</div>`);
}
function uploadWithProgress(url,formData,title){
  return new Promise((resolve,reject)=>{
    const xhr=new XMLHttpRequest();
    xhr.open('POST',url);
    xhr.setRequestHeader('X-MTA-Request','1');
    xhr.upload.onprogress=e=>{if(e.lengthComputable)showMediaProgress(title,Math.min(54,Math.round(e.loaded/e.total*54)),title==='Import MTA'?'Upload MTA':'Upload della traccia')};
    xhr.onload=()=>{if(xhr.status>=200&&xhr.status<300){try{resolve(JSON.parse(xhr.responseText))}catch(e){reject(e)}}else reject(new Error(xhr.responseText||`HTTP ${xhr.status}`))};
    xhr.onerror=()=>reject(new Error('Errore di rete durante upload'));
    xhr.send(formData);
  });
}
async function pollMediaJob(jobId,title,onDone){
  clearTimeout(mediaProgressTimer);
  try{
    const job=await api(`/api/media-jobs/${jobId}`);
    showMediaProgress(title,job.progress,job.message,job.error||'');
    if(job.status==='completed'){setMobileBusy(false);await onDone(job);return}
    if(job.status==='failed'){setMobileBusy(false);toast(job.error||'Operazione fallita');return}
    mediaProgressTimer=setTimeout(()=>pollMediaJob(jobId,title,onDone),500);
  }catch(e){setMobileBusy(false);toast(e.message)}
}
async function downloadWithProgress(url,filename,title,share=false,mime='application/octet-stream'){
  showMediaProgress(title,2,'Preparazione download');
  if(isMobileClient()&&mobileSaveRemoteFile(url,filename,mime,share)){
    setMobileBusy(false);$('#utilityBackdrop')?.classList.add('hidden');return;
  }
  const r=await fetch(url);
  if(!r.ok)throw new Error(await r.text());
  const total=Number(r.headers.get('content-length')||0),reader=r.body?.getReader(),chunks=[];let loaded=0;
  if(reader){
    while(true){const {done,value}=await reader.read();if(done)break;chunks.push(value);loaded+=value.length;if(total)showMediaProgress(title,90+Math.round(loaded/total*10),'Download del file')}
    const blob=new Blob(chunks);
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1200);
  }else{const blob=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=filename;a.click()}
  $('#utilityBackdrop').classList.add('hidden');
}
async function addTrack(){
  const f=$('#newTrackFile')?.files?.[0];if(!f)return toast('Choose an MP3/WAV/audio file');lastSelectedAudioFile=f;
  await save();
  const fd=new FormData();fd.append('file',f);
  const mode=$('#newSync').value,off=parseInt($('#newOffset').value)||0,ref=$('#newRef').value;
  const q=`name=${encodeURIComponent(f.name.replace(/\.[^.]+$/,''))}&sync_mode=${mode}&offset_ms=${off}&reference_track_id=${encodeURIComponent(ref)}`;
  try{
    const job=await uploadWithProgress(`/api/projects/${current.id}/track-import-jobs?${q}`,fd,'Import traccia');
    showMediaProgress('Import traccia',job.progress,job.message,current.tracks.length===0?'Prima traccia: stima automatica BPM in corso.':'');
    pollMediaJob(job.id,'Import traccia',async completed=>{
      current=await api(`/api/projects/${current.id}`);
      selectedTrackId=current.tracks.at(-1)?.id;render();await refresh();
      $('#utilityBackdrop').classList.add('hidden');
      if($('#newTrackFile'))$('#newTrackFile').value='';
      toast(`Traccia importata${current.tracks.length===1?` · BPM ${current.bpm}`:''}`);
    });
  }catch(e){if($('#newTrackFile'))$('#newTrackFile').value='';toast(e.message)}
}
async function replaceTrack(id,input){
  const f=input.files[0];if(!f)return;
  const mode=prompt('Synchronization: keep, manual or auto','keep')||'keep';
  let off=0;if(mode==='manual')off=parseInt(prompt('Offset in milliseconds (+ later, - earlier)','0'))||0;
  const ref=current.tracks.find(t=>t.id!==id)?.id||'';
  const fd=new FormData();fd.append('file',f);
  try{
    showMediaProgress('Sostituzione traccia',1,'Preparazione upload');
    const url=`/api/projects/${current.id}/tracks/${id}/replace?sync_mode=${encodeURIComponent(mode)}&offset_ms=${off}&reference_track_id=${encodeURIComponent(ref)}`;
    current=await uploadWithProgress(url,fd,'Sostituzione traccia');
    showMediaProgress('Sostituzione traccia',100,'Traccia sostituita');
    render();await refresh();setTimeout(()=>$('#utilityBackdrop').classList.add('hidden'),350);
    toast('Track replaced');
  }catch(e){toast(e.message)}
}
function openStemWorkflow(){
  const stem=pluginInfo.stem_splitter||{};
  const defaultName=current?.title||'Nuovo progetto da MP3';
  const models=(stem.models||['htdemucs_6s']).map(x=>`<option value="${esc(x)}" ${x===stem.recommended_model?'selected':''}>${esc(x)}</option>`).join('');
  const rememberedFile=lastSelectedAudioFile&&/\.mp3$/i.test(lastSelectedAudioFile.name)?lastSelectedAudioFile:null;
  const remembered=rememberedFile?.name?`<div class="workflow-note">File MP3 già selezionato: <b>${esc(rememberedFile.name)}</b>. Verrà usato se non ne scegli un altro.</div>`:'';
  showUtilityModal('Importa brano e separa strumenti',`
    <div class="stem-workflow">
      <p class="hint"><span class="status-dot ${stem.available?'ok':'bad'}"></span>${stem.available?'Demucs disponibile. Il brano viene salvato subito nel progetto; la separazione continua in background.':'Demucs non è disponibile nel runtime corrente.'}</p>
      <label class="workflow-field"><span>Destinazione</span><select id="stemProjectMode" onchange="updateStemWorkflowMode()"><option value="existing" ${current?'selected':''}>Progetto corrente${current?`: ${esc(current.title)}`:''}</option><option value="new" ${current?'':'selected'}>Nuovo progetto persistente</option></select></label>
      <label class="workflow-field" id="stemProjectNameRow"><span>Nome nuovo progetto</span><input id="stemProjectTitle" maxlength="200" value="${esc(defaultName)}"></label>
      <div class="workflow-grid">
        <label class="workflow-field"><span>Tipo progetto</span><select id="stemProjectTarget"><option value="MTA8">MTA8</option><option value="MTA16">MTA16</option></select></label>
        <label class="workflow-field"><span>Modello AI</span><select id="stemWorkflowModel">${models}</select></label>
      </div>
      <label class="workflow-field"><span>Brano completo MP3</span><input id="stemWorkflowFile" type="file" accept=".mp3,audio/mpeg"></label>
      ${remembered}
      <label class="workflow-check"><input id="stemKeepOriginal" type="checkbox" checked> Mantieni anche la traccia “Original Mix” nel progetto</label>
      <div class="workflow-note">Il file originale viene sempre conservato in <b>Originals</b>. Il progetto viene salvato dopo l’import e dopo ogni stem aggiunto.</div>
      <div class="utility-actions">
        <button class="utility-btn primary" type="button" onclick="startStemWorkflow()" ${stem.available?'':'disabled'}><span>Importa e separa</span></button>
        <button class="utility-btn secondary" type="button" onclick="closeUtilityModal()"><span>Annulla</span></button>
      </div>
    </div>`);
  updateStemWorkflowMode();
}
function updateStemWorkflowMode(){
  const mode=$('#stemProjectMode')?.value;
  const row=$('#stemProjectNameRow'),target=$('#stemProjectTarget');
  if(row)row.style.display=mode==='new'?'grid':'none';
  if(target)target.disabled=mode!=='new';
}
async function startStemWorkflow(){
  const f=$('#stemWorkflowFile')?.files?.[0]||(lastSelectedAudioFile&&/\.mp3$/i.test(lastSelectedAudioFile.name)?lastSelectedAudioFile:null);
  if(!f)return toast('Seleziona un file MP3');
  const mode=$('#stemProjectMode').value;
  const title=$('#stemProjectTitle')?.value?.trim()||'';
  if(mode==='new'&&!title)return toast('Inserisci il nome del nuovo progetto');
  await flushAutosave();
  const fd=new FormData();fd.append('file',f);
  const projectId=mode==='existing'&&current?current.id:'';
  const target=mode==='existing'?(current?.target||'MTA8'):$('#stemProjectTarget').value;
  const model=$('#stemWorkflowModel').value;
  const keep=$('#stemKeepOriginal').checked;
  let nativeProjectPath=null;
  if(mode==='new'&&currentUser?.native_single_user){
    const apiBridge=await waitForNativeApi();
    if(!apiBridge?.choose_project_save_path)return toast('Bridge nativo non disponibile: impossibile scegliere dove salvare il nuovo progetto.');
    try{
      const chosen=await apiBridge.choose_project_save_path(title||'Nuovo progetto');
      if(!chosen?.ok)return;
      nativeProjectPath=chosen.path;
    }catch(e){return toast('Scelta destinazione progetto fallita: '+e.message)}
  }
  try{
    const r=await api(`/api/stems/jobs?project_id=${encodeURIComponent(projectId)}&project_title=${encodeURIComponent(title)}&target=${encodeURIComponent(target)}&model=${encodeURIComponent(model)}&keep_original_track=${keep}`,{method:'POST',body:fd});
    if(nativeProjectPath&&window.pywebview?.api?.bind_project_path){
      await window.pywebview.api.bind_project_path(r.project.id,nativeProjectPath);
    }
    activeStemJob=r.job.id;setMobileBusy(true);
    activeStemProjectId=r.job.project_id;
    current=r.project;
    selectedTrackId=current.tracks.at(-1)?.id||null;
    render();await refresh();
    showStemProgress(r.job);pollStemJob(r.job.id);
  }catch(e){toast(e.message)}
}
function showStemProgress(job){
  const done=['completed','failed','cancelled'].includes(job.status);
  const pct=Math.max(0,Math.min(100,Number(job.progress)||0));
  showUtilityModal('Separazione strumenti',`
    <div class="stem-progress-card">
      <div class="stem-progress-head"><b>${esc(job.filename)}</b><span>${pct}%</span></div>
      <div class="stem-progress"><div class="stem-progress-fill" style="width:${pct}%"></div></div>
      <div class="stem-progress-message">${esc(job.message||job.status)}</div>
      ${job.error?`<pre class="stem-error">${esc(job.error)}</pre>`:''}
      <div class="utility-actions">
        ${!done?`<button class="danger-action" onclick="cancelStemJob('${job.id}')">Annulla separazione</button>`:''}
        ${done?`<button onclick="closeUtilityModal()">Chiudi</button>`:''}
      </div>
    </div>`,true);
}
async function pollStemJob(jobId){
  clearTimeout(stemPollTimer);
  try{
    const job=await api(`/api/stems/jobs/${jobId}`);
    if(!current||current.id!==job.project_id){
      current=await api(`/api/projects/${job.project_id}`);
      selectedTrackId=job.source_track_id&&current.tracks.some(t=>t.id===job.source_track_id)?job.source_track_id:(current.tracks[0]?.id||null);
      render();await refresh();
    }
    showStemProgress(job);
    if(job.status==='completed'){
      current=await api(`/api/projects/${job.project_id}`);
      const preferred=job.source_track_id&&current.tracks.some(t=>t.id===job.source_track_id)?job.source_track_id:null;
      selectedTrackId=preferred||selectedTrackId||current.tracks[0]?.id||null;
      render();await refresh();
      await syncNativeProjectFile(job.project_id);
      showStemProgress(job);
      activeStemJob=null;
      activeStemProjectId=null;setMobileBusy(false);
      toast('Separazione completata e progetto salvato');
      return;
    }
    if(job.status==='failed'||job.status==='cancelled'){
      activeStemJob=null;activeStemProjectId=null;setMobileBusy(false);
      showStemProgress(job);
      toast(job.status==='cancelled'?'Separazione annullata':'Separazione fallita');
      return;
    }
    stemPollTimer=setTimeout(()=>pollStemJob(jobId),700);
  }catch(e){toast(e.message);stemPollTimer=setTimeout(()=>pollStemJob(jobId),1500)}
}
async function cancelStemJob(jobId){
  try{
    const job=await api(`/api/stems/jobs/${jobId}/cancel`,{method:'POST'});
    showStemProgress(job);pollStemJob(jobId);
  }catch(e){toast(e.message)}
}
function toggleStemCard(){openStemWorkflow()}

async function drawWave(t){const c=$('#wave-'+t.id);if(!c)return;const ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);try{audioCtx=audioCtx||new(window.AudioContext||window.webkitAudioContext)();const ab=await fetch(`/api/projects/${current.id}/audio/${encodeURIComponent(t.filename)}`).then(r=>r.arrayBuffer());const b=await audioCtx.decodeAudioData(ab);const d=b.getChannelData(0),color=t.color||'#2f81f7';ctx.strokeStyle=color;ctx.globalAlpha=.86;ctx.lineWidth=1;for(const clip of t.clips||[]){const tl=clip.timeline_start_ms/1000*pxPerSec,tw=(clip.source_end_ms-clip.source_start_ms)/1000*pxPerSec,x0=Math.floor(tl),x1=Math.ceil(tl+tw);ctx.beginPath();for(let x=x0;x<x1;x++){const frac=(x-tl)/Math.max(1,tw),srcMs=clip.source_start_ms+frac*(clip.source_end_ms-clip.source_start_ms),center=Math.floor(srcMs/1000*b.sampleRate),span=Math.max(1,Math.floor(b.sampleRate/pxPerSec/2));let mn=1,mx=-1;for(let j=Math.max(0,center-span);j<Math.min(d.length,center+span);j+=Math.max(1,Math.floor(span/20))){mn=Math.min(mn,d[j]);mx=Math.max(mx,d[j])}ctx.moveTo(x+.5,39-mx*28);ctx.lineTo(x+.5,39-mn*28)}ctx.stroke()}}catch(e){ctx.fillStyle='#6d8294';ctx.fillText('waveform unavailable',10,39)}}
function setZoom(v){pxPerSec=Number(v);if(current){current.timeline_zoom_px_per_sec=pxPerSec;markDirty(150)}if($('#topZoom'))$('#topZoom').value=v;render()}

function tempoRatio(){const base=Number(current?.base_bpm||current?.bpm||120);return Math.max(.25,Math.min(4,Number(current?.bpm||base)/base))}
function setProjectBpm(v){
  if(!current)return;const n=Math.max(30,Math.min(300,Number(v)||current.bpm));
  if(!current.base_bpm)current.base_bpm=current.bpm||n;
  current.bpm=n;$('#transportBpm').textContent=n.toFixed(1);if($('#transportBpmInput'))$('#transportBpmInput').value=n.toFixed(1);markDirty();stopPlayback();
}
function setProjectPitch(v){
  if(!current)return;const n=Math.max(-6,Math.min(6,Number(v)||0));current.pitch_semitones=n;if($('#transportPitchInput'))$('#transportPitchInput').value=n.toFixed(1);markDirty();stopPlayback();
}
function toggleRenderPreview(){
  if(!current)return;current.render_preview_enabled=!current.render_preview_enabled;updateTransportToggleButtons();markDirty();stopPlayback();
}

function toggleFollowPlayback(){
  if(!current)return;
  current.follow_playback_enabled=!current.follow_playback_enabled;
  updateTransportToggleButtons();
  markDirty();
  if(current.follow_playback_enabled)followPlayhead(playCursorMs/1000*pxPerSec,true);
}
function followPlayhead(x,force=false){
  if(!current?.follow_playback_enabled)return;
  const pane=$('#timelinePane');if(!pane)return;
  const left=pane.scrollLeft,right=left+pane.clientWidth;
  const margin=Math.max(60,pane.clientWidth*.18);
  if(force||x>right-margin||x<left+margin){
    pane.scrollLeft=Math.max(0,x-pane.clientWidth*.35);
    uiState.timelineLeft=pane.scrollLeft;
  }
}

function toggleRealtimeMeters(){
  if(!current)return;current.realtime_meter_enabled=!current.realtime_meter_enabled;$('#realtimeBtn')?.classList.toggle('active',current.realtime_meter_enabled);$$('.meter-realtime').forEach(x=>x.classList.toggle('hidden',!current.realtime_meter_enabled));markDirty();
  if(!current.realtime_meter_enabled)resetVuMeters();
  if(playAudio||trackPlaybacks.length){const pos=playCursorMs;stopPlayback();setPlayCursor(pos);previewMaster()}
}
function updateTransportToggleButtons(){
  $('#renderBtn')?.classList.toggle('active',!!current?.render_preview_enabled);
  $('#followBtn')?.classList.toggle('active',!!current?.follow_playback_enabled);
}
function resetVuMeters(){
  $$('[id^="vu-"]').forEach(x=>x.style.height='0%');
}
function playbackActuallyRunning(){
  const masterRunning=!!(playAudio&&!playAudio.paused&&!playAudio.ended);
  const trackRunning=trackPlaybacks.some(item=>item.audio&&!item.audio.paused&&!item.audio.ended);
  return masterRunning||trackRunning;
}
function startVuMeterLoop(){
  if(meterRaf){cancelAnimationFrame(meterRaf);meterRaf=null}
  const token=++meterRunToken;
  const tick=()=>{
    if(token!==meterRunToken)return;
    updateVuMeters(token);
  };
  meterRaf=requestAnimationFrame(tick);
}
function analyserLevel(analyser,cacheOwner,key){
  if(!analyser)return 0;
  cacheOwner.meterData=cacheOwner.meterData||{};
  const data=cacheOwner.meterData[key]||(cacheOwner.meterData[key]=new Uint8Array(analyser.fftSize));
  analyser.getByteTimeDomainData(data);
  let sum=0;
  for(const value of data){const x=(value-128)/128;sum+=x*x}
  const rms=Math.sqrt(sum/Math.max(1,data.length));
  const db=20*Math.log10(Math.max(1e-5,rms));
  return Math.max(0,Math.min(100,(db+60)/60*100));
}
function setVu(id,pct){const el=$(id);if(el)el.style.height=`${pct}%`}
function updateVuMeters(token=meterRunToken){
  if(token!==meterRunToken)return;
  if(!current?.realtime_meter_enabled||!playbackActuallyRunning()){
    resetVuMeters();
    meterRaf=null;
    return;
  }
  let masterLeftEnergy=0,masterRightEnergy=0;
  for(const item of trackPlaybacks){
    const analysers=item.analysers||[];
    if(!analysers.length)continue;
    if(item.channels===1){
      const mono=analyserLevel(analysers[0],item,'m');
      setVu(`#vu-${item.trackId}-M`,mono);
      masterLeftEnergy+=mono*mono;masterRightEnergy+=mono*mono;
    }else{
      const left=analyserLevel(analysers[0],item,'l');
      const right=analyserLevel(analysers[1],item,'r');
      setVu(`#vu-${item.trackId}-L`,left);setVu(`#vu-${item.trackId}-R`,right);
      masterLeftEnergy+=left*left;masterRightEnergy+=right*right;
    }
  }
  if(masterMeterAnalysers?.length===2){
    const holder=masterMeterAnalysers;
    holder.meterData=holder.meterData||{};
    setVu('#vu-master-L',analyserLevel(holder[0],holder,'l'));
    setVu('#vu-master-R',analyserLevel(holder[1],holder,'r'));
  }else{
    setVu('#vu-master-L',Math.min(100,Math.sqrt(masterLeftEnergy)));
    setVu('#vu-master-R',Math.min(100,Math.sqrt(masterRightEnergy)));
  }
  meterRaf=requestAnimationFrame(()=>{
    if(token===meterRunToken)updateVuMeters(token);
  });
}
async function attachPlaybackGraph(audio,track,channels=2,silent=false,masterRendered=false){
  audioCtx=audioCtx||new(window.AudioContext||window.webkitAudioContext)();
  await audioCtx.resume();
  const source=audioCtx.createMediaElementSource(audio);
  const gainNode=audioCtx.createGain();
  const panner=audioCtx.createStereoPanner();
  const db=masterRendered
    ? Number(current?.master_volume_db||0)
    : Number(track?.volume_db||0)+Number(current?.master_volume_db||0);
  gainNode.gain.value=silent?0:dbToGain(db);
  panner.pan.value=clampPan(track?.pan||0);
  source.connect(gainNode);gainNode.connect(panner);
  const zero=audioCtx.createGain();zero.gain.value=0;zero.connect(audioCtx.destination);
  if(silent)panner.connect(zero);else panner.connect(audioCtx.destination);
  const analysers=[];
  if(current.realtime_meter_enabled){
    if(channels===1){
      const analyser=audioCtx.createAnalyser();analyser.fftSize=512;
      panner.connect(analyser);analyser.connect(zero);analysers.push(analyser);
    }else{
      const splitter=audioCtx.createChannelSplitter(2),left=audioCtx.createAnalyser(),right=audioCtx.createAnalyser();
      left.fftSize=512;right.fftSize=512;
      panner.connect(splitter);splitter.connect(left,0);splitter.connect(right,1);
      left.connect(zero);right.connect(zero);analysers.push(left,right);
    }
  }
  return {analysers,gainNode,panner};
}
async function makeTrackPlayback(track,renderFilters,silent=false){
  const audio=new Audio(`/api/projects/${current.id}/preview-track/${track.id}?render=${renderFilters?'true':'false'}&t=${Date.now()}`);
  audio.preload='auto';
  const channels=renderFilters?effectiveTrackChannels(track):(Number(track.channels)===1?1:2);
  const graph=await attachPlaybackGraph(audio,track,channels,silent);
  await new Promise((resolve,reject)=>{audio.addEventListener('loadedmetadata',resolve,{once:true});audio.addEventListener('error',()=>reject(new Error(`Preview non disponibile: ${track.name}`)),{once:true});audio.load()});
  audio.currentTime=Math.min(playCursorMs/1000/tempoRatio(),Math.max(0,(audio.duration||0)-0.01));
  audio.addEventListener('ended',()=>requestAnimationFrame(()=>{
    if(!playbackActuallyRunning())resetVuMeters();
  }));
  return {trackId:track.id,audio,analysers:graph.analysers,channels,silent,meterData:{},gainNode:graph.gainNode,panner:graph.panner};
}
async function startDynamicTrackPreview(renderFilters,silentMeters=false){
  const anySolo=current.tracks.some(t=>t.solo),audible=current.tracks.filter(t=>!t.mute&&(!anySolo||t.solo));
  const items=await Promise.all(audible.map(t=>makeTrackPlayback(t,renderFilters,silentMeters)));
  trackPlaybacks.push(...items);await Promise.all(items.map(item=>item.audio.play()));
  if(current.realtime_meter_enabled&&!meterRaf)startVuMeterLoop();
  return items[0]?.audio||null;
}

function stopPlayback(){
  playbackPaused=false;
  meterRunToken++;
  if(playRaf){cancelAnimationFrame(playRaf);playRaf=null}
  if(meterRaf){cancelAnimationFrame(meterRaf);meterRaf=null}
  if(playAudio){playAudio.pause();playAudio.currentTime=0;playAudio=null}
  for(const item of trackPlaybacks){try{item.audio.pause();item.audio.currentTime=0;item.audio.src=''}catch(e){}}
  trackPlaybacks=[];masterMeterAnalysers=null;masterPlaybackGainNode=null;
  resetVuMeters();
  requestAnimationFrame(resetVuMeters);
  if($('#playMaster')){$('#playMaster').textContent='▶';$('#playMaster').title='Play / Preview'}
}
function pausePlayback(){
  if(!playAudio&&!trackPlaybacks.length)return;
  if(playAudio)playAudio.pause();
  for(const item of trackPlaybacks)try{item.audio.pause()}catch(e){}
  playbackPaused=true;
  if(playRaf){cancelAnimationFrame(playRaf);playRaf=null}
  if(meterRaf){cancelAnimationFrame(meterRaf);meterRaf=null}
  if($('#playMaster')){$('#playMaster').textContent='▶';$('#playMaster').title='Riprendi'}
}
async function resumePlayback(){
  const audios=[...new Set([playAudio,...trackPlaybacks.map(item=>item.audio)].filter(Boolean))];
  if(!audios.length)return previewMaster();
  await Promise.all(audios.map(audio=>audio.play()));
  playbackPaused=false;
  if($('#playMaster')){$('#playMaster').textContent='❚❚';$('#playMaster').title='Pausa'}
  playRaf=requestAnimationFrame(movePlayhead);
  if(current?.realtime_meter_enabled&&!meterRaf)meterRaf=requestAnimationFrame(updateVuMeters);
}
async function togglePlayback(){
  if(playbackPaused)return resumePlayback();
  if(playAudio&&!playAudio.paused)return pausePlayback();
  return previewMaster();
}
function seekTransport(deltaMs){setPlayCursor(Math.max(0,playCursorMs+deltaMs));const sec=playCursorMs/1000/tempoRatio();if(playAudio)playAudio.currentTime=sec;for(const item of trackPlaybacks)try{item.audio.currentTime=sec}catch(e){}}
async function previewTrack(id){
  const t=trackById(id);if(!t)return;stopPlayback();
  try{const item=await makeTrackPlayback(t,true,false);trackPlaybacks=[item];playAudio=item.audio;await item.audio.play();requestAnimationFrame(movePlayhead);if(current.realtime_meter_enabled)startVuMeterLoop()}catch(e){toast(e.message)}
}
async function previewMaster(){
  if(!current||!current.tracks.length)return;
  try{
    await flushAutosave(false);stopPlayback();const token=++playbackToken;
    const needsRenderedMaster=!!current.render_preview_enabled||Math.abs(Number(current.master_volume_db||0))>0.001||(current.master_inserts||[]).some(x=>x.enabled);
    if(needsRenderedMaster){
      const audio=new Audio(`/api/projects/${current.id}/preview-mix?t=${Date.now()}`);playAudio=audio;
      await new Promise((resolve,reject)=>{audio.addEventListener('loadedmetadata',resolve,{once:true});audio.addEventListener('error',()=>reject(new Error('Anteprima renderizzata non disponibile')),{once:true});audio.load()});
      if(token!==playbackToken)return;
      audio.currentTime=Math.min(playCursorMs/1000/tempoRatio(),Math.max(0,(audio.duration||0)-0.01));
      if(current.realtime_meter_enabled){
        const masterGraph=await attachPlaybackGraph(audio,{volume_db:0,pan:0},2,false,true);
        masterMeterAnalysers=masterGraph.analysers;
        masterPlaybackGainNode=masterGraph.gainNode;
        await startDynamicTrackPreview(true,true);
      }else{
        const masterGraph=await attachPlaybackGraph(audio,{volume_db:0,pan:0},2,false,true);
        masterPlaybackGainNode=masterGraph.gainNode;
      }
      await audio.play();
    }else{
      playAudio=await startDynamicTrackPreview(true,false);
    }
    if(!playAudio)return;playbackPaused=false;$('#playMaster').textContent='❚❚';$('#playMaster').title='Pausa';requestAnimationFrame(movePlayhead);toast(needsRenderedMaster?'Anteprima Master: volume e insert applicati':'Anteprima dinamica tracce');
  }catch(e){stopPlayback();toast(e.message)}
}
function movePlayhead(){
  if(!playAudio||playAudio.paused)return;
  playCursorMs=playAudio.currentTime*1000*tempoRatio();
  const playheadX=playCursorMs/1000*pxPerSec;
  if($('#playhead'))$('#playhead').style.left=playheadX+'px';
  followPlayhead(playheadX);
  if($('#transportTime'))$('#transportTime').textContent=fmtTime(playCursorMs/1000,true);
  playRaf=requestAnimationFrame(movePlayhead);
}
function selectExport(format){exportFormat=format;if(current){current.export_format=format;markDirty(150)}render()}
async function exportTrack(id,format){
  if(!current)return;
  await save();
  try{
    const job=await api(`/api/projects/${current.id}/tracks/${encodeURIComponent(id)}/track-export-jobs?format=${encodeURIComponent(format)}`,{method:'POST'});
    showMediaProgress('Export traccia',job.progress,job.message);
    pollMediaJob(job.id,'Export traccia',async completed=>{
      const result=completed.result||{};
      await downloadWithProgress(result.download_url,result.filename||`track.${format}`,'Export traccia');
      toast('Export traccia completato');
    });
  }catch(e){toast(e.message)}
}
async function doExport(format=exportFormat){
  if(!current)return;
  exportFormat=format;
  current.export_format=format;
  markDirty(100);
  const safe=(current.title||'project').replace(/[^A-Za-z0-9._ -]+/g,'_').trim()||'project';
  const targetExt=current.target==='MTA8'?'mta8':'mta16';
  const ext=format==='mta'?targetExt:format;
  const audioParams=format==='wav'
    ?`<div class="workflow-grid"><label class="workflow-field"><span>Sample rate</span><select id="exportSampleRate"><option value="44100">44.1 kHz</option><option value="48000">48 kHz</option></select></label><label class="workflow-field"><span>Bit depth</span><select id="exportWavBits"><option value="16">16 bit PCM</option><option value="24" selected>24 bit PCM</option><option value="32">32 bit float</option></select></label></div>`
    :format==='mp3'
      ?`<div class="workflow-grid"><label class="workflow-field"><span>Sample rate</span><select id="exportSampleRate"><option value="44100">44.1 kHz</option><option value="48000">48 kHz</option></select></label><label class="workflow-field"><span>Bitrate</span><select id="exportMp3Bitrate"><option value="128">128 kbps</option><option value="192">192 kbps</option><option value="256">256 kbps</option><option value="320" selected>320 kbps</option></select></label></div>`
      :format==='flac'
        ?`<div class="workflow-grid"><label class="workflow-field"><span>Sample rate</span><select id="exportSampleRate"><option value="44100">44.1 kHz</option><option value="48000">48 kHz</option></select></label><label class="workflow-field"><span>Compressione</span><select id="exportFlacCompression">${Array.from({length:13},(_,i)=>`<option value="${i}" ${i===8?'selected':''}>${i}</option>`).join('')}</select></label></div>`
        :`<div class="workflow-note">Formato progetto: <b>${esc(current.target)}</b>. L'export MTA userà l'estensione <b>.${ext}</b>.</div>`;
  showUtilityModal('Esporta progetto',`
    <div class="stem-workflow">
      <label class="workflow-field"><span>Formato</span><input value="${format==='mta'?current.target:format.toUpperCase()}" disabled></label>
      <label class="workflow-field"><span>Nome file</span><div class="export-name-row"><input id="exportFileName" maxlength="180" value="${esc(safe)}"><span>.${ext}</span></div></label>
      ${audioParams}
      <div class="workflow-note">${currentUser?.native_single_user?'Dopo Conferma verrà aperto il selettore del filesystem per scegliere la cartella di destinazione.':isMobileClient()?'L’app mobile userà il selettore file del sistema operativo. Puoi anche condividere direttamente l’output.':'Il browser chiederà dove salvare il file secondo le impostazioni di download del browser.'}</div>
      <div class="utility-actions">
        <button class="utility-btn primary" onclick="confirmConfiguredExport('${format}',false)">Conferma export</button>
        ${isMobileClient()?`<button class="utility-btn secondary" onclick="confirmConfiguredExport('${format}',true)">Condividi…</button>`:''}
        <button class="utility-btn secondary" type="button" onclick="closeUtilityModal()">Annulla</button>
      </div>
    </div>`);
}
async function confirmConfiguredExport(format,share=false){
  if(!current)return;
  const name=($('#exportFileName')?.value||'project').trim();
  if(!name)return toast('Inserisci un nome file');
  const config={
    format,
    filename:name,
    mp3_bitrate_kbps:Number($('#exportMp3Bitrate')?.value||320),
    sample_rate:Number($('#exportSampleRate')?.value||44100),
    wav_bit_depth:Number($('#exportWavBits')?.value||24),
    flac_compression:Number($('#exportFlacCompression')?.value||8),
    slots:[],
    output_path:null,
    share:!!share
  };
  pendingExportConfig=config;
  closeUtilityModal();
  if(format==='mta'){
    try{
      const plan=await api(`/api/projects/${current.id}/export-plan`);
      if(plan.requires_mapping){openExportMapping(plan,config);return}
    }catch(e){return toast(e.message)}
  }
  await executeConfiguredExport(config,[]);
}
async function executeConfiguredExport(config,slots=[]){
  if(!current)return;
  try{
    await flushAutosave();
    const ext=config.format==='mta'?(current.target==='MTA8'?'mta8':'mta16'):config.format;
    const safeName=(config.filename||'project').replace(/[^A-Za-z0-9._ -]+/g,'_').trim()||'project';
    if(currentUser?.native_single_user&&window.pywebview?.api?.choose_export_save_path){
      const chosen=await window.pywebview.api.choose_export_save_path(safeName,ext);
      if(!chosen?.ok)return;
      config.output_path=chosen.path;
    }
    if(isMobileClient()){
      const job=await api(`/api/projects/${current.id}/configured-export-jobs`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({...config,slots,output_path:null})});
      showMediaProgress('Export progetto',job.progress,job.message);
      pollMediaJob(job.id,'Export progetto',async completed=>{
        const result=completed.result||{};
        const mime=result.media_type||({wav:'audio/wav',mp3:'audio/mpeg',flac:'audio/flac'}[config.format]||'application/octet-stream');
        mobileSaveRemoteFile(result.download_url,result.filename||`${safeName}.${ext}`,mime,!!config.share);
        $('#utilityBackdrop')?.classList.add('hidden');pendingExportConfig=null;toast(config.share?'Output pronto per la condivisione':'Export pronto per il salvataggio');
      });
      return;
    }
    const response=await fetch(`/api/projects/${current.id}/configured-export`,{
      method:'POST',
      headers:{'content-type':'application/json','X-MTA-Request':'1'},
      body:JSON.stringify({...config,slots})
    });
    if(!response.ok)throw new Error(await response.text());
    if(config.output_path){
      const result=await response.json();
      toast(`Export salvato in ${result.path}`);
      pendingExportConfig=null;
      return;
    }
    const blob=await response.blob();
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url;a.download=`${safeName}.${ext}`;document.body.appendChild(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1500);
    pendingExportConfig=null;
    toast('Export completato');
  }catch(e){toast(e.message)}
}
function openExportMapping(plan,config=pendingExportConfig){
  pendingExportConfig=config||pendingExportConfig;
  const m=$('#exportMapModal');const options=Array.from({length:plan.max_output_slots},(_,i)=>`<option value="${i+1}">Slot ${i+1}</option>`).join('');
  m.innerHTML=`<h3>${plan.target} export mapping</h3><p class="hint">Assign every project track to an output slot. Tracks assigned to the same slot are mixed together before the MTA is generated.</p><div class="mapping-grid">${plan.tracks.map((t,i)=>`<label><span>${esc(t.name)} <small>${esc(t.type)}</small></span><select class="slot-map" data-track="${t.id}">${options.replace(`value=\"${Math.min(i+1,plan.max_output_slots)}\"`,`value=\"${Math.min(i+1,plan.max_output_slots)}\" selected`)}</select></label>`).join('')}</div><div class="modal-actions"><button onclick="submitExportMapping('${plan.target}')">Merge &amp; export MTA</button><button onclick="closeExportMapping()">Cancel</button></div>`;m.classList.remove('hidden')
}
function closeExportMapping(){$('#exportMapModal')?.classList.add('hidden')}
async function submitExportMapping(target){
  const grouped={};$$('.slot-map').forEach(x=>{(grouped[x.value]??=[]).push(x.dataset.track)});
  const slots=Object.entries(grouped).map(([slot,ids])=>{const ts=ids.map(trackById).filter(Boolean);return{slot:Number(slot),name:ts.map(t=>t.name).join(' + ').slice(0,200),type:ts.length===1?ts[0].type:(target==='MTA8'&&Number(slot)<=8?['drums','bass','guitars','keyboards','orchestra','winds','melody','click'][Number(slot)-1]:'other'),track_ids:ids}});
  closeExportMapping();
  const config=pendingExportConfig||{format:'mta',filename:current.title||'project',mp3_bitrate_kbps:320,sample_rate:44100,wav_bit_depth:24,flac_compression:8,output_path:null};
  await executeConfiguredExport(config,slots);
}
async function showMtaAnalysis(){try{const r=await api(`/api/projects/${current.id}/mta-analysis`);const a=r.attachments||[];alert(`Container: ${r.observations?.container_is_matroska?'Matroska':'unknown'}\nAudio streams: ${(r.audio_streams||[]).length}\nAttachments: ${a.length}\nSYL candidates: ${(r.observations?.syl_candidates||[]).join(', ')||'none detected'}\n\nDetailed analysis is available from the API and project data.`)}catch(e){toast(e.message)}}


async function showProjectSetup(){
  if(!current)return toast('Apri prima un progetto');
  let savePath='';
  let storageMode=currentUser?.native_single_user?'Native filesystem':'Server workspace';
  if(currentUser?.native_single_user&&window.pywebview?.api?.get_project_path){
    try{
      const info=await window.pywebview.api.get_project_path(current.id);
      savePath=info?.bound?info.path:'Non ancora associato a un file';
    }catch(e){savePath='Percorso non disponibile'}
  }else{
    savePath=`Workspace gestito · project id ${current.id}`;
  }
  const stereo=current.tracks.filter(t=>Number(t.channels)===2).length;
  const mono=current.tracks.filter(t=>Number(t.channels)===1).length;
  const unknown=current.tracks.length-stereo-mono;
  const trackInserts=current.tracks.reduce((n,t)=>n+(t.inserts?.length||0),0);
  const maxDuration=Math.max(0,...current.tracks.map(t=>Number(t.duration_ms)||0));
  showUtilityModal('Project setup',`
    <div class="project-setup-card">
      <div class="setup-grid">
        <div><span>Nome</span><b>${esc(current.title)}</b></div>
        <div><span>Formato</span><b>${esc(current.target)}</b></div>
        <div><span>Project ID</span><b>${esc(current.id)}</b></div>
        <div><span>Storage</span><b>${esc(storageMode)}</b></div>
        <div class="setup-wide"><span>Path di salvataggio</span><b>${esc(savePath)}</b></div>
        <div><span>Tracce</span><b>${current.tracks.length}</b></div>
        <div><span>Canali</span><b>${stereo} stereo · ${mono} mono${unknown?` · ${unknown} n/d`:''}</b></div>
        <div><span>Durata max</span><b>${fmtTime(maxDuration/1000,true)}</b></div>
        <div><span>BPM</span><b>${Number(current.bpm||120).toFixed(1)}</b></div>
        <div><span>Pitch</span><b>${Number(current.pitch_semitones||0).toFixed(1)} st</b></div>
        <div><span>Insert tracce</span><b>${trackInserts}</b></div>
        <div><span>Insert Master</span><b>${current.master_inserts?.length||0}</b></div>
        <div><span>Auto Mix</span><b>${current.auto_mix_enabled?`Attivo · ${esc(current.auto_mix_style||'balanced')}`:'Disattivato'}</b></div>
        <div><span>Preview</span><b>${current.render_preview_enabled?'Render':'Dynamic'}</b></div>
        <div><span>Follow</span><b>${current.follow_playback_enabled?'Attivo':'Disattivato'}</b></div>
        <div><span>RealTime meters</span><b>${current.realtime_meter_enabled?'Attivi':'Disattivati'}</b></div>
      </div>
      <div class="utility-actions">
        ${currentUser?.native_single_user?`<button class="utility-btn primary" onclick="closeUtilityModal();saveProjectLocal()">Cambia percorso / Salva con nome</button>`:''}
        <button class="utility-btn secondary" onclick="closeUtilityModal()">Chiudi</button>
      </div>
    </div>`);
}

async function showAbout(){
  try{
    const info=await api('/api/about');
    showUtilityModal('Informazioni',`
      <div class="about-card">
        <img src="/static/logo.svg" alt="MTA Audio Editor" class="about-logo">
        <h3>${esc(info.name||'MTA Audio Editor')}</h3>
        <dl>
          <dt>Versione</dt><dd>${esc(info.version||'')}</dd>
          <dt>Build</dt><dd>${esc(info.build||'')}</dd>
          <dt>Creatore</dt><dd>${esc(info.creator||'')}</dd>
          <dt>Licenza</dt><dd>${esc(info.license||'')}</dd>
          <dt>Progetto</dt><dd><a href="${esc(info.repository||'#')}" target="_blank" rel="noopener">${esc(info.repository||'')}</a></dd>
        </dl>
        <div class="utility-actions"><button class="utility-btn primary" onclick="closeUtilityModal()">Chiudi</button></div>
      </div>`);
  }catch(e){toast(e.message)}
}

function openExportPanel(){if(!current)return;if(!current.export_panel_visible){current.export_panel_visible=true;render();markDirty(100)}focusMixer();$('#exportPane')?.scrollIntoView({behavior:'smooth',block:'nearest'})}
function requireOpenProject(action){if(current)return true;toast(`Apri o crea un progetto per ${action}`);return false}
function focusProjectWorkspace(){if(!current){$('#emptyState')?.scrollIntoView({behavior:'smooth',block:'center'});return}$('#editor')?.scrollIntoView({behavior:'smooth',block:'start'})}
function focusTracks(){if(!requireOpenProject('visualizzare le tracce'))return;const el=$('.tracks-scroll')||$('.tracks')||$('#editor');el?.scrollIntoView({behavior:'smooth',block:'start'});el?.classList.add('nav-focus-pulse');setTimeout(()=>el?.classList.remove('nav-focus-pulse'),900)}
function focusMixer(){if(!requireOpenProject('aprire il mixer'))return;const el=$('#mixerDock');if(el){el.hidden=false;el.scrollIntoView({behavior:'smooth',block:'nearest'});el.classList.add('nav-focus-pulse');setTimeout(()=>el.classList.remove('nav-focus-pulse'),900)}}
function focusInspector(){if(!requireOpenProject('aprire i plugin'))return;const el=$('#inspector');if(!el)return toast('Seleziona una traccia per visualizzare i plugin');el.scrollIntoView({behavior:'smooth',block:'nearest'});el.classList.add('nav-focus-pulse');setTimeout(()=>el.classList.remove('nav-focus-pulse'),900)}
function focusImport(){$('#newTrackFile')?.click()}

function editProjectMeta(){if(!current)return;const title=prompt('Project title',current.title);if(title!==null&&title.trim())current.title=title.trim().slice(0,200);const artist=prompt('Artist',current.artist||'');if(artist!==null)current.artist=artist.slice(0,200);const bpm=prompt('BPM',String(current.bpm));if(bpm!==null&&Number(bpm)>0)setProjectBpm(Math.min(300,Number(bpm)));render();markDirty()}
function editTimed(kind){if(!current)return;const config={lyrics:['text','Lyrics: seconds[TAB]text'],chords:['chord','Chords: seconds[TAB]chord'],markers:['label','Markers: seconds[TAB]label']}[kind];if(!config)return;const [key,label]=config;const raw=prompt(label,linesToText(current[kind],key));if(raw!==null){current[kind]=textToLines(raw,key);render();markDirty()}}



window.addEventListener('pointerdown',e=>{
  const menu=$('#trackContextMenu');
  if(menu&&!menu.contains(e.target))closeTrackContextMenu();
});
window.addEventListener('keydown',e=>{
  if((e.ctrlKey||e.metaKey)&&!e.altKey){const key=e.key.toLowerCase();if(key==='z'){e.preventDefault();if(e.shiftKey)redoEdit();else undoEdit();return}if(key==='y'){e.preventDefault();redoEdit();return}if(key==='x'){e.preventDefault();cutTimelineSelection();return}if(key==='c'){e.preventDefault();copyTimelineSelection();return}if(key==='v'){e.preventDefault();pasteTimelineSelection();return}if(key==='s'){e.preventDefault();save();return}}
  if(e.key==='Escape'){closeTrackContextMenu();return}

  if(e.code!=='Space')return;
  const target=e.target;
  if(target instanceof HTMLInputElement||target instanceof HTMLTextAreaElement||target instanceof HTMLSelectElement||target?.isContentEditable)return;
  e.preventDefault();
  if(playAudio||trackPlaybacks.length||playbackPaused)stopPlayback();else previewMaster();
});

$('#mtafile').addEventListener('change',async e=>{
  const f=e.target.files[0];if(!f)return;
  const fd=new FormData();fd.append('file',f);
  try{
    showMediaProgress('Import MTA',1,'Preparazione upload');
    const job=await uploadWithProgress('/api/import-jobs',fd,'Import MTA');
    showMediaProgress('Import MTA',job.progress,job.message);
    pollMediaJob(job.id,'Import MTA',async completed=>{
      current=await api(`/api/projects/${completed.result.project_id}`);
      selectedTrackId=current.tracks[0]?.id||null;
      render();await refresh();
      $('#utilityBackdrop').classList.add('hidden');
      toast(`MTA importato · ${completed.result.track_count} tracce`);
    });
  }catch(err){
    $('#utilityBackdrop').classList.add('hidden');
    toast('Import MTA fallito: '+err.message);
  }finally{
    e.target.value='';
  }
});
init();


function showUtilityModal(title,html,stemProgress=false){
  if(activeStemJob&&!stemProgress){
    toast('La separazione è in corso: la barra di progresso rimane visibile fino al completamento.');
    return;
  }
  $('#utilityTitle').textContent=title;$('#utilityBody').innerHTML=html;$('#utilityBackdrop').classList.remove('hidden');
}
function closeUtilityModal(){if(activeStemJob){toast('La separazione è in corso: usa Annulla separazione se vuoi interromperla.');return}$('#utilityBackdrop').classList.add('hidden')}
function exportProjectArchive(){if(!current){toast('Apri prima un progetto');return}window.location.href=`/api/projects/${current.id}/archive`}
async function deleteCurrentProject(){if(!current){toast('Apri prima un progetto');return}await deleteProjectFromWorkspace(current.id,current.title)}
$('#projectArchiveFile').addEventListener('change',async e=>{const f=e.target.files[0];if(!f)return;const fd=new FormData();fd.append('file',f);try{current=await api('/api/project-archives/import',{method:'POST',body:fd});selectedTrackId=current.tracks[0]?.id||null;render();await refresh();toast('Progetto completo importato')}catch(err){toast('Import progetto fallito: '+err.message)}finally{e.target.value=''}})
async function manageProjectFiles(){
  if(!current){toast('Apri prima un progetto');return}
  try{
    const files=await api(`/api/projects/${current.id}/files`);
    const rows=files.map((f,i)=>{
      const deletable=!f.referenced&&f.category!=='source';
      return `<tr>
        <td>${deletable?`<input class="project-file-check" type="checkbox" data-category="${esc(f.category)}" data-name="${encodeURIComponent(f.name)}">`:''}</td>
        <td>${esc(f.category)}</td><td>${esc(f.name)}</td><td>${(f.size/1024/1024).toFixed(2)} MB</td><td>${f.referenced?'in uso':''}</td>
        <td><a class="mini-link" href="/api/projects/${current.id}/files/${encodeURIComponent(f.category)}/${encodeURIComponent(f.name)}">Scarica</a>${deletable?` <button onclick="deleteProjectFile('${esc(f.category)}','${encodeURIComponent(f.name)}')">Elimina</button>`:''}</td>
      </tr>`;
    }).join('');
    showUtilityModal('File del progetto',`
      <div class="utility-actions">
        <label class="utility-upload">Carica file originale<input id="extraProjectFile" type="file" hidden></label>
        <button class="utility-btn secondary" onclick="toggleAllProjectFiles(true)">Seleziona tutti</button>
        <button class="utility-btn secondary" onclick="toggleAllProjectFiles(false)">Deseleziona</button>
        <button class="utility-btn danger-action" onclick="deleteSelectedProjectFiles()">Elimina selezionati</button>
      </div>
      <div class="table-scroll"><table class="users-table"><thead><tr><th></th><th>Tipo</th><th>File</th><th>Dimensione</th><th>Stato</th><th>Azioni</th></tr></thead><tbody>${rows||'<tr><td colspan="6">Nessun file.</td></tr>'}</tbody></table></div>
      <p class="hint">I file in uso e il source MTA non sono selezionabili. I dump completi includono project.json, audio, attachment, source MTA e originali.</p>`);
    $('#extraProjectFile').addEventListener('change',uploadExtraProjectFile);
  }catch(e){toast(e.message)}
}
function toggleAllProjectFiles(value){$$('.project-file-check').forEach(x=>x.checked=!!value)}
async function deleteSelectedProjectFiles(){
  const selected=$$('.project-file-check:checked').map(x=>({category:x.dataset.category,name:decodeURIComponent(x.dataset.name)}));
  if(!selected.length)return toast('Seleziona almeno un file');
  if(!confirm(`Eliminare ${selected.length} file selezionati?`))return;
  try{
    const result=await api(`/api/projects/${current.id}/files/batch-delete`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(selected)});
    await manageProjectFiles();
    toast(result.ok?`${selected.length} file eliminati`:`Eliminati ${result.deleted.length} file; ${result.errors.length} non eliminati`);
  }catch(e){toast(e.message)}
}
async function uploadExtraProjectFile(e){const f=e.target.files[0];if(!f)return;const fd=new FormData();fd.append('file',f);try{const r=await api(`/api/projects/${current.id}/files/upload`,{method:'POST',body:fd});await manageProjectFiles();toast(r.duplicate?'File già presente: nessuna copia aggiunta':'File caricato')}catch(err){toast(err.message)}}
async function deleteProjectFile(category,name){name=decodeURIComponent(name);if(!confirm(`Eliminare ${name}?`))return;try{await api(`/api/projects/${current.id}/files/${encodeURIComponent(category)}/${encodeURIComponent(name)}`,{method:'DELETE'});await manageProjectFiles()}catch(e){toast(e.message)}}
async function manageProjectSharing(){
  if(!current){toast('Apri prima un progetto');return}
  try{
    const shares=await api(`/api/projects/${current.id}/shares`);
    showUtilityModal('Condivisione progetto',`<div class="share-form"><input id="shareIdentifier" placeholder="Username o email"><button onclick="addProjectShare()">Condividi</button></div><div class="share-list">${shares.map(u=>`<div><span><b>${esc(u.display_name||u.username)}</b><small>${esc(u.username)} · ${esc(u.email)}</small></span><button onclick="removeProjectShare(${u.id})">Rimuovi</button></div>`).join('')||'<p class="hint">Il progetto non è condiviso con altri utenti.</p>'}</div><p class="hint">Gli utenti condivisi possono aprire e modificare il progetto; solo il proprietario o un amministratore possono cambiarne le condivisioni o eliminarlo.</p>`);
  }catch(e){toast(e.message)}
}
async function addProjectShare(){const identifier=$('#shareIdentifier').value.trim();if(!identifier)return;try{await api(`/api/projects/${current.id}/shares`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({identifier})});await manageProjectSharing();toast('Progetto condiviso')}catch(e){toast(e.message)}}
async function removeProjectShare(userId){try{await api(`/api/projects/${current.id}/shares/${userId}`,{method:'DELETE'});await manageProjectSharing()}catch(e){toast(e.message)}}

async function showNativeSettings(){
  if(!currentUser?.native_single_user){toast('Settings è disponibile nell’app desktop nativa');return}
  const apiBridge=await waitForNativeApi();
  if(!apiBridge?.get_native_settings){toast('Bridge nativo non disponibile. Riprova tra un istante.');return}
  try{
    const cfg=await apiBridge.get_native_settings();
    showUtilityModal('Settings',`<div class="form-grid"><label>Maximum import/upload size (MB)<input id="nativeMaxUploadMb" type="number" min="1" max="10240" step="1" value="${Number(cfg.max_upload_mb)||1024}"></label><label class="workflow-check"><input id="nativeAutosaveEnabled" type="checkbox" ${cfg.autosave_enabled!==false?'checked':''}> Auto-save project changes</label><p>With Auto-save disabled, changes remain in the current session until you press <b>Save</b>. Undo/Redo is session-only.</p><div class="form-actions"><button class="accent" onclick="saveNativeSettings()">Save</button></div></div>`);
  }catch(err){toast('Impossibile leggere le impostazioni native: '+err.message)}
}
async function saveNativeSettings(){
  const value=Number($('#nativeMaxUploadMb')?.value);
  if(!Number.isInteger(value)||value<1||value>10240){toast('Inserisci un valore intero tra 1 e 10240 MB');return}
  try{
    const apiBridge=await waitForNativeApi();if(!apiBridge?.set_native_settings)return toast('Bridge nativo non disponibile');
    const enabled=$('#nativeAutosaveEnabled')?.checked!==false;const result=await apiBridge.set_native_settings(value,enabled);autosaveEnabled=result.autosave_enabled!==false;if(autosaveEnabled&&projectDirty)markDirty(50);
    closeUtilityModal();toast(`Limite import/upload impostato a ${result.max_upload_mb} MB`);
  }catch(err){toast('Salvataggio impostazioni fallito: '+err.message)}
}
function exposeNativeSettings(){
  const b=$('#nativeSettingsButton');if(b&&window.pywebview?.api)b.hidden=false;
}
window.addEventListener('pywebviewready',exposeNativeSettings);
