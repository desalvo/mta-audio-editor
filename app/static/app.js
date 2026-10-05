
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
let preferredStemCount=Number(localStorage.getItem('mtaStemCount')||0);if(preferredStemCount!==0&&(preferredStemCount<2||preferredStemCount>64))preferredStemCount=0;
function setPreferredStemCount(value){const n=Number(value||0);preferredStemCount=(n===0||(n>=2&&n<=64))?n:0;localStorage.setItem('mtaStemCount',String(preferredStemCount));}
let preferredStemExecution=localStorage.getItem('mtaStemExecution')||'auto';if(!['auto','local','server'].includes(preferredStemExecution))preferredStemExecution='auto';
function setPreferredStemExecution(value){preferredStemExecution=['auto','local','server'].includes(value)?value:'auto';localStorage.setItem('mtaStemExecution',preferredStemExecution);}
let undoStack=[],redoStack=[],historyProjectId=null,lastHistoryState=null,timelineClipboard=null;
let playCursorMs=0, playRaf=null, mediaProgressTimer=null;
let uiState={trackTop:0,timelineTop:0,timelineLeft:0,mixerLeft:0};
let waveformJobs={}, waveformValidationProjectId=null, trackPlaybacks=[], meterRaf=null, meterRunToken=0, playbackToken=0, masterMeterAnalysers=null, masterPlaybackGainNode=null;
let renderedMasterPlayback=false, renderedMasterDirty=false, renderedMasterRefreshPromise=null, renderedMasterBaseVolumeDb=0, renderedMasterAudio=null;
let dynamicSyncClock=null, dynamicSyncTimer=null, playbackBuffering=false;
const liveFxRefreshTimers={};
let lastSelectedAudioFile=null, playbackPaused=false, mixerMetaTab='lyrics', pendingExportConfig=null, pendingNewProjectPath=null;
let sampleEditor=null,sampleEditorPreviewAbort=null,sampleEditorPreviewTimer=null,serverProjects=[];
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const TRACK_COLORS=['#2f81f7','#28b463','#f0a52b','#8a58db','#e9506c','#8395a7','#24b8d4','#b26ff2','#e67e22','#16a085','#d35400','#7f8c8d'];

function mobilePlatform(){
  try{return window.MtaMobile?.getPlatform?.()||''}catch(e){return ''}
}
function isMobileClient(){return ['android','ios'].includes(mobilePlatform())}
function supportsLocalIosStems(){return mobilePlatform()==='ios'&&!!window.MtaMobile?.startLocalStemSeparation}
function nativeApi(){return window.pywebview?.api||null}
function isNativeDesktop(){return !!nativeApi()||!!currentUser?.native_single_user}
function forceNativeViewportTop(){if(!currentUser?.native_single_user&&!document.body.classList.contains('native-single-user'))return;requestAnimationFrame(()=>{window.scrollTo(0,0);document.documentElement.scrollTop=0;document.body.scrollTop=0})}
function installNativeViewportGuard(){if(!currentUser?.native_single_user)return;document.body.classList.add('native-single-user');const guard=()=>{if(window.scrollY||document.documentElement.scrollTop||document.body.scrollTop)forceNativeViewportTop()};window.addEventListener('scroll',guard,{passive:true});window.addEventListener('focus',forceNativeViewportTop);document.addEventListener('focusin',()=>setTimeout(forceNativeViewportTop,0));forceNativeViewportTop()}
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

async function init(){if(isMobileClient())document.body.classList.add('mobile-client');try{currentUser=await api('/api/session');const a=$('#adminNav');if(a)a.hidden=!!currentUser.native_single_user||currentUser.role!=='admin';const sb=$('#nativeSettingsButton');if(sb)sb.hidden=false;const recentBtn=$('#openRecentProjectBtn'),localBtn=$('#openLocalProjectBtn');if(currentUser.native_single_user){document.body.classList.add('native-single-user');if(recentBtn)recentBtn.hidden=false;if(localBtn)localBtn.hidden=true}else{if(recentBtn)recentBtn.hidden=true;if(localBtn)localBtn.hidden=false}}catch(e){}if(currentUser?.native_single_user)installNativeViewportGuard();if(currentUser&&!currentUser.native_single_user)autosaveEnabled=localStorage.getItem('mtaWebAutosaveEnabled')!=='false';if(currentUser?.native_single_user){const bridge=await waitForNativeApi();if(bridge?.get_native_settings){try{const cfg=await bridge.get_native_settings();autosaveEnabled=cfg.autosave_enabled!==false}catch(e){}}setTimeout(()=>checkNativeAppUpdate(false),1200)}try{pluginInfo=await api('/api/plugins')}catch(e){}await refresh()}

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

function recentProjectIds(){try{return JSON.parse(localStorage.getItem('mtaRecentProjects')||'[]').filter(Boolean)}catch(e){return[]}}
function rememberRecentProject(id){if(!id)return;const ids=[String(id),...recentProjectIds().filter(x=>String(x)!==String(id))].slice(0,12);localStorage.setItem('mtaRecentProjects',JSON.stringify(ids))}
function forgetRecentProject(id){localStorage.setItem('mtaRecentProjects',JSON.stringify(recentProjectIds().filter(x=>String(x)!==String(id))))}
function resetProjectUiForOpen(){clipBrowserExpanded=false;clipBrowserQuery='';clipBrowserPage=1;expandedProjectClipDetails=new Set();uiState={trackTop:0,timelineTop:0,timelineLeft:0,mixerLeft:0};if(currentUser?.native_single_user)forceNativeViewportTop()}
async function refresh(){
  try{serverProjects=await api('/api/projects')}catch(e){serverProjects=[]}
  return serverProjects;
}
function projectPickerRows(projects,emptyMessage){
  return projects.length?`<div class="project-picker-list">${projects.map(p=>{const shared=currentUser&&p.owner_user_id&&p.owner_user_id!==currentUser.id;return `<button class="project-picker-row" onclick="openProjectFromPicker('${esc(p.id)}')"><span><b>${shared?'⌘ ':''}${esc(p.title)}</b><small>${shared?'Shared · ':''}${esc(p.target||'DAW')}</small></span><strong>Apri ›</strong></button>`}).join('')}</div>`:`<p class="hint">${esc(emptyMessage)}</p>`;
}
async function openProjectFromPicker(id){closeUtilityModal();await openP(id)}
async function openProjectSelector(){
  if(currentUser?.native_single_user)return openProjectArchive();
  const projects=await refresh();
  showUtilityModal('Open project',`${projectPickerRows(projects,'Nessun progetto attivo sul server.')}<div class="utility-actions"><button class="utility-btn secondary" onclick="closeUtilityModal()">Annulla</button></div>`);
}
async function openRecentProjects(){
  if(!currentUser?.native_single_user)return;
  const projects=await refresh(),byId=new Map(projects.map(p=>[String(p.id),p]));
  const recent=recentProjectIds().map(id=>byId.get(String(id))).filter(Boolean);
  showUtilityModal('Open recent',`${projectPickerRows(recent,'Nessun progetto recente ancora disponibile.')}<div class="utility-actions"><button class="utility-btn secondary" onclick="closeUtilityModal()">Annulla</button></div>`);
}
function openLocalProject(){
  if(currentUser?.native_single_user)return openProjectArchive();
  $('#projectArchiveFile')?.click();
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
      <label class="workflow-field"><span>Tipo progetto</span><select id="newProjectTarget"><option value="DAW">Multitrack DAW</option><option value="MTA8">MTA8</option><option value="MTA16">MTA16</option></select></label>
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
  const target=$('#newProjectTarget')?.value||'DAW';
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
    current=created;rememberRecentProject(current.id);
    selectedTrackId=null;resetProjectUiForOpen();resetSessionHistory();
    closeUtilityModal();render();await refresh();
    toast(currentUser?.native_single_user?`Progetto ${target} creato in ${pendingNewProjectPath}`:`Progetto ${target} creato e salvato nel workspace`);
    pendingNewProjectPath=null;
  }catch(e){toast(e.message)}
}
async function openP(id){
  if(activeStemJob&&activeStemProjectId&&id!==activeStemProjectId){
    return toast('La separazione è in corso: resta nel progetto corrente fino al completamento.');
  }
  await flushAutosave();stopPlayback();
  current=await api('/api/projects/'+id);rememberRecentProject(current.id);selectedTrackId=current.tracks[0]?.id||null;resetProjectUiForOpen();resetSessionHistory();render();refresh();
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
      current=result.project;rememberRecentProject(current.id);selectedTrackId=current.tracks[0]?.id||null;resetProjectUiForOpen();render();await refresh();toast('Progetto aperto dal filesystem');return;
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
    forgetRecentProject(id);
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
    ${clipBrowserHtml()}
    <div class="editor-grid" id="editorGrid" style="--track-column-width:${trackWidth}px">
      <div class="track-column" id="trackColumn"><div class="track-column-head">TRACKS</div>${current.tracks.map((t,i)=>trackHead(t,i)).join('')}</div>
      <div class="track-resizer" id="trackResizer" title="Ridimensiona Tracks"></div>
      <div class="timeline-pane" id="timelinePane"><div class="ruler"><canvas id="ruler" width="${W}" height="30"></canvas></div><div class="lanes" id="lanes" style="width:${W}px">${current.tracks.map((t,i)=>lane(t,W,i)).join('')}<div class="selection" id="selection" style="display:none"></div><div class="playhead" id="playhead" style="left:${playCursorMs/1000*pxPerSec}px"></div></div></div>
      ${inspectorHtml()}
    </div>`;
  $('#mixerDock').innerHTML=mixerHtml();
  updateMixerDockLayout();updatePanelMenuButtons();
  drawRuler();bindTimeline();bindProjectClipDrop();bindTrackTimelineScroll();bindTrackResizer();
  current.tracks.forEach(drawWave);if(waveformValidationProjectId!==current.id){waveformValidationProjectId=current.id;ensureWaveforms(true)}else ensureWaveforms(false);updateSel();bindModelInputs();updateMuteSoloVisuals();restoreUiState();ensureSessionHistory();updateEditActionState();forceNativeViewportTop();
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
    <button class="toolbar-action" onclick="openYoutubeImport()" title="Importa solo audio da un singolo video YouTube">▶ Import YouTube</button>
    <button class="toolbar-action" onclick="createMetronomeTrack()" title="Crea una traccia click per tutta la durata corrente del progetto">♩ Metronomo</button>
    <div class="toolbar-group"><input id="newTrackFile" type="file" accept=".mp3,.wav,.flac,.m4a,audio/*" onchange="addTrack()"><select id="newSync"><option value="manual">Manual sync</option><option value="auto">Auto sync</option></select><input id="newOffset" type="number" value="0" title="Offset ms" style="width:72px"><select id="newRef" style="max-width:115px">${refs}</select><button class="toolbar-action" onclick="addTrack()">♫ Import Audio Track</button></div>
    <div class="toolbar-sep"></div><button id="undoBtn" class="toolbar-action" onclick="undoEdit()">↶ Undo</button><button id="redoBtn" class="toolbar-action" onclick="redoEdit()">↷ Redo</button><button class="toolbar-action" onclick="cutTimelineSelection()">✂ Cut</button><button class="toolbar-action" onclick="copyTimelineSelection()">⧉ Copy</button><button id="pasteBtn" class="toolbar-action" onclick="pasteTimelineSelection()">▣ Paste</button><button class="toolbar-action danger" onclick="removeTimelineSelection()">⌫ Remove</button> <div class="toolbar-grow"></div><span class="selection-info" id="selectionInfo">0.000 → 0.000 s</span><button class="toolbar-action danger" onclick="deleteSelection(false)">Delete tracks</button><label class="hint"><input id="ripple" type="checkbox"> ripple</label><button class="toolbar-action danger" onclick="deleteSelection(true)">Delete song segment</button>
  </div>`
}

let clipBrowserExpanded=false;
let clipBrowserQuery='';
let clipBrowserPage=1;
const CLIP_BROWSER_PAGE_SIZE=10;
let draggedLibraryClipId=null;
let clipPointerDrag=null;
let clipPreviewAudio=null;
let clipPreviewId=null;
let expandedProjectClipDetails=new Set();

function clipDurationHms(ms){
  const total=Math.max(0,Math.floor((Number(ms)||0)/1000));
  const h=Math.floor(total/3600),m=Math.floor((total%3600)/60),sec=total%60;
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
}
function clipBytesLabel(value){
  const n=Math.max(0,Math.round(Number(value)||0));
  return `${n.toLocaleString('it-IT')} bytes`;
}
function clipMetadataHtml(item){
  const entries=Object.entries(item.embedded_metadata||{});
  if(!entries.length)return '<span class="clip-meta-empty">Nessun metadato embedded rilevato</span>';
  return `<dl class="clip-embedded-meta">${entries.map(([k,v])=>`<div><dt>${esc(k)}</dt><dd>${esc(String(v))}</dd></div>`).join('')}</dl>`;
}
function toggleProjectClipDetails(id){
  if(expandedProjectClipDetails.has(id))expandedProjectClipDetails.delete(id);else expandedProjectClipDetails.add(id);
  render();
}
async function saveProjectClipNotes(id){
  if(!current||!id)return;
  const field=document.querySelector(`[data-clip-notes="${id}"]`);if(!field)return;
  try{
    await flushAutosave();
    const result=await api(`/api/projects/${current.id}/clip-library/${encodeURIComponent(id)}`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({notes:String(field.value||'')})});
    current=result.project;expandedProjectClipDetails.add(id);render();toast('Note della clip salvate');
  }catch(e){toast('Impossibile salvare le note: '+e.message)}
}
function clipBrowserHtml(){
  const all=current?.clip_library||[];
  const q=String(clipBrowserQuery||'').trim().toLocaleLowerCase();
  const filtered=q?all.filter(item=>String(item.name||'').toLocaleLowerCase().includes(q)):all;
  const pageCount=Math.max(1,Math.ceil(filtered.length/CLIP_BROWSER_PAGE_SIZE));
  clipBrowserPage=Math.min(Math.max(1,clipBrowserPage),pageCount);
  const start=(clipBrowserPage-1)*CLIP_BROWSER_PAGE_SIZE;
  const items=filtered.slice(start,start+CLIP_BROWSER_PAGE_SIZE);
  const body=items.length?items.map(item=>{
    const expanded=expandedProjectClipDetails.has(item.id);
    const bitrate=Number(item.bitrate_bps)||0;
    return `<div class="project-clip-card ${expanded?'details-open':''}" draggable="true" data-project-clip="${item.id}" ondragstart="beginProjectClipDrag(event,'${item.id}')" ondragend="endProjectClipDrag()">
      <div class="project-clip-summary">
        <button class="clip-drag-handle" title="Trascina sulla timeline" aria-label="Trascina ${esc(item.name)} sulla timeline" onpointerdown="beginProjectClipPointer(event,'${item.id}')">⠿</button>
        <div class="project-clip-info"><strong title="${esc(item.name)}">${esc(item.name)}</strong><span>${esc(item.type||'other')} · ${clipDurationHms(item.duration_ms)}${item.channels?` · ${item.channels===1?'mono':item.channels===2?'stereo':`${item.channels} ch`}`:''}</span></div>
        <div class="project-clip-actions">
          <button class="clip-preview-btn ${clipPreviewId===item.id?'active':''}" onclick="previewProjectClip('${item.id}')" title="Preview audio">${clipPreviewId===item.id?'■':'▶'}</button>
          <button class="clip-rename-btn" onclick="renameProjectClip('${item.id}')" title="Rinomina clip">✎</button>
          <button class="clip-add-btn" onclick="instantiateProjectClip('${item.id}',playCursorMs)" title="Aggiungi alla posizione del cursore">＋</button>
          <button class="clip-details-btn" onclick="toggleProjectClipDetails('${item.id}')" title="${expanded?'Nascondi':'Mostra'} dettagli clip">${expanded?'⌃':'⌄'}</button>
        </div>
      </div>
      ${expanded?`<div class="project-clip-details" onclick="event.stopPropagation()" ondragstart="event.preventDefault();event.stopPropagation()">
        <dl class="clip-detail-grid">
          <div><dt>Tipo clip</dt><dd>${esc(item.type||'other')}</dd></div>
          <div><dt>Formato</dt><dd>${esc(item.format||'—')}</dd></div>
          <div><dt>Bitrate</dt><dd>${bitrate?`${Math.round(bitrate/1000)} kb/s (${bitrate.toLocaleString('it-IT')} bps)`:'—'}</dd></div>
          <div><dt>Durata</dt><dd>${clipDurationHms(item.duration_ms)}</dd></div>
          <div><dt>Dimensione</dt><dd>${clipBytesLabel(item.size_bytes)}</dd></div>
          <div><dt>Provenienza</dt><dd>${esc(item.provenance||'Audio del progetto')}</dd></div>
          <div class="wide"><dt>Locazione attuale</dt><dd><code>${esc(item.current_location||`audio/${item.filename||''}`)}</code></dd></div>
          <div class="wide"><dt>Metadati clip</dt><dd>${clipMetadataHtml(item)}</dd></div>
          <div class="wide clip-notes-field"><dt>Note</dt><dd><textarea data-clip-notes="${item.id}" maxlength="4000" placeholder="Note sulla clip…">${esc(item.notes||'')}</textarea><button onclick="saveProjectClipNotes('${item.id}')">Salva note</button></dd></div>
        </dl>
      </div>`:''}
    </div>`;
  }).join(''):`<div class="clip-browser-empty">${q?'Nessuna clip corrisponde alla ricerca.':'Le clip audio importate appariranno qui e resteranno riutilizzabili nel progetto.'}</div>`;
  return `<section class="clip-browser ${clipBrowserExpanded?'':'collapsed'}" id="clipBrowser">
    <button class="clip-browser-toggle" onclick="clipBrowserExpanded=!clipBrowserExpanded;render()" title="Mostra/nascondi browser clip"><span>▦ CLIP DEL PROGETTO</span><b>${all.length}</b><i>${clipBrowserExpanded?'⌃':'⌄'}</i></button>
    ${clipBrowserExpanded?`<div class="clip-browser-main">
      <div class="clip-browser-controls">
        <input class="clip-browser-search" type="search" placeholder="Cerca clip per nome…" value="${esc(clipBrowserQuery)}" oninput="setClipBrowserQuery(this.value)">
        <span>${filtered.length} risultat${filtered.length===1?'o':'i'}</span>
        <button ${clipBrowserPage<=1?'disabled':''} onclick="setClipBrowserPage(${clipBrowserPage-1})">‹</button>
        <b>${clipBrowserPage}/${pageCount}</b>
        <button ${clipBrowserPage>=pageCount?'disabled':''} onclick="setClipBrowserPage(${clipBrowserPage+1})">›</button>
      </div>
      <div class="clip-browser-items">${body}</div>
    </div>`:''}
  </section>`;
}

function setClipBrowserQuery(value){clipBrowserQuery=String(value||'');clipBrowserPage=1;render()}
function setClipBrowserPage(page){clipBrowserPage=Math.max(1,Number(page)||1);render()}

async function renameProjectClip(id){
  if(!current||!id)return;
  const asset=(current.clip_library||[]).find(item=>item.id===id);if(!asset)return;
  const name=prompt('Nuovo nome della clip',asset.name||'');
  if(name===null)return;
  const trimmed=String(name).trim();if(!trimmed)return toast('Il nome della clip non può essere vuoto');
  try{
    await flushAutosave();
    const result=await api(`/api/projects/${current.id}/clip-library/${encodeURIComponent(id)}`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({name:trimmed})});
    current=result.project;render();toast('Clip rinominata. Le tracce associate restano collegate tramite ID.');
  }catch(e){toast('Impossibile rinominare la clip: '+e.message)}
}

function stopProjectClipPreview(){
  if(clipPreviewAudio){try{clipPreviewAudio.pause();clipPreviewAudio.currentTime=0}catch(_e){}}
  clipPreviewAudio=null;clipPreviewId=null;render();
}
function previewProjectClip(id){
  if(!current||!id)return;
  if(clipPreviewId===id){stopProjectClipPreview();return}
  if(clipPreviewAudio){try{clipPreviewAudio.pause()}catch(_e){}}
  const asset=(current.clip_library||[]).find(item=>item.id===id);if(!asset)return;
  const audio=new Audio(`/api/projects/${current.id}/audio/${encodeURIComponent(asset.filename)}?t=${Date.now()}`);
  clipPreviewAudio=audio;clipPreviewId=id;render();
  audio.addEventListener('ended',()=>{if(clipPreviewAudio===audio){clipPreviewAudio=null;clipPreviewId=null;render()}});
  audio.addEventListener('error',()=>{if(clipPreviewAudio===audio){clipPreviewAudio=null;clipPreviewId=null;render();toast('Preview clip non disponibile')}});
  audio.play().catch(e=>{clipPreviewAudio=null;clipPreviewId=null;render();toast('Impossibile avviare il preview: '+e.message)});
}

