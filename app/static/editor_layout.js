/* r210: identity-scoped toolbar layout, compact controls and floating AI monitor. */
(() => {
'use strict';
let prefs={rows:[]}, ready=false, saving=Promise.resolve(), frame=0, draft=null, layoutDraftRows=null, items=new Map(), drag=null;
const text=(en,it)=>window.MtaLocale?.language==='it'?it:en;
const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const svg=path=>`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${path}"/></svg>`;
const shapes={
 audioCaptureOpen:'M8 6a4 4 0 0 1 8 0v6a4 4 0 0 1-8 0zM5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8',
 renderBtn:'M4 5h16v14H4z M8 9h8M8 13h5', followBtn:'M4 12h16m-5-5 5 5-5 5M4 5v14',
 toolSelect:'m6 3 12 9-7 1-3 7z',toolSplit:'M8 8 20 20M8 16 20 4M6 4a3 3 0 1 0 0 6 3 3 0 0 0 0-6M6 14a3 3 0 1 0 0 6 3 3 0 0 0 0-6',
 toolRange:'M4 4v16M20 4v16M4 7h16M4 17h16',toolRipple:'M3 12h18M7 8l-4 4 4 4m10-8 4 4-4 4',
 trimLeft:'M4 4v16m15-14L9 12l10 6',trimRight:'M20 4v16M5 6l10 6-10 6',fade:'M3 19 9 5h6l6 14',
 separate:'M4 4h5v5H4zm11 0h5v5h-5zM4 15h5v5H4zm11 0h5v5h-5zM9 7l6 10M9 17l6-10',
 youtube:'M3 5h18v14H3zm7 3 6 4-6 4z',metronome:'m6 20 4-16h4l4 16zm6-7 6-9M4 20h16',
 grid:'M4 4h16v16H4zM4 10h16M10 4v16',chords:'M3 6h18v13H3zM7 6v8m5-8v8m5-8v8',
 magnet:'M5 4v10a7 7 0 0 0 14 0V4h-4v10a3 3 0 0 1-6 0V4z',
 delete:'M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 9v9m4-9v9',
 cut:'M8 8 20 20M8 16 20 4M3 5h5v5H3zM3 15h5v5H3z',copy:'M8 8h12v13H8zM16 8V3H3v13h5',paste:'M8 4H5v17h14V4h-3M8 3h8v4H8z',
 undo:'m9 4-6 5 6 5M3 9h10a7 7 0 0 1 7 7v4',redo:'m15 4 6 5-6 5m6-5H11a7 7 0 0 0-7 7v4',
 bounce:'M3 4h12v9H3zM9 13v7m-4-4 4 4 4-4M17 4h4v16h-4',
 settings:'M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6m-6 0v6',
 save:'M4 3h13l4 4v14H3V3h1m3 0v6h10V3M7 21v-8h10v8',
 folder:'M3 7h7l2-3h8v16H3z',new:'M12 4v16M4 12h16',account:'M4 21v-3a8 8 0 0 1 16 0v3M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8',
 logout:'M9 3H3v18h6m4-14 5 5-5 5m-6-5h12',shift:'M3 12h18m-5-5 5 5-5 5M3 4v16',tap:'M9 19V4l10-2v13M3 19h6m4-4h6'
};
function pathFor(node){
 const action=node.getAttribute('onclick')||'';
 if(shapes[node.id])return shapes[node.id];
 const map=[['trimProjectTimeline(\'left', 'trimLeft'],['trimProjectTimeline(\'right','trimRight'],['Fade','fade'],['Stem','separate'],['Youtube','youtube'],['MetronomeGrid','grid'],['MetronomeShift','shift'],['Metronome','metronome'],['ChordsTrack','chords'],['timeline_magnetic','magnet'],['deleteSelection','delete'],['removeTimeline','delete'],['cutTimeline','cut'],['copyTimeline','copy'],['pasteTimeline','paste'],['undoEdit','undo'],['redoEdit','redo'],['bounceToTrack','bounce'],['tapProject','tap'],['showProjectSetup','settings'],['openAiRemix','chords'],['openExport','bounce'],['saveAs','save'],['save()','save'],['newProject','new'],['openProject','folder']];
 for(const [needle,name] of map)if(action.includes(needle))return shapes[name];
 if(node.matches('a[href="/account"]'))return shapes.account;
 if(node.matches('a[href="/settings"]'))return shapes.settings;
 if(node.matches('a[href="/logout"]'))return shapes.logout;
 return null;
}
function iconOnly(node){
 const path=pathFor(node);
 if(path){if(node.dataset.layoutIcon!==path||!node.querySelector('svg')){node.dataset.layoutIcon=path;node.innerHTML=svg(path)}}
 // Existing symbols/SVG remain valid icons. Text labels are never removed from
 // accessibility: preserve the original tooltip and aria-label before painting.
 node.classList.add('layout-icon-only');
}
function hash(value){let n=2166136261;for(const c of value)n=Math.imul(n^c.charCodeAt(0),16777619);return (n>>>0).toString(36)}
function register(scope,bar){
 if(!scope)return;
 const selector=bar==='header'?'.transport>button,.header-actions>button,.header-actions>a,.app-github-mark,#headerProjectName,.timebox,.transport-seek-box,.zoom-top,.layout-config-button':':scope>button,:scope>.toolbar-group,:scope>.selected-track-count,:scope>.selection-info,.toolbar-destructive-group>button';
 let count=0;
 for(const node of scope.querySelectorAll(selector)){
  if(node.closest('.layout-row-break'))continue;
  const key=node.dataset.layoutId||`${bar}_${node.id||hash(node.getAttribute('onclick')||node.getAttribute('href')||node.querySelector('select[id],input[id]')?.id||node.className+'_'+count)}`;
  node.dataset.layoutId=key;count++;
  const groupNames={timebox:text('Position, BPM, meter and pitch','Posizione, BPM, misura e tonalità'),'transport-seek-box':text('Project position','Posizione progetto'),'zoom-top':text('Timeline zoom','Zoom timeline')};
  const groupName=Object.keys(groupNames).find(k=>node.classList.contains(k));
  const name=(groupName?groupNames[groupName]:node.querySelector('#timelineSnap')?'Snap':node.querySelector('#newSync')?text('Import alignment options','Allineamento importazione'):null)||node.dataset.layoutLabel||node.getAttribute('title')||node.getAttribute('aria-label')||node.textContent.trim();
  node.dataset.layoutLabel=name;
  if(node.matches('button,a')){node.title=node.title||name;node.setAttribute('aria-label',node.getAttribute('aria-label')||name);iconOnly(node)}
  items.set(key,{key,bar,node,label:name});
 }
 const relevant=[...items.values()].filter(i=>i.bar===bar&&i.node.isConnected);
 const signature=JSON.stringify(prefs.rows)+'|'+relevant.map(i=>i.key).join(',');
 if(scope.dataset.layoutApplied===signature)return;
 scope.dataset.layoutApplied=signature;
 scope.querySelectorAll(':scope>.layout-row-break').forEach(n=>n.remove());
 const seen=new Set();let order=0,nonempty=0;
 for(const row of prefs.rows){
  const rowItems=row.map(k=>items.get(k)).filter(i=>i&&i.bar===bar&&i.node.isConnected);
  if(!rowItems.length)continue;
  if(nonempty++){const br=document.createElement('div');br.className='layout-row-break';br.style.order=String(order++);br.setAttribute('aria-hidden','true');scope.append(br)}
  for(const i of rowItems){i.node.style.order=String(order++);seen.add(i.key)}
 }
 for(const i of relevant)if(!seen.has(i.key))i.node.style.order=String(order++);
}
function compactNumbers(){
 for(const input of document.querySelectorAll('#transportBpmInput,#transportPitchInput,#newOffset,#youtubeImportOffset,input.track-delay-input[type=number]')){
  if(input.closest('.compact-number'))continue;
  const wrap=document.createElement('span');wrap.className='compact-number';input.before(wrap);wrap.append(input);
  const steps=document.createElement('span');steps.className='compact-number-steps';wrap.append(steps);
  for(const [symbol,direction] of [['+',1],['−',-1]]){
   const button=document.createElement('button');button.type='button';button.textContent=symbol;button.title=text(direction>0?'Increase':'Decrease',direction>0?'Aumenta':'Diminuisci')+' · '+(input.title||input.getAttribute('aria-label')||input.id);button.setAttribute('aria-label',button.title);
   button.onclick=e=>{e.stopPropagation();try{direction>0?input.stepUp():input.stepDown();input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}))}catch(_){}};steps.append(button);
  }
 }
}
function clampMenu(menu){
 if(!menu.isConnected)return;
 const vp=window.visualViewport,pad=8,left=vp?.offsetLeft||0,top=vp?.offsetTop||0,width=vp?.width||innerWidth,height=vp?.height||innerHeight;
 menu.style.maxHeight=Math.max(48,height-pad*2)+'px';menu.style.maxWidth=Math.max(80,width-pad*2)+'px';
 const box=menu.getBoundingClientRect();menu.style.left=Math.max(left+pad,Math.min(box.left,left+width-box.width-pad))+'px';menu.style.top=Math.max(top+pad,Math.min(box.top,top+height-box.height-pad))+'px';
}
const menus=new WeakSet();
function watchMenus(){for(const menu of document.querySelectorAll('.track-context-menu,.lc-context-menu,.meta-context-menu')){
 if(!menus.has(menu)){menus.add(menu);menu.addEventListener('toggle',e=>{clampMenu(menu);if(e.target.open)requestAnimationFrame(()=>{clampMenu(menu);e.target.querySelector('summary')?.scrollIntoView({block:'nearest'})})},true);new ResizeObserver(()=>clampMenu(menu)).observe(menu)}clampMenu(menu);
}}
function schedule(){if(!frame)frame=requestAnimationFrame(()=>{frame=0;refresh()})}
function refresh(){
 register(document.querySelector('.topbar'),'header');register(document.querySelector('.editor-toolbar'),'editor');
 compactNumbers();watchMenus();attachMonitor();
}
async function persist(){const snapshot=JSON.parse(JSON.stringify(prefs));saving=saving.catch(()=>{}).then(async()=>{const response=await fetch('/api/account/editor-layout',{method:'PUT',headers:{'content-type':'application/json','X-MTA-Request':'1'},body:JSON.stringify(snapshot)});if(!response.ok)throw Error(text('Cannot save layout','Impossibile salvare il layout'));});try{await saving}catch(e){window.toast?.(e.message);throw e}}
function monitorPosition(){
 const launch=document.getElementById('aj-launch');if(!launch)return;
 const handle=document.getElementById('aj-drag');if(!handle)return;
 const box=launch.getBoundingClientRect(),total=box.width+handle.offsetWidth+4,spaceX=Math.max(0,innerWidth-total-16),spaceY=Math.max(0,innerHeight-box.height-16),p=prefs.job_position;
 // The neutral default is the sidebar footer, away from faders and transport.
 const neutral=document.querySelector('.sidebar nav')?.getBoundingClientRect().bottom;
 const x=8+(p?p.x*spaceX:0),y=p?8+p.y*spaceY:Math.max(8,Math.min(8+spaceY,neutral?neutral+20:8+spaceY));
 launch.style.setProperty('left',(x+handle.offsetWidth+4)+'px');launch.style.setProperty('top',y+'px');launch.style.right='auto';launch.style.bottom='auto';
 handle.style.left=x+'px';handle.style.top=y+'px';
}
function attachMonitor(){
 const launch=document.getElementById('aj-launch');if(!ready||!launch)return;
 if(!document.getElementById('aj-drag')){
  const handle=document.createElement('button');handle.id='aj-drag';handle.className='aj-drag';handle.type='button';handle.textContent='⠿';handle.title=text('Move AI monitor · arrows to move, Home to reset','Sposta monitor AI · frecce per muovere, Home per ripristinare');handle.setAttribute('aria-label',handle.title);launch.before(handle);
  handle.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();handle.setPointerCapture(e.pointerId);const r=handle.getBoundingClientRect();drag={dx:e.clientX-r.left,dy:e.clientY-r.top}};
  handle.onpointermove=e=>{if(!drag)return;const width=launch.offsetWidth+handle.offsetWidth+4,height=launch.offsetHeight;prefs.job_position={x:Math.max(0,Math.min(1,(e.clientX-drag.dx-8)/Math.max(1,innerWidth-width-16))),y:Math.max(0,Math.min(1,(e.clientY-drag.dy-8)/Math.max(1,innerHeight-height-16)))};monitorPosition()};
  new ResizeObserver(monitorPosition).observe(launch);
  handle.onpointerup=()=>{if(!drag)return;drag=null;void persist().catch(()=>{})};handle.onpointercancel=()=>{drag=null;void persist().catch(()=>{})};
  handle.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home'].includes(e.key))return;e.preventDefault();if(e.key==='Home')delete prefs.job_position;else{const r=handle.getBoundingClientRect(),p=prefs.job_position||{x:(r.left-8)/Math.max(1,innerWidth-launch.offsetWidth-handle.offsetWidth-20),y:(r.top-8)/Math.max(1,innerHeight-launch.offsetHeight-16)};prefs.job_position={x:Math.max(0,Math.min(1,p.x+(e.key==='ArrowRight'?.02:e.key==='ArrowLeft'?-.02:0))),y:Math.max(0,Math.min(1,p.y+(e.key==='ArrowDown'?.02:e.key==='ArrowUp'?-.02:0)))}}monitorPosition();void persist().catch(()=>{})};
 }
 monitorPosition();
}
function configRows(bar){
 const source=layoutDraftRows||prefs.rows;const sorted=[];for(const row of source)for(const key of row)if(items.get(key)?.bar===bar&&items.get(key).node.isConnected)sorted.push(key);
 for(const i of items.values())if(i.bar===bar&&i.node.isConnected&&!sorted.includes(i.key))sorted.push(i.key);
 return sorted.map(key=>({key,row:Math.max(0,source.findIndex(r=>r.includes(key)))}));
}
function drawConfig(bar){
 draft={bar,entries:configRows(bar)};paintConfig();
}
function paintConfig(){
 const host=document.getElementById('layout-items');if(!host)return;
 host.innerHTML=draft.entries.map((entry,index)=>`<div class="layout-edit-item" draggable="true" data-layout-index="${index}"><span class="layout-drag-mark" aria-hidden="true">⠿</span><span>${escape(items.get(entry.key).label)}</span><button type="button" data-move="-1" data-index="${index}" ${!index?'disabled':''} aria-label="${text('Move up','Sposta su')}">↑</button><button type="button" data-move="1" data-index="${index}" ${index===draft.entries.length-1?'disabled':''} aria-label="${text('Move down','Sposta giù')}">↓</button><label>${text('Row','Riga')} <select data-row="${index}">${[0,1,2,3,4,5].map(n=>`<option value="${n}" ${entry.row===n?'selected':''}>${n+1}</option>`).join('')}</select></label></div>`).join('');
}
function configure(){
 if(!ready)return window.toast?.(text('Loading layout preferences…','Caricamento preferenze del layout…'));
 refresh();layoutDraftRows=JSON.parse(JSON.stringify(prefs.rows));window.showUtilityModal(text('Toolbar layout','Organizza barra strumenti'),`<div class="layout-config"><p>${text('Drag items or use arrows; choose a row for each item. The window wraps rows when needed. Layout follows your server account, or this native installation.','Trascina gli elementi o usa le frecce; scegli la riga per ogni elemento. Le righe vanno a capo quando necessario. Il layout segue l’account sul server oppure questa installazione nativa.')}</p><label>${text('Toolbar','Barra')} <select id="layout-bar"><option value="header">${text('Transport and project','Transport e progetto')}</option><option value="editor">${text('Editing tools','Strumenti di editing')}</option></select></label><div id="layout-items"></div><div class="form-actions"><button id="layout-reset">${text('Restore defaults','Ripristina default')}</button><button id="layout-save" class="primary">${text('Save layout','Salva layout')}</button></div></div>`);
 const host=document.getElementById('layout-items');let draggingIndex=null;
 host.onclick=e=>{const b=e.target.closest('[data-move]');if(!b)return;const from=Number(b.dataset.index),to=from+Number(b.dataset.move);[draft.entries[from],draft.entries[to]]=[draft.entries[to],draft.entries[from]];paintConfig()};
 host.onchange=e=>{if(e.target.dataset.row!==undefined)draft.entries[Number(e.target.dataset.row)].row=Number(e.target.value)};
 host.ondragstart=e=>{const row=e.target.closest('[data-layout-index]');draggingIndex=Number(row.dataset.layoutIndex);e.dataTransfer.setData('text/plain',String(draggingIndex));e.dataTransfer.effectAllowed='move'};
 host.ondragover=e=>e.preventDefault();host.ondrop=e=>{e.preventDefault();const row=e.target.closest('[data-layout-index]');if(row&&draggingIndex!==null){const [entry]=draft.entries.splice(draggingIndex,1);draft.entries.splice(Number(row.dataset.layoutIndex),0,entry);paintConfig()}draggingIndex=null};
 const commitDraft=()=>{const keys=new Set(draft.entries.map(e=>e.key));const rows=Array.from({length:6},(_,index)=>(layoutDraftRows[index]||[]).filter(key=>!keys.has(key)));for(const entry of draft.entries)rows[entry.row].push(entry.key);while(rows.length&&!rows.at(-1).length)rows.pop();layoutDraftRows=rows};
 document.getElementById('layout-bar').onchange=e=>{commitDraft();drawConfig(e.target.value)};
 document.getElementById('layout-save').onclick=async()=>{commitDraft();prefs.rows=layoutDraftRows;try{await persist();refresh();window.closeUtilityModal()}catch(_){}};
 document.getElementById('layout-reset').onclick=async()=>{prefs={rows:[]};try{await persist();refresh();window.closeUtilityModal()}catch(_){}};drawConfig('header');
}
function audioPublished(data){
 const project=data?.project||data;if(!window.current&&typeof current==='undefined')return;
 if(!project?.id||!Array.isArray(project.tracks)||typeof current==='undefined'||current?.id!==project.id)return;
 const changed=project.tracks.filter(t=>t.type==='click'&&t.waveform_revision&&t.waveform_revision!==current.tracks.find(x=>x.id===t.id)?.waveform_revision).map(t=>t.id);
 if(changed.length)setTimeout(()=>{if(current?.id===project.id){window.timingAudioChanged(changed);window.render?.()}},0);
}
window.MtaEditorLayout={configure,audioPublished,refresh};
async function init(){
 if(ready)return;
 const bar=document.querySelector('.topbar');
 if(!document.querySelector('link[href*="editor_layout.css"]')){const css=document.createElement('link');css.rel='stylesheet';css.href='/static/editor_layout.css?v=0.3.0-r210-zones-layout';document.head.append(css)}
 if(bar){
 const button=document.createElement('button');button.className='layout-config-button';button.disabled=true;button.title=text('Toolbar layout','Organizza barra strumenti');button.setAttribute('aria-label',button.title);button.innerHTML=svg(shapes.settings);button.onclick=configure;bar.append(button);}
 register(bar,'header');register(document.querySelector('.editor-toolbar'),'editor');compactNumbers();watchMenus();
 new MutationObserver(changes=>{const selector='.topbar,.editor-toolbar,.track-context-menu,.lc-context-menu,.meta-context-menu,#mta-ai-job-center,input[type=number]';for(const change of changes){if(change.target.matches?.('#renderBtn,#followBtn,#audioCaptureOpen')){schedule();break}if([...change.addedNodes].some(n=>n.nodeType===1&&(n.matches?.(selector)||n.querySelector?.(selector)))){schedule();break}}}).observe(document.body,{childList:true,subtree:true});
 const controller=typeof AbortController==='function'?new AbortController():null,timeout=controller?setTimeout(()=>controller.abort(),6000):null;
 try{const response=await fetch('/api/account/editor-layout',controller?{signal:controller.signal}:{});if(!response.ok)throw Error();prefs=await response.json()}catch(_){prefs={rows:[]}}finally{clearTimeout(timeout)}
 ready=true;const configureButton=document.querySelector('.layout-config-button');if(configureButton)configureButton.disabled=false;document.body.classList.add('editor-layout-ready');refresh();

 if(bar)new ResizeObserver(()=>{document.documentElement.style.setProperty('--mta-topbar-height',bar.getBoundingClientRect().height+'px');monitorPosition()}).observe(bar);
 window.addEventListener('resize',()=>{schedule();monitorPosition()});window.visualViewport?.addEventListener('resize',schedule);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else void init();
})();