function beginProjectClipDrag(event,id){
  draggedLibraryClipId=id;
  event.dataTransfer.effectAllowed='copy';
  event.dataTransfer.setData('application/x-mta-project-clip',id);
  event.dataTransfer.setData('text/plain',id);
  event.currentTarget.classList.add('dragging');
  $('#timelinePane')?.classList.add('clip-drop-ready');
}
function endProjectClipDrag(){
  draggedLibraryClipId=null;
  $$('.project-clip-card').forEach(x=>x.classList.remove('dragging'));
  $('#timelinePane')?.classList.remove('clip-drop-ready','clip-drop-active');
}
function timelineMsFromClientX(clientX){
  const pane=$('#timelinePane');if(!pane)return playCursorMs;
  const r=pane.getBoundingClientRect();
  return Math.max(0,Math.round((clientX-r.left+pane.scrollLeft)/pxPerSec*1000));
}
async function instantiateProjectClip(id,timelineStartMs=0){
  if(!current||!id)return;
  try{
    await flushAutosave();
    const result=await api(`/api/projects/${current.id}/clip-library/${encodeURIComponent(id)}/instantiate`,{
      method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({timeline_start_ms:Math.max(0,Math.round(Number(timelineStartMs)||0))})
    });
    current=result.project;selectedTrackId=result.track.id;render();await refresh();
    toast(`Clip aggiunta come nuova traccia a ${fmtTime((Number(timelineStartMs)||0)/1000,true)}`);
  }catch(e){toast('Impossibile aggiungere la clip: '+e.message)}
}
function bindProjectClipDrop(){
  const pane=$('#timelinePane');if(!pane)return;
  pane.addEventListener('dragover',event=>{
    const id=draggedLibraryClipId||event.dataTransfer?.getData('application/x-mta-project-clip');
    if(!id)return;event.preventDefault();event.dataTransfer.dropEffect='copy';pane.classList.add('clip-drop-active');
  });
  pane.addEventListener('dragleave',event=>{if(!pane.contains(event.relatedTarget))pane.classList.remove('clip-drop-active')});
  pane.addEventListener('drop',event=>{
    const id=draggedLibraryClipId||event.dataTransfer?.getData('application/x-mta-project-clip')||event.dataTransfer?.getData('text/plain');
    if(!id)return;event.preventDefault();const ms=timelineMsFromClientX(event.clientX);endProjectClipDrag();instantiateProjectClip(id,ms);
  });
}
function beginProjectClipPointer(event,id){
  if(event.pointerType==='mouse')return;
  event.preventDefault();
  const handle=event.currentTarget;handle.setPointerCapture?.(event.pointerId);
  clipPointerDrag={id,pointerId:event.pointerId,startX:event.clientX,startY:event.clientY,x:event.clientX,y:event.clientY,active:false,handle,ghost:null};
  const move=e=>{
    if(!clipPointerDrag||e.pointerId!==clipPointerDrag.pointerId)return;
    clipPointerDrag.x=e.clientX;clipPointerDrag.y=e.clientY;
    if(!clipPointerDrag.active&&Math.hypot(e.clientX-clipPointerDrag.startX,e.clientY-clipPointerDrag.startY)>8){
      clipPointerDrag.active=true;
      const asset=(current?.clip_library||[]).find(x=>x.id===id);
      const ghost=document.createElement('div');ghost.className='clip-touch-ghost';ghost.textContent=asset?.name||'Clip';document.body.appendChild(ghost);clipPointerDrag.ghost=ghost;
      $('#timelinePane')?.classList.add('clip-drop-ready');
    }
    if(clipPointerDrag.active&&clipPointerDrag.ghost){clipPointerDrag.ghost.style.left=(e.clientX+12)+'px';clipPointerDrag.ghost.style.top=(e.clientY+12)+'px';const pane=$('#timelinePane');pane?.classList.toggle('clip-drop-active',!!document.elementFromPoint(e.clientX,e.clientY)?.closest?.('#timelinePane'))}
  };
  const end=e=>{
    if(!clipPointerDrag||e.pointerId!==clipPointerDrag.pointerId)return;
    const state=clipPointerDrag;clipPointerDrag=null;state.ghost?.remove();
    const over=document.elementFromPoint(e.clientX,e.clientY)?.closest?.('#timelinePane');
    $('#timelinePane')?.classList.remove('clip-drop-ready','clip-drop-active');
    window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',end);window.removeEventListener('pointercancel',cancel);
    if(state.active&&over)instantiateProjectClip(state.id,timelineMsFromClientX(e.clientX));
  };
  const cancel=e=>{if(!clipPointerDrag||e.pointerId!==clipPointerDrag.pointerId)return;clipPointerDrag.ghost?.remove();clipPointerDrag=null;$('#timelinePane')?.classList.remove('clip-drop-ready','clip-drop-active');window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',end);window.removeEventListener('pointercancel',cancel)};
  window.addEventListener('pointermove',move,{passive:false});window.addEventListener('pointerup',end);window.addEventListener('pointercancel',cancel);
}

function setTrackColor(id,value){
  const t=trackById(id);if(!t||!/^#[0-9A-Fa-f]{6}$/.test(String(value||'')))return;
  t.color=value;render();markDirty(100);
}
let draggingTrackId=null;
function beginTrackDrag(event,id){draggingTrackId=id;event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',id);event.currentTarget.closest('.track-head')?.classList.add('dragging')}
function endTrackDrag(){draggingTrackId=null;$$('.track-head').forEach(x=>x.classList.remove('dragging','drag-target'))}
function trackDragOver(event,id){if(!draggingTrackId||draggingTrackId===id)return;event.preventDefault();event.dataTransfer.dropEffect='move';$$('.track-head').forEach(x=>x.classList.toggle('drag-target',x.id===`head-${id}`))}
function dropTrack(event,targetId){
  event.preventDefault();const sourceId=draggingTrackId||event.dataTransfer.getData('text/plain');endTrackDrag();if(!current||!sourceId||sourceId===targetId)return;
  const from=current.tracks.findIndex(t=>t.id===sourceId),to=current.tracks.findIndex(t=>t.id===targetId);if(from<0||to<0)return;
  const [moved]=current.tracks.splice(from,1);current.tracks.splice(to,0,moved);render();markDirty(100);toast('Ordine tracce aggiornato');
}
const NOTE_PC={C:0,'C#':1,Db:1,D:2,'D#':3,Eb:3,E:4,F:5,'F#':6,Gb:6,G:7,'G#':8,Ab:8,A:9,'A#':10,Bb:10,B:11};
const SHARP_NOTES=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'],FLAT_NOTES=['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'];
function transposeNoteName(note,shift){const pc=NOTE_PC[note];if(pc===undefined)return note;const names=note.includes('b')?FLAT_NOTES:SHARP_NOTES;return names[(pc+Math.round(Number(shift||0))+120)%12]}
function transposeChordLabel(label,shift){const n=Math.round(Number(shift||0));if(!n)return label;const m=String(label||'').match(/^([A-G](?:#|b)?)(.*)$/);if(!m)return label;let suffix=m[2].replace(/\/([A-G](?:#|b)?)/g,(_,x)=>'/'+transposeNoteName(x,n));return transposeNoteName(m[1],n)+suffix}
function effectiveProjectKey(){const key=String(current?.key||'');const m=key.match(/^\s*([A-G](?:#|b)?)(.*)$/);return m?transposeNoteName(m[1],current?.pitch_semitones||0)+m[2]:key}

function trackHead(t,i){
  const color=t.color||TRACK_COLORS[i%TRACK_COLORS.length],anySolo=current.tracks.some(x=>x.solo),inaudible=t.mute||(anySolo&&!t.solo);
  const audioMode=t.channels===2?'STEREO':(t.channels===1?'MONO':(t.channel_layout?String(t.channel_layout).toUpperCase():''));
  return `<div class="track-head ${t.id===selectedTrackId?'selected':''} ${inaudible?'audibly-muted':''}" id="head-${t.id}" data-track-context-id="${t.id}" style="--track-color:${color}" onclick="selectTrack('${t.id}')" oncontextmenu="openTrackContextMenu(event,'${t.id}')" ondragover="trackDragOver(event,'${t.id}')" ondrop="dropTrack(event,'${t.id}')">
    <div class="track-color"></div>
    <div class="track-num">${i+1}</div>
    <div class="track-info">
      <div class="track-title-row">
        <input class="track-name model-input" data-i="${i}" data-k="name" value="${esc(t.name)}" title="Rinomina traccia" onchange="renameTrackInline('${t.id}',this.value)">
        <span class="track-type">${esc(t.type)}${audioMode?` · ${esc(audioMode)}`:''}</span>
      </div>
      <div class="track-buttons">
        <span class="track-drag-handle" draggable="true" title="Trascina per riordinare" ondragstart="event.stopPropagation();beginTrackDrag(event,'${t.id}')" ondragend="endTrackDrag()" onclick="event.stopPropagation()">⋮⋮</span>
        <input class="track-color-picker" type="color" value="${color}" title="Colore traccia" onclick="event.stopPropagation()" onchange="event.stopPropagation();setTrackColor('${t.id}',this.value)">
        <button class="tiny-btn" title="Rinomina traccia" onclick="event.stopPropagation();renameTrack('${t.id}')">✎</button>
        <button data-mute-track="${t.id}" class="tiny-btn mute ${t.mute?'on':''}" onclick="event.stopPropagation();toggleBool(this,'${t.id}','mute')">M</button>
        <button data-solo-track="${t.id}" class="tiny-btn solo ${t.solo?'on':''}" onclick="event.stopPropagation();toggleBool(this,'${t.id}','solo')">S</button>
        <button class="tiny-btn preview" onclick="event.stopPropagation();previewTrack('${t.id}')">▶</button>
        <button class="tiny-btn track-more-menu" type="button" title="Menu traccia" aria-label="Apri menu contestuale di ${esc(t.name)}" onclick="event.stopPropagation();openTrackContextMenu(event,'${t.id}')">⋯</button>
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
function openTrackContextMenuAt(id,clientX,clientY){
  closeTrackContextMenu();
  const track=trackById(id);if(!track)return;
  selectedTrackId=id;
  $$('.track-head').forEach(el=>el.classList.toggle('selected',el.id===`head-${id}`));
  const stem=pluginInfo.stem_splitter||{};
  const disabled=stem.available?'':'disabled';
  const menu=document.createElement('div');
  menu.id='trackContextMenu';
  menu.className='track-context-menu';
  menu.setAttribute('role','menu');
  menu.innerHTML=`
    <button type="button" onclick="closeTrackContextMenu();renameTrack('${id}')">✎ <span>Rinomina</span></button>
    <button type="button" ${disabled} onclick="closeTrackContextMenu();openTrackStemWorkflow('${id}')">▥ <span>Separa</span></button>
    <button type="button" onclick="closeTrackContextMenu();openSampleEditor('${id}')">⌁ <span>Editor waveform / campioni</span></button>
    <button type="button" onclick="closeTrackContextMenu();openTextAnalysisChooser('${id}','lyrics')">≡ <span>Estrai lyrics</span></button>
    <button type="button" onclick="closeTrackContextMenu();openTextAnalysisChooser('${id}','chords')">♬ <span>Estrai chords</span></button>
    <button type="button" class="danger" onclick="closeTrackContextMenu();deleteTracksByIds(['${id}'])">× <span>Rimuovi</span></button>
  `;
  document.body.appendChild(menu);
  const pad=8,r=menu.getBoundingClientRect();
  const x=Number.isFinite(Number(clientX))?Number(clientX):window.innerWidth/2;
  const y=Number.isFinite(Number(clientY))?Number(clientY):window.innerHeight/2;
  menu.style.left=`${Math.max(pad,Math.min(x,window.innerWidth-r.width-pad))}px`;
  menu.style.top=`${Math.max(pad,Math.min(y,window.innerHeight-r.height-pad))}px`;
}
function openTrackContextMenu(event,id){
  event?.preventDefault?.();event?.stopPropagation?.();
  let x=event?.clientX,y=event?.clientY;
  if((!x&&!y)&&event?.currentTarget?.getBoundingClientRect){const b=event.currentTarget.getBoundingClientRect();x=b.right;y=b.bottom}
  openTrackContextMenuAt(id,x,y);
}

const TRACK_CONTEXT_LONG_PRESS_MS=600,TRACK_CONTEXT_MOVE_PX=12;
let trackContextPress=null,trackContextSuppressClickUntil=0;
function cancelTrackContextLongPress(){
  if(trackContextPress?.timer)clearTimeout(trackContextPress.timer);
  trackContextPress=null;
}
function trackContextPointerDown(event){
  if(event.pointerType!=='touch'&&event.pointerType!=='pen')return;
  const target=event.target.closest?.('[data-track-context-id]');
  if(!target||event.target.closest?.('button,input,select,textarea,a,[draggable="true"]'))return;
  cancelTrackContextLongPress();
  const state={pointerId:event.pointerId,id:target.dataset.trackContextId,x:event.clientX,y:event.clientY,target,timer:null};
  state.timer=setTimeout(()=>{
    if(trackContextPress!==state)return;
    trackContextSuppressClickUntil=Date.now()+800;
    if(navigator.vibrate)navigator.vibrate(12);
    openTrackContextMenuAt(state.id,state.x,state.y);
    trackContextPress=null;
  },TRACK_CONTEXT_LONG_PRESS_MS);
  trackContextPress=state;
}
function trackContextPointerMove(event){
  const state=trackContextPress;if(!state||state.pointerId!==event.pointerId)return;
  if(Math.hypot(event.clientX-state.x,event.clientY-state.y)>TRACK_CONTEXT_MOVE_PX)cancelTrackContextLongPress();
}
function trackContextPointerEnd(event){
  if(trackContextPress?.pointerId===event.pointerId)cancelTrackContextLongPress();
}
document.addEventListener('pointerdown',trackContextPointerDown,{passive:true});
document.addEventListener('pointermove',trackContextPointerMove,{passive:true});
document.addEventListener('pointerup',trackContextPointerEnd,{passive:true});
document.addEventListener('pointercancel',trackContextPointerEnd,{passive:true});
document.addEventListener('click',event=>{
  if(Date.now()<trackContextSuppressClickUntil&&event.target.closest?.('[data-track-context-id]')){event.preventDefault();event.stopPropagation()}
},true);
function textModelCatalog(){return pluginInfo.text_models||{lyrics:{models:[]},chords:{engines:[],models:[]}}}
function openTextAnalysisChooser(id,kind){
  const cat=textModelCatalog(),track=trackById(id);if(!track)return toast('Traccia non trovata');
  if(kind==='lyrics'){const c=cat.lyrics||{},opts=(c.models||[]).map(m=>`<option value="${esc(m.id)}" ${m.id===c.default_model?'selected':''}>${esc(m.display_name)} · ${m.installed?'installato':(c.storage==='local'?'download locale':'download server')}</option>`).join('');showUtilityModal('Estrai lyrics',`<div class="form-grid"><p><b>Motore:</b> OpenAI Whisper</p><label>Modello<select id="textAnalysisChoice">${opts}</select></label><p class="hint">Il modello viene scaricato on-demand (download modello al primo uso) e conservato ${c.storage==='local'?'localmente nell’app nativa':'sul server'}.</p><div class="form-actions"><button class="utility-btn secondary model-download-btn" type="button" onclick="downloadTextAnalysisSelection('lyrics')">Scarica modello</button><button class="utility-btn primary accent" type="button" onclick="startTrackTextAnalysis('${esc(id)}','lyrics',$('#textAnalysisChoice').value);closeUtilityModal()">Estrai lyrics</button></div></div>`);return}
  const c=cat.chords||{},models=Object.fromEntries((c.models||[]).map(x=>[x.id,x])),opts=(c.engines||[]).map(e=>{const m=models[e.model_id]||{};let state;if(e.model_id)state=m.installed?'modello installato':(c.storage==='local'?'modello scaricabile localmente':'modello scaricabile sul server');else if(e.id==='chordino')state=e.available?'nessun modello AI · motore locale disponibile':'nessun modello AI · richiede Sonic Annotator + Chordino';else state='nessun modello AI richiesto';return `<option value="${esc(e.id)}" ${e.id===c.default_engine?'selected':''} ${e.available?'':'disabled'}>${esc(e.display_name)} · ${esc(state)}</option>`}).join('');showUtilityModal('Estrai chords',`<div class="form-grid"><p><b>Motore che verrà usato:</b> <span id="chordEngineLabel"></span></p><label>Motore / modello<select id="textAnalysisChoice" onchange="updateChordEngineDisclosure()">${opts}</select></label><div id="chordEngineDisclosure" class="workflow-note"></div><div class="form-actions"><button class="utility-btn secondary model-download-btn" type="button" onclick="downloadTextAnalysisSelection('chords')">Scarica modello selezionato</button><button class="utility-btn primary accent" type="button" onclick="startTrackTextAnalysis('${esc(id)}','chords',$('#textAnalysisChoice').value);closeUtilityModal()">Estrai chords</button></div></div>`);updateChordEngineDisclosure()}
function updateChordEngineDisclosure(){const c=textModelCatalog().chords||{},id=$('#textAnalysisChoice')?.value,e=(c.engines||[]).find(x=>x.id===id),m=(c.models||[]).find(x=>x.id===e?.model_id);if($('#chordEngineLabel'))$('#chordEngineLabel').textContent=e?.display_name||id||'—';if($('#chordEngineDisclosure'))$('#chordEngineDisclosure').innerHTML=e?.model_id?`Modello: <b>${esc(m?.display_name||e.model_id)}</b> · ${m?.installed?'installato':'sarà scaricato al primo uso'}${m?.license?`<br>Licenza pesi: ${esc(m.license)}`:''}`:'Questo motore non richiede un modello AI scaricabile.'}
async function downloadTextAnalysisSelection(kind){const cat=textModelCatalog(),choice=$('#textAnalysisChoice')?.value;try{if(kind==='lyrics'){toast('Download modello lyrics…');await api(`/api/ai-models/lyrics/${encodeURIComponent(choice)}/download`,{method:'POST'})}else{const e=(cat.chords?.engines||[]).find(x=>x.id===choice);if(!e?.model_id)return toast('Il motore selezionato non richiede un modello');toast('Download modello chords…');await api(`/api/ai-models/chords/${encodeURIComponent(e.model_id)}/download`,{method:'POST'})}pluginInfo=await api('/api/plugins');toast(currentUser?.native_single_user?'Modello scaricato localmente':'Modello scaricato sul server');if(kind==='chords')updateChordEngineDisclosure()}catch(e){toast(e.message)}}
async function startTrackTextAnalysis(id,kind,choice=''){
  if(!current)return;
  const track=trackById(id);if(!track)return toast('Traccia non trovata');
  const label=kind==='lyrics'?'Lyrics':'Chords';
  await flushAutosave();
  try{
    const param=kind==='lyrics'?'model':'engine';
    const suffix=choice?`?${param}=${encodeURIComponent(choice)}`:'';
    const job=await api(`/api/projects/${current.id}/tracks/${id}/extract-${kind}-jobs${suffix}`,{method:'POST'});
    showMediaProgress(`Estrazione ${label}`,job.progress,job.message);
    pollMediaJob(job.id,`Estrazione ${label}`,async()=>{
      current=await api(`/api/projects/${current.id}`);
      mixerMetaTab=kind;current.mixer_meta_tab=kind;
      render();toast(`${label} estratti e sincronizzati nel progetto`);
    });
  }catch(e){toast(e.message)}
}

function openTrackStemWorkflow(id){
  const track=trackById(id);if(!track)return toast('Traccia non trovata');
  const stem=pluginInfo.stem_splitter||{};if(!stem.available)return toast('Demucs non è disponibile in questo runtime');
  const profiles=stem.model_profiles||[],profileMap=Object.fromEntries(profiles.map(p=>[p.model,p]));
  const recommended=stem.recommended_model||(stem.models||['htdemucs_6s'])[0];
  const models=(stem.models||['htdemucs_6s']).map(x=>{const p=profileMap[x]||{};return `<option value="${esc(x)}" ${x===recommended?'selected':''}>${esc(p.display_name||x)}${p.stem_count?' · '+p.stem_count+' stem':''}</option>`}).join('');
  const counts=[...new Set((stem.supported_stem_counts||[2,4,6]).map(Number).filter(n=>n>=2&&n<=64))].sort((a,b)=>a-b);
  const recommendedCount=Number(profileMap[recommended]?.stem_count)||counts[0]||4;
  const countOptions=counts.map(n=>{const p=profiles.find(x=>Number(x.stem_count)===n),labels=p?.stem_labels||[];const detail=labels.length&&labels.length<=8?' · '+labels.join(' / '):(p?.display_name?' · '+p.display_name:'');return `<option value="${n}" ${n===recommendedCount?'selected':''}>${n} stem${esc(detail)}</option>`}).join('');
  const leadBacking=stem.lead_backing||{},backingModels=(leadBacking.models||[]).map(m=>`<option value="${esc(m.id)}" ${m.id===leadBacking.default_model?'selected':''}>${esc(m.display_name)} · ${m.installed?'installato':(leadBacking.storage==='local'?'download locale':'download server')}</option>`).join('');
  showUtilityModal('Separa traccia',`<div class="stem-workflow"><p class="hint">Sorgente: <b>${esc(track.name)}</b>. La separazione partirà solo dopo la conferma dei parametri.</p><div class="workflow-grid"><label class="workflow-field"><span>Modello AI</span><select id="trackStemModel" onchange="syncTrackStemModelCount('model')">${models}</select></label><label class="workflow-field"><span>Numero stem</span><select id="trackStemCount" onchange="syncTrackStemModelCount('count')">${countOptions}</select></label></div><label class="workflow-check"><input id="trackSplitBackingVocals" type="checkbox" onchange="$('#trackBackingModelRow').classList.toggle('hidden',!this.checked)"> Separa anche voce principale e backing vocals</label><label class="workflow-field hidden" id="trackBackingModelRow"><span>Modello Lead / Backing Vocals</span><select id="trackBackingVocalModel">${backingModels}<option value="ffmpeg-center-side">Fallback DSP center/side</option></select><button type="button" onclick="downloadTrackBackingModel()">Scarica modello</button></label><div id="trackStemDisclosure" class="workflow-note"></div><div class="utility-actions"><button class="utility-btn primary" type="button" onclick="startTrackStemSplit('${esc(id)}')">Avvia separazione</button><button class="utility-btn secondary" type="button" onclick="closeUtilityModal()">Annulla</button></div></div>`);
  syncTrackStemModelCount('model');
}
function syncTrackStemModelCount(source){
  const stem=pluginInfo.stem_splitter||{},profiles=stem.model_profiles||[],modelEl=$('#trackStemModel'),countEl=$('#trackStemCount');if(!modelEl||!countEl)return;
  if(source==='model'){const p=profiles.find(x=>x.model===modelEl.value);if(p?.stem_count)countEl.value=String(p.stem_count)}
  else{const n=Number(countEl.value),p=profiles.find(x=>Number(x.stem_count)===n);if(p)modelEl.value=p.model}
  const p=profiles.find(x=>x.model===modelEl.value),labels=p?.stem_labels||[],el=$('#trackStemDisclosure');if(el)el.textContent=`Parametri selezionati: ${p?.display_name||modelEl.value} · ${countEl.value} stem${labels.length?' · '+labels.join(' / '):''}`;
}
async function downloadTrackBackingModel(){const id=$('#trackBackingVocalModel')?.value;if(!id||id==='ffmpeg-center-side')return toast('Il fallback DSP non richiede modelli');try{await api(`/api/vocal-separation/models/${encodeURIComponent(id)}/download`,{method:'POST'});pluginInfo=await api('/api/plugins');toast(currentUser?.native_single_user?'Modello scaricato localmente':'Modello scaricato sul server')}catch(e){toast(e.message)}}
async function startTrackStemSplit(id){
  if(!current)return;const track=trackById(id);if(!track)return toast('Traccia non trovata');const stem=pluginInfo.stem_splitter||{};if(!stem.available)return toast('Demucs non è disponibile in questo runtime');
  const model=$('#trackStemModel')?.value,stemCount=Number($('#trackStemCount')?.value||0),splitBackingVocals=!!$('#trackSplitBackingVocals')?.checked,backingVocalModel=$('#trackBackingVocalModel')?.value||'uvr_mdxnet_kara_2';
  if(!model||!stemCount)return toast('Seleziona modello AI e numero di stem prima di procedere');
  await flushAutosave();
  try{const q=new URLSearchParams({model,stem_count:String(stemCount),split_backing_vocals:String(splitBackingVocals),backing_vocal_model:backingVocalModel});const job=await api(`/api/projects/${current.id}/tracks/${id}/stem-jobs?${q}`,{method:'POST'});closeUtilityModal();activeStemJob=job.id;activeStemProjectId=job.project_id;showStemProgress(job);pollStemJob(job.id)}catch(e){toast(e.message)}
}
function renameTrackInline(id,value){const t=trackById(id);if(!t)return;const v=String(value||'').trim();if(!v)return;t.name=v.slice(0,200);markDirty()}
function renameTrack(id){const t=trackById(id);if(!t)return;const value=prompt('Nome traccia',t.name);if(value===null)return;const v=value.trim();if(!v)return toast('Il nome non può essere vuoto');t.name=v.slice(0,200);render();markDirty(100)}

function projectFormatLabel(target=current?.target){return target==='DAW'?'Multitrack DAW':target}
function mtaSlotLimit(target=current?.target){return target==='MTA8'?8:16}
function setTrackMtaSlot(id,value){const t=trackById(id);if(!t)return;const n=Number(value||0),limit=mtaSlotLimit();t.mta_slot=n>=1&&n<=limit?n:null;markDirty(100);render()}
function lane(t,W,i){const color=t.color||TRACK_COLORS[i%TRACK_COLORS.length];const anySolo=current.tracks.some(x=>x.solo);const inaudible=t.mute||(anySolo&&!t.solo);return `<div class="lane ${inaudible?'audibly-muted':''}" id="lane-${t.id}" data-track="${t.id}" data-track-context-id="${t.id}" style="width:${W}px;--track-color:${color}" oncontextmenu="openTrackContextMenu(event,'${t.id}')"><canvas class="wave" id="wave-${t.id}" width="${W}" height="78" ondblclick="event.stopPropagation();openSampleEditor('${t.id}')" title="Doppio click: editor waveform/campioni"></canvas><div class="waveform-progress ${t.waveform_peaks?.length?'hidden':''}" id="wave-progress-${t.id}"><div class="waveform-progress-bar" id="wave-progress-bar-${t.id}" style="width:2%"></div><span id="wave-progress-label-${t.id}">Waveform…</span></div>${(t.clips||[]).map((c,j)=>{const l=c.timeline_start_ms/1000*pxPerSec,w=(c.source_end_ms-c.source_start_ms)/1000*pxPerSec;return `<div class="clip-block" style="left:${l}px;width:${Math.max(2,w)}px"><span class="clip-label">${esc(t.name)}_${String(j+1).padStart(2,'0')}</span></div>`}).join('')}</div>`}

function inspectorHtml(){const t=selectedTrack();if(!t)return `<aside class="inspector"><div class="inspector-tabs"><button class="inspector-tab active">Inspector</button><button class="inspector-tab">Stems</button><button class="inspector-tab">Metadata</button></div><div class="inspector-body"><p class="hint">Import a track to open the inspector.</p></div></aside>`;const i=current.tracks.indexOf(t);return `<aside class="inspector" id="inspector"><div class="inspector-tabs"><button class="inspector-tab active">Inspector</button><button class="inspector-tab">Stems</button><button class="inspector-tab">Metadata</button></div><div class="inspector-body"><div class="inspector-track-title"><span>◉</span>${esc(t.name)}<label class="tool" style="margin-left:auto;min-width:auto;height:28px">Replace<input type="file" accept="audio/*,.mp3,.wav" hidden onchange="replaceTrack('${t.id}',this)"></label></div><div class="inspector-row"><label>Volume</label><input class="track-volume-range" data-volume-track="${t.id}" type="range" min="-60" max="12" step="0.5" value="${t.volume_db}" oninput="setTrackVolume('${t.id}',this.value)"><input class="valuebox volume-number" id="ins-db-${t.id}" data-volume-number="${t.id}" type="number" min="-60" max="12" step="0.1" value="${Number(t.volume_db).toFixed(1)}" oninput="setTrackVolume('${t.id}',this.value)" aria-label="Volume ${esc(t.name)} in dB" title="Volume in dB"></div><div class="inspector-row"><label>Pan</label><input type="range" min="-1" max="1" step="0.01" value="${t.pan||0}" oninput="setTrackPan('${t.id}',this.value)"><div class="valuebox" id="pan-${t.id}">${Number(t.pan||0).toFixed(2)}</div></div><div class="inspector-row"><label>Type</label><select class="model-input" data-i="${i}" data-k="type">${['drums','bass','guitars','keyboards','orchestra','winds','melody','click','choirs','other'].map(x=>`<option ${x===t.type?'selected':''}>${x}</option>`).join('')}</select><div class="valuebox">${t.duration_ms?fmtTime(t.duration_ms/1000):'--'}</div></div><div class="inspector-row"><label>MTA Slot</label><select onchange="setTrackMtaSlot('${t.id}',this.value)"><option value="" ${!t.mta_slot?'selected':''}>Auto</option>${Array.from({length:mtaSlotLimit()},(_,n)=>`<option value="${n+1}" ${Number(t.mta_slot)===n+1?'selected':''}>${n+1}</option>`).join('')}</select><div class="valuebox">${t.mta_slot?`Slot ${t.mta_slot}`:'Auto'}</div></div>${insertPanelHtml(t,false)}<div class="panel-section"><div class="section-title">Track export</div><div class="track-export-actions"><button onclick="exportTrack('${t.id}','wav')">WAV</button><button onclick="exportTrack('${t.id}','mp3')">MP3</button><button onclick="exportTrack('${t.id}','flac')">FLAC</button></div></div><div class="panel-section"><div class="collapsed-row">› Send</div><div class="collapsed-row">› Track Automation</div><div class="collapsed-row">› Advanced</div></div></div></aside>`}

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
  markDirty(100);queueLiveFxRefresh(isMaster,trackId);
  if(!isMaster)queueInsertWaveformRefresh(trackId||selectedTrack()?.id||'');
  if(trackId||isMaster)openMixerInsertManager(trackId||'master');else render();
}
function removeInsert(isMaster,id,trackId=''){
  const arr=insertArray(isMaster,trackId);if(!arr)return;
  const idx=arr.findIndex(x=>x.id===id);if(idx<0)return;
  arr.splice(idx,1);markDirty(100);queueLiveFxRefresh(isMaster,trackId);
  if(!isMaster)queueInsertWaveformRefresh(trackId||selectedTrack()?.id||'');
  if(trackId||isMaster)openMixerInsertManager(trackId||'master');else render();
}
function toggleInsert(isMaster,id,trackId=''){
  const x=insertArray(isMaster,trackId)?.find(p=>p.id===id);if(!x)return;
  x.enabled=!x.enabled;markDirty(100);queueLiveFxRefresh(isMaster,trackId);
  if(!isMaster)queueInsertWaveformRefresh(trackId||selectedTrack()?.id||'');
  if(trackId||isMaster)openMixerInsertManager(trackId||'master');else render();
}
function presetParamsFor(plugin,preset){
  if(String(preset||'').startsWith('user:'))return structuredClone(pluginInfo.custom?.[plugin]?.[String(preset).slice(5)]||{});
  return structuredClone(pluginInfo.factory_params?.[plugin]?.[preset]||defaultPluginParams(plugin));
}
function changeInsertPreset(isMaster,id,preset,trackId=''){
  const x=insertArray(isMaster,trackId)?.find(p=>p.id===id);if(!x)return;
  x.preset=preset;x.params=presetParamsFor(x.plugin,preset);markDirty(100);queueLiveFxRefresh(isMaster,trackId);
  if(!isMaster)queueInsertWaveformRefresh(trackId||selectedTrack()?.id||'');
}
function editorPresetChanged(isMaster,id,preset,trackId=''){
  changeInsertPreset(isMaster,id,preset,trackId);
  setTimeout(()=>openInsertEditor(isMaster,id,trackId),30);
}
function defaultPluginParams(kind){const schema=pluginInfo.schemas?.[kind]||{};return Object.fromEntries(Object.entries(schema).map(([k,v])=>[k,Number(v.default??0)]))}
function graphicEqEditorFields(schema,params,isMaster,id,trackId){
  return `<div class="geq-editor">
    <div class="geq-scale"><span>+12</span><span>0</span><span>-12</span></div>
    <div class="geq-bands">${Object.entries(schema).map(([k,v])=>{
      const freq=k.slice(1),value=Number(params[k]??v.default);
      return `<label class="geq-band" title="${freq} Hz · ${value.toFixed(1)} dB">
        <span class="geq-value" id="geq-val-${k}">${value.toFixed(1)}</span>
        <input class="plugin-param geq-slider" data-key="${k}" type="range" min="${v.min}" max="${v.max}" step="${v.step}" value="${value}" oninput="$('#geq-val-${k}').textContent=Number(this.value).toFixed(1)" onchange="commitPluginEditorParams(${isMaster},'${id}','${trackId}')">
        <span class="geq-freq">${Number(freq)>=1000?(Number(freq)/1000).toFixed(Number(freq)%1000?1:0)+'k':freq}</span>
      </label>`;
    }).join('')}</div>
  </div>`;
}
function commitPluginEditorParams(isMaster,id,trackId=''){
  const x=insertArray(isMaster,trackId)?.find(p=>p.id===id);if(!x)return;
  const params={};$$('.plugin-param').forEach(el=>params[el.dataset.key]=Number(el.value));
  x.preset='custom';x.params=params;markDirty(80);queueLiveFxRefresh(isMaster,trackId);
  if(!isMaster)queueInsertWaveformRefresh(trackId||selectedTrack()?.id||'');
}
function pluginNumberKey(event,isMaster,id,trackId=''){if(event.key==='Enter'){event.preventDefault();event.currentTarget.blur();commitPluginEditorParams(isMaster,id,trackId)}}
function syncPluginControl(key,value,source){
  const number=$(`#plugin-param-${CSS.escape(key)}`),knob=document.querySelector(`[data-knob-key="${CSS.escape(key)}"]`);
  if(source!=='number'&&number)number.value=value;
  if(source!=='knob'&&knob)knob.value=value;
  const target=knob?.closest('.plugin-knob-shell');if(target){const min=Number(knob.min),max=Number(knob.max),v=Number(value),pct=max>min?(v-min)/(max-min):0;target.style.setProperty('--knob-turn',`${-135+pct*270}deg`)}
}
function openInsertEditor(isMaster,id,trackId=''){
  const x=insertArray(isMaster,trackId)?.find(p=>p.id===id);if(!x)return;
  const schema=pluginInfo.schemas?.[x.plugin]||{},custom=x.preset.startsWith('user:')?pluginInfo.custom?.[x.plugin]?.[x.preset.slice(5)]:null;
  const presets=pluginInfo.inserts?.[x.plugin]||['default'];
  const params=Object.keys(x.params||{}).length?x.params:(custom||presetParamsFor(x.plugin,x.preset));
  const fields=x.plugin==='graphic_eq_32'
    ?graphicEqEditorFields(schema,params,isMaster,id,trackId)
    :Object.entries(schema).map(([k,v])=>{const value=Number(params[k]??v.default);return `<label class="plugin-field plugin-field-knob"><span>${esc(k.replaceAll('_',' '))}</span><div class="plugin-control-pair"><div class="plugin-knob-shell" style="--knob-turn:${-135+((value-Number(v.min))/(Number(v.max)-Number(v.min)||1))*270}deg" title="${esc(k.replaceAll('_',' '))}"><input class="plugin-knob" data-knob-key="${k}" type="range" min="${v.min}" max="${v.max}" step="${v.step}" value="${value}" oninput="syncPluginControl('${k}',this.value,'knob')" onchange="commitPluginEditorParams(${isMaster},'${id}','${trackId}')"></div><input class="plugin-param plugin-number" id="plugin-param-${k}" data-key="${k}" type="number" min="${v.min}" max="${v.max}" step="${v.step}" value="${value}" oninput="syncPluginControl('${k}',this.value,'number')" onblur="commitPluginEditorParams(${isMaster},'${id}','${trackId}')" onkeydown="pluginNumberKey(event,${isMaster},'${id}','${trackId}')"></div><small>${v.min} … ${v.max}</small></label>`}).join('');
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
  closeExportMapping();markDirty(100);queueLiveFxRefresh(isMaster,trackId);
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
  const limit=current.target==='DAW'?null:mtaSlotLimit(),over=limit!==null&&current.tracks.length>limit;
  const metaPane=current.metadata_panel_visible?metaPaneHtml():'';
  return `<div class="mixer-pane" id="mixer">
    <div class="dock-tabs"><button class="dock-tab active">Mixer</button><button class="dock-tab">Master / Preview</button><button id="realtimeBtn" class="dock-tab realtime-toggle ${current.realtime_meter_enabled?'active':''}" onclick="toggleRealtimeMeters()">RealTime</button>
      <button class="dock-tab" onclick="toggleMuteAll()">${current.tracks.length&&current.tracks.every(t=>t.mute)?'Unmute all':'Mute all'}</button><button class="dock-tab" onclick="toggleSoloAll()">${current.tracks.length&&current.tracks.every(t=>t.solo)?'Unsolo all':'Solo all'}</button><button class="dock-tab" onclick="toggleAllPlugins()">${[...(current.master_inserts||[]),...current.tracks.flatMap(t=>t.inserts||[])].some(x=>x.enabled)?'Bypass all FX':'Enable all FX'}</button>
      <div class="automix-control"><label class="switch"><input type="checkbox" ${current.auto_mix_enabled?'checked':''} onchange="setAutoMix(this.checked)"><span></span></label><b>Auto Mix</b><select id="autoMixStyle" onchange="changeAutoMixStyle(this.value)"><option value="balanced" ${current.auto_mix_style==='balanced'?'selected':''}>Balanced</option><option value="studio" ${current.auto_mix_style==='studio'?'selected':''}>Studio</option><option value="live" ${current.auto_mix_style==='live'?'selected':''}>Live</option><option value="gentle" ${current.auto_mix_style==='gentle'?'selected':''}>Gentle</option></select><button onclick="showAutoMixInfo()">?</button></div>
      <span class="capacity-badge ${over?'over':''}">${current.target==='DAW'?`${current.tracks.length} project tracks · unrestricted DAW project`:`${current.tracks.length} project tracks · ${limit} ${current.target} output slots`}</span>
    </div>
    <div class="channels">${current.tracks.map((t,i)=>channelHtml(t,i)).join('')}<div class="master-divider" aria-hidden="true"></div>${masterChannelHtml()}</div>
  </div>${metaPane}<div id="exportMapModal" class="modal-card export-map-modal hidden"></div>`;
}
function exportWindowHtml(){
  const limit=current.target==='DAW'?null:mtaSlotLimit(),over=limit!==null&&current.tracks.length>limit;
  return `<div class="export-dialog"><div class="export-title">Final output</div>${over?`<div class="export-warning">Project has more tracks than ${current.target}. MTA export will ask how to merge tracks into ${limit} output slots.</div>`:''}<div class="export-format-grid"><button class="format-option" onclick="doExport('mta')"><span>▧ MTA (${current.target==='DAW'?'MTA8 / MTA16':current.target})</span><span>Configura ›</span></button><button class="format-option" onclick="doExport('wav')"><span>♫ WAV</span><span>24 bit / PCM ›</span></button><button class="format-option" onclick="doExport('mp3')"><span>♫ MP3</span><span>Configura bitrate ›</span></button><button class="format-option" onclick="doExport('flac')"><span>♫ FLAC</span><span>Lossless ›</span></button><button class="format-option ${current.lyrics?.length?'':'disabled'}" ${current.lyrics?.length?'onclick="openKaraokeExport()"':'disabled'}><span>▣ MP4 Karaoke</span><span>${current.lyrics?.length?'Configura ›':'Lyrics richieste'}</span></button></div><div class="export-dialog-tools"><button class="utility-btn secondary" onclick="previewMaster()">▶ Render &amp; Preview Master</button><button class="utility-btn secondary" onclick="showMtaAnalysis()">⌁ MTA format analysis</button></div><div class="utility-actions"><button class="utility-btn secondary" onclick="closeUtilityModal()">Annulla</button></div></div>`;
}
function metaPaneHtml(){
  const config={lyrics:['text','Lyrics'],chords:['chord','Chords'],markers:['label','Markers']},[key,label]=config[mixerMetaTab]||config.lyrics,rows=current[mixerMetaTab]||[];const displayValue=x=>mixerMetaTab==='chords'?transposeChordLabel(x[key],current.pitch_semitones||0):x[key];
  const resetButton=mixerMetaTab==='lyrics'?`<button class="tool danger" onclick="resetTimedData('lyrics')">Reset lyrics</button>`:mixerMetaTab==='chords'?`<button class="tool danger" onclick="resetTimedData('chords')">Reset chords</button>`:'';
  const hasLyrics=!!(current.lyrics||[]).length,hasChords=!!(current.chords||[]).length;
  const lyricsExports=mixerMetaTab==='lyrics'&&hasLyrics?`<button class="tool" onclick="downloadProjectLyrics(false)">TXT Lyrics</button>${hasChords?`<button class="tool" onclick="downloadProjectLyrics(true)">TXT Lyrics + Chords</button><button class="tool" onclick="downloadProjectChordPro()">ChordPro Lyrics + Chords</button>`:''}<label class="tool" title="Colore chords nel PDF">Chord color <input id="lyricsPdfChordColor" type="color" value="#7B1FA2" style="width:28px;height:22px;padding:0;border:0;background:none"></label><button class="tool" onclick="previewProjectLyricsPdf()">Anteprima PDF ${hasChords?'Lyrics + Chords':'Lyrics'}</button><button class="tool" onclick="downloadProjectLyricsPdf()">Scarica PDF ${hasChords?'Lyrics + Chords':'Lyrics'}</button>`:'';
  return `<div class="meta-pane" id="metaPane"><div class="dock-tabs"><button class="dock-tab ${mixerMetaTab==='lyrics'?'active':''}" onclick="showMetaPanel('lyrics')">Lyrics</button><button class="dock-tab ${mixerMetaTab==='chords'?'active':''}" onclick="showMetaPanel('chords')">Chords</button><button class="dock-tab ${mixerMetaTab==='markers'?'active':''}" onclick="showMetaPanel('markers')">Markers</button><button class="dock-close" onclick="toggleMixerPanel('meta')" title="Nascondi Lyrics/Chords/Markers">×</button></div><div class="meta-tabs-content"><div class="meta-list">${rows.map(x=>`<div class="meta-line"><time>${fmtTime(x.time_ms/1000)}</time><span>${esc(displayValue(x))}</span></div>`).join('')||`<div class="hint">No synchronized ${label.toLowerCase()} yet.</div>`}</div><div class="meta-actions"><button class="tool" onclick="editTimed('${mixerMetaTab}')">Edit ${label.toLowerCase()}</button>${resetButton}${lyricsExports}</div><textarea id="lyrics" hidden>${esc(linesToText(current.lyrics,'text'))}</textarea><textarea id="chords" hidden>${esc(linesToText(current.chords,'chord'))}</textarea><textarea id="markers" hidden>${esc(linesToText(current.markers,'label'))}</textarea></div></div>`;
}
function updateMixerDockLayout(){
  const dock=$('#mixerDock');if(!dock||!current)return;
  const meta=!!current.metadata_panel_visible;
  dock.classList.toggle('meta-hidden',!meta);
  dock.classList.toggle('sidepanels-hidden',!meta);
  dock.style.gridTemplateColumns=meta?'minmax(0,1fr) 320px':'minmax(0,1fr)';
  const mixer=$('#mixer');if(mixer)mixer.style.width='100%';
}
function updatePanelMenuButtons(){
  $('#metaPanelMenuBtn')?.classList.toggle('panel-hidden',!current?.metadata_panel_visible);
}
function toggleMixerPanel(which){
  if(!current)return;
  if(which==='export'){openExportPanel();return}
  current.metadata_panel_visible=!current.metadata_panel_visible;
  render();
  requestAnimationFrame(()=>{updateMixerDockLayout();$('#mixer')?.scrollIntoView({block:'nearest'})});
  markDirty(100);focusMixer();
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
  const outChannels=effectiveTrackChannels(t),stereoByFx=Number(t.channels)===1&&outChannels===2;
  return `<div class="channel ${inaudible?'audibly-muted':''}" data-channel-track="${t.id}" style="--track-color:${color}">
    <div class="channel-name">${esc(t.name)}</div>
    <div class="pan-control">
      <div id="pan-knob-${t.id}" class="pan-knob interactive" style="--pan-angle:${angle}deg" title="Pan ${pan.toFixed(2)} · trascina, doppio click = center" onpointerdown="startPanDrag(event,'${t.id}')" ondblclick="resetTrackPan('${t.id}')" role="slider" tabindex="0" aria-valuemin="-1" aria-valuemax="1" aria-valuenow="${pan.toFixed(2)}"></div>
      <input id="pan-input-${t.id}" class="pan-value-input" type="number" min="-1" max="1" step="0.01" value="${pan.toFixed(2)}" onchange="setTrackPan('${t.id}',this.value)" onkeydown="if(event.key==='Enter')this.blur()" aria-label="Pan ${esc(t.name)}">
      <span id="pan-label-${t.id}" class="pan-label">${panLabel(pan)}</span>
    </div>
    <div class="channel-buttons"><button data-mute-track="${t.id}" class="${t.mute?'on':''}" onclick="toggleBool(this,'${t.id}','mute')">M</button><button data-solo-track="${t.id}" class="${t.solo?'on':''}" onclick="toggleBool(this,'${t.id}','solo')">S</button><button class="channel-fx ${t.inserts?.length?'active':''}" onclick="openMixerInsertManager('${t.id}')" title="Gestisci insert">FX${t.inserts?.length?` ${t.inserts.length}`:''}</button></div>
    <div class="channel-mode">${outChannels===1?'MONO':(stereoByFx?'STEREO · FX':'STEREO')}</div>
    <div class="channel-fader-area">
      <div class="fader-column"><input class="v-fader track-volume-range" data-volume-track="${t.id}" type="range" min="-60" max="12" step="0.5" value="${t.volume_db}" oninput="setTrackVolume('${t.id}',this.value)" ondblclick="resetTrackVolumeToUnity('${t.id}',event)" title="Volume · doppio click = 0 dB"></div>
      <div class="db-scale" aria-hidden="true"><span>+12</span><span>+6</span><span>0</span><span>-6</span><span>-12</span><span>-24</span><span>-36</span><span>-48</span><span>-60</span></div>
      <div class="meter-stack"><div id="peak-${t.id}" class="peak-led ${current.realtime_meter_enabled?'':'hidden'}" title="Peak 0 dBFS">PEAK</div><div class="meter-pair">${outChannels===1?`<div class="meter meter-realtime ${current.realtime_meter_enabled?'':'hidden'}" title="VU mono"><span id="vu-${t.id}-M" style="height:0%"></span><em>M</em></div>`:`<div class="meter meter-realtime ${current.realtime_meter_enabled?'':'hidden'}" title="VU Left"><span id="vu-${t.id}-L" style="height:0%"></span><em>L</em></div><div class="meter meter-realtime ${current.realtime_meter_enabled?'':'hidden'}" title="VU Right"><span id="vu-${t.id}-R" style="height:0%"></span><em>R</em></div>`}</div></div>
    </div>
    <input class="channel-value volume-number" id="mix-db-${t.id}" data-volume-number="${t.id}" type="number" min="-60" max="12" step="0.1" value="${Number(t.volume_db).toFixed(1)}" onchange="setTrackVolume('${t.id}',this.value)" onkeydown="if(event.key==='Enter')this.blur()" aria-label="Volume ${esc(t.name)} in dB" title="Volume in dB">
  </div>`;
}
function masterChannelHtml(){
  const v=current.master_volume_db||0,fx=current.master_inserts||[];
  return `<div class="channel master" style="--track-color:#644ce5"><div class="channel-name">MASTER</div><div class="pan-knob"></div><div class="channel-buttons"><button class="channel-fx master-fx ${fx.length?'active':''}" onclick="openMixerInsertManager('master')" title="Gestisci insert Master">FX${fx.length?` ${fx.length}`:''}</button></div><div class="channel-fader-area"><div class="fader-column"><input id="master-volume-range" class="v-fader" type="range" min="-60" max="12" step="0.5" value="${v}" oninput="setMasterVolume(this.value)" ondblclick="resetMasterVolumeToUnity(event)" title="Master volume · doppio click = 0 dB"></div><div class="db-scale" aria-hidden="true"><span>+12</span><span>+6</span><span>0</span><span>-6</span><span>-12</span><span>-24</span><span>-36</span><span>-48</span><span>-60</span></div><div class="meter-stack"><div id="peak-master" class="peak-led ${current.realtime_meter_enabled?'':'hidden'}" title="Master peak 0 dBFS">PEAK</div><div class="meter-pair master-meter-pair"><div class="meter meter-realtime ${current.realtime_meter_enabled?'':'hidden'}" title="Master Left"><span id="vu-master-L" style="height:0%"></span><em>L</em></div><div class="meter meter-realtime ${current.realtime_meter_enabled?'':'hidden'}" title="Master Right"><span id="vu-master-R" style="height:0%"></span><em>R</em></div></div></div></div><input class="channel-value volume-number" id="master-db" type="number" min="-60" max="12" step="0.1" value="${Number(v).toFixed(1)}" onchange="setMasterVolume(this.value)" onkeydown="if(event.key==='Enter')this.blur()" aria-label="Master volume in dB" title="Master volume in dB"></div>`;
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
function trackAudibleNow(track){
  if(!track||track.mute)return false;
  const anySolo=(current?.tracks||[]).some(t=>t.solo);
  return !anySolo||!!track.solo;
}
function playbackGainForTrack(track,item=null){
  if(!track)return 0;
  if(item?.respectMuteSolo!==false&&!trackAudibleNow(track))return 0;
  return dbToGain(Number(track.volume_db||0)+Number(current?.master_volume_db||0));
}
function updatePlaybackGains(){
  const now=audioCtx?.currentTime||0;
  for(const item of trackPlaybacks){
    const track=trackById(item.trackId);if(!track||!item.gainNode)continue;
    // Mixer controls are applied downstream of the media decoder. Never wait for
    // buffering or a new server preview before changing volume/mute/solo.
    item.gainNode.gain.cancelScheduledValues(now);
    item.gainNode.gain.setValueAtTime(playbackGainForTrack(track,item),now);
  }
}
function refreshRenderedMasterForMixState(){
  if(!renderedMasterPlayback)return;
  if(playbackPaused||!playAudio||playAudio.paused){renderedMasterDirty=true;return}
  if(renderedMasterRefreshPromise)return;
  renderedMasterRefreshPromise=(async()=>{
    const previous=playAudio,cursor=playCursorMs,token=++playbackToken;
    try{
      collect();
      await persistCurrentProject(false);
      const audio=new Audio(`/api/projects/${current.id}/preview-mix?t=${Date.now()}`);
      await new Promise((resolve,reject)=>{audio.addEventListener('loadedmetadata',resolve,{once:true});audio.addEventListener('error',()=>reject(new Error('Anteprima renderizzata non disponibile')),{once:true});audio.load()});
      if(token!==playbackToken)return;
      audio.currentTime=Math.min(cursor/1000/tempoRatio(),Math.max(0,(audio.duration||0)-0.01));
      renderedMasterBaseVolumeDb=Number(current?.master_volume_db||0);
      const graph=await attachPlaybackGraph(audio,{volume_db:0,pan:0},2,false,true,false);
      graph.gainNode.gain.setValueAtTime(1,audioCtx?.currentTime||0);
      await audio.play();
      try{previous.pause();previous.src=''}catch(e){}
      playAudio=audio;renderedMasterAudio=audio;masterPlaybackGainNode=graph.gainNode;masterMeterAnalysers=graph.analysers;
      renderedMasterDirty=false;
      if(current?.follow_playback_enabled)followPlayhead(playCursorMs/1000*pxPerSec,true);
      if(!playRaf)playRaf=requestAnimationFrame(movePlayhead);
    }catch(e){
      renderedMasterDirty=true;
      console.warn('Aggiornamento live del master renderizzato fallito',e);
    }finally{renderedMasterRefreshPromise=null}
  })();
}
function applyLiveMuteSolo(){
  updatePlaybackGains();
  refreshRenderedMasterForMixState();
}
function queueRenderedMasterRefresh(delay=90){
  if(!renderedMasterPlayback)return;
  clearTimeout(liveFxRefreshTimers.master);
  liveFxRefreshTimers.master=setTimeout(()=>{
    delete liveFxRefreshTimers.master;
    refreshRenderedMasterForMixState();
  },delay);
}
async function refreshDynamicTrackPlayback(trackId){
  if(renderedMasterPlayback||playbackPaused||!playbackActuallyRunning())return;
  const track=trackById(trackId);if(!track)return;
  const oldIndex=trackPlaybacks.findIndex(item=>item.trackId===trackId);
  if(oldIndex<0)return;
  const oldItem=trackPlaybacks[oldIndex],wasClock=playAudio===oldItem.audio;
  try{
    collect();
    await persistCurrentProject(false);
    const replacement=await makeTrackPlayback(track,true,false,true);
    replacement.audio.currentTime=Math.min(playCursorMs/1000/tempoRatio(),Math.max(0,(replacement.audio.duration||0)-0.01));
    await replacement.audio.play();
    trackPlaybacks.splice(oldIndex,1,replacement);
    if(wasClock)playAudio=replacement.audio;
    try{oldItem.audio.pause();oldItem.audio.src=''}catch(e){}
    updatePlaybackGains();
  }catch(e){console.warn('Aggiornamento live FX traccia fallito',trackId,e)}
}
function queueLiveFxRefresh(isMaster,trackId='',delay=90){
  if(!playAudio&&!trackPlaybacks.length)return;
  if(isMaster||renderedMasterPlayback){
    queueRenderedMasterRefresh(delay);
    return;
  }
  const id=trackId||selectedTrack()?.id||'';
  if(!id)return;
  clearTimeout(liveFxRefreshTimers[id]);
  liveFxRefreshTimers[id]=setTimeout(()=>{
    delete liveFxRefreshTimers[id];
    refreshDynamicTrackPlayback(id);
  },delay);
}
function toggleBool(btn,id,k){const t=trackById(id);if(!t)return;t[k]=!t[k];updateMuteSoloVisuals();applyLiveMuteSolo();markDirty();toast(k==='mute'?(t[k]?'Mute attivato':'Mute disattivato'):(t[k]?'Solo attivato':'Solo disattivato'))}
function toggleMuteAll(){
  if(!current?.tracks?.length)return;
  const next=!current.tracks.every(t=>t.mute);
  current.tracks.forEach(t=>{t.mute=next});updateMuteSoloVisuals();applyLiveMuteSolo();markDirty();render();toast(next?'Mute attivato su tutte le tracce':'Mute rimosso da tutte le tracce');
}
function toggleSoloAll(){
  if(!current?.tracks?.length)return;
  const next=!current.tracks.every(t=>t.solo);
  current.tracks.forEach(t=>{t.solo=next});updateMuteSoloVisuals();applyLiveMuteSolo();markDirty();render();toast(next?'Solo attivato su tutte le tracce':'Solo rimosso da tutte le tracce');
}
function toggleAllPlugins(){
  if(!current)return;
  const plugins=[...(current.master_inserts||[]),...current.tracks.flatMap(t=>t.inserts||[])];
  if(!plugins.length)return toast('Nessun plugin configurato');
  const enable=!plugins.some(x=>x.enabled);
  plugins.forEach(x=>{x.enabled=enable});
  for(const t of current.tracks){if(t.inserts?.length){queueInsertWaveformRefresh(t.id);queueLiveFxRefresh(false,t.id)}}
  if((current.master_inserts||[]).length)queueLiveFxRefresh(true,'');
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
  updatePlaybackGains();
  if(renderedMasterPlayback)queueRenderedMasterRefresh();
  $$(`[data-volume-track="${id}"]`).forEach(el=>{if(Number(el.value)!==n)el.value=n});
  $$(`[data-volume-number="${id}"]`).forEach(el=>{if(document.activeElement!==el||String(el.value)!==String(v))el.value=n.toFixed(1)});
  markDirty();
}
function dbToGain(db){return Math.pow(10,Number(db||0)/20)}
function resetTrackVolumeToUnity(id,event){
  event?.preventDefault();event?.stopPropagation();setTrackVolume(id,0);markDirty();
}
function resetMasterVolumeToUnity(event){
  event?.preventDefault();event?.stopPropagation();setMasterVolume(0);markDirty();
}
function setMasterVolume(v){
  const n=normalizeVolume(v);if(!current||n===null)return;
  current.master_volume_db=n;
  if($('#master-volume-range')&&Number($('#master-volume-range').value)!==n)$('#master-volume-range').value=n;
  if($('#master-db')&&document.activeElement!==$('#master-db'))$('#master-db').value=n.toFixed(1);
  updatePlaybackGains();
  if(masterPlaybackGainNode){
    const liveDb=renderedMasterPlayback?n-renderedMasterBaseVolumeDb:n;
    masterPlaybackGainNode.gain.setValueAtTime(dbToGain(liveDb),audioCtx?.currentTime||0);
  }
  markDirty();
}
function setTrackPan(id,v){
  const t=trackById(id);if(!t)return;
  const n=clampPan(v);t.pan=n;updatePanUi(id,n);
  const item=trackPlaybacks.find(x=>x.trackId===id);
  if(item?.panner){const now=audioCtx?.currentTime||0;item.panner.pan.cancelScheduledValues(now);item.panner.pan.setValueAtTime(n,now);}
  if(renderedMasterPlayback)queueRenderedMasterRefresh();
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
async function ensureWaveforms(validateExisting=false){
  // Selection/rerender must not trigger waveform work. Existing persisted peaks are
  // validated once when a project is opened; later renders only request missing peaks.
  // This keeps project opening fast while guaranteeing stale/missing waveforms are regenerated and saved.
  for(const t of current?.tracks||[]){
    if(t.waveform_peaks?.length){drawWave(t);if(!validateExisting)continue}
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
  const textModels=pluginInfo.text_models||{},lyricsModels=textModels.lyrics||{},chordModels=textModels.chords||{};
  const lyricsModelOptions=(lyricsModels.models||[]).map(m=>`<option value="${esc(m.id)}" ${m.id===lyricsModels.default_model?'selected':''}>${esc(m.display_name)} · ${m.installed?'installato':'on-demand'}</option>`).join('');
  const chordModelMap=Object.fromEntries((chordModels.models||[]).map(m=>[m.id,m]));const chordEngineOptions=(chordModels.engines||[]).map(e=>`<option value="${esc(e.id)}" ${e.id===chordModels.default_engine?'selected':''} ${e.available?'':'disabled'}>${esc(e.display_name)}${e.model_id?' · '+(chordModelMap[e.model_id]?.installed?'installato':'on-demand'):' · no model'}</option>`).join('');
  const leadBacking=stem.lead_backing||{};const backingModels=(leadBacking.models||[]).map(m=>`<option value="${esc(m.id)}" ${m.id===leadBacking.default_model?'selected':''}>${esc(m.display_name)} · ${m.installed?'installato':(leadBacking.storage==='local'?'download locale':'download server')}</option>`).join('');
  const defaultName=current?.title||'Nuovo progetto da MP3';
  const profileMap=Object.fromEntries((stem.model_profiles||[]).map(p=>[p.model,p]));const models=(stem.models||['htdemucs_6s']).map(x=>{const p=profileMap[x]||{};return `<option value="${esc(x)}" ${x===stem.recommended_model?'selected':''}>${esc(p.display_name||x)}${p.stem_count?' · '+p.stem_count+' stem':''}</option>`}).join('');
  const stemCounts=[...new Set((stem.supported_stem_counts||[2,4,6]).map(Number).filter(n=>n>=2&&n<=64))].sort((a,b)=>a-b);
  const profiles=stem.model_profiles||[];
  const stemCountOptions=['<option value="0" '+(preferredStemCount===0?'selected':'')+'>Auto · model-driven</option>',...stemCounts.map(n=>{const p=profiles.find(x=>Number(x.stem_count)===n),labels=(p?.stem_labels||[]);const detail=labels.length&&labels.length<=8?' · '+labels.join(' / '):(p?.display_name?' · '+p.display_name:'');return `<option value="${n}" ${preferredStemCount===n?'selected':''}>${n} stem${esc(detail)}</option>`;})].join('');
  const rememberedFile=lastSelectedAudioFile&&/\.mp3$/i.test(lastSelectedAudioFile.name)?lastSelectedAudioFile:null;
  const remembered=rememberedFile?.name?`<div class="workflow-note">File MP3 già selezionato: <b>${esc(rememberedFile.name)}</b>. Verrà usato se non ne scegli un altro.</div>`:'';
  showUtilityModal('Importa brano e separa strumenti',`
    <div class="stem-workflow">
      <p class="hint"><span class="status-dot ${stem.available?'ok':'bad'}"></span>${stem.available?'Demucs disponibile. Il brano viene salvato subito nel progetto; la separazione continua in background.':'Demucs non è disponibile nel runtime corrente.'}</p>
      <label class="workflow-field"><span>Destinazione</span><select id="stemProjectMode" onchange="updateStemWorkflowMode()"><option value="existing" ${current?'selected':''}>Progetto corrente${current?`: ${esc(current.title)}`:''}</option><option value="new" ${current?'':'selected'}>Nuovo progetto persistente</option></select></label>
      <label class="workflow-field" id="stemProjectNameRow"><span>Nome nuovo progetto</span><input id="stemProjectTitle" maxlength="200" value="${esc(defaultName)}"></label>
      <div class="workflow-grid">
        <label class="workflow-field"><span>Tipo progetto</span><select id="stemProjectTarget"><option value="DAW">Multitrack DAW</option><option value="MTA8">MTA8</option><option value="MTA16">MTA16</option></select></label>
        <label class="workflow-field"><span>Modello AI</span><select id="stemWorkflowModel">${models}</select></label>
        <label class="workflow-field"><span>Numero stem</span><select id="stemWorkflowCount" onchange="setPreferredStemCount(this.value)">${stemCountOptions}</select></label>
        ${supportsLocalIosStems()?`<label class="workflow-field"><span>Elaborazione</span><select id="stemExecutionMode" onchange="setPreferredStemExecution(this.value)"><option value="auto" ${preferredStemExecution==='auto'?'selected':''}>Auto · locale se possibile</option><option value="local" ${preferredStemExecution==='local'?'selected':''}>Locale · Core ML</option><option value="server" ${preferredStemExecution==='server'?'selected':''}>Server cloud</option></select></label>`:''}
      </div>
      <label class="workflow-field"><span>Brano completo MP3</span><input id="stemWorkflowFile" type="file" accept=".mp3,audio/mpeg"></label>
      ${remembered}
      <label class="workflow-check"><input id="stemKeepOriginal" type="checkbox" checked> Mantieni anche la traccia “Original Mix” nel progetto</label>
      <label class="workflow-check"><input id="stemExtractLyrics" type="checkbox" onchange="$('#stemLyricsModelRow').classList.toggle('hidden',!this.checked)"> Estrai anche le lyrics</label>
      <label class="workflow-field hidden" id="stemLyricsModelRow"><span>Motore lyrics · OpenAI Whisper</span><select id="stemLyricsModel">${lyricsModelOptions}</select><button type="button" onclick="downloadStemTextModel('lyrics')">Scarica modello</button></label>
      <label class="workflow-check"><input id="stemExtractChords" type="checkbox" onchange="$('#stemChordsEngineRow').classList.toggle('hidden',!this.checked);updateStemChordEngineDisclosure()"> Estrai anche i chords</label>
      <label class="workflow-field hidden" id="stemChordsEngineRow"><span>Motore chords</span><select id="stemChordsEngine" onchange="updateStemChordEngineDisclosure()">${chordEngineOptions}</select><small id="stemChordEngineDisclosure"></small><button type="button" onclick="downloadStemTextModel('chords')">Scarica modello</button></label>
      <label class="workflow-check"><input id="stemSplitBackingVocals" type="checkbox" onchange="updateBackingModelRow()"> Separa anche voce principale e backing vocals (secondo passaggio AI)</label><label class="workflow-field hidden" id="backingModelRow"><span>Modello Lead / Backing Vocals</span><select id="stemBackingVocalModel">${backingModels}<option value="ffmpeg-center-side">Fallback DSP center/side</option></select><button type="button" onclick="downloadSelectedBackingModel()">Scarica modello</button></label>
      <div class="workflow-note">Il file originale viene sempre conservato in <b>Originals</b>. Il progetto viene salvato dopo l’import e dopo ogni stem aggiunto. Su iPhone/iPad, <b>Auto</b> usa Core ML sul dispositivo quando il modello richiesto è disponibile e ricade automaticamente sul server negli altri casi. I modelli locali vengono scaricati una sola volta e restano disponibili offline. 8 stem richiede un modello compatibile.</div>
      <div class="utility-actions">
        <button class="utility-btn primary" type="button" onclick="startStemWorkflow()" ${stem.available?'':'disabled'}><span>Importa e separa</span></button>
        <button class="utility-btn secondary" type="button" onclick="closeUtilityModal()"><span>Annulla</span></button>
      </div>
    </div>`);
  updateStemWorkflowMode();
}
function updateBackingModelRow(){const row=$('#backingModelRow'),on=$('#stemSplitBackingVocals')?.checked;if(row)row.classList.toggle('hidden',!on)}
async function downloadSelectedBackingModel(){const id=$('#stemBackingVocalModel')?.value;if(!id||id==='ffmpeg-center-side')return toast('Il fallback DSP non richiede modelli');try{toast('Download modello in corso…');await api(`/api/vocal-separation/models/${encodeURIComponent(id)}/download`,{method:'POST'});pluginInfo=await api('/api/plugins');toast(currentUser?.native_single_user?'Modello scaricato localmente':'Modello scaricato sul server')}catch(e){toast(e.message)}}

function updateStemChordEngineDisclosure(){const c=textModelCatalog().chords||{},id=$('#stemChordsEngine')?.value,e=(c.engines||[]).find(x=>x.id===id),m=(c.models||[]).find(x=>x.id===e?.model_id),el=$('#stemChordEngineDisclosure');if(el)el.textContent=e?`${e.display_name}${e.model_id?' · modello '+(m?.display_name||e.model_id)+(m?.installed?' · installato':' · download on-demand'): ' · nessun modello AI'}`:''}
async function downloadStemTextModel(kind){const cat=textModelCatalog();try{if(kind==='lyrics'){const id=$('#stemLyricsModel')?.value;if(!id)return;await api(`/api/ai-models/lyrics/${encodeURIComponent(id)}/download`,{method:'POST'})}else{const id=$('#stemChordsEngine')?.value,e=(cat.chords?.engines||[]).find(x=>x.id===id);if(!e?.model_id)return toast('Questo motore non richiede un modello');await api(`/api/ai-models/chords/${encodeURIComponent(e.model_id)}/download`,{method:'POST'})}pluginInfo=await api('/api/plugins');toast(currentUser?.native_single_user?'Modello scaricato localmente':'Modello scaricato sul server');updateStemChordEngineDisclosure()}catch(e){toast(e.message)}}
function updateStemWorkflowMode(){
  const mode=$('#stemProjectMode')?.value;
  const row=$('#stemProjectNameRow'),target=$('#stemProjectTarget');
  if(row)row.style.display=mode==='new'?'grid':'none';
  if(target){
    target.disabled=mode!=='new';
    if(mode==='existing'&&current?.target&&['DAW','MTA8','MTA16'].includes(current.target))target.value=current.target;
  }
}

async function runTextAnalysisAndWait(projectId,trackId,kind,choice=""){
  if(!trackId)return null;
  const param=kind==='lyrics'?'model':'engine';const suffix=choice?`?${param}=${encodeURIComponent(choice)}`:'';const job=await api(`/api/projects/${projectId}/tracks/${trackId}/extract-${kind}-jobs${suffix}`,{method:'POST'});
  for(;;){
    const state=await api(`/api/media-jobs/${job.id}`);
    if(state.status==='completed')return state;
    if(state.status==='failed'||state.status==='cancelled')throw new Error(state.error||`Estrazione ${kind} non riuscita`);
    await new Promise(resolve=>setTimeout(resolve,600));
  }
}

async function startIosLocalStemWorkflow({projectId,stemCount,modelId,keep,extractLyrics=false,extractChords=false,lyricsModel='',chordsEngine=''}){
  showUtilityModal('Separazione locale',`<div class="stem-progress-card"><div class="stem-progress-head"><b>Demucs Core ML</b><span id="localStemPct">0%</span></div><div class="stem-progress"><div id="localStemFill" class="stem-progress-fill" style="width:0%"></div></div><div id="localStemMessage" class="stem-progress-message">Preparazione modello locale…</div><div class="utility-actions"><button class="danger-action" onclick="window.MtaMobile?.cancelLocalStemSeparation?.()">Annulla separazione</button></div></div>`);
  const onProgress=e=>{const pct=Math.max(0,Math.min(100,Number(e.detail?.progress)||0));if($('#localStemPct'))$('#localStemPct').textContent=pct+'%';if($('#localStemFill'))$('#localStemFill').style.width=pct+'%';if($('#localStemMessage'))$('#localStemMessage').textContent=e.detail?.message||'Separazione locale'};
  window.addEventListener('mtaLocalStemProgress',onProgress);
  try{
    const result=await window.MtaMobile.startLocalStemSeparation(projectId,stemCount,modelId||"",keep);
    await refresh();
    current=await api(`/api/projects/${projectId}`);selectedTrackId=current.tracks.at(-1)?.id||null;render();
    if(extractLyrics||extractChords){
      const vocal=current.tracks.find(t=>t.type==='melody'||/vocals?/i.test(t.name||''));
      const original=current.tracks.find(t=>/original mix/i.test(t.name||''))||current.tracks[0];
      if(extractLyrics){if($('#localStemMessage'))$('#localStemMessage').textContent='Estrazione lyrics ad alta accuratezza…';await runTextAnalysisAndWait(projectId,vocal?.id||original?.id,'lyrics',lyricsModel)}
      if(extractChords){if($('#localStemMessage'))$('#localStemMessage').textContent='Analisi chords ad alta accuratezza…';await runTextAnalysisAndWait(projectId,original?.id||vocal?.id,'chords',chordsEngine)}
      current=await api(`/api/projects/${projectId}`);render();
    }
    toast(`Separazione locale completata · ${result.stemCount} stem`);
    closeUtilityModal();return true;
  }finally{window.removeEventListener('mtaLocalStemProgress',onProgress)}
}

async function startStemWorkflow(){
  const f=$('#stemWorkflowFile')?.files?.[0]||(lastSelectedAudioFile&&/\.mp3$/i.test(lastSelectedAudioFile.name)?lastSelectedAudioFile:null);
  if(!f)return toast('Seleziona un file MP3');
  const mode=$('#stemProjectMode').value;
  const title=$('#stemProjectTitle')?.value?.trim()||'';
  if(mode==='new'&&!title)return toast('Inserisci il nome del nuovo progetto');
  await flushAutosave();
  const fd=new FormData();fd.append('file',f);
  let projectId=mode==='existing'&&current?current.id:'';
  const target=mode==='existing'?(current?.target||'MTA8'):$('#stemProjectTarget').value;
  const model=$('#stemWorkflowModel').value;
  const keep=$('#stemKeepOriginal').checked;
  const stemCount=Number($('#stemWorkflowCount')?.value||preferredStemCount||0);setPreferredStemCount(stemCount);
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
  const extractLyrics=!!$('#stemExtractLyrics')?.checked,extractChords=!!$('#stemExtractChords')?.checked;
  const lyricsModel=$('#stemLyricsModel')?.value||textModelCatalog().lyrics?.default_model||'large-v3';
  const chordsEngine=$('#stemChordsEngine')?.value||textModelCatalog().chords?.default_engine||'madmom-deep-chroma';
  const splitBackingVocals=!!$('#stemSplitBackingVocals')?.checked;
  const backingVocalModel=$('#stemBackingVocalModel')?.value||'uvr_mdxnet_kara_2';
  let execution=$('#stemExecutionMode')?.value||preferredStemExecution||'server';
  if(splitBackingVocals&&execution!=='server'){execution='server';toast('La separazione Lead/Backing Vocals richiede il secondo passaggio sul server.');}
  if(supportsLocalIosStems()&&execution!=='server'){
    let localProjectId=projectId;
    if(!localProjectId){
      const created=await api(`/api/projects?title=${encodeURIComponent(title||f.name.replace(/\.mp3$/i,''))}&target=${encodeURIComponent(target)}`,{method:'POST'});
      localProjectId=created.id;current=created;selectedTrackId=null;render();
    }
    try{
      const caps=await window.MtaMobile.localStemCapabilities();
      const installedCounts=(caps.installedStemCounts||[]).map(Number).sort((a,b)=>b-a);
      const hardwareRecommended=Number(caps.recommendedStemCount)||4;
      const requested=stemCount||installedCounts.find(n=>n<=hardwareRecommended)||hardwareRecommended;
      const installed=installedCounts.includes(requested);
      if(execution==='local'||installed){
        setMobileBusy(true);
        try{return await startIosLocalStemWorkflow({projectId:localProjectId,stemCount:stemCount,modelId:model,keep,extractLyrics,extractChords,lyricsModel,chordsEngine})}finally{setMobileBusy(false)}
      }
      // Auto: native layer may download a model from the configured server. If it
      // cannot, fall through to the established server-side Demucs workflow.
      try{
        setMobileBusy(true);
        return await startIosLocalStemWorkflow({projectId:localProjectId,stemCount:stemCount,modelId:model,keep,extractLyrics,extractChords,lyricsModel,chordsEngine});
      }catch(localError){
        setMobileBusy(false);
        toast('Modello locale non disponibile: uso il server.');
        if(!projectId)projectId=localProjectId;
      }
    }catch(localError){
      if(execution==='local')return toast(localError.message);
    }
  }
  try{
    if(mobilePlatform()==='android'&&window.MtaMobile?.ensureLocalStemModel){
      try{const raw=window.MtaMobile.ensureLocalStemModel(model,stemCount||0);const state=typeof raw==='string'?JSON.parse(raw):raw;if(state&&!state.ok)console.warn('Android local model prefetch:',state.error)}catch(e){console.warn('Android local model prefetch failed',e)}
    }
    const r=await api(`/api/stems/jobs?project_id=${encodeURIComponent(projectId)}&project_title=${encodeURIComponent(title)}&target=${encodeURIComponent(target)}&model=${encodeURIComponent(model)}&stem_count=${stemCount}&keep_original_track=${keep}&extract_lyrics=${extractLyrics}&extract_chords=${extractChords}&lyrics_model=${encodeURIComponent(lyricsModel)}&chords_engine=${encodeURIComponent(chordsEngine)}&split_backing_vocals=${splitBackingVocals}&backing_vocal_model=${encodeURIComponent(backingVocalModel)}`,{method:'POST',body:fd});
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
      ${job.analysis&&Object.keys(job.analysis).length?`<div class="workflow-note">${Object.entries(job.analysis).map(([k,v])=>`${k==='lyrics'?'Lyrics':'Chords'}: ${v.ok?`OK · ${v.count||0} eventi`:`errore · ${esc(v.error||'analisi non riuscita')}`}`).join('<br>')}</div>`:''}
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
      const failedAnalysis=Object.entries(job.analysis||{}).filter(([,v])=>!v.ok);
      toast(failedAnalysis.length?`Separazione completata; analisi ${failedAnalysis.map(([k])=>k).join(', ')} non riuscita`:'Separazione completata e progetto salvato');
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

async function drawWave(t){
  const c=$('#wave-'+t.id);if(!c)return;
  const ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);
  const peaks=Array.isArray(t.waveform_peaks)?t.waveform_peaks:[];
  if(!peaks.length){ctx.fillStyle='#6d8294';ctx.fillText('waveform unavailable',10,39);return}
  const color=t.color||'#2f81f7',mid=c.height/2,amp=Math.max(4,c.height*.36);
  ctx.strokeStyle=color;ctx.globalAlpha=.86;ctx.lineWidth=1;
  const durationMs=Math.max(1,Number(t.duration_ms||0));
  for(const clip of t.clips||[]){
    const sourceStart=Math.max(0,Number(clip.source_start_ms||0));
    const sourceEnd=Math.max(sourceStart+1,Number(clip.source_end_ms||durationMs));
    const tl=Number(clip.timeline_start_ms||0)/1000*pxPerSec;
    const tw=(sourceEnd-sourceStart)/1000*pxPerSec;
    if(tw<=0)continue;
    const firstBin=Math.max(0,Math.min(peaks.length-1,Math.floor(sourceStart/durationMs*peaks.length)));
    const lastBin=Math.max(firstBin+1,Math.min(peaks.length,Math.ceil(sourceEnd/durationMs*peaks.length)));
    const sourceBins=Math.max(1,lastBin-firstBin);
    // Never draw more columns than either the visible pixel width or the cached
    // source detail.  Zooming in increases spacing/detail without inventing points;
    // zooming out aggregates source bins into one pixel column.
    const columns=Math.max(1,Math.min(Math.ceil(tw),sourceBins));
    const xStep=tw/columns;
    ctx.beginPath();
    for(let col=0;col<columns;col++){
      const a=firstBin+Math.floor(col*sourceBins/columns);
      const b=Math.max(a+1,firstBin+Math.ceil((col+1)*sourceBins/columns));
      let peak=0;
      for(let i=a;i<Math.min(lastBin,b);i++)peak=Math.max(peak,Number(peaks[i]||0));
      const x=tl+(col+.5)*xStep;
      const h=Math.min(1,peak)*amp;
      ctx.moveTo(x,mid-h);ctx.lineTo(x,mid+h);
    }
    ctx.stroke();
  }
}
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
  if(!current)return;current.realtime_meter_enabled=!current.realtime_meter_enabled;$('#realtimeBtn')?.classList.toggle('active',current.realtime_meter_enabled);$$('.meter-realtime,.peak-led').forEach(x=>x.classList.toggle('hidden',!current.realtime_meter_enabled));markDirty();
  if(!current.realtime_meter_enabled)resetVuMeters();
  if(playAudio||trackPlaybacks.length){const pos=playCursorMs;stopPlayback();setPlayCursor(pos);previewMaster()}
}
function updateTransportToggleButtons(){
  $('#renderBtn')?.classList.toggle('active',!!current?.render_preview_enabled);
  $('#followBtn')?.classList.toggle('active',!!current?.follow_playback_enabled);
}
function resetVuMeters(){
  $$('[id^="vu-"]').forEach(x=>x.style.height='0%');
  $$('.peak-led').forEach(x=>x.classList.remove('active'));
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
function latchPeak(id,pct){if(pct>=99.5)$(id)?.classList.add('active')}
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
      setVu(`#vu-${item.trackId}-M`,mono);latchPeak(`#peak-${item.trackId}`,mono);
      masterLeftEnergy+=mono*mono;masterRightEnergy+=mono*mono;
    }else{
      const left=analyserLevel(analysers[0],item,'l');
      const right=analyserLevel(analysers[1],item,'r');
      setVu(`#vu-${item.trackId}-L`,left);setVu(`#vu-${item.trackId}-R`,right);latchPeak(`#peak-${item.trackId}`,Math.max(left,right));
      masterLeftEnergy+=left*left;masterRightEnergy+=right*right;
    }
  }
  if(masterMeterAnalysers?.length===2){
    const holder=masterMeterAnalysers;
    holder.meterData=holder.meterData||{};
    const masterL=analyserLevel(holder[0],holder,'l'),masterR=analyserLevel(holder[1],holder,'r');
    setVu('#vu-master-L',masterL);setVu('#vu-master-R',masterR);latchPeak('#peak-master',Math.max(masterL,masterR));
  }else{
    const masterL=Math.min(100,Math.sqrt(masterLeftEnergy)),masterR=Math.min(100,Math.sqrt(masterRightEnergy));
    setVu('#vu-master-L',masterL);setVu('#vu-master-R',masterR);latchPeak('#peak-master',Math.max(masterL,masterR));
  }
  meterRaf=requestAnimationFrame(()=>{
    if(token===meterRunToken)updateVuMeters(token);
  });
}
async function attachPlaybackGraph(audio,track,channels=2,silent=false,masterRendered=false,respectMuteSolo=true){
  audioCtx=audioCtx||new(window.AudioContext||window.webkitAudioContext)();
  await audioCtx.resume();
  const source=audioCtx.createMediaElementSource(audio);
  const gainNode=audioCtx.createGain();
  const panner=audioCtx.createStereoPanner();
  const db=masterRendered
    ? Number(current?.master_volume_db||0)
    : Number(track?.volume_db||0)+Number(current?.master_volume_db||0);
  const audible=masterRendered||!respectMuteSolo||trackAudibleNow(track);
  // Meter-only playback keeps the real level up to the analysers and is
  // silenced only at the destination sink below.
  gainNode.gain.value=!audible?0:dbToGain(db);
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
async function makeTrackPlayback(track,renderFilters,silent=false,respectMuteSolo=true){
  const audio=new Audio(`/api/projects/${current.id}/preview-track/${track.id}?render=${renderFilters?'true':'false'}&t=${Date.now()}`);
  audio.preload='auto';
  const channels=renderFilters?effectiveTrackChannels(track):(Number(track.channels)===1?1:2);
  const graph=await attachPlaybackGraph(audio,track,channels,silent,false,respectMuteSolo);
  await new Promise((resolve,reject)=>{audio.addEventListener('loadedmetadata',resolve,{once:true});audio.addEventListener('error',()=>reject(new Error(`Preview non disponibile: ${track.name}`)),{once:true});audio.load()});
  audio.currentTime=Math.min(playCursorMs/1000/tempoRatio(),Math.max(0,(audio.duration||0)-0.01));
  audio.addEventListener('ended',()=>requestAnimationFrame(()=>{
    if(!playbackActuallyRunning())resetVuMeters();
  }));
  return {trackId:track.id,audio,analysers:graph.analysers,channels,silent,respectMuteSolo,meterData:{},gainNode:graph.gainNode,panner:graph.panner};
}
function waitForMediaBuffer(audio,label='traccia',timeoutMs=12000){
  const enough=()=>{if(audio.readyState<3)return false;try{const pos=audio.currentTime||0;for(let i=0;i<audio.buffered.length;i++){if(audio.buffered.start(i)<=pos+.05&&audio.buffered.end(i)-pos>=Math.min(3,Math.max(.5,(audio.duration||3)-pos)))return true}}catch(e){}return audio.readyState>=4};
  if(enough())return Promise.resolve();
  return new Promise((resolve,reject)=>{let done=false;const finish=()=>{if(done)return;done=true;cleanup();resolve()},fail=()=>{if(done)return;done=true;cleanup();reject(new Error(`Buffering non riuscito: ${label}`))},check=()=>{if(enough())finish()},cleanup=()=>{clearTimeout(timer);clearInterval(poll);audio.removeEventListener('canplaythrough',check);audio.removeEventListener('progress',check);audio.removeEventListener('error',fail)},poll=setInterval(check,100),timer=setTimeout(()=>audio.readyState>=3?finish():fail(),timeoutMs);audio.addEventListener('canplaythrough',check);audio.addEventListener('progress',check);audio.addEventListener('error',fail,{once:true});audio.load()});
}
function stopDynamicSyncMonitor(){
  if(dynamicSyncTimer){clearInterval(dynamicSyncTimer);dynamicSyncTimer=null}
  dynamicSyncClock=null;
}
function dynamicClockAudio(){
  if(renderedMasterPlayback&&renderedMasterAudio)return renderedMasterAudio;
  const preferred=dynamicSyncClock?.audio||playAudio;if(preferred&&!preferred.ended&&preferred.readyState>=2)return preferred;
  const active=trackPlaybacks.find(item=>item.audio&&!item.audio.paused&&!item.audio.ended&&item.audio.readyState>=2);
  if(active){dynamicSyncClock=active;return active.audio}
  return preferred||trackPlaybacks[0]?.audio||null;
}
function alignDynamicTracks(force=false){
  if(renderedMasterPlayback||playbackPaused||!trackPlaybacks.length)return;
  const clock=dynamicClockAudio();if(!clock||clock.paused||clock.ended||clock.readyState<2)return;
  const ref=clock.currentTime,now=Date.now();
  for(const item of trackPlaybacks){
    const audio=item.audio;if(audio===clock||audio.paused||audio.ended)continue;
    // Never chase a buffering decoder with repeated seeks: that can keep it in
    // permanent starvation. A forced relock is reserved for start/seek/resume.
    if(audio.readyState<3||audio.seeking){audio.playbackRate=1;item.needsRelock=true;continue}
    const drift=audio.currentTime-ref;
    try{
      if(force||(item.needsRelock&&Math.abs(drift)>.080)){
        audio.currentTime=ref;audio.playbackRate=1;item.needsRelock=false;item.lastHardSync=now;
      }else if(Math.abs(drift)>.035){
        audio.playbackRate=Math.max(.995,Math.min(1.005,1-drift*.06));
      }else if(Math.abs(audio.playbackRate-1)>.0005){audio.playbackRate=1}
    }catch(e){}
  }
}
function startDynamicSyncMonitor(){
  stopDynamicSyncMonitor();dynamicSyncClock=trackPlaybacks.find(x=>x.audio&&!x.audio.ended)||null;
  // HTML media elements already share the browser media clock. We only correct
  // meaningful drift and never hammer stalled decoders.
  dynamicSyncTimer=setInterval(()=>alignDynamicTracks(false),250);
}
async function startDynamicTrackPreview(renderFilters,silentMeters=false,token=playbackToken){
  playbackBuffering=true;const tracks=current.tracks||[];showMediaProgress('Buffering tracce',5,`Pre-buffer ${tracks.length} tracce… attendere`);
  try{
    const items=await Promise.all(tracks.map(t=>makeTrackPlayback(t,renderFilters,silentMeters,true)));if(token!==playbackToken)return null;
    showMediaProgress('Buffering tracce',45,'Preparazione decoder… attendere');
    await Promise.all(items.map((item,i)=>waitForMediaBuffer(item.audio,tracks[i]?.name||`traccia ${i+1}`,18000)));if(token!==playbackToken)return null;
    const sec=playCursorMs/1000/tempoRatio();
    for(const item of items){item.audio.pause();item.audio.playbackRate=1;item.needsRelock=false;item.lastHardSync=0;item.audio.currentTime=Math.min(sec,Math.max(0,(item.audio.duration||0)-0.01))}
    trackPlaybacks.push(...items);updatePlaybackGains();if(audioCtx?.state==='suspended')try{await audioCtx.resume()}catch(e){}
    showMediaProgress('Buffering tracce',82,'Avvio sincronizzato…');
    await Promise.all(items.map(item=>item.audio.play()));if(token!==playbackToken){for(const item of items)try{item.audio.pause()}catch(e){};return null}
    dynamicSyncClock=items.find(x=>x.audio&&!x.audio.ended)||items[0]||null;alignDynamicTracks(true);startDynamicSyncMonitor();$('#utilityBackdrop')?.classList.add('hidden');if(current.realtime_meter_enabled&&!meterRaf)startVuMeterLoop();return dynamicSyncClock?.audio||null;
  }finally{if(token===playbackToken)playbackBuffering=false}
}

function stopPlayback(){
  ++playbackToken;
  playbackBuffering=false;
  playbackPaused=false;
  meterRunToken++;
  if(playRaf){cancelAnimationFrame(playRaf);playRaf=null}
  if(meterRaf){cancelAnimationFrame(meterRaf);meterRaf=null}
  if(playAudio){playAudio.pause();playAudio.currentTime=0;playAudio=null}
  for(const item of trackPlaybacks){try{item.audio.pause();item.audio.currentTime=0;item.audio.removeAttribute('src');item.audio.load()}catch(e){}}
  trackPlaybacks=[];masterMeterAnalysers=null;masterPlaybackGainNode=null;
  renderedMasterPlayback=false;renderedMasterDirty=false;renderedMasterRefreshPromise=null;renderedMasterBaseVolumeDb=0;renderedMasterAudio=null;
  stopDynamicSyncMonitor();
  for(const key of Object.keys(liveFxRefreshTimers)){clearTimeout(liveFxRefreshTimers[key]);delete liveFxRefreshTimers[key]}
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
  if(renderedMasterPlayback&&renderedMasterDirty)return previewMaster();
  const audios=[...new Set([playAudio,...trackPlaybacks.map(item=>item.audio)].filter(Boolean))];
  if(!audios.length)return previewMaster();
  const ref=playCursorMs/1000/tempoRatio();
  for(const audio of audios)try{audio.currentTime=Math.min(ref,Math.max(0,(audio.duration||0)-0.01))}catch(e){}
  await Promise.all(audios.map(audio=>audio.play()));
  playbackPaused=false;
  if(!renderedMasterPlayback){alignDynamicTracks(true);startDynamicSyncMonitor()}
  if($('#playMaster')){$('#playMaster').textContent='❚❚';$('#playMaster').title='Pausa'}
  playRaf=requestAnimationFrame(movePlayhead);
  if(current?.realtime_meter_enabled&&!meterRaf)meterRaf=requestAnimationFrame(updateVuMeters);
}
function goTransportStart(){
  setPlayCursor(0);
  if(renderedMasterAudio)try{renderedMasterAudio.currentTime=0}catch(e){}
  if(playAudio)try{playAudio.currentTime=0}catch(e){}
  for(const item of trackPlaybacks)try{item.audio.currentTime=0}catch(e){}
  alignDynamicTracks(true);
  if($('#transportTime'))$('#transportTime').textContent='00:00.000';
  if($('#playhead'))$('#playhead').style.left='0px';
  if(current?.follow_playback_enabled)followPlayhead(0,true);
}
async function togglePlayback(){
  if(playbackPaused)return resumePlayback();
  if(playAudio&&!playAudio.paused)return pausePlayback();
  return previewMaster();
}
function seekTransport(deltaMs){
  setPlayCursor(Math.max(0,playCursorMs+deltaMs));
  const sec=playCursorMs/1000/tempoRatio();
  if(renderedMasterAudio)try{renderedMasterAudio.currentTime=sec}catch(e){}
  if(playAudio)try{playAudio.currentTime=sec}catch(e){}
  for(const item of trackPlaybacks)try{item.audio.currentTime=sec}catch(e){}
  alignDynamicTracks(true);
  if(current?.follow_playback_enabled)followPlayhead(playCursorMs/1000*pxPerSec,true);
}
async function previewTrack(id){
  const t=trackById(id);if(!t)return;stopPlayback();
  try{const item=await makeTrackPlayback(t,true,false,false);trackPlaybacks=[item];playAudio=item.audio;await item.audio.play();requestAnimationFrame(movePlayhead);if(current.realtime_meter_enabled)startVuMeterLoop()}catch(e){toast(e.message)}
}
async function previewMaster(){
  if(!current||!current.tracks.length)return;
  try{
    await flushAutosave(false);stopPlayback();const token=++playbackToken;
    const needsRenderedMaster=!!current.render_preview_enabled||Math.abs(Number(current.master_volume_db||0))>0.001||(current.master_inserts||[]).some(x=>x.enabled);
    if(needsRenderedMaster){
      renderedMasterPlayback=true;renderedMasterDirty=false;
      renderedMasterBaseVolumeDb=Number(current.master_volume_db||0);
      const audio=new Audio(`/api/projects/${current.id}/preview-mix?t=${Date.now()}`);playAudio=audio;renderedMasterAudio=audio;
      await new Promise((resolve,reject)=>{audio.addEventListener('loadedmetadata',resolve,{once:true});audio.addEventListener('error',()=>reject(new Error('Anteprima renderizzata non disponibile')),{once:true});audio.load()});
      if(token!==playbackToken)return;
      audio.currentTime=Math.min(playCursorMs/1000/tempoRatio(),Math.max(0,(audio.duration||0)-0.01));
      if(current.realtime_meter_enabled){
        const masterGraph=await attachPlaybackGraph(audio,{volume_db:0,pan:0},2,false,true);
        masterMeterAnalysers=masterGraph.analysers;
        masterPlaybackGainNode=masterGraph.gainNode;
        masterPlaybackGainNode.gain.setValueAtTime(1,audioCtx?.currentTime||0);
        await startDynamicTrackPreview(true,true,token);if(token!==playbackToken)return;
      }else{
        const masterGraph=await attachPlaybackGraph(audio,{volume_db:0,pan:0},2,false,true);
        masterPlaybackGainNode=masterGraph.gainNode;
        masterPlaybackGainNode.gain.setValueAtTime(1,audioCtx?.currentTime||0);
      }
      await audio.play();
    }else{
      renderedMasterPlayback=false;renderedMasterDirty=false;renderedMasterAudio=null;
      playAudio=await startDynamicTrackPreview(true,false,token);if(token!==playbackToken)return;
    }
    if(!playAudio)return;playbackPaused=false;$('#playMaster').textContent='❚❚';$('#playMaster').title='Pausa';
    if(current?.follow_playback_enabled)followPlayhead(playCursorMs/1000*pxPerSec,true);
    requestAnimationFrame(movePlayhead);
    toast(needsRenderedMaster?'Anteprima Master: volume e insert applicati':'Anteprima dinamica tracce');
  }catch(e){stopPlayback();toast(e.message)}
}
function movePlayhead(){
  const clock=dynamicClockAudio();
  if(!clock||clock.paused)return;
  playCursorMs=clock.currentTime*1000*tempoRatio();
  if(!renderedMasterPlayback)alignDynamicTracks(false);
  const playheadX=playCursorMs/1000*pxPerSec;
  if($('#playhead'))$('#playhead').style.left=playheadX+'px';
  followPlayhead(playheadX);
  if($('#transportTime'))$('#transportTime').textContent=fmtTime(playCursorMs/1000,true);
  playRaf=requestAnimationFrame(movePlayhead);
}
function selectExport(format){exportFormat=format;if(current){current.export_format=format;markDirty(150)}}
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
  const initialMtaTarget=current.target==='DAW'?'MTA16':current.target;
  const targetExt=initialMtaTarget==='MTA8'?'mta8':'mta16';
  const ext=format==='mta'?targetExt:format;
  const mtaProfile=current.mta_device_profile||'auto';
  const mtaTargetField=format==='mta'&&current.target==='DAW'?`<label class="workflow-field"><span>Formato MTA di destinazione</span><select id="exportMtaTarget"><option value="MTA8">MTA8</option><option value="MTA16" selected>MTA16</option></select></label>`:'';
  const mtaProfileField=format==='mta'?`<label class="workflow-field"><span>Profilo dispositivo MTA</span><select id="exportMtaProfile">
    <option value="auto" ${mtaProfile==='auto'?'selected':''}>Auto (MTA8: B.Beat/DIVO · MTA16: Click 1, Melody 9)</option>
    <option value="merish5_xynthia2" ${mtaProfile==='merish5_xynthia2'?'selected':''}>Merish5 / Xynthia2 · MTA8 (Melody 7, Click 8)</option>
    <option value="bbeat_divo" ${mtaProfile==='bbeat_divo'?'selected':''}>B.Beat / B.Beat Plus / Evo / Pro16 / DIVO · MTA8 (Click 7, Melody 8)</option>
    <option value="mlive_mta16_default" ${mtaProfile==='mlive_mta16_default'?'selected':''}>MTA16 M-Live · default corpus (Click 1, Melody 9)</option>
    <option value="merish5_plus_mta16" ${mtaProfile==='merish5_plus_mta16'?'selected':''}>Merish5+ PLUS · compatibilità MTA16 (Click 1, Melody 9 modificabili)</option>
    <option value="generic" ${mtaProfile==='generic'?'selected':''}>Generic MTA · ordine manuale</option>
  </select></label>`:'';
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
      ${mtaTargetField}
      ${mtaProfileField}
      ${audioParams}
      <div class="workflow-note">${format==='mta'?'Il profilo MTA controlla l’ordine fisico delle tracce Click/Melody nel file. MTA8 mantiene le posizioni specifiche del dispositivo; per MTA16 il default derivato dal corpus è Click 1 / Melody 9. Se servono stream intermedi vengono creati slot silenziosi. ':''}${currentUser?.native_single_user?'Dopo Conferma verrà aperto il selettore del filesystem per scegliere la cartella di destinazione.':isMobileClient()?'L’app mobile userà il selettore file del sistema operativo. Puoi anche condividere direttamente l’output.':'Il browser chiederà dove salvare il file secondo le impostazioni di download del browser.'}</div>
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
    mta_target:$('#exportMtaTarget')?.value||(current.target==='DAW'?'MTA16':current.target),
    mta_device_profile:$('#exportMtaProfile')?.value||current.mta_device_profile||'auto',
    slots:[],
    output_path:null,
    share:!!share
  };
  if(format==='mta'){
    current.mta_device_profile=config.mta_device_profile;
    markDirty(50);
  }
  pendingExportConfig=config;
  closeUtilityModal();
  if(format==='mta'){
    try{
      const plan=await api(`/api/projects/${current.id}/export-plan?profile=${encodeURIComponent(config.mta_device_profile)}&target=${encodeURIComponent(config.mta_target||current.target)}`);
      if(plan.requires_mapping){openExportMapping(plan,config);return}
    }catch(e){return toast(e.message)}
  }
  await executeConfiguredExport(config,[]);
}
async function executeConfiguredExport(config,slots=[]){
  if(!current)return;
  try{
    await flushAutosave();
    const exportMtaTarget=config.mta_target||(current.target==='DAW'?'MTA16':current.target);
    const ext=config.format==='mta'?(exportMtaTarget==='MTA8'?'mta8':'mta16'):config.format;
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
  const suggested={};for(const slot of plan.suggested_slots||[])for(const id of slot.track_ids||[])suggested[id]=slot.slot;
  const warning=plan.mta16_default_roles?'<p class="workflow-note"><b>Default MTA16:</b> Click/Metronomo nello slot 1 e Melody nello slot 9, ricavati dal corpus MTA disponibile. Il mapping resta modificabile prima dell’export.</p>':'';
  m.innerHTML=`<h3>${plan.target} export mapping</h3>${warning}<p class="hint">Assign every project track to an output slot. Tracks assigned to the same slot are mixed together before the MTA is generated.</p><div class="mapping-grid">${plan.tracks.map((t,i)=>{const wanted=Number(suggested[t.id]||Math.min(i+1,plan.max_output_slots));return`<label><span>${esc(t.name)} <small>${esc(t.type)}</small></span><select class="slot-map" data-track="${t.id}">${options.replace(`value=\"${wanted}\"`,`value=\"${wanted}\" selected`)}</select></label>`}).join('')}</div><div class="modal-actions"><button onclick="submitExportMapping('${plan.target}')">Merge &amp; export MTA</button><button onclick="closeExportMapping()">Cancel</button></div>`;m.classList.remove('hidden')
}
function closeExportMapping(){$('#exportMapModal')?.classList.add('hidden')}
async function submitExportMapping(target){
  const grouped={};$$('.slot-map').forEach(x=>{(grouped[x.value]??=[]).push(x.dataset.track)});
  const profile=pendingExportConfig?.mta_device_profile||current.mta_device_profile||'auto';
  const profileTypes=profile==='merish5_xynthia2'
    ?['drums','bass','guitars','keyboards','orchestra','winds','melody','click']
    :['drums','bass','guitars','keyboards','orchestra','winds','click','melody'];
  const slots=Object.entries(grouped).map(([slot,ids])=>{const ts=ids.map(trackById).filter(Boolean);for(const t of ts)t.mta_slot=Number(slot);return{slot:Number(slot),name:ts.map(t=>t.name).join(' + ').slice(0,200),type:ts.length===1?ts[0].type:(target==='MTA8'&&Number(slot)<=8?profileTypes[Number(slot)-1]:'other'),track_ids:ids}});
  markDirty(50);
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
        <div><span>Formato</span><b>${esc(projectFormatLabel())}</b></div>
        <div><span>Profilo MTA</span><b>${esc(current.mta_device_profile||'auto')}</b></div>
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
        <div class="about-photo" aria-hidden="true"></div>
        <div class="about-info-panel">
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
        </div>
      </div>`);
  }catch(e){toast(e.message)}
}

function openExportPanel(){if(!current)return toast('Apri prima un progetto');showUtilityModal('Export',exportWindowHtml())}
function requireOpenProject(action){if(current)return true;toast(`Apri o crea un progetto per ${action}`);return false}
function focusProjectWorkspace(){if(!current){$('#emptyState')?.scrollIntoView({behavior:'smooth',block:'center'});return}$('#editor')?.scrollIntoView({behavior:'smooth',block:'start'})}
function focusTracks(){if(!requireOpenProject('visualizzare le tracce'))return;const el=$('.tracks-scroll')||$('.tracks')||$('#editor');el?.scrollIntoView({behavior:'smooth',block:'start'});el?.classList.add('nav-focus-pulse');setTimeout(()=>el?.classList.remove('nav-focus-pulse'),900)}
function focusMixer(){if(!requireOpenProject('aprire il mixer'))return;const el=$('#mixerDock');if(el){el.hidden=false;el.scrollIntoView({behavior:'smooth',block:'nearest'});el.classList.add('nav-focus-pulse');setTimeout(()=>el.classList.remove('nav-focus-pulse'),900)}}
function focusInspector(){if(!requireOpenProject('aprire i plugin'))return;const el=$('#inspector');if(!el)return toast('Seleziona una traccia per visualizzare i plugin');el.scrollIntoView({behavior:'smooth',block:'nearest'});el.classList.add('nav-focus-pulse');setTimeout(()=>el.classList.remove('nav-focus-pulse'),900)}

function openYoutubeImport(){
  if(!current)return toast('Apri prima un progetto');
  const refs=current.tracks.map(t=>`<option value="${t.id}">${esc(t.name)}</option>`).join('');
  $('#utilityTitle').textContent='Import audio da YouTube';
  $('#utilityBody').innerHTML=`<div class="form-grid">
    <label class="full">URL YouTube<input id="youtubeImportUrl" type="url" inputmode="url" autocomplete="off" placeholder="https://www.youtube.com/watch?v=…"></label>
    <label class="full">Nome traccia (opzionale)<input id="youtubeImportName" type="text" maxlength="200" placeholder="Usa il titolo YouTube"></label>
    <label>Sincronizzazione<select id="youtubeImportSync"><option value="manual">Manuale</option><option value="auto">Automatica</option></select></label>
    <label>Offset ms<input id="youtubeImportOffset" type="number" value="0"></label>
    <label class="full">Traccia di riferimento<select id="youtubeImportRef"><option value="">Prima traccia disponibile</option>${refs}</select></label>
    <label class="full hint"><input id="youtubeImportRights" type="checkbox"> Confermo di essere autorizzato a scaricare/importare l'audio di questo contenuto.</label>
    <p class="hint full">Viene importato solo l'audio di un singolo video. Playlist non supportate. Il server deve poter raggiungere YouTube.</p>
    <div class="full modal-actions"><button onclick="closeUtilityModal()">Annulla</button><button class="accent" onclick="startYoutubeImport()">▶ Importa audio</button></div>
  </div>`;
  $('#utilityBackdrop').classList.remove('hidden');
  setTimeout(()=>$('#youtubeImportUrl')?.focus(),50);
}
async function startYoutubeImport(){
  if(!current)return;
  const url=String($('#youtubeImportUrl')?.value||'').trim();
  if(!url)return toast('Inserisci un URL YouTube');
  if(!$('#youtubeImportRights')?.checked)return toast('Devi confermare di disporre dei diritti necessari');
  const body={url,name:String($('#youtubeImportName')?.value||'').trim(),sync_mode:$('#youtubeImportSync')?.value||'manual',offset_ms:parseInt($('#youtubeImportOffset')?.value||'0')||0,reference_track_id:$('#youtubeImportRef')?.value||'',confirm_rights:true};
  try{
    await save();
    const job=await api(`/api/projects/${current.id}/youtube-import-jobs`,{method:'POST',body:JSON.stringify(body)});
    showMediaProgress('Import YouTube',job.progress,job.message,'Download ed estrazione della sola traccia audio.');
    pollMediaJob(job.id,'Import YouTube',async completed=>{
      current=await api(`/api/projects/${current.id}`);selectedTrackId=completed.result?.track_id||current.tracks.at(-1)?.id;render();await refresh();
      $('#utilityBackdrop').classList.add('hidden');toast(`Audio YouTube importato${current.tracks.length===1?` · BPM ${current.bpm}`:''}`);
    });
  }catch(e){toast(e.message)}
}
function focusImport(){$('#newTrackFile')?.click()}

function editProjectMeta(){if(!current)return;const title=prompt('Project title',current.title);if(title!==null&&title.trim())current.title=title.trim().slice(0,200);const originalTitle=prompt('Titolo originale',current.original_title||'');if(originalTitle!==null)current.original_title=originalTitle.trim().slice(0,300);const authors=prompt('Autori / compositori (separati da virgola)',(current.authors||[]).join(', '));if(authors!==null)current.authors=authors.split(/[,;]/).map(x=>x.trim()).filter(Boolean).slice(0,64);const artist=prompt('Interprete / artista',current.artist||'');if(artist!==null)current.artist=artist.slice(0,200);const key=prompt('Tonalità / Key',current.key||'');if(key!==null)current.key=key.trim().slice(0,40);const bpm=prompt('BPM',String(current.bpm));if(bpm!==null&&Number(bpm)>0)setProjectBpm(Math.min(300,Number(bpm)));render();markDirty()}
function downloadProjectLyrics(withChords=false){if(!current)return;if(!(current.lyrics||[]).length)return toast('Il progetto non contiene lyrics');if(withChords&&!(current.chords||[]).length)return toast('Il progetto non contiene chords');window.location.href=`/api/projects/${current.id}/lyrics.txt?chords=${withChords?'true':'false'}`}
function downloadProjectChordPro(){if(!current)return;if(!(current.lyrics||[]).length)return toast('Il progetto non contiene lyrics');if(!(current.chords||[]).length)return toast('Il progetto non contiene chords');window.location.href=`/api/projects/${current.id}/lyrics.chordpro`}
function lyricsPdfUrl(preview=false){const color=$('#lyricsPdfChordColor')?.value||'#7B1FA2';return `/api/projects/${current.id}/lyrics.pdf?chord_color=${encodeURIComponent(color)}${preview?'&preview=true':''}`}
function downloadProjectLyricsPdf(){if(!current)return;if(!(current.lyrics||[]).length)return toast('Il progetto non contiene lyrics');window.location.href=lyricsPdfUrl(false)}
function previewProjectLyricsPdf(){if(!current)return;if(!(current.lyrics||[]).length)return toast('Il progetto non contiene lyrics');const hasChords=!!(current.chords||[]).length,title=hasChords?'Anteprima PDF · Lyrics + Chords':'Anteprima PDF · Lyrics';showUtilityModal(title,`<div class="pdf-preview-wrap"><iframe class="pdf-preview-frame" src="${esc(lyricsPdfUrl(true))}" title="${esc(title)}"></iframe></div><div class="utility-actions pdf-preview-actions"><button class="utility-btn secondary" onclick="closeUtilityModal()">Chiudi</button><button class="utility-btn primary" onclick="downloadProjectLyricsPdf()">Scarica PDF ${hasChords?'Lyrics + Chords':'Lyrics'}</button></div>`)}
async function resetTimedData(kind){
  if(!current||!['lyrics','chords'].includes(kind))return;
  const label=kind==='lyrics'?'lyrics':'chords';
  if(!confirm(`Azzerare completamente ${label}? Potrai riscriverli o estrarli nuovamente.`))return;
  try{
    const result=await api(`/api/projects/${current.id}/${kind}/reset`,{method:'POST'});
    current[kind]=[];
    if(kind==='lyrics'){current.lyrics_engine=result.lyrics_engine||'';current.lyrics_model=result.lyrics_model||''}
    else{current.chords_engine=result.chords_engine||'';current.chords_model=result.chords_model||''}
    render();toast(`${kind==='lyrics'?'Lyrics':'Chords'} azzerati`);
  }catch(e){toast(e.message)}
}

let rightsCandidateRecords=[];
function rightsRecordKey(r){return `${r.society||''}|${r.uid||''}|${r.original_title||r.title||''}|${JSON.stringify(r.identifiers||{})}`}
function rightsRecordSummary(r){const ids=Object.entries(r.identifiers||{}).map(([k,v])=>`${k}: ${v}`).join(', ');return [r.title?`Titolo: ${r.title}`:'',r.original_title?`Titolo originale: ${r.original_title}`:'',(r.authors||[]).length?`Autori: ${(r.authors||[]).join(', ')}`:'',(r.performers||[]).length?`Interpreti: ${(r.performers||[]).join(', ')}`:'',(r.publishers||[]).length?`Editori: ${(r.publishers||[]).join(', ')}`:'',ids?`ID: ${ids}`:'',r.source_url?`Fonte: ${r.source_url}`:''].filter(Boolean).join(' · ')}
async function openRightsSearch(){
  if(!current)return;
  rightsCandidateRecords=[...(current.rights_records||[])];
  let catalog={providers:[{id:'SIAE',name:'SIAE',active_by_default:true},{id:'SOUNDREEF',name:'Soundreef',active_by_default:true}]};
  try{catalog=await api('/api/rights-providers')}catch(e){}
  const checks=(catalog.providers||[]).map(p=>`<label class="workflow-check"><input class="rights-provider-check" type="checkbox" value="${esc(p.id)}" ${(current.rights_societies||['SIAE','SOUNDREEF']).includes(p.id)?'checked':''}> ${esc(p.name)}${p.structured_search?'':' · portale ufficiale'}</label>`).join('');
  showUtilityModal('Ricerca repertorio / diritti',`<div class="stem-workflow">
    <div class="workflow-note">Ricerca usando i metadata del progetto. SIAE e Soundreef sono attivi per default. Lo stesso brano può avere registrazioni in più provider: tutte le registrazioni selezionate vengono conservate insieme nel progetto ed esportate integralmente sia nel PDF Lyrics + Chords sia nel ChordPro.</div>
    <label class="workflow-field"><span>Titolo</span><input id="rightsTitle" value="${esc(current.title||'')}"></label>
    <label class="workflow-field"><span>Titolo originale</span><input id="rightsOriginalTitle" value="${esc(current.original_title||'')}"></label>
    <label class="workflow-field"><span>Autori / compositori</span><input id="rightsAuthors" value="${esc((current.authors||[]).join(', '))}"></label>
    <label class="workflow-field"><span>Interprete / artista</span><input id="rightsArtist" value="${esc(current.artist||'')}"></label>
    <div>${checks}</div>
    <div class="utility-actions"><button class="utility-btn primary" onclick="performRightsSearch()">Cerca nei repertori</button><button class="utility-btn secondary" onclick="addManualRightsRecord()">Aggiungi risultato verificato</button></div>
    <div id="rightsProviderStatus"></div><div id="rightsResults"></div>
    <div class="utility-actions"><button class="utility-btn primary" onclick="saveRightsSelection()">Salva selezione nel progetto</button><button class="utility-btn secondary" onclick="closeUtilityModal()">Chiudi</button></div>
  </div>`);
  renderRightsCandidates();
}
function renderRightsCandidates(){
  const el=$('#rightsResults');if(!el)return;
  el.innerHTML=rightsCandidateRecords.length?`<div class="table-scroll"><table class="users-table"><thead><tr><th>Usa</th><th>Società</th><th>Opera</th><th>Dettagli</th></tr></thead><tbody>${rightsCandidateRecords.map((r,i)=>`<tr><td><input class="rights-result-check" type="checkbox" data-index="${i}" ${r._new===false?'checked':'checked'}></td><td>${esc(r.society||'')}</td><td><b>${esc(r.original_title||r.title||'—')}</b></td><td>${esc(rightsRecordSummary(r))}</td></tr>`).join('')}</tbody></table></div>`:'<p class="hint">Nessun risultato selezionato.</p>';
}
async function performRightsSearch(){
  if(!current)return;
  const societies=$$('.rights-provider-check:checked').map(x=>x.value);if(!societies.length)return toast('Seleziona almeno una società');
  try{
    const data=await api(`/api/projects/${current.id}/rights-search`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({societies,title:$('#rightsTitle')?.value||'',original_title:$('#rightsOriginalTitle')?.value||'',authors:$('#rightsAuthors')?.value||'',artist:$('#rightsArtist')?.value||''})});
    const existing=new Set(rightsCandidateRecords.map(rightsRecordKey));for(const r of data.results||[]){if(!existing.has(rightsRecordKey(r))){rightsCandidateRecords.push(r);existing.add(rightsRecordKey(r))}}
    $('#rightsProviderStatus').innerHTML=(data.providers||[]).map(p=>`<div class="workflow-note"><b>${esc(p.name||p.provider)}</b>: ${p.mode==='api'?'ricerca strutturata':'ricerca strutturata non configurata'}${p.message?` · ${esc(p.message)}`:''}${p.portal_url?` · <a href="${esc(p.portal_url)}" target="_blank" rel="noopener">Apri repertorio ufficiale</a>`:''}</div>`).join('');
    renderRightsCandidates();
  }catch(e){toast(e.message)}
}
function addManualRightsRecord(){
  const society=prompt('Società (es. SIAE o SOUNDREEF)','SIAE');if(!society)return;const title=prompt('Titolo originale / opera',$('#rightsOriginalTitle')?.value||$('#rightsTitle')?.value||'');if(!title)return;const authors=prompt('Autori / compositori',$('#rightsAuthors')?.value||'')||'';const performers=prompt('Interpreti',$('#rightsArtist')?.value||'')||'';const idType=prompt('Tipo identificativo (es. ISWC, IPI, WORK_ID)','ISWC')||'';const idValue=prompt('Valore identificativo','')||'';rightsCandidateRecords.push({uid:`${society.toUpperCase()}:manual:${Date.now()}`,society:society.toUpperCase(),title,original_title:title,authors:authors.split(/[,;]/).map(x=>x.trim()).filter(Boolean),performers:performers.split(/[,;]/).map(x=>x.trim()).filter(Boolean),publishers:[],identifiers:idType&&idValue?{[idType.toUpperCase()]:idValue}:{},source_url:''});renderRightsCandidates();
}
async function saveRightsSelection(){
  if(!current)return;
  const selected=$$('.rights-result-check:checked').map(x=>rightsCandidateRecords[Number(x.dataset.index)]).filter(Boolean);
  const societies=$$('.rights-provider-check:checked').map(x=>x.value);
  try{
    const d=await api(`/api/projects/${current.id}/rights-records`,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({records:selected,societies})});
    current.rights_records=d.rights_records||selected;
    current.rights_societies=d.rights_societies||societies;
    markDirty(50);toast('Dati repertorio salvati');showProjectInfo();
  }catch(e){toast(e.message)}
}
function openKaraokeExport(){
  if(!current)return;
  if(!(current.lyrics||[]).length)return toast('L’export MP4 richiede lyrics sincronizzate');
  showUtilityModal('Esporta MP4 Karaoke',`<div class="stem-workflow">
    <div class="workflow-note">Il video usa l’audio completo del progetto e le lyrics sincronizzate. Quando sono disponibili timestamp parola-per-parola, il testo viene evidenziato in stile karaoke.</div>
    <label class="workflow-check"><input id="karaokeIncludeChords" type="checkbox" ${(current.chords||[]).length?'checked':''} ${(current.chords||[]).length?'':'disabled'}> Mostra anche i chords sincronizzati sopra alle lyrics</label>
    <label class="workflow-field"><span>Background opzionale</span><input id="exportKaraokeBackground" type="file" accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp"></label>
    <div class="workflow-note">Senza immagine verrà usato uno sfondo nero. L’immagine viene adattata a 1920×1080 senza deformazioni.</div>
    <div class="utility-actions"><button class="utility-btn primary" onclick="startKaraokeExport()">Esporta MP4</button><button class="utility-btn secondary" onclick="closeUtilityModal()">Annulla</button></div>
  </div>`);
}
async function startKaraokeExport(){
  if(!current||(current.lyrics||[]).length)return toast('L’export MP4 richiede lyrics sincronizzate');
  const fd=new FormData(),bg=$('#exportKaraokeBackground')?.files?.[0];if(bg)fd.append('background',bg);
  try{
    await flushAutosave();
    const includeChords=!!$('#karaokeIncludeChords')?.checked;
    const job=await api(`/api/projects/${current.id}/karaoke-export-jobs?include_chords=${includeChords}`,{method:'POST',body:fd});
    showMediaProgress('Export MP4 Karaoke',job.progress,job.message);
    pollMediaJob(job.id,'Export MP4 Karaoke',async completed=>{
      const result=completed.result||{};
      if(isMobileClient())mobileSaveRemoteFile(result.download_url,result.filename||'karaoke.mp4','video/mp4',false);
      else await downloadWithProgress(result.download_url,result.filename||'karaoke.mp4','Export MP4 Karaoke');
      toast('MP4 karaoke esportato');
    });
  }catch(e){toast(e.message)}
}
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
  let nativeProjectPath=null;
  try{
    if(currentUser?.native_single_user){
      const bridge=await waitForNativeApi();
      if(!bridge?.choose_project_save_path){
        toast('Bridge nativo non disponibile: impossibile scegliere dove salvare il progetto importato.');
        return;
      }
      const suggested=(f.name||'progetto').replace(/\.(mta|mta8|mta16)$/i,'')||'progetto';
      const chosen=await bridge.choose_project_save_path(suggested);
      if(!chosen?.ok)return;
      nativeProjectPath=chosen.path;
    }
    const fd=new FormData();fd.append('file',f);
    showMediaProgress('Import MTA',1,'Preparazione upload');
    const job=await uploadWithProgress('/api/import-jobs',fd,'Import MTA');
    showMediaProgress('Import MTA',job.progress,job.message);
    pollMediaJob(job.id,'Import MTA',async completed=>{
      const projectId=completed.result.project_id;
      if(nativeProjectPath){
        const bridge=await waitForNativeApi();
        if(!bridge?.bind_project_path)throw new Error('Bridge nativo non disponibile durante il salvataggio del progetto importato');
        await bridge.bind_project_path(projectId,nativeProjectPath);
      }
      current=await api(`/api/projects/${projectId}`);
      selectedTrackId=current.tracks[0]?.id||null;
      render();await refresh();
      $('#utilityBackdrop').classList.add('hidden');
      toast(nativeProjectPath
        ?`MTA importato · ${completed.result.track_count} tracce · progetto salvato in ${nativeProjectPath}`
        :`MTA importato · ${completed.result.track_count} tracce`);
    });
  }catch(err){
    $('#utilityBackdrop').classList.add('hidden');
    toast('Import MTA fallito: '+err.message);
  }finally{
    e.target.value='';
  }
});
init();



function seSel(){if(!sampleEditor)return[0,0];let a=Math.round(Math.min(sampleEditor.a,sampleEditor.b)),b=Math.round(Math.max(sampleEditor.a,sampleEditor.b));if(b<=a){a=sampleEditor.viewStart;b=sampleEditor.viewEnd}return[a,b]}
function seDefaults(effect,preset){if(effect==='pitch')return{semitones:0,cents:0};if(effect==='autotune')return{key:(current?.key||'C').split(/\s+/)[0]||'C',scale:/min/i.test(current?.key||'')?'minor':'major',strength:preset==='hard'?1:preset==='gentle'?.45:.75};if(effect==='normalizer'){const x={streaming:[-14,-1],broadcast:[-23,-2],music:[-12,-1],gentle:[-16,-1.5]}[preset]||[-14,-1];return{target_lufs:x[0],true_peak_db:x[1]}}if(effect==='maximizer'){const x={gentle:[1.5,-1],balanced:[3,-1],loud:[6,-.8],live:[2,-1.5]}[preset]||[3,-1];return{drive_db:x[0],ceiling_db:x[1]}}if(effect==='eq32')return{gains:Array(32).fill(0)};return{}}
function seEffectHtml(){const e=sampleEditor.effect,p=sampleEditor.preset,q=sampleEditor.params||seDefaults(e,p),presets=sampleEditor.info.presets[e]||[];let f='';if(e==='pitch')f=`<div class="sample-param-grid"><label>Semitoni<input id="seSemi" type="number" min="-12" max="12" step="0.01" value="${q.semitones||0}" oninput="seParam()"></label><label>Centesimi<input id="seCents" type="number" min="-100" max="100" step="1" value="${q.cents||0}" oninput="seParam()"></label></div>`;if(e==='autotune')f=`<div class="sample-param-grid"><label>Tonalità<select id="seKey" onchange="seParam()">${['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'].map(x=>`<option ${x===q.key?'selected':''}>${x}</option>`).join('')}</select></label><label>Scala<select id="seScale" onchange="seParam()"><option value="major" ${q.scale==='major'?'selected':''}>Major</option><option value="minor" ${q.scale==='minor'?'selected':''}>Minor</option></select></label><label>Strength<input id="seStrength" type="range" min="0" max="1" step="0.05" value="${q.strength??.75}" oninput="seParam()"></label></div>`;if(e==='normalizer')f=`<div class="sample-param-grid"><label>Target LUFS<input id="seLufs" type="number" min="-30" max="-5" step="0.5" value="${q.target_lufs??-14}" oninput="seParam()"></label><label>True Peak dB<input id="sePeak" type="number" min="-6" max="-.1" step=".1" value="${q.true_peak_db??-1}" oninput="seParam()"></label></div>`;if(e==='maximizer')f=`<div class="sample-param-grid"><label>Drive dB<input id="seDrive" type="number" min="0" max="12" step=".1" value="${q.drive_db??3}" oninput="seParam()"></label><label>Ceiling dB<input id="seCeil" type="number" min="-6" max="-.1" step=".1" value="${q.ceiling_db??-1}" oninput="seParam()"></label></div>`;if(e==='eq32'){const bands=sampleEditor.info.eq_bands,g=q.gains||Array(32).fill(0);f=`<div class="sample-eq32">${bands.map((x,i)=>`<label><span>${x>=1000?(x/1000)+'k':x}</span><input class="seEq" type="range" min="-18" max="18" step=".5" value="${g[i]||0}" oninput="seParam()"><em>${Number(g[i]||0).toFixed(1)}</em></label>`).join('')}</div>`}return `<div class="sample-effect-head"><label>Processore<select id="seEffect" onchange="seEffectChange(this.value)"><option value="pitch" ${e==='pitch'?'selected':''}>Pitch correction</option><option value="autotune" ${e==='autotune'?'selected':''}>Auto-Tune</option><option value="normalizer" ${e==='normalizer'?'selected':''}>Normalizer</option><option value="maximizer" ${e==='maximizer'?'selected':''}>Maximizer</option><option value="eq32" ${e==='eq32'?'selected':''}>EQ grafico 32 bande</option></select></label><label>Preset<select id="sePreset" onchange="sePresetChange(this.value)">${presets.map(x=>`<option ${x===p?'selected':''}>${x}</option>`).join('')}</select></label></div>${f}<div class="sample-effect-actions"><button onclick="sePlayOriginal()">A · Originale</button><button onclick="sePreview(false)">B · Preview</button><button class="accent" onclick="seApply()">Applica in-place</button><span id="seStatus" class="hint"></span></div>`}
function seEffectChange(v){sampleEditor.effect=v;sampleEditor.preset=(sampleEditor.info.presets[v]||[])[0]||'default';sampleEditor.params=seDefaults(v,sampleEditor.preset);$('#sampleFx').innerHTML=seEffectHtml();seSchedule()}
function sePresetChange(v){sampleEditor.preset=v;sampleEditor.params=seDefaults(sampleEditor.effect,v);$('#sampleFx').innerHTML=seEffectHtml();seSchedule()}
function seParam(){const e=sampleEditor.effect,p={};if(e==='pitch'){p.semitones=Number($('#seSemi')?.value||0);p.cents=Number($('#seCents')?.value||0)}if(e==='autotune'){p.key=$('#seKey')?.value||'C';p.scale=$('#seScale')?.value||'major';p.strength=Number($('#seStrength')?.value||.75)}if(e==='normalizer'){p.target_lufs=Number($('#seLufs')?.value||-14);p.true_peak_db=Number($('#sePeak')?.value||-1)}if(e==='maximizer'){p.drive_db=Number($('#seDrive')?.value||3);p.ceiling_db=Number($('#seCeil')?.value||-1)}if(e==='eq32')p.gains=$$('.seEq').map(x=>{const v=Number(x.value);x.parentElement.querySelector('em').textContent=v.toFixed(1);return v});sampleEditor.params=p;seSchedule()}
function seReq(){const[a,b]=seSel();return{effect:sampleEditor.effect,start_sample:a,end_sample:b,preset:sampleEditor.preset,params:sampleEditor.params||{}}}
function seSchedule(){clearTimeout(sampleEditorPreviewTimer);sampleEditorPreviewTimer=setTimeout(()=>sePreview(true),350)}
async function sePreview(auto=false){if(sampleEditorPreviewAbort)sampleEditorPreviewAbort.abort();sampleEditorPreviewAbort=new AbortController();const st=$('#seStatus');if(st)st.textContent='Rendering…';try{const r=await fetch(`/api/projects/${current.id}/tracks/${sampleEditor.trackId}/sample-editor/effect-preview`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(seReq()),signal:sampleEditorPreviewAbort.signal});if(!r.ok)throw new Error(await r.text());const b=await r.blob();if(sampleEditor.preview)URL.revokeObjectURL(sampleEditor.preview);sampleEditor.preview=URL.createObjectURL(b);const a=$('#sampleAudio');if(a){a.src=sampleEditor.preview;if(!auto)await a.play().catch(()=>{})}if(st)st.textContent='Preview aggiornata'}catch(e){if(e.name!=='AbortError'&&st)st.textContent=e.message}}
function sePlayOriginal(){const a=$('#sampleAudio');if(a){a.src=sampleEditor.audioUrl;a.currentTime=seSel()[0]/sampleEditor.info.sample_rate;a.play().catch(()=>{})}}
async function seApply(){if(!confirm('Applicare il processing in-place alla selezione?'))return;const r=await api(`/api/projects/${current.id}/tracks/${sampleEditor.trackId}/sample-editor/effect-apply`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(seReq())});current=r.project;toast('Processing applicato');await openSampleEditor(sampleEditor.trackId,true)}
async function seEdit(action){const[a,b]=seSel();if(['cut','delete'].includes(action)&&!confirm(action==='cut'?'Tagliare la selezione?':'Rimuovere la selezione?'))return;const r=await api(`/api/projects/${current.id}/tracks/${sampleEditor.trackId}/sample-editor/edit`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action,start_sample:a,end_sample:b,cursor_sample:sampleEditor.cursor||a})});if(action==='copy')return toast('Campioni copiati');current=r.project;toast('Traccia aggiornata');await openSampleEditor(sampleEditor.trackId,true)}
function seEnvelope(buf,block=256){const out=[];for(let ch=0;ch<buf.numberOfChannels;ch++){const d=buf.getChannelData(ch),n=Math.ceil(d.length/block),mn=new Float32Array(n),mx=new Float32Array(n);for(let i=0;i<n;i++){let lo=1,hi=-1;for(let j=i*block;j<Math.min(d.length,(i+1)*block);j++){const v=d[j];if(v<lo)lo=v;if(v>hi)hi=v}mn[i]=lo;mx[i]=hi}out.push({mn,mx})}return{block,channels:out}}
function seDraw(){const s=sampleEditor,c=$('#sampleCanvas');if(!s||!c)return;const w=Math.max(300,c.clientWidth),h=Math.max(180,c.clientHeight),dpr=devicePixelRatio||1;c.width=Math.round(w*dpr);c.height=Math.round(h*dpr);const x=c.getContext('2d');x.setTransform(dpr,0,0,dpr,0,0);x.fillStyle='#07131d';x.fillRect(0,0,w,h);const span=s.viewEnd-s.viewStart,spp=span/w,e=s.env;x.strokeStyle='#47b8ff';x.beginPath();for(let px=0;px<w;px++){const a=Math.floor(s.viewStart+px*spp),b=Math.ceil(s.viewStart+(px+1)*spp);let lo=1,hi=-1;if(spp>=e.block*.75){for(const ch of e.channels)for(let i=Math.floor(a/e.block);i<Math.ceil(b/e.block)&&i<ch.mn.length;i++){lo=Math.min(lo,ch.mn[i]);hi=Math.max(hi,ch.mx[i])}}else{for(let ch=0;ch<s.buffer.numberOfChannels;ch++){const d=s.buffer.getChannelData(ch);for(let i=a;i<b&&i<d.length;i++){lo=Math.min(lo,d[i]);hi=Math.max(hi,d[i])}}}if(hi<lo)lo=hi=0;x.moveTo(px+.5,h/2-hi*h*.46);x.lineTo(px+.5,h/2-lo*h*.46)}x.stroke();const[a,b]=seSel(),sx=(a-s.viewStart)/span*w,ex=(b-s.viewStart)/span*w;x.fillStyle='rgba(68,170,255,.2)';x.fillRect(Math.max(0,sx),0,Math.max(1,Math.min(w,ex)-Math.max(0,sx)),h);$('#seStart').value=a;$('#seEnd').value=b;$('#seRead').textContent=`${(a/s.info.sample_rate).toFixed(6)}s → ${(b/s.info.sample_rate).toFixed(6)}s · ${(b-a).toLocaleString()} campioni`;$('#sePos').value=Math.round(s.viewStart)}
function seBind(){const c=$('#sampleCanvas'),at=e=>{const r=c.getBoundingClientRect();return Math.round(sampleEditor.viewStart+(e.clientX-r.left)/r.width*(sampleEditor.viewEnd-sampleEditor.viewStart))};let down=false;c.onpointerdown=e=>{down=true;c.setPointerCapture(e.pointerId);sampleEditor.a=sampleEditor.b=sampleEditor.cursor=at(e);seDraw()};c.onpointermove=e=>{if(down){sampleEditor.b=sampleEditor.cursor=at(e);seDraw()}};c.onpointerup=e=>{down=false;sampleEditor.b=sampleEditor.cursor=at(e);seDraw();seSchedule()};c.onwheel=e=>{e.preventDefault();const z=$('#seZoom');z.value=Math.max(0,Math.min(100,Number(z.value)+(e.deltaY<0?5:-5)));seZoom(z.value)}}
function seZoom(v){const s=sampleEditor,min=Math.max(128,Math.round(s.info.sample_rate*.004)),max=s.info.total_samples,span=Math.round(min*Math.pow(max/min,1-Number(v)/100)),center=(s.viewStart+s.viewEnd)/2;s.viewStart=Math.max(0,Math.min(max-span,Math.round(center-span/2)));s.viewEnd=s.viewStart+span;$('#sePos').max=Math.max(0,max-span);seDraw()}
function sePosition(v){const s=sampleEditor,span=s.viewEnd-s.viewStart;s.viewStart=Math.max(0,Math.min(s.info.total_samples-span,Number(v)||0));s.viewEnd=s.viewStart+span;seDraw()}
function seInputs(){sampleEditor.a=Math.max(0,Math.min(sampleEditor.info.total_samples,Number($('#seStart').value)||0));sampleEditor.b=Math.max(0,Math.min(sampleEditor.info.total_samples,Number($('#seEnd').value)||0));sampleEditor.cursor=sampleEditor.a;seDraw();seSchedule()}
async function openSampleEditor(trackId,reopen=false){try{if(!reopen)showUtilityModal('Editor waveform / campioni','<p class="hint">Preparazione audio…</p>');const info=await api(`/api/projects/${current.id}/tracks/${trackId}/sample-editor`),audioUrl=info.audio_url+'?v='+Date.now(),r=await fetch(audioUrl),ab=await r.arrayBuffer(),ctx=audioCtx||new(window.AudioContext||window.webkitAudioContext)();audioCtx=ctx;const buf=await ctx.decodeAudioData(ab.slice(0)),seconds=Math.max(.25,Math.min(buf.duration,Math.max(2,1100/Math.max(25,pxPerSec)))),span=Math.min(info.total_samples,Math.round(seconds*info.sample_rate));sampleEditor={trackId,info,buffer:buf,env:seEnvelope(buf),audioUrl,preview:null,viewStart:0,viewEnd:span,a:0,b:Math.min(span,info.sample_rate),cursor:0,effect:'pitch',preset:'subtle',params:seDefaults('pitch','subtle')};showUtilityModal(`Editor waveform / campioni · ${esc(info.name)}`,`<div class="sample-editor"><div class="sample-toolbar"><button onclick="seEdit('cut')">✂ Taglia</button><button onclick="seEdit('copy')">⧉ Copia</button><button onclick="seEdit('paste')">▣ Incolla</button><button class="danger" onclick="seEdit('delete')">⌫ Rimuovi</button><span class="sample-rate">${info.sample_rate.toLocaleString()} Hz · ${info.total_samples.toLocaleString()} campioni</span></div><canvas id="sampleCanvas" class="sample-editor-wave"></canvas><div class="sample-nav"><label>Zoom<input id="seZoom" type="range" min="0" max="100" value="42" oninput="seZoom(this.value)"></label><label>Posizione<input id="sePos" type="range" min="0" max="${Math.max(0,info.total_samples-span)}" value="0" oninput="sePosition(this.value)"></label></div><div class="sample-selection"><label>Campione iniziale<input id="seStart" type="number" onchange="seInputs()"></label><label>Campione finale<input id="seEnd" type="number" onchange="seInputs()"></label><strong id="seRead"></strong></div><audio id="sampleAudio" controls src="${audioUrl}"></audio><section id="sampleFx" class="sample-effect-panel">${seEffectHtml()}</section><p class="hint">La vista iniziale segue lo zoom della timeline; usa rotella/Zoom per arrivare al dettaglio dei campioni. Il processing è pre-insert e il commit crea una nuova sorgente solo per questa traccia.</p></div>`);seBind();seDraw()}catch(e){toast('Editor waveform: '+e.message)}}

function showUtilityModal(title,html,stemProgress=false){
  if(activeStemJob&&!stemProgress){
    toast('La separazione è in corso: la barra di progresso rimane visibile fino al completamento.');
    return;
  }
  $('#utilityTitle').textContent=title;$('#utilityBody').innerHTML=html;$('#utilityBackdrop').classList.remove('hidden');
}
function closeUtilityModal(){if(activeStemJob){toast('La separazione è in corso: usa Annulla separazione se vuoi interromperla.');return}$('#utilityBackdrop').classList.add('hidden');document.querySelector('.utility-modal')?.classList.remove('sample-editor-modal');sampleEditorState=null;clearTimeout(samplePreviewTimer);forceNativeViewportTop()}
function exportProjectArchive(){if(!current){toast('Apri prima un progetto');return}window.location.href=`/api/projects/${current.id}/archive`}
async function deleteCurrentProject(){if(!current){toast('Apri prima un progetto');return}await deleteProjectFromWorkspace(current.id,current.title)}
$('#projectArchiveFile').addEventListener('change',async e=>{const f=e.target.files[0];if(!f)return;const fd=new FormData();fd.append('file',f);try{current=await api('/api/project-archives/import',{method:'POST',body:fd});rememberRecentProject(current.id);selectedTrackId=current.tracks[0]?.id||null;resetProjectUiForOpen();render();await refresh();toast('Progetto completo importato')}catch(err){toast('Import progetto fallito: '+err.message)}finally{e.target.value=''}})
function projectDurationMs(){
  if(!current)return 0;
  let end=0;
  for(const t of current.tracks||[]){
    if(t.clips?.length){
      for(const c of t.clips)end=Math.max(end,Number(c.timeline_start_ms||0)+Math.max(0,Number(c.source_end_ms||0)-Number(c.source_start_ms||0)));
    }else end=Math.max(end,Number(t.duration_ms||0));
  }
  return end;
}
function formatProjectDuration(ms){
  const total=Math.max(0,Math.round(Number(ms)||0));
  const h=Math.floor(total/3600000),m=Math.floor((total%3600000)/60000),s=Math.floor((total%60000)/1000),x=total%1000;
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}.${String(x).padStart(3,'0')}`;
}
async function showProjectInfo(){
  if(!current)return toast('Apri prima un progetto');
  let location='Workspace server',home='Workspace applicativo';
  if(currentUser?.native_single_user){
    const bridge=await waitForNativeApi();
    if(bridge?.get_project_path){
      try{
        const info=await bridge.get_project_path(current.id);
        home=info?.home||'Application Support / MTA Audio Editor';
        location=info?.bound&&info?.path?info.path:'Workspace interno · file progetto non ancora associato';
      }catch(e){
        location='Workspace interno · locazione esterna non disponibile';
      }
    }
  }
  const duration=formatProjectDuration(projectDurationMs());
  const rows=[
    ['Nome',current.title||'—'],
    ['ID progetto',current.id||'—'],
    ['Home / workspace',home],
    ['Locazione',location],
    ['Tipo',current.target||'—'],
    ['Profilo MTA',current.mta_device_profile||'auto'],
    ['Durata',duration],
    ['Tracce',String((current.tracks||[]).length)],
    ['Titolo originale',current.original_title||'—'],
    ['Autori / compositori',(current.authors||[]).join(', ')||'—'],
    ['Artista / interprete',current.artist||'—'],
    ['Registrazioni repertorio',String((current.rights_records||[]).length)],
    ['BPM',Number(current.bpm||0).toFixed(1)],
    ['Tonalità',effectiveProjectKey()||'—'],
    ['Auto-save',autosaveEnabled?'Attivo':'Disattivato'],
  ];
  const rights=(current.rights_records||[]);
  const rightsRows=rights.length?`<h4>Dati repertorio / provider diritti</h4><div class="table-scroll"><table class="users-table"><thead><tr><th>Provider</th><th>Opera</th><th>Dati registrati</th></tr></thead><tbody>${rights.map(r=>`<tr><td><b>${esc(r.society||'—')}</b></td><td>${esc(r.original_title||r.title||'—')}</td><td>${esc(rightsRecordSummary(r))}</td></tr>`).join('')}</tbody></table></div>`:'<p class="hint">Nessun dato repertorio registrato nel progetto.</p>';
  showUtilityModal('Info progetto',`<div class="utility-actions"><button class="utility-btn" onclick="editProjectMeta();showProjectInfo()">Modifica titolo / autore / BPM e metadata</button><button class="utility-btn secondary" onclick="openRightsSearch()">Cerca repertorio autori</button></div><div class="table-scroll"><table class="users-table project-info-table"><tbody>${rows.map(([k,v])=>`<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join('')}</tbody></table></div>${rightsRows}`);
}
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

async function showSettings(){
  if(!currentUser){try{currentUser=await api('/api/session')}catch(e){return toast('Impossibile caricare la sessione: '+e.message)}}
  if(currentUser?.native_single_user)return showNativeSettings();
  return showWebSettings();
}
function showWebSettings(){
  const enabled=localStorage.getItem('mtaWebAutosaveEnabled')!=='false';
  showUtilityModal('Settings',`<div class="form-grid web-settings"><label class="workflow-check"><input id="webAutosaveEnabled" type="checkbox" ${enabled?'checked':''}> Auto-save project changes</label><p class="hint">Le preferenze dell'editor sono salvate in questo browser. I modelli AI della web app sono invece gestiti sul server.</p><div class="form-actions"><button type="button" onclick="openAiModelManager()">Manage Lyrics / Chords models</button><button type="button" onclick="location.href='/account'">Account / Profile</button>${currentUser?.role==='admin'?`<button type="button" onclick="location.href='/settings'">Server administration</button>`:''}<button class="accent" onclick="saveWebSettings()">Save</button></div></div>`);
}
function saveWebSettings(){const enabled=$('#webAutosaveEnabled')?.checked!==false;localStorage.setItem('mtaWebAutosaveEnabled',enabled?'true':'false');autosaveEnabled=enabled;if(autosaveEnabled&&projectDirty)markDirty(50);closeUtilityModal();toast('Settings salvati')}
async function showNativeSettings(){
  if(!currentUser?.native_single_user){if(currentUser?.role==='admin'){location.href='/settings';return}return}
  const apiBridge=await waitForNativeApi();
  if(!apiBridge?.get_native_settings){toast('Bridge nativo non disponibile. Riprova tra un istante.');return}
  try{
    const cfg=await apiBridge.get_native_settings();
    showUtilityModal('Settings',`<div class="form-grid native-settings"><label>Maximum import/upload size (MB)<input id="nativeMaxUploadMb" type="number" min="1" max="10240" step="1" value="${Number(cfg.max_upload_mb)||1024}"></label><label class="workflow-check"><input id="nativeAutosaveEnabled" type="checkbox" ${cfg.autosave_enabled!==false?'checked':''}> Auto-save project changes</label><label>Update channel<select id="nativeUpdateChannel"><option value="stable" ${cfg.update_channel!=='early'?'selected':''}>Stable · GitHub tags/releases only</option><option value="early" ${cfg.update_channel==='early'?'selected':''}>Early release · include latest main packages</option></select></label><p>Stable checks only tagged GitHub releases. Early release also checks the rolling <b>early-main</b> package produced from main.</p><div class="form-actions"><button type="button" onclick="checkNativeAppUpdate(true)">Check for updates</button><button type="button" onclick="openNativeModelManager()">Manage Demucs models</button><button type="button" onclick="openAiModelManager()">Manage Lyrics / Chords models</button><button class="accent" onclick="saveNativeSettings()">Save</button></div></div>`);
  }catch(err){toast('Impossibile leggere le impostazioni native: '+err.message)}
}
async function saveNativeSettings(){
  const value=Number($('#nativeMaxUploadMb')?.value);
  if(!Number.isInteger(value)||value<1||value>10240){toast('Inserisci un valore intero tra 1 e 10240 MB');return}
  try{
    const apiBridge=await waitForNativeApi();if(!apiBridge?.set_native_settings)return toast('Bridge nativo non disponibile');
    const enabled=$('#nativeAutosaveEnabled')?.checked!==false;const channel=$('#nativeUpdateChannel')?.value==='early'?'early':'stable';const result=await apiBridge.set_native_settings(value,enabled,channel);autosaveEnabled=result.autosave_enabled!==false;if(autosaveEnabled&&projectDirty)markDirty(50);
    closeUtilityModal();toast(`Limite import/upload impostato a ${result.max_upload_mb} MB`);
  }catch(err){toast('Salvataggio impostazioni fallito: '+err.message)}
}

async function checkNativeAppUpdate(manual=false){
  if(!currentUser?.native_single_user)return;
  const bridge=await waitForNativeApi();
  if(!bridge?.check_for_updates)return;
  try{
    const info=await bridge.check_for_updates();
    if(!info?.ok){if(manual)toast('Controllo aggiornamenti non riuscito: '+(info?.error||'errore sconosciuto'));return}
    if(!info.available){if(manual)toast(`MTA Audio Editor è aggiornato (${info.current_version})`);return}
    const channel=info.channel==='early'?'Early release':'Stable';
    showUtilityModal('Aggiornamento disponibile',`<div class="form-grid"><p><b>${esc(info.latest_version)}</b> è disponibile sul canale ${channel}. Versione installata: ${esc(info.current_version)}.</p><p>${info.asset_name?`Installer: <b>${esc(info.asset_name)}</b>`:'Apri la release GitHub per scegliere il pacchetto.'}</p><div class="form-actions"><button onclick="closeUtilityModal()">Più tardi</button><button class="accent" onclick="installNativeAppUpdate('${esc(info.asset_url)}','${esc(info.asset_name)}','${esc(info.release_url)}')">Aggiorna</button></div></div>`);
  }catch(err){if(manual)toast('Controllo aggiornamenti fallito: '+err.message)}
}
async function installNativeAppUpdate(assetUrl,assetName,releaseUrl){
  try{
    const bridge=await waitForNativeApi();
    if(assetUrl&&bridge?.install_update){toast('Download aggiornamento in corso…');await bridge.install_update(assetUrl,assetName);closeUtilityModal();return}
    if(releaseUrl)window.open(releaseUrl,'_blank','noopener');
  }catch(err){toast('Avvio aggiornamento fallito: '+err.message)}
}

function exposeNativeSettings(){
  const b=$('#nativeSettingsButton');if(b)b.hidden=false;
}
window.addEventListener('pywebviewready',exposeNativeSettings);

async function openAiModelManager(){try{const d=await api('/api/ai-models'),l=d.lyrics||{},c=d.chords||{};const lrows=(l.models||[]).map(m=>`<tr><td>${esc(m.display_name)}</td><td>OpenAI Whisper</td><td>${m.installed?'Installato':'On-demand'}</td><td><button onclick="manageAiModel('lyrics','${esc(m.id)}','download')">${m.installed?'Verifica / riscarica':'Scarica'}</button>${m.installed?` <button onclick="manageAiModel('lyrics','${esc(m.id)}','delete')">Elimina</button>`:''}</td></tr>`).join('');const crows=(c.models||[]).map(m=>`<tr><td>${esc(m.display_name)}</td><td>${esc(m.engine)}</td><td>${m.installed?'Installato':'On-demand'}</td><td><button onclick="manageAiModel('chords','${esc(m.id)}','download')">${m.installed?'Verifica / riscarica':'Scarica'}</button>${m.installed?` <button onclick="manageAiModel('chords','${esc(m.id)}','delete')">Elimina</button>`:''}<br><small>${esc(m.license||'')}</small></td></tr>`).join('');showUtilityModal(`AI models · ${d.storage==='local'?'locale':'server'}`,`<h3>Lyrics</h3><div class="table-scroll"><table><thead><tr><th>Modello</th><th>Motore</th><th>Stato</th><th>Azioni</th></tr></thead><tbody>${lrows}</tbody></table></div><h3>Chords</h3><div class="table-scroll"><table><thead><tr><th>Modello</th><th>Motore</th><th>Stato</th><th>Azioni</th></tr></thead><tbody>${crows}</tbody></table></div><p class="hint">Nella web app i modelli sono conservati sul server; nelle applicazioni native sono conservati localmente. I motori Chordino e MTA Chromagram non richiedono pesi AI.</p>`)}catch(e){toast(e.message)}}
async function manageAiModel(kind,id,action){try{await api(`/api/ai-models/${kind}/${encodeURIComponent(id)}${action==='delete'?'':'/download'}`,{method:action==='delete'?'DELETE':'POST'});pluginInfo=await api('/api/plugins');openAiModelManager()}catch(e){toast(e.message)}}
async function openNativeModelManager(){const b=await waitForNativeApi();if(!b?.list_local_models)return toast('Native model manager unavailable');try{const d=await b.list_local_models(),profiles=d.catalog?.model_profiles||[],local=new Set((d.local||[]).map(x=>x.id.replace(/\.server-model$/,'')));const rows=profiles.map(p=>`<tr><td>${esc(p.display_name||p.model)}</td><td>${p.stem_count||'—'}</td><td>${local.has(p.model)?'Installed':'On demand'}</td><td><button onclick="nativeModelUpdate('${esc(p.model)}')">${local.has(p.model)?'Force update':'Download'}</button>${local.has(p.model)?` <button onclick="nativeModelDelete('${esc(p.model)}')">Delete local</button>`:''}</td></tr>`).join('');showUtilityModal('Demucs models',`<div class="table-scroll"><table><thead><tr><th>Model</th><th>Stems</th><th>Local</th><th>Actions</th></tr></thead><tbody>${rows}</tbody></table></div><p>Missing models are downloaded automatically when requested for splitting.</p>`) }catch(e){toast(e.message)}}
async function nativeModelUpdate(id){const b=await waitForNativeApi();try{await b.update_local_model(id);toast('Model updated: '+id);openNativeModelManager()}catch(e){toast(e.message)}}
async function nativeModelDelete(id){const b=await waitForNativeApi();try{await b.delete_local_model(id);toast('Local model deleted: '+id);openNativeModelManager()}catch(e){toast(e.message)}}
