
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
const DEFAULT_ZOOM_PX_PER_SEC=70,MIN_ZOOM_PX_PER_SEC=25,MAX_ZOOM_PX_PER_SEC=1200;
let zoomPreviewState=null;
let sel={a:0,b:0}, dragging=false, audioCtx=null, playAudio=null, selectedTrackId=null, exportFormat='mta';
let selectedTrackIdSet=new Set(), timelineTool='range', rippleEnabled=false, timelineClipDrag=null;
let autosaveTimer=null, autosaveBusy=false, autosaveQueued=false, autosaveEnabled=true, projectDirty=false, stemPollTimer=null, activeStemJob=null, activeStemProjectId=null;
let lyricsPdfPreviewObjectUrl=null;
let nativeRecentProjects=[];
let preferredStemCount=Number(localStorage.getItem('mtaStemCount')||0);if(preferredStemCount!==0&&(preferredStemCount<2||preferredStemCount>64))preferredStemCount=0;
function setPreferredStemCount(value){const n=Number(value||0);preferredStemCount=(n===0||(n>=2&&n<=64))?n:0;localStorage.setItem('mtaStemCount',String(preferredStemCount));}
let preferredStemExecution=localStorage.getItem('mtaStemExecution')||'auto';if(!['auto','local','server'].includes(preferredStemExecution))preferredStemExecution='auto';
function setPreferredStemExecution(value){preferredStemExecution=['auto','local','server'].includes(value)?value:'auto';localStorage.setItem('mtaStemExecution',preferredStemExecution);}
let undoStack=[],redoStack=[],historyProjectId=null,lastHistoryState=null,timelineClipboard=null;
let playCursorMs=0, playRaf=null, mediaProgressTimer=null;
let uiState={trackTop:0,timelineTop:0,timelineLeft:0,mixerLeft:0};
let mixerResizeState=null;
let waveformJobs={}, waveformValidationProjectId=null, trackPlaybacks=[], meterRaf=null, meterRunToken=0, playbackToken=0, masterMeterAnalysers=null, masterPlaybackGainNode=null;
let renderedMasterPlayback=false, renderedStemPlayback=false, renderedMasterDirty=false, renderedMasterRefreshPromise=null, renderedMasterRefreshQueued=false, renderedMasterBaseVolumeDb=0, renderedMasterAudio=null;
let dynamicSyncClock=null, dynamicSyncTimer=null, playbackBuffering=false;
let transportClockStartCtx=0, transportClockCursorMs=0, transportClockRunning=false;
let playbackWarmCache=new Map(), playbackWarmProjectId=null, playbackWarmSignature='', playbackWarmTimer=null;
const liveFxRefreshTimers={};
let lastSelectedAudioFile=null, playbackPaused=false, mixerMetaTab='lyrics', pendingExportConfig=null, pendingNewProjectPath=null;
let sampleEditor=null,sampleEditorPreviewAbort=null,sampleEditorPreviewTimer=null,serverProjects=[];
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const TRACK_COLORS=['#2f81f7','#28b463','#f0a52b','#8a58db','#e9506c','#8395a7','#24b8d4','#b26ff2','#e67e22','#16a085','#d35400','#7f8c8d'];

const UI_TEXT_PAIRS=[
['Project','Progetto'],['No project loaded','Nessun progetto caricato'],['New project','Nuovo progetto'],['Open project','Apri progetto'],['Open recent','Apri recenti'],['Close project','Chiudi progetto'],['Delete project','Elimina progetto'],['Project files','File progetto'],['Share project','Condividi progetto'],['Info progetto','Info progetto'],['Save','Salva'],['Save as','Salva con nome'],['Save project','Salva progetto'],['Save project as…','Salva progetto con nome…'],['Save project locally','Salva progetto localmente'],['Open local project','Apri progetto locale'],['Open recent','Apri recenti'],['Export','Esporta'],['Settings','Impostazioni'],['About','Informazioni'],['Docs & Help','Documentazione e aiuto'],['Account','Account'],['Esci','Esci'],['Tracks','Tracce'],['Mixer','Mixer'],['Plugins','Plugin'],['Lyrics','Testo'],['Chords','Accordi'],['Markers','Marker'],['Select','Seleziona'],['Split','Dividi'],['Range','Intervallo'],['Ripple','Ripple'],['Bars','Battute'],['Beats','Quarti'],['Off','Disattivato'],['Import Audio Track','Importa traccia audio'],['Import Audio','Importa audio'],['Import YouTube','Importa YouTube'],['Import & Separate','Importa e separa'],['Metronomo','Metronomo'],['Undo','Annulla'],['Redo','Ripristina'],['Cut','Taglia'],['Copy','Copia'],['Paste','Incolla'],['Remove','Rimuovi'],['Delete tracks','Elimina tracce'],['Delete selected range','Elimina intervallo selezionato'],['Show Lyrics','Mostra testo'],['Show Chords','Mostra accordi'],['Follow','Segui'],['Render','Render'],['Setup','Impostazioni progetto'],['Maximum import/upload size (MB)','Dimensione massima import/upload (MB)'],['Auto-save project changes','Salvataggio automatico modifiche progetto'],['Show previous and next chords','Mostra accordo precedente e successivo'],['Show previous and next lyrics','Mostra testo precedente e successivo'],['Update channel','Canale aggiornamenti'],['Stable · GitHub tags/releases only','Stabile · solo tag/release GitHub'],['Early release · include latest main packages','Early release · include gli ultimi pacchetti main'],['Check for updates','Controlla aggiornamenti'],['Manage Demucs models','Gestisci modelli Demucs'],['Manage Lyrics / Chords models','Gestisci modelli Lyrics / Chords'],['Cancel','Annulla'],['Annulla','Annulla'],['Apply','Applica'],['Applica','Applica'],['Reset','Ripristina'],['Ripristina','Ripristina'],['Normal','Normale'],['Bold','Grassetto'],['Italic','Corsivo'],['Title','Titolo'],['Subtitle','Sottotitolo'],['BPM','BPM'],['Time signature','Metrica'],['Artist / performer','Artista / interprete'],['Original title','Titolo originale'],['Authors / composers','Autori / compositori'],['Key','Tonalità'],['Project type','Tipo progetto'],['MTA profile','Profilo MTA'],['Rights societies','Società repertorio'],['Edit project metadata','Modifica metadata progetto'],['Save project manually','Salva progetto manualmente'],['Check for updates','Controlla aggiornamenti'],['Language','Lingua'],['Auto (system)','Auto (sistema)'],['Italian','Italiano'],['English','Inglese'],['selected','selezionate'],['TRACKS','TRACCE'],['Inspector','Inspector'],['Stems','Stem'],['Metadata','Metadata'],['Volume','Volume'],['Pan','Pan'],['Type','Tipo'],['Replace','Sostituisci'],['Track export','Export traccia'],['Advanced','Avanzate'],['Send','Send'],['Track Automation','Automazione traccia'],['Rinomina','Rinomina'],['Separa','Separa'],['Estrai lyrics','Estrai testo'],['Estrai chords','Estrai accordi'],['Sincronizza metronomo','Sincronizza metronomo'],['Delay / anticipo traccia…','Ritardo / anticipo traccia…'],['Modifica metadata progetto','Modifica metadata progetto'],['Titolo','Titolo'],['Titolo originale','Titolo originale'],['Autori / compositori','Autori / compositori'],['Artista / interprete','Artista / interprete'],['Tonalità / Key','Tonalità'],['Tipo progetto','Tipo progetto'],['Profilo MTA','Profilo MTA'],['Società repertorio','Società repertorio'],['Salva','Salva'],['Version','Versione'],['Revision','Revisione'],['Release','Release'],['Build','Build'],['Creator','Creatore'],['License','Licenza'],['Repository','Progetto'],['Early Access','Accesso anticipato'],['Close','Chiudi'],['Chiudi menu','Chiudi menu'],['Menu','Menu']
];
let uiLanguage=null;
const UI_EN_IT=new Map(UI_TEXT_PAIRS),UI_IT_EN=new Map(UI_TEXT_PAIRS.map(([en,it])=>[it,en]));
const UI_IT_EN_PHRASES=[
['Aggiornamento disponibile','Update available'],['Aggiornamento live FX traccia fallito','Live track FX update failed'],['Aggiornamento live del master renderizzato fallito','Rendered master live update failed'],['Aggiornamento live master fallito','Live master update failed'],['Annullamento richiesto…','Cancellation requested…'],['Anteprima in riproduzione…','Preview playing…'],['Anteprima interrotta','Preview stopped'],['Anteprima renderizzata non disponibile','Rendered preview unavailable'],['Apertura progetto fallita','Project open failed'],['Apertura progetto recente fallita','Recent project open failed'],['Applicare il processing in-place alla selezione?','Apply processing in-place to the selection?'],['Apri la release GitHub per scegliere il pacchetto.','Open the GitHub release to choose the package.'],['Attendi il completamento della separazione prima di chiudere il progetto.','Wait for separation to finish before closing the project.'],['Attendi il completamento della separazione prima di creare un altro progetto.','Wait for separation to finish before creating another project.'],['Audio del progetto','Project audio'],['Autori e interpreti inseriti nelle informazioni del progetto','Authors and performers added to project information'],['Autosave fallito','Autosave failed'],['Avvio aggiornamento fallito','Update launch failed'],['Avvio non riuscito','Start failed'],['Bridge nativo non ancora disponibile. Riprova tra un istante.','Native bridge is not ready yet. Try again in a moment.'],['Bridge nativo non disponibile. Riprova tra un istante.','Native bridge unavailable. Try again in a moment.'],['Bridge nativo non disponibile','Native bridge unavailable'],['Campioni copiati','Samples copied'],['Cerca clip per nome…','Search clips by name…'],['Clipboard timeline vuota','Timeline clipboard is empty'],['Clipboard vuota o non accessibile','Clipboard is empty or unavailable'],['Colore sezione (#RRGGBB)','Section color (#RRGGBB)'],['Colore traccia','Track color'],['Condivisione progetto','Project sharing'],['Controllo aggiornamenti fallito','Update check failed'],['Controllo aggiornamenti non riuscito','Update check unsuccessful'],['Crea una traccia click per tutta la durata corrente del progetto','Create a click track for the current project duration'],['Dati repertorio salvati','Catalog data saved'],['Demucs non è disponibile in questo runtime','Demucs is unavailable in this runtime'],['Dimensione massima import/upload (MB)','Maximum import/upload size (MB)'],['Dividi la riga dopo questa parola','Split the line after this word'],['Download aggiornamento in corso…','Downloading update…'],['Download del file','File download'],['Download modello in corso…','Downloading model…'],['Editor Lyrics + Chords salvato: override applicati anche agli eventi MTA','Lyrics + Chords editor saved: overrides also applied to MTA events'],['Elimina intervallo selezionato','Delete selected range'],['Elimina tracce','Delete tracks'],['Errore di rete durante upload','Network error during upload'],['Escludi chord selezionato','Exclude selected chord'],['Espandi in finestra dedicata','Expand in dedicated window'],['Estrazione annullata','Extraction cancelled'],['File caricato','File uploaded'],['File del progetto','Project files'],['File già presente: nessuna copia aggiunta','File already present: no copy added'],['Filesystem mobile non disponibile','Mobile filesystem unavailable'],['Generazione anteprima PDF reale','Generating actual PDF preview'],['Gestisci insert Master','Manage Master inserts'],['Gestisci insert','Manage inserts'],['Il browser chiederà dove salvare il file secondo le impostazioni di download del browser.','The browser will ask where to save the file according to its download settings.'],['Il motore selezionato non richiede un modello','The selected engine does not require a model'],['Il nome della clip non può essere vuoto','Clip name cannot be empty'],['Il nome non può essere vuoto','Name cannot be empty'],['Il progetto non contiene chords attivi','The project contains no active chords'],['Il progetto non contiene lyrics','The project contains no lyrics'],['Il titolo del progetto non può essere vuoto','Project title cannot be empty'],['Import MTA fallito','MTA import failed'],['Import progetto fallito','Project import failed'],['Importa almeno una traccia audio per definire la durata del progetto','Import at least one audio track to define the project duration'],['Importa brano e separa strumenti','Import song and separate instruments'],['Importa solo audio da un singolo video YouTube','Import audio only from a single YouTube video'],['Impossibile aggiungere la clip','Unable to add clip'],['Impossibile aprire il progetto','Unable to open project'],['Impossibile leggere le impostazioni native','Unable to read native settings'],['Impossibile rinominare la clip','Unable to rename clip'],['Impossibile salvare le note','Unable to save notes'],['Impostazione offset fallita','Offset setting failed'],['Inizio sezione strumentale (secondi)','Instrumental section start (seconds)'],['Inserisci il nome del nuovo progetto','Enter the new project name'],['Inserisci un URL YouTube','Enter a YouTube URL'],['Inserisci un nome file','Enter a file name'],['Inserisci un nome per il progetto','Enter a project name'],['Inserisci un valore intero tra 1 e 10240 MB','Enter an integer value between 1 and 10240 MB'],['Intervallo eliminato con ripple sulle tracce selezionate','Range deleted with ripple on selected tracks'],['Intervallo eliminato dalle tracce selezionate','Range deleted from selected tracks'],['Segmento spostato sulla timeline','Segment moved on timeline'],['Segmenti della traccia spostati sulla timeline','Track segments moved on timeline'],['Segmenti delle tracce selezionate spostati sulla timeline','Selected-track segments moved on timeline'],['La scelta del percorso è disponibile nell’app desktop nativa','Path selection is available in the native desktop app'],['La selezione non contiene audio nelle tracce selezionate','The selection contains no audio on the selected tracks'],['La separazione è in corso: la barra di progresso rimane visibile fino al completamento.','Separation is in progress: the progress bar stays visible until completion.'],['La separazione è in corso: resta nel progetto corrente fino al completamento.','Separation is in progress: stay in the current project until completion.'],['La separazione è in corso: usa Annulla separazione se vuoi interromperla.','Separation is in progress: use Cancel separation to stop it.'],['Le clip audio importate appariranno qui e resteranno riutilizzabili nel progetto.','Imported audio clips appear here and remain reusable in the project.'],['L’estrazione automatica delle sezioni può richiedere molto tempo a seconda della durata del brano e dell’hardware. Continuare?','Automatic section extraction may take a long time depending on song duration and hardware. Continue?'],['Marker / sezioni','Markers / sections'],['Metadata progetto salvati','Project metadata saved'],['Metadata salvati; ricalcolo BPM non riuscito','Metadata saved; BPM recalculation failed'],['Modello locale non disponibile: uso il server.','Local model unavailable: using server.'],['Modello pronto','Model ready'],['Modello scaricato localmente','Model downloaded locally'],['Modello scaricato sul server','Model downloaded on server'],['Mostra/nascondi browser clip','Show/hide clip browser'],['Mute attivato su tutte le tracce','Mute enabled on all tracks'],['Mute rimosso da tutte le tracce','Mute removed from all tracks'],['Nascondi Lyrics/Chords/Markers','Hide Lyrics/Chords/Markers'],['Nessun clip attraversa il punto di split nelle tracce selezionate','No clip crosses the split point on the selected tracks'],['Nessun plugin configurato','No plugin configured'],['Nessun progetto attivo sul server.','No active project on the server.'],['Nessuna operazione da annullare','Nothing to undo'],['Nessuna operazione da ripristinare','Nothing to redo'],['Nome sezione / marker','Section / marker name'],['Nome sezione','Section name'],['Nome traccia','Track name'],['Non ancora associato a un file','Not yet associated with a file'],['Non ci sono parole lyrics disponibili','No lyric words are available'],['Non puoi eliminare il progetto mentre è in corso la separazione.','You cannot delete the project while separation is in progress.'],['Note della clip salvate','Clip notes saved'],['Note sulla clip…','Clip notes…'],['Nuova lyric (usa "." per una sezione strumentale senza testo)','New lyric (use "." for an instrumental section without text)'],['Nuovo nome della clip','New clip name'],['Offset traccia azzerato','Track offset reset'],['Operazione fallita','Operation failed'],['Ordine tracce aggiornato','Track order updated'],['Override Lyrics/Chords/Markers salvati e applicati agli eventi MTA','Lyrics/Chords/Markers overrides saved and applied to MTA events'],['Parte di traccia rimossa','Track segment removed'],['Percorso non disponibile','Path unavailable'],['Preparazione del progetto e verifica del modello…','Preparing project and checking model…'],['Preview aggiornata','Preview updated'],['Preview clip non disponibile','Clip preview unavailable'],['Prima traccia: stima automatica BPM in corso.','First track: automatic BPM estimation in progress.'],['Processing applicato','Processing applied'],['Progetto aperto dal filesystem','Project opened from filesystem'],['Progetto chiuso','Project closed'],['Progetto completo importato','Complete project imported'],['Progetto condiviso','Project shared'],['Progetto e relativi file eliminati dal workspace','Project and related files deleted from workspace'],['Progetto recente aperto','Recent project opened'],['Progetto recente non disponibile','Recent project unavailable'],['Progetto salvato manualmente','Project saved manually'],['Questo motore non richiede un modello','This engine does not require a model'],['Reincludi chord selezionato','Re-include selected chord'],['Ricalcolo waveform dopo modifica insert…','Recalculating waveform after insert change…'],['Ricalcolo waveform fallito','Waveform recalculation failed'],['Ridimensiona Tracks','Resize Tracks'],['Rimuovere la selezione?','Remove the selection?'],['Rimuovi insert','Remove insert'],['Ripple attivo sulle tracce selezionate','Ripple enabled on selected tracks'],['Salva PDF Lyrics + Chords','Save Lyrics + Chords PDF'],['Salva PDF Lyrics','Save Lyrics PDF'],['Salvataggio fallito','Save failed'],['Salvataggio impostazioni fallito','Settings save failed'],['Salvataggio nativo fallito','Native save failed'],['Scelta destinazione progetto fallita','Project destination selection failed'],['Seleziona almeno un file','Select at least one file'],['Seleziona almeno una società','Select at least one society'],['Seleziona almeno una traccia','Select at least one track'],['Seleziona modello AI e numero di stem prima di procedere','Select an AI model and stem count before continuing'],['Seleziona prima un intervallo nella timeline','Select a range on the timeline first'],['Seleziona un file MP3','Select an MP3 file'],['Seleziona un insert','Select an insert'],['Seleziona una traccia da analizzare','Select a track to analyze'],['Seleziona una traccia per visualizzare i plugin','Select a track to view plugins'],['Selezione copiata','Selection copied'],['Selezione incollata','Selection pasted'],['Selezione tagliata con ripple','Selection cut with ripple'],['Selezione tagliata','Selection cut'],['Separazione annullata','Separation cancelled'],['Separazione completata e progetto salvato','Separation completed and project saved'],['Separazione fallita','Separation failed'],['Separazione locale','Local separation'],['Separazione strumenti','Instrument separation'],['Sincronizzazione metronomo fallita','Metronome synchronization failed'],['Solo attivato su tutte le tracce','Solo enabled on all tracks'],['Solo rimosso da tutte le tracce','Solo removed from all tracks'],['Sostituzione traccia','Replace track'],['Sottotitolo / artista / tonalità','Subtitle / artist / key'],['Stile PDF salvato nel progetto','PDF style saved in project'],['Tagliare la selezione?','Cut the selection?'],['Tempo aggiornato; ricalcolo BPM non riuscito','Time signature updated; BPM recalculation failed'],['Tempo chord (secondi)','Chord time (seconds)'],['Tempo iniziale (secondi)','Start time (seconds)'],['Tempo iniziale in secondi','Start time in seconds'],['Tempo iniziale non valido','Invalid start time'],['Tempo marker (secondi)','Marker time (seconds)'],['Tempo marker in secondi','Marker time in seconds'],['Testo lyrics','Lyric text'],['Titolo originale / opera','Original title / work'],['Torna alla dimensione standard','Return to standard size'],['Tracce eliminate','Tracks deleted'],['Traccia aggiornata','Track updated'],['Traccia eliminata','Track deleted'],['Traccia non trovata','Track not found'],['Traccia sostituita','Track replaced'],['Trascina per modificare l\'altezza della traccia','Drag to change track height'],['Trascina per ridimensionare il mixer','Drag to resize mixer'],['Upload della traccia','Track upload'],['Usa il titolo YouTube','Use YouTube title'],['Verifica / riscarica','Verify / redownload'],['Waveform fallita','Waveform failed'],['Waveform non disponibile','Waveform unavailable'],['Workspace interno · file progetto non ancora associato','Internal workspace · project file not yet associated'],['Workspace interno · locazione esterna non disponibile','Internal workspace · external location unavailable']
];
for(const [it,en] of UI_IT_EN_PHRASES){if(!UI_IT_EN.has(it))UI_IT_EN.set(it,en);if(!UI_EN_IT.has(en))UI_EN_IT.set(en,it)}

function tr(en,it){if(uiLanguage==='it')return it;if(uiLanguage==='en')return en;return en}
function trDynamic(value){const raw=String(value??'');if(!uiLanguage)return raw;const lead=(raw.match(/^\s*/)||[''])[0],trail=(raw.match(/\s*$/)||[''])[0],core=raw.trim();if(!core)return raw;const map=uiLanguage==='it'?UI_EN_IT:UI_IT_EN;if(map.has(core))return lead+map.get(core)+trail;
  const patterns=uiLanguage==='it'?[[/^(\d+) selected$/,'$1 selezionate'],[/^Settings saved$/,'Impostazioni salvate'],[/^Project saved$/,'Progetto salvato'],[/^No project open$/,'Nessun progetto aperto'],[/^Open a project first$/,'Apri prima un progetto']]:[[/^(\d+) selezionat[ae]$/,'$1 selected'],[/^Impostazioni salvate$/,'Settings saved'],[/^Progetto salvato(?: manualmente)?$/,'Project saved'],[/^Nessun progetto aperto$/,'No project open'],[/^Apri prima un progetto$/,'Open a project first']];
  for(const [re,repl] of patterns)if(re.test(core))return lead+core.replace(re,repl)+trail;return raw}
function applyInterfaceLanguage(root=document){if(!uiLanguage||!root)return;document.documentElement.lang=uiLanguage;const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);for(const n of nodes){if(n.parentElement?.matches('script,style,textarea,input'))continue;const x=trDynamic(n.nodeValue);if(x!==n.nodeValue)n.nodeValue=x}root.querySelectorAll?.('[title],[aria-label],[placeholder]').forEach(el=>{for(const a of ['title','aria-label','placeholder']){if(el.hasAttribute(a))el.setAttribute(a,trDynamic(el.getAttribute(a)))}});ensureControlTooltips(root)}
const _nativeConfirm=window.confirm.bind(window),_nativeAlert=window.alert.bind(window);window.confirm=(m)=>_nativeConfirm(trDynamic(m));window.alert=(m)=>_nativeAlert(trDynamic(m));

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
function toast(s){const t=$('#toast');t.textContent=trDynamic(s);t.style.display='block';clearTimeout(t._timer);t._timer=setTimeout(()=>t.style.display='none',4200)}
function setRenderPlaybackPreparing(active){const b=$('#playMaster'),t=$('#toast');if(active){if(b){b.dataset.prepareText=b.textContent||'▶';b.textContent='…';b.title='Preparazione render in corso';b.classList.add('preparing')}if(t){clearTimeout(t._timer);t.textContent='Preparazione del render in corso, attendere…';t.style.display='block'}}else{if(b){if(b.classList.contains('preparing'))b.textContent='▶';b.classList.remove('preparing');b.title='Play / Preview'}if(t&&t.textContent==='Preparazione del render in corso, attendere…')t.style.display='none'}}
function fmtTime(sec,ms=false){sec=Math.max(0,sec);const m=Math.floor(sec/60),s=sec-m*60;return ms?`${String(m).padStart(2,'0')}:${String(Math.floor(s)).padStart(2,'0')}.${String(Math.floor((s%1)*1000)).padStart(3,'0')}`:`${m}:${String(Math.floor(s)).padStart(2,'0')}`}
function trackDelayMs(t){return Number(t?.delay_ms||0)||0}
function effectiveClipStartMs(t,c){return Number(c?.timeline_start_ms||0)+trackDelayMs(t)}
function projectEnd(){let e=10000;for(const t of current?.tracks||[])for(const c of t.clips||[])e=Math.max(e,Math.max(0,effectiveClipStartMs(t,c))+(c.source_end_ms-c.source_start_ms));return e}
function widthPx(){return Math.max(980,projectEnd()/1000*pxPerSec+180)}
function trackById(id){return current?.tracks?.find(t=>t.id===id)}
function selectedTrack(){return trackById(selectedTrackId)||current?.tracks?.[0]||null}
function ensureTrackSelection(){
  if(!current){selectedTrackIdSet.clear();return}
  const known=new Set((current.tracks||[]).map(t=>t.id));
  selectedTrackIdSet=new Set([...selectedTrackIdSet].filter(id=>known.has(id)));
  if(selectedTrackId&&!known.has(selectedTrackId))selectedTrackId=null;
  if(!selectedTrackIdSet.size&&current.tracks?.length){const id=selectedTrackId||current.tracks[0].id;selectedTrackId=id;selectedTrackIdSet.add(id)}
  if(selectedTrackId&&!selectedTrackIdSet.has(selectedTrackId))selectedTrackId=[...selectedTrackIdSet][0]||null;
}
function selectedTrackIds(){ensureTrackSelection();return (current?.tracks||[]).filter(t=>selectedTrackIdSet.has(t.id)).map(t=>t.id)}
function trackHeightPx(t){return Math.max(78,Math.min(420,Math.round(Number(t?.height_px)||78)))}
function linesToText(a,b){return(a||[]).map(x=>`${(x.time_ms/1000).toFixed(3)}\t${x[b]}`).join('\n')}
function textToLines(v,key){return v.split(/\n/).map(x=>x.trim()).filter(Boolean).map(line=>{const [t,...rest]=line.split(/\t|\s{2,}/);return{time_ms:Math.max(0,Math.round(parseFloat(t)*1000)||0),[key]:rest.join(' ').trim()}})}

async function init(){if(isMobileClient())document.body.classList.add('mobile-client');try{currentUser=await api('/api/session');const a=$('#adminNav');if(a)a.hidden=!!currentUser.native_single_user||currentUser.role!=='admin';const sb=$('#nativeSettingsButton');if(sb)sb.hidden=false;const recentBtn=$('#openRecentProjectBtn'),localBtn=$('#openLocalProjectBtn'),manualSave=$('#saveProjectManualNav'),localSave=$('#saveProjectLocalNav');if(currentUser.native_single_user){document.body.classList.add('native-single-user');if(recentBtn)recentBtn.hidden=false;if(localBtn)localBtn.hidden=true;if(manualSave)manualSave.hidden=false;if(localSave)localSave.hidden=true}else{if(recentBtn)recentBtn.hidden=true;if(localBtn)localBtn.hidden=false;if(manualSave)manualSave.hidden=true;if(localSave)localSave.hidden=false}}catch(e){}if(currentUser?.native_single_user)installNativeViewportGuard();if(currentUser&&!currentUser.native_single_user)autosaveEnabled=localStorage.getItem('mtaWebAutosaveEnabled')!=='false';let nativeBridge=null;if(currentUser?.native_single_user){nativeBridge=await waitForNativeApi();if(nativeBridge?.get_native_settings){try{const cfg=await nativeBridge.get_native_settings();autosaveEnabled=cfg.autosave_enabled!==false;nativeRecentProjects=Array.isArray(cfg.recent_projects)?cfg.recent_projects.map(String).filter(Boolean):[];const pref=['it','en'].includes(cfg.language)?cfg.language:'auto';uiLanguage=pref==='auto'?(String(cfg.system_language||'en').toLowerCase().startsWith('it')?'it':'en'):pref;applyInterfaceLanguage()}catch(e){}}setTimeout(()=>checkNativeAppUpdate(false),1200)}try{pluginInfo=await api('/api/plugins')}catch(e){}if(nativeBridge?.consume_startup_project){try{const startup=await nativeBridge.consume_startup_project();if(startup?.project?.id){rememberRecentProject(startup.project.id);await openP(startup.project.id);return}if(startup&&!startup.ok&&startup.error)toast('Impossibile aprire il progetto: '+startup.error)}catch(e){toast('Impossibile aprire il progetto: '+e.message)}}await refresh()}

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
function releaseProjectPreviewCache(projectId){
  if(!projectId)return;
  fetch(`/api/projects/${projectId}/preview-cache`,{method:'DELETE',credentials:'same-origin',keepalive:true}).catch(()=>{});
}

function closeCurrentProject(){
  if(!current)return toast('Nessun progetto aperto');
  if(activeStemJob&&activeStemProjectId===current.id)return toast('Attendi il completamento della separazione prima di chiudere il progetto.');
  const closingProjectId=current.id;
  stopPlayback();
  clearTimedPlaybackOverlay();
  clearTimeout(autosaveTimer);autosaveTimer=null;
  releaseProjectPreviewCache(closingProjectId);
  current=null;selectedTrackId=null;pendingExportConfig=null;playCursorMs=0;
  if($('#headerProjectName'))$('#headerProjectName').textContent='No project loaded';
  if($('#transportTime'))$('#transportTime').textContent='00:00.000';
  render();refresh();
  toast('Progetto chiuso');
}

window.addEventListener('pagehide',()=>{
  const pid=current?.id;if(!pid)return;
  releaseProjectPreviewCache(pid);
});

function recentProjectIds(){
  if(currentUser?.native_single_user)return [...nativeRecentProjects];
  try{return JSON.parse(localStorage.getItem('mtaRecentProjects')||'[]').filter(Boolean)}catch(e){return[]}
}
async function persistNativeRecentProjects(){
  if(!currentUser?.native_single_user)return;
  const bridge=await waitForNativeApi();
  if(bridge?.set_recent_projects){try{await bridge.set_recent_projects(nativeRecentProjects)}catch(e){console.warn('Persist recent projects failed',e)}}
}
function rememberRecentProject(id){
  if(!id)return;const ids=[String(id),...recentProjectIds().filter(x=>String(x)!==String(id))].slice(0,12);
  if(currentUser?.native_single_user){nativeRecentProjects=ids;void persistNativeRecentProjects()}
  else localStorage.setItem('mtaRecentProjects',JSON.stringify(ids));
}
function forgetRecentProject(id){
  const ids=recentProjectIds().filter(x=>String(x)!==String(id));
  if(currentUser?.native_single_user){nativeRecentProjects=ids;void persistNativeRecentProjects()}
  else localStorage.setItem('mtaRecentProjects',JSON.stringify(ids));
}
function resetProjectUiForOpen(){clipBrowserExpanded=false;clipBrowserQuery='';clipBrowserPage=1;expandedProjectClipDetails=new Set();uiState={trackTop:0,timelineTop:0,timelineLeft:0,mixerLeft:0};mixerResizeState=null;if(currentUser?.native_single_user)forceNativeViewportTop()}
async function refresh(){
  try{serverProjects=await api('/api/projects')}catch(e){serverProjects=[]}
  return serverProjects;
}
function showProjectOpenProgress(pct,message){
  const p=Math.max(0,Math.min(100,Number(pct)||0));
  setMobileBusy(p<100);
  showUtilityModal('Apertura progetto',`<div class="stem-progress-card project-open-progress"><div class="stem-progress-head"><b>Apertura progetto</b><span>${p}%</span></div><div class="stem-progress"><div class="stem-progress-fill" style="width:${p}%"></div></div><div class="stem-progress-message">${esc(message||'')}</div></div>`);
}
function finishProjectOpenProgress(){setMobileBusy(false);if(document.querySelector('.utility-modal .project-open-progress'))$('#utilityBackdrop')?.classList.add('hidden')}
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
  const bridge=await waitForNativeApi();
  if(!bridge?.list_recent_projects)return toast('Bridge nativo non disponibile. Riprova tra un istante.');
  try{
    const result=await bridge.list_recent_projects();
    const recent=Array.isArray(result?.projects)?result.projects:[];
    const body=recent.length?`<div class="project-picker-list">${recent.map(p=>`<button class="project-picker-row" onclick="openRecentNativeProject('${esc(p.id)}')"><span><b>${esc(p.name||'Project')}</b><small>${esc(p.path||'')}</small></span><strong>Apri ›</strong></button>`).join('')}</div>`:'<p class="hint">Nessun progetto recente ancora disponibile.</p>';
    showUtilityModal('Open recent',`${body}<div class="utility-actions"><button class="utility-btn secondary" onclick="closeUtilityModal()">Annulla</button></div>`);
  }catch(e){toast('Impossibile leggere i progetti recenti: '+e.message)}
}
async function openRecentNativeProject(id){
  const bridge=await waitForNativeApi();if(!bridge?.open_recent_project)return toast('Bridge nativo non disponibile.');showProjectOpenProgress(8,'Apertura progetto recente…');
  try{const result=await bridge.open_recent_project(id);if(!result?.ok||!result?.project?.id)throw new Error(result?.error||'Progetto recente non disponibile');showProjectOpenProgress(40,'Inizializzazione tracce e metadata…');current=result.project;rememberRecentProject(current.id);selectedTrackId=current.tracks?.[0]?.id||null;resetProjectUiForOpen();resetSessionHistory();render();showProjectOpenProgress(70,'Caricamento waveform e interfaccia…');await refresh();showProjectOpenProgress(88,'Preparazione motore audio…');schedulePlaybackPrewarm(40);focusProjectWorkspace();showProjectOpenProgress(100,'Progetto pronto');finishProjectOpenProgress();toast('Progetto recente aperto')}catch(e){finishProjectOpenProgress();toast('Apertura progetto recente fallita: '+e.message)}
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
    const createdId=created.id;
    closeUtilityModal();
    // Load the newly-created project explicitly before refreshing the native workspace.
    // This avoids the historical native flow where the archive was created but the editor stayed empty.
    current=await api('/api/projects/'+createdId);
    rememberRecentProject(current.id);
    selectedTrackId=current.tracks?.[0]?.id||null;
    resetProjectUiForOpen();resetSessionHistory();render();
    await refresh();schedulePlaybackPrewarm(40);focusProjectWorkspace();
    toast(currentUser?.native_single_user?`Progetto ${target} creato in ${pendingNewProjectPath}`:`Progetto ${target} creato e salvato nel workspace`);
    pendingNewProjectPath=null;
  }catch(e){toast(e.message)}
}
async function openP(id){
  if(activeStemJob&&activeStemProjectId&&id!==activeStemProjectId)return toast('La separazione è in corso: resta nel progetto corrente fino al completamento.');
  showProjectOpenProgress(5,'Preparazione apertura…');
  try{await flushAutosave();stopPlayback();showProjectOpenProgress(18,'Caricamento progetto…');current=await api('/api/projects/'+id);showProjectOpenProgress(42,'Inizializzazione tracce e metadata…');rememberRecentProject(current.id);selectedTrackId=current.tracks[0]?.id||null;resetProjectUiForOpen();resetSessionHistory();render();showProjectOpenProgress(68,'Caricamento waveform e interfaccia…');await refresh();showProjectOpenProgress(86,'Preparazione motore audio…');schedulePlaybackPrewarm(40);focusProjectWorkspace();showProjectOpenProgress(100,'Progetto pronto');finishProjectOpenProgress()}catch(e){finishProjectOpenProgress();toast('Impossibile aprire il progetto: '+e.message)}
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
    showProjectOpenProgress(5,'Selezione e lettura file progetto…');
    try{const result=await window.pywebview.api.open_project();if(!result?.ok){finishProjectOpenProgress();return}showProjectOpenProgress(42,'Inizializzazione tracce e metadata…');current=result.project;rememberRecentProject(current.id);selectedTrackId=current.tracks[0]?.id||null;resetProjectUiForOpen();resetSessionHistory();render();showProjectOpenProgress(70,'Caricamento waveform e interfaccia…');await refresh();showProjectOpenProgress(88,'Preparazione motore audio…');schedulePlaybackPrewarm(40);focusProjectWorkspace();showProjectOpenProgress(100,'Progetto pronto');finishProjectOpenProgress();toast('Progetto aperto dal filesystem');return}catch(e){finishProjectOpenProgress();toast('Apertura progetto fallita: '+e.message);return}
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
  $('#transportBpm').textContent=String(Math.round(Number(current.bpm||120)));
  if($('#transportBpmInput'))$('#transportBpmInput').value=String(Math.round(Number(current.bpm||120)));
  if($('#transportTimeSignature'))$('#transportTimeSignature').value=current.time_signature||'4/4';
  if($('#transportPitchInput'))$('#transportPitchInput').value=Number(current.pitch_semitones||0).toFixed(1);
  updateTransportToggleButtons();
  if(!selectedTrackId||!trackById(selectedTrackId))selectedTrackId=current.tracks[0]?.id||null;
  ensureTrackSelection();
  const W=widthPx(),trackWidth=Math.max(160,Math.min(520,Number(current.track_panel_width_px)||225));
  $('#editor').innerHTML=`
    ${toolbarHtml()}
    ${clipBrowserHtml()}
    <div class="editor-grid ${current.inspector_visible===false?'inspector-hidden':''}" id="editorGrid" style="--track-column-width:${trackWidth}px">
      <div class="track-column" id="trackColumn"><div class="track-column-head">TRACKS</div>${current.tracks.map((t,i)=>trackHead(t,i)).join('')}</div>
      <div class="track-resizer" id="trackResizer" title="Ridimensiona Tracks"></div>
      <div class="timeline-pane" id="timelinePane"><div class="ruler"><canvas id="ruler" width="${W}" height="30"></canvas></div><div class="lanes" id="lanes" style="width:${W}px"><div class="timeline-chord-lane ${current.show_chords_playback?'':'hidden'}" id="timelineChordLane">${timelineChordLaneHtml(W)}</div>${current.tracks.map((t,i)=>lane(t,W,i)).join('')}<div class="playhead" id="playhead" style="left:${playCursorMs/1000*pxPerSec}px"></div></div></div>
      ${inspectorHtml()}
    </div>`;
  $('#mixerDock').innerHTML=mixerHtml();
  syncZoomControls(pxPerSec);
  updateMixerDockLayout();updatePanelMenuButtons();bindMixerResizer();
  drawRuler();bindTimeline();bindProjectClipDrop();bindTrackTimelineScroll();bindTrackResizer();
  current.tracks.forEach(drawWave);if(waveformValidationProjectId!==current.id){waveformValidationProjectId=current.id;ensureWaveforms(true)}else ensureWaveforms(false);updateSel();bindModelInputs();updateMuteSoloVisuals();restoreUiState();ensureSessionHistory();updateEditActionState();applyInterfaceLanguage();forceNativeViewportTop();schedulePlaybackPrewarm(180);
}
let chordsTrackCreatePending=false;
async function createChordsTrack(){
  if(chordsTrackCreatePending)return toast('Creazione/aggiornamento traccia Chords già in corso…');
  if(!current)return toast('Apri prima un progetto');
  if(!(current.chords||[]).some(ch=>!ch.excluded&&!ch.deleted))return toast('Il progetto non contiene chords attivi');
  try{
    chordsTrackCreatePending=true;
    await flushAutosave();
    const result=await api(`/api/projects/${current.id}/chords-track`,{method:'POST'});
    current=result.project;
    selectedTrackId=result.track.id;
    render();
    await refresh();
    toast(`${result.reused?'Traccia Chords aggiornata':'Traccia Chords creata'} · ${result.chord_count} accordi · piano digitale`);
  }catch(e){toast(e.message)}finally{chordsTrackCreatePending=false}
}

let metronomeCreatePending=false;
async function createMetronomeTrack(){
  if(metronomeCreatePending)return toast('Creazione/aggiornamento metronomo già in corso…');
  if(!current)return toast('Apri prima un progetto');
  if(!current.tracks.length)return toast('Importa almeno una traccia audio per definire la durata del progetto');
  try{
    metronomeCreatePending=true;
    await flushAutosave();
    const result=await api(`/api/projects/${current.id}/metronome-track`,{method:'POST'});
    current=result.project;
    selectedTrackId=result.track.id;
    render();
    await refresh();
    toast(`${result.reused?'Traccia metronomo aggiornata':'Traccia metronomo creata'} a ${Number(current.bpm).toFixed(1)} BPM`);
  }catch(e){toast(e.message)}finally{metronomeCreatePending=false}
}

function toolbarHtml(){
  const refs=current.tracks.map(t=>`<option value="${t.id}">${esc(t.name)}</option>`).join('');
  const stem=pluginInfo.stem_splitter||{};
  return `<div class="editor-toolbar">
    <button id="toolSelect" class="tool ${timelineTool==='select'?'active':''}" onclick="setTimelineTool('select')"><strong>➤</strong>Select</button><button id="toolSplit" class="tool ${timelineTool==='split'?'active':''}" onclick="setTimelineTool('split')"><strong>✂</strong>Split</button><button id="toolRange" class="tool ${timelineTool==='range'?'active':''}" onclick="setTimelineTool('range')"><strong>▭</strong>Range</button><button id="toolRipple" class="tool ${rippleEnabled?'active':''}" onclick="toggleRippleTool()" aria-pressed="${rippleEnabled?'true':'false'}"><strong>↔</strong>Ripple</button>
    <div class="toolbar-sep destructive-sep"></div><div class="toolbar-destructive-group"><button class="toolbar-action danger compact-delete" onclick="deleteSelection(false)">Delete tracks</button><button class="toolbar-action danger compact-delete" onclick="deleteSelection(true)">Delete selected range</button></div>
    <div class="toolbar-sep"></div><div class="toolbar-group"><label>Snap</label><select><option>Bars</option><option>Beats</option><option>Off</option></select></div>
    <button class="toolbar-action emphasis" onclick="openStemWorkflow()">▥ Import &amp; Separate</button>
    <button class="toolbar-action" onclick="openYoutubeImport()" title="Importa solo audio da un singolo video YouTube">▶ Import YouTube</button>
    <button class="toolbar-action" onclick="createMetronomeTrack()" title="Crea una traccia click per tutta la durata corrente del progetto">♩ Metronomo</button><button class="toolbar-action" onclick="createChordsTrack()" title="Crea o rigenera una sola traccia Chords con piano digitale sincronizzato agli accordi del progetto">♬ Chords</button>
    <div class="toolbar-group"><input id="newTrackFile" type="file" accept=".mp3,.wav,.flac,.m4a,audio/*" onchange="addTrack()"><select id="newSync"><option value="manual">Manual sync</option><option value="auto">Auto sync</option></select><input id="newOffset" type="number" value="0" title="Offset ms" style="width:72px"><select id="newRef" style="max-width:115px">${refs}</select><button class="toolbar-action" onclick="addTrack()">♫ Import Audio Track</button></div>
    <div class="toolbar-sep"></div><button id="undoBtn" class="toolbar-action" onclick="undoEdit()">↶ Undo</button><button id="redoBtn" class="toolbar-action" onclick="redoEdit()">↷ Redo</button><button class="toolbar-action" onclick="cutTimelineSelection()">✂ Cut</button><button class="toolbar-action" onclick="copyTimelineSelection()">⧉ Copy</button><button id="pasteBtn" class="toolbar-action" onclick="pasteTimelineSelection()">▣ Paste</button><button class="toolbar-action danger" onclick="removeTimelineSelection()">⌫ Remove</button><div class="toolbar-grow"></div><span class="selected-track-count" id="selectedTrackCount">${selectedTrackIds().length} selected</span><span class="selection-info" id="selectionInfo">0.000 → 0.000 s</span>
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
function beginTrackHeightResize(event,id){
  const t=trackById(id);if(!t)return;
  event.preventDefault();event.stopPropagation();
  const startY=event.clientY,startH=trackHeightPx(t);document.body.classList.add('resizing-track-height');
  const move=e=>{
    const h=Math.max(78,Math.min(420,Math.round(startH+(e.clientY-startY))));if(h===trackHeightPx(t))return;t.height_px=h;
    const head=$(`#head-${id}`),ln=$(`#lane-${id}`),canvas=$(`#wave-${id}`);
    if(head)head.style.height=`${h}px`;if(ln)ln.style.height=`${h}px`;if(canvas){canvas.height=h;drawWave(t)}
  };
  const up=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',up);window.removeEventListener('pointercancel',up);document.body.classList.remove('resizing-track-height');markDirty(80)};
  window.addEventListener('pointermove',move,{passive:false});window.addEventListener('pointerup',up);window.addEventListener('pointercancel',up);
}
const NOTE_PC={C:0,'C#':1,Db:1,D:2,'D#':3,Eb:3,E:4,F:5,'F#':6,Gb:6,G:7,'G#':8,Ab:8,A:9,'A#':10,Bb:10,B:11};
const SHARP_NOTES=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'],FLAT_NOTES=['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'];
function transposeNoteName(note,shift){const pc=NOTE_PC[note];if(pc===undefined)return note;const names=note.includes('b')?FLAT_NOTES:SHARP_NOTES;return names[(pc+Math.round(Number(shift||0))+120)%12]}
function transposeChordLabel(label,shift){const n=Math.round(Number(shift||0));if(!n)return label;const m=String(label||'').match(/^([A-G](?:#|b)?)(.*)$/);if(!m)return label;let suffix=m[2].replace(/\/([A-G](?:#|b)?)/g,(_,x)=>'/'+transposeNoteName(x,n));return transposeNoteName(m[1],n)+suffix}
function effectiveProjectKey(){const key=String(current?.key||'');const m=key.match(/^\s*([A-G](?:#|b)?)(.*)$/);return m?transposeNoteName(m[1],current?.pitch_semitones||0)+m[2]:key}

function trackHead(t,i){
  const color=t.color||TRACK_COLORS[i%TRACK_COLORS.length],anySolo=current.tracks.some(x=>x.solo),inaudible=t.mute||(anySolo&&!t.solo);
  const audioMode=t.channels===2?'STEREO':(t.channels===1?'MONO':(t.channel_layout?String(t.channel_layout).toUpperCase():''));
  const height=trackHeightPx(t);
  return `<div class="track-head ${selectedTrackIdSet.has(t.id)?'selected':''} ${t.id===selectedTrackId?'primary-selected':''} ${inaudible?'audibly-muted':''}" id="head-${t.id}" data-track-context-id="${t.id}" style="--track-color:${color};height:${height}px" onclick="selectTrack('${t.id}',event)" oncontextmenu="openTrackContextMenu(event,'${t.id}')" ondragover="trackDragOver(event,'${t.id}')" ondrop="dropTrack(event,'${t.id}')">
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
    <div class="track-height-resizer" title="Trascina per modificare l'altezza della traccia" onpointerdown="beginTrackHeightResize(event,'${t.id}')"></div>
  </div>`;
}
function closeTrackContextMenu(){
  const menu=$('#trackContextMenu');
  if(menu)menu.remove();
}
function openTrackContextMenuAt(id,clientX,clientY){
  closeTrackContextMenu();
  const track=trackById(id);if(!track)return;
  if(!selectedTrackIdSet.has(id)){selectedTrackIdSet=new Set([id])}
  selectedTrackId=id;
  $$('.track-head').forEach(el=>{const tid=el.id.replace(/^head-/,'');el.classList.toggle('selected',selectedTrackIdSet.has(tid));el.classList.toggle('primary-selected',tid===id)});
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
    <button type="button" onclick="closeTrackContextMenu();recalculateBpmFromTrack('${id}')">♩ <span>Ricalcola BPM da questa traccia</span></button>
    <button type="button" onclick="closeTrackContextMenu();openTextAnalysisChooser('${id}','lyrics')">≡ <span>Estrai lyrics</span></button>
    <button type="button" onclick="closeTrackContextMenu();openTextAnalysisChooser('${id}','chords')">♬ <span>Estrai chords</span></button>
    <button type="button" onclick="closeTrackContextMenu();extractMarkersFromTrack('${id}')">⚑ <span>Estrai marker automaticamente</span></button>
    <button type="button" onclick="closeTrackContextMenu();syncMetronomeToTrack('${id}')">⌁ <span>Sincronizza metronomo</span></button>
    <button type="button" onclick="closeTrackContextMenu();openTrackDelayDialog('${id}')">↔ <span>Delay / anticipo traccia…</span></button>
    <button type="button" onclick="closeTrackContextMenu();addTimelineChordAtPlayhead()">♬ <span>+ Chord alla posizione corrente</span></button>
    <button type="button" class="danger" onclick="closeTrackContextMenu();deleteSelection(true)">⌫ <span>Delete selected range</span></button>
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

async function syncMetronomeToTrack(id){
  const track=trackById(id);if(!track)return;
  try{
    toast(`Sincronizzazione metronomo con ${track.name}…`);
    const result=await api(`/api/projects/${current.id}/tracks/${id}/sync-metronome`,{method:'POST'});
    current=result.project;
    render();markDirty(0);
    const sign=Number(result.delta_ms)>=0?'+':'';
    toast(`Metronomo sincronizzato: ${sign}${Number(result.delta_ms)} ms`);
  }catch(e){toast(e.message||'Sincronizzazione metronomo fallita')}
}
function delayMsFromUnit(value,unit){
  const n=Number(value);if(!Number.isFinite(n))return 0;
  const bpm=Math.max(1,Number(current?.bpm||120));
  if(unit==='bars'){const beats=Math.max(1,Number(String(current?.time_signature||'4/4').split('/')[0])||4);return Math.round(n*beats*60000/bpm);}
  if(unit==='quarters')return Math.round(n*60000/bpm);
  return Math.round(n);
}
function delayValueFromMs(ms,unit){
  const bpm=Math.max(1,Number(current?.bpm||120));
  if(unit==='bars'){const beats=Math.max(1,Number(String(current?.time_signature||'4/4').split('/')[0])||4);return Number(ms)*bpm/(beats*60000);}
  if(unit==='quarters')return Number(ms)*bpm/60000;
  return Number(ms);
}
function openTrackDelayDialog(id){
  const track=trackById(id);if(!track)return;
  const currentMs=trackDelayMs(track);
  showUtilityModal('Delay / anticipo traccia',`<div class="form-grid"><p><b>${esc(track.name)}</b></p><p class="hint">Valori positivi ritardano la traccia; valori negativi la anticipano. L'offset è non distruttivo e viene applicato a playback, Render ed export.</p><label>Unità<select id="trackDelayUnit" onchange="trackDelayUnitChanged('${esc(id)}')"><option value="ms">Millisecondi</option><option value="quarters">Quarti / battiti</option><option value="bars">Battute (${current?.time_signature||'4/4'})</option></select></label><label>Valore<input id="trackDelayValue" type="number" step="1" value="${currentMs}"></label><div class="workflow-note">Offset attuale: <b id="trackDelayComputed">${currentMs>=0?'+':''}${currentMs} ms</b> · BPM progetto: ${Number(current?.bpm||120).toFixed(1)}</div><div class="form-actions"><button class="utility-btn secondary" onclick="closeUtilityModal()">Annulla</button><button class="utility-btn secondary" onclick="setTrackDelay('${esc(id)}',0,'ms')">Azzera</button><button class="utility-btn primary" onclick="applyTrackDelayDialog('${esc(id)}')">Applica</button></div></div>`);
  $('#trackDelayValue')?.addEventListener('input',()=>updateTrackDelayComputed());
}
function trackDelayUnitChanged(id){const track=trackById(id);if(!track)return;const unit=$('#trackDelayUnit')?.value||'ms';const v=delayValueFromMs(trackDelayMs(track),unit);const input=$('#trackDelayValue');if(input){input.step=unit==='ms'?'1':'0.01';input.value=unit==='ms'?String(Math.round(v)):String(Math.round(v*1000)/1000)}updateTrackDelayComputed()}
function updateTrackDelayComputed(){const unit=$('#trackDelayUnit')?.value||'ms',value=$('#trackDelayValue')?.value||0,ms=delayMsFromUnit(value,unit);const el=$('#trackDelayComputed');if(el)el.textContent=`${ms>=0?'+':''}${ms} ms`}
async function applyTrackDelayDialog(id){const unit=$('#trackDelayUnit')?.value||'ms',value=$('#trackDelayValue')?.value||0;await setTrackDelay(id,value,unit)}
async function setTrackDelay(id,value,unit='ms'){
  const ms=delayMsFromUnit(value,unit);
  try{
    const result=await api(`/api/projects/${current.id}/tracks/${id}/delay`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({delay_ms:ms})});
    current=result.project;clearPlaybackWarmCache();closeUtilityModal();render();markDirty(0);
    toast(ms?`Offset traccia impostato a ${ms>=0?'+':''}${ms} ms`:'Offset traccia azzerato');
  }catch(e){toast(e.message||'Impostazione offset fallita')}
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
  if(kind==='lyrics'){const c=cat.lyrics||{},opts=(c.models||[]).map(m=>`<option value="${esc(m.id)}" ${m.id===c.default_model?'selected':''}>${esc(m.display_name)} · ${m.installed?'installato':(c.storage==='local'?'download locale':'download server')}</option>`).join('');showUtilityModal('Estrai lyrics',`<div class="form-grid"><p><b>Motore:</b> OpenAI Whisper</p><label>Modello<select id="textAnalysisChoice">${opts}</select></label><label class="workflow-check"><input id="lyricsAdvancedAlignment" type="checkbox"> Allineamento avanzato parola / sillaba</label><p class="hint">Pipeline opzionale: Whisper → word timestamps → forced alignment acustico → suddivisione sillabica → timeline MTA. Migliora il posizionamento di lyrics e chords. L’estrazione viene sempre eseguita dall’inizio della traccia e il testo parziale non viene mostrato durante la generazione per evitare duplicati o frasi spezzate.</p><p class="hint">Il modello viene scaricato on-demand (download modello al primo uso) e conservato ${c.storage==='local'?'localmente nell’app nativa':'sul server'}.</p><div class="workflow-note warning"><b>Attenzione:</b> l’estrazione può richiedere molto tempo. La durata dipende dalla lunghezza della traccia, dal modello scelto e dall’hardware CPU/GPU disponibile. Durante l’analisi evita di chiudere l’app o interrompere il dispositivo.</div><div class="form-actions"><button class="utility-btn secondary model-download-btn" type="button" onclick="downloadTextAnalysisSelection('lyrics')">Scarica modello</button><button class="utility-btn primary accent" type="button" onclick="startTrackTextAnalysis('${esc(id)}','lyrics',$('#textAnalysisChoice').value)">Estrai lyrics</button></div></div>`);return}
  const c=cat.chords||{},models=Object.fromEntries((c.models||[]).map(x=>[x.id,x])),opts=(c.engines||[]).map(e=>{const m=models[e.model_id]||{};let state;if(e.model_id)state=m.installed?'modello installato':(c.storage==='local'?'modello scaricabile localmente':'modello scaricabile sul server');else if(e.id==='chordino'){const r=e.runtime||{};const reason={ 'chordino-plugin-missing':'host Vamp presente · plugin Chordino non rilevato','vamp-host-missing':'host Vamp incluso non trovato nel bundle','vamp-host-failed':'host Vamp trovato ma non avviabile'}[r.reason]||'runtime Chordino non disponibile';state=e.available?`nessun modello AI · Chordino incluso (${r.host_kind||'Vamp host'} · ${r.host||'bundle'})`:`${reason}${r.host?` · ${r.host}`:''}`;}else state='nessun modello AI richiesto';return `<option value="${esc(e.id)}" ${e.id===c.default_engine?'selected':''} ${e.available?'':'disabled'}>${esc(e.display_name)} · ${esc(state)}</option>`}).join(''),presets=(c.presets||[]).map(x=>`<option value="${esc(x.id)}">${esc(x.display_name)}</option>`).join('');showUtilityModal('Estrai chords',`<div class="form-grid chord-extraction-config"><p><b>Motore che verrà usato:</b> <span id="chordEngineLabel"></span></p><label>Motore / modello<select id="textAnalysisChoice" onchange="updateChordEngineDisclosure()">${opts}</select></label><div id="chordEngineDisclosure" class="workflow-note"></div><label>Profilo del risultato<select id="chordPipelinePreset" onchange="applyChordPipelinePreset(this.value)">${presets}</select></label><div id="chordPresetDescription" class="hint"></div><label>Sensibilità ai cambi accordo <span id="chordSensitivityValue">45</span>/100<input id="chordSensitivity" type="range" min="0" max="100" step="1" value="45" oninput="$('#chordSensitivityValue').textContent=this.value"></label><div class="workflow-note"><b>Meno sensibilità</b> = meno accordi, segmenti più lunghi e maggiore soppressione dei transitori. <b>Più sensibilità</b> = segue cambi armonici più brevi.</div><details class="workflow-note"><summary><b>Pipeline avanzata / stadi opzionali</b></summary><div class="form-grid compact"><label class="workflow-check"><input id="chordHarmonicRefinement" type="checkbox"> Refinement chroma armonica</label><label class="workflow-check"><input id="chordDetectSevenths" type="checkbox"> 7 / maj7 / m7</label><label class="workflow-check"><input id="chordDetectSus" type="checkbox"> sus2 / sus4</label><label class="workflow-check"><input id="chordDetectDimAug" type="checkbox"> dim / aug</label><label class="workflow-check"><input id="chordDetectSlashBass" type="checkbox"> Inversioni / slash bass</label><label class="workflow-check"><input id="chordTemporalSmoothing" type="checkbox"> Stabilizzazione temporale</label><label class="workflow-check"><input id="chordBeatSync" type="checkbox"> Quantizza cambi ai beat del progetto</label><label>Durata minima accordo (ms)<input id="chordMinDuration" type="number" min="0" max="10000" step="100" value="1800"></label><label>Massimo cambi/minuto<input id="chordMaxChanges" type="number" min="0" max="240" step="1" value="24"></label></div></details><div class="workflow-note warning">l’analisi degli accordi può richiedere molto tempo, soprattutto con modelli AI o ensemble.</div><div class="workflow-note warning"><b>Suggerimento:</b> per una progressione leggibile usa Songbook/Stabile. “Solo recognizer / Raw” salta refinement e filtri MTA; è utile per confrontare il risultato originale del motore.</div><div class="form-actions"><button class="utility-btn secondary model-download-btn" type="button" onclick="downloadTextAnalysisSelection('chords')">Scarica modello selezionato</button><button class="utility-btn primary accent" type="button" onclick="startTrackTextAnalysis('${esc(id)}','chords',$('#textAnalysisChoice').value)">Estrai chords</button></div></div>`);updateChordEngineDisclosure();restoreChordExtractionSettings()}
const CHORD_EXTRACTION_SETTINGS_KEY='mta.chordExtractionSettings.v1';
function defaultChordExtractionSettings(){return {engine:'madmom-deep-chroma',preset:'default-complete',sensitivity:45,harmonic_refinement:true,detect_sevenths:true,detect_sus:true,detect_dim_aug:true,detect_slash_bass:true,temporal_smoothing:true,beat_sync:false,min_chord_ms:1100,max_changes_per_minute:36}}
function loadChordExtractionSettings(){const defaults=defaultChordExtractionSettings();try{const saved=JSON.parse(localStorage.getItem(CHORD_EXTRACTION_SETTINGS_KEY)||'null');return saved&&typeof saved==='object'?{...defaults,...saved}:defaults}catch(e){return defaults}}
function captureChordExtractionSettings(){const val=(sel,def='')=>$(sel)?.value??def,check=sel=>!!$(sel)?.checked;return {engine:val('#textAnalysisChoice','madmom-deep-chroma'),preset:val('#chordPipelinePreset','default-complete'),sensitivity:Number(val('#chordSensitivity','45')),harmonic_refinement:check('#chordHarmonicRefinement'),detect_sevenths:check('#chordDetectSevenths'),detect_sus:check('#chordDetectSus'),detect_dim_aug:check('#chordDetectDimAug'),detect_slash_bass:check('#chordDetectSlashBass'),temporal_smoothing:check('#chordTemporalSmoothing'),beat_sync:check('#chordBeatSync'),min_chord_ms:Number(val('#chordMinDuration','1100')),max_changes_per_minute:Number(val('#chordMaxChanges','36'))}}
function saveChordExtractionSettings(){try{localStorage.setItem(CHORD_EXTRACTION_SETTINGS_KEY,JSON.stringify(captureChordExtractionSettings()))}catch(e){}}
function applyChordExtractionSettings(settings){const s={...defaultChordExtractionSettings(),...(settings||{})},engine=$('#textAnalysisChoice'),preset=$('#chordPipelinePreset');if(engine){const requested=[...engine.options].find(o=>o.value===s.engine&&!o.disabled);const fallback=[...engine.options].find(o=>o.value==='madmom-deep-chroma'&&!o.disabled)||[...engine.options].find(o=>!o.disabled);if(requested||fallback)engine.value=(requested||fallback).value}if(preset){const option=[...preset.options].find(o=>o.value===s.preset)||[...preset.options].find(o=>o.value==='default-complete');if(option)preset.value=option.value}const set=(sel,v)=>{const el=$(sel);if(el)el.checked=!!v};if($('#chordSensitivity')){$('#chordSensitivity').value=String(Math.max(0,Math.min(100,Number(s.sensitivity)||45)));$('#chordSensitivityValue').textContent=$('#chordSensitivity').value}set('#chordHarmonicRefinement',s.harmonic_refinement);set('#chordDetectSevenths',s.detect_sevenths);set('#chordDetectSus',s.detect_sus);set('#chordDetectDimAug',s.detect_dim_aug);set('#chordDetectSlashBass',s.detect_slash_bass);set('#chordTemporalSmoothing',s.temporal_smoothing);set('#chordBeatSync',s.beat_sync);if($('#chordMinDuration'))$('#chordMinDuration').value=String(Math.max(0,Number(s.min_chord_ms)||0));if($('#chordMaxChanges'))$('#chordMaxChanges').value=String(Math.max(0,Number(s.max_changes_per_minute)||0));updateChordEngineDisclosure();const spec=chordPipelinePresetSpec(preset?.value||s.preset);if($('#chordPresetDescription'))$('#chordPresetDescription').textContent=spec.description||''}
function restoreChordExtractionSettings(){applyChordExtractionSettings(loadChordExtractionSettings())}
function chordPipelinePresetSpec(id){return (textModelCatalog().chords?.presets||[]).find(x=>x.id===id)||{id:'default-complete',sensitivity:45,harmonic_refinement:true,detect_sevenths:true,detect_sus:true,detect_dim_aug:true,detect_slash_bass:true,temporal_smoothing:true,beat_sync:false,min_chord_ms:1100,max_changes_per_minute:36}}
function applyChordPipelinePreset(id){const p=chordPipelinePresetSpec(id);if($('#chordPresetDescription'))$('#chordPresetDescription').textContent=p.description||'';const set=(sel,v)=>{const el=$(sel);if(el)el.checked=!!v};if($('#chordSensitivity')){$('#chordSensitivity').value=p.sensitivity??25;$('#chordSensitivityValue').textContent=$('#chordSensitivity').value}set('#chordHarmonicRefinement',p.harmonic_refinement);set('#chordDetectSevenths',p.detect_sevenths);set('#chordDetectSus',p.detect_sus);set('#chordDetectDimAug',p.detect_dim_aug);set('#chordDetectSlashBass',p.detect_slash_bass);set('#chordTemporalSmoothing',p.temporal_smoothing);set('#chordBeatSync',p.beat_sync);if($('#chordMinDuration'))$('#chordMinDuration').value=p.min_chord_ms??0;if($('#chordMaxChanges'))$('#chordMaxChanges').value=p.max_changes_per_minute??0}
function chordPipelineQuery(){const val=(sel,def='')=>$(sel)?.value??def,check=sel=>!!$(sel)?.checked;return [`preset=${encodeURIComponent(val('#chordPipelinePreset','default-complete'))}`,`sensitivity=${encodeURIComponent(val('#chordSensitivity','45'))}`,`harmonic_refinement=${check('#chordHarmonicRefinement')}`,`detect_sevenths=${check('#chordDetectSevenths')}`,`detect_sus=${check('#chordDetectSus')}`,`detect_dim_aug=${check('#chordDetectDimAug')}`,`detect_slash_bass=${check('#chordDetectSlashBass')}`,`temporal_smoothing=${check('#chordTemporalSmoothing')}`,`beat_sync=${check('#chordBeatSync')}`,`min_chord_ms=${encodeURIComponent(val('#chordMinDuration','1100'))}`,`max_changes_per_minute=${encodeURIComponent(val('#chordMaxChanges','36'))}`]}
function updateChordEngineDisclosure(){const c=textModelCatalog().chords||{},id=$('#textAnalysisChoice')?.value,e=(c.engines||[]).find(x=>x.id===id),m=(c.models||[]).find(x=>x.id===e?.model_id),models=Object.fromEntries((c.models||[]).map(x=>[x.id,x]));if($('#chordEngineLabel'))$('#chordEngineLabel').textContent=e?.display_name||id||'—';let html='';if(e?.profile==='stable')html='<b>Songbook / Stable:</b> priorità Madmom Deep Chroma + CRF (major/minor e transizioni regolarizzate), poi Chordino/MTA come fallback. Pensato per una progressione leggibile con pochi falsi cambi.';else if(e?.profile==='fast')html='<b>Fast:</b> usa Chordino se disponibile, altrimenti MTA Chromagram; gli stadi successivi dipendono dal profilo pipeline scelto.';else if(e?.profile==='accurate')html=`<b>Accurate:</b> priorità ChordFormer → BTC-HCQT → Madmom → Chordino. ChordFormer: ${models.chordformer?.installed?'installato':'non installato'}; BTC-HCQT: ${models['btc-hcqt']?.installed?'installato':'non installato'}.`;else if(e?.profile==='maximum')html=`<b>Maximum accuracy:</b> ensemble dei recognizer disponibili (ChordFormer, BTC-HCQT, Chordino, Madmom) con voto pesato + bass-chroma/refinement. ChordFormer: ${models.chordformer?.installed?'installato':'non installato'}; BTC-HCQT: ${models['btc-hcqt']?.installed?'installato':'non installato'}.`;else if(e?.model_id)html=`Modello: <b>${esc(m?.display_name||e.model_id)}</b> · ${m?.installed?'installato':'scaricabile dal gestore modelli'}${m?.license?`<br>Licenza/pesi: ${esc(m.license)}`:''}`;else html='Questo motore non richiede un modello AI scaricabile.';if($('#chordEngineDisclosure'))$('#chordEngineDisclosure').innerHTML=html}
async function downloadTextAnalysisSelection(kind){const cat=textModelCatalog(),choice=$('#textAnalysisChoice')?.value;try{let modelId=choice;if(kind==='chords'){const e=(cat.chords?.engines||[]).find(x=>x.id===choice);if(!e?.model_id)return toast('Il motore selezionato non richiede un modello');modelId=e.model_id}await startModelDownload(kind,modelId,async()=>{pluginInfo=await api('/api/plugins');toast(currentUser?.native_single_user?'Modello scaricato localmente':'Modello scaricato sul server');if(kind==='chords')updateChordEngineDisclosure()})}catch(e){toast(e.message)}}
async function startTrackTextAnalysis(id,kind,choice=''){
  if(!current)return;
  const track=trackById(id);if(!track)return toast('Traccia non trovata');
  const label=kind==='lyrics'?'Lyrics':'Chords';
  const startButton=$('#utilityBody .form-actions .primary');
  const cancelButton=$('#utilityBody .form-actions .secondary:not(.model-download-btn)');
  const previousStartText=startButton?.textContent||'';
  if(startButton){startButton.disabled=true;startButton.textContent='Preparazione…'}
  if(cancelButton)cancelButton.disabled=true;
  let status=$('#textAnalysisLaunchStatus');
  if(!status){status=document.createElement('div');status.id='textAnalysisLaunchStatus';status.className='workflow-note';$('#utilityBody .form-grid')?.appendChild(status)}
  if(status)status.textContent='Preparazione del progetto e verifica del modello…';
  try{
    await flushAutosave();
    if(status)status.textContent='Avvio del job di estrazione…';
    const param=kind==='lyrics'?'model':'engine';
    let query=[];if(choice)query.push(`${param}=${encodeURIComponent(choice)}`);if(kind==='lyrics'&&$('#lyricsAdvancedAlignment')?.checked)query.push('advanced_alignment=true');if(kind==='chords'){saveChordExtractionSettings();query.push(...chordPipelineQuery());}const suffix=query.length?'?'+query.join('&'):'';
    const job=await api(`/api/projects/${current.id}/tracks/${id}/extract-${kind}-jobs${suffix}`,{method:'POST'});
    // Only now replace the chooser: the progress dialog is already backed by a real job.
    showMediaProgress(`Estrazione ${label}`,job.progress,job.message||'Job avviato','',job.id);
    pollMediaJob(job.id,`Estrazione ${label}`,async()=>{
      current=await api(`/api/projects/${current.id}`);
      mixerMetaTab=kind;current.mixer_meta_tab=kind;
      // Render the freshly loaded timed-text state before persisting UI metadata.
      // collect() reads the hidden lyrics/chords fields; persisting before render
      // would overwrite newly extracted events with the stale pre-job DOM values.
      render();
      await persistCurrentProject(false);
      await syncNativeProjectFile(current.id);
      render();toast(`${label} estratti e sincronizzati nel progetto`);
    });
  }catch(e){
    if(startButton){startButton.disabled=false;startButton.textContent=previousStartText||`Estrai ${kind}`}
    if(cancelButton)cancelButton.disabled=false;
    if(status)status.textContent='Avvio non riuscito: '+e.message;
    toast(e.message);
  }
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
function lane(t,W,i){
  const color=t.color||TRACK_COLORS[i%TRACK_COLORS.length];
  const anySolo=current.tracks.some(x=>x.solo),inaudible=t.mute||(anySolo&&!t.solo),height=trackHeightPx(t);
  return `<div class="lane ${inaudible?'audibly-muted':''} ${selectedTrackIdSet.has(t.id)?'edit-selected':''}" id="lane-${t.id}" data-track="${t.id}" data-track-context-id="${t.id}" style="width:${W}px;--track-color:${color};height:${height}px" oncontextmenu="openTrackContextMenu(event,'${t.id}')"><canvas class="wave" id="wave-${t.id}" width="${W}" height="${height}" ondblclick="event.stopPropagation();openSampleEditor('${t.id}')" title="Doppio click: editor waveform/campioni"></canvas><div class="waveform-progress ${t.waveform_peaks?.length?'hidden':''}" id="wave-progress-${t.id}"><div class="waveform-progress-bar" id="wave-progress-bar-${t.id}" style="width:2%"></div><span id="wave-progress-label-${t.id}">Waveform…</span></div><div class="selection lane-selection" data-selection-track="${t.id}" style="display:none"></div>${(t.clips||[]).map((c,j)=>{const l=Math.max(0,effectiveClipStartMs(t,c))/1000*pxPerSec,w=(c.source_end_ms-c.source_start_ms)/1000*pxPerSec;return `<div class="clip-block" data-track-id="${t.id}" data-clip-id="${c.id}" style="left:${l}px;width:${Math.max(2,w)}px" onpointerdown="beginTimelineClipDrag(event,'${t.id}','${c.id}')" ondblclick="event.stopPropagation();openSampleEditor('${t.id}')" title="Select: trascina il segmento · Shift+trascina: sposta tutti i segmenti della traccia/tracce selezionate"><span class="clip-label">${esc(t.name)}_${String(j+1).padStart(2,'0')}</span></div>`}).join('')}</div>`
}


function timelineChordLaneHtml(W=widthPx()){
  if(!current?.show_chords_playback)return '';
  return (current.chords||[]).map((ch,index)=>{
    const left=Math.max(0,Number(ch.time_ms||0))/1000*pxPerSec;
    const inactive=!!ch.excluded||!!ch.deleted;
    const label=transposeChordLabel(ch.chord||'?',current.pitch_semitones||0);
    return `<button type="button" class="timeline-chord-marker ${inactive?'inactive':''} ${ch.deleted?'deleted':''}" data-chord-index="${index}" style="left:${left}px" onpointerdown="beginTimelineChordDrag(event,${index})" ondblclick="return beginTimelineChordInlineEdit(event,${index})" oncontextmenu="return openTimelineChordContextMenu(event,${index})" title="${esc(lyricsChordsEditorPosition(ch.time_ms||0))} · trascina per cambiare timing · doppio click per modificare">${esc(label)}</button>`;
  }).join('');
}
function refreshTimelineChordLane(){
  const lane=$('#timelineChordLane');if(!lane)return;
  lane.classList.toggle('hidden',!current?.show_chords_playback);
  lane.innerHTML=timelineChordLaneHtml();
}
let timelineChordDrag=null;
function beginTimelineChordDrag(event,index){
  if(event.button!==0)return;event.preventDefault();event.stopPropagation();
  const item=current?.chords?.[Number(index)],pane=$('#timelinePane'),el=event.currentTarget;if(!item||!pane||!el)return;
  const startTime=Number(item.time_ms||0),startX=event.clientX,pointerId=event.pointerId;
  timelineChordDrag={index:Number(index),startTime,startX,pointerId,el,moved:false,lastTime:startTime};
  el.setPointerCapture?.(pointerId);el.classList.add('dragging');
  const move=ev=>{const d=timelineChordDrag;if(!d||ev.pointerId!==d.pointerId)return;const delta=(ev.clientX-d.startX)/Math.max(1,pxPerSec)*1000;d.lastTime=Math.max(0,Math.round(d.startTime+delta));d.moved=d.moved||Math.abs(ev.clientX-d.startX)>2;d.el.style.left=`${d.lastTime/1000*pxPerSec}px`;d.el.title=`${lyricsChordsEditorPosition(d.lastTime)} · rilascio per salvare`;};
  const finish=async ev=>{const d=timelineChordDrag;if(!d||ev.pointerId!==d.pointerId)return;window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',cancel);d.el.classList.remove('dragging');timelineChordDrag=null;if(!d.moved){refreshTimelineChordLane();return}const chord=current?.chords?.[d.index];if(!chord)return;checkpointHistory();ensureEventSnapshot(chord);chord.time_ms=d.lastTime;current.chords.sort((a,b)=>Number(a.time_ms||0)-Number(b.time_ms||0));projectDirty=true;await saveMetaQuickEdit();refreshTimelineChordLane();markDirty(0);};
  const cancel=ev=>{const d=timelineChordDrag;if(!d||ev.pointerId!==d.pointerId)return;window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',cancel);d.el.classList.remove('dragging');timelineChordDrag=null;refreshTimelineChordLane();};
  window.addEventListener('pointermove',move);window.addEventListener('pointerup',finish);window.addEventListener('pointercancel',cancel);
}
function beginTimelineChordInlineEdit(event,index){
  event?.preventDefault?.();event?.stopPropagation?.();const item=current?.chords?.[Number(index)],host=event?.currentTarget;if(!item||!host)return false;
  const input=document.createElement('input');input.className='timeline-chord-inline';input.value=String(item.chord||'');host.replaceChildren(input);input.focus();input.select();
  const cancel=()=>refreshTimelineChordLane();
  const commit=async()=>{if(input.dataset.committed==='1')return;input.dataset.committed='1';const value=String(input.value||'').trim();if(!value){toast('Il chord non può essere vuoto');return cancel()}checkpointHistory();ensureEventSnapshot(item);item.chord=value;projectDirty=true;await saveMetaQuickEdit();refreshTimelineChordLane();markDirty(0)};
  input.addEventListener('pointerdown',e=>e.stopPropagation());input.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();input.blur()}else if(e.key==='Escape'){e.preventDefault();input.dataset.committed='1';cancel()}});input.addEventListener('blur',commit,{once:true});return false;
}
function closeTimelineChordContextMenu(){document.querySelector('#timelineChordContextMenu')?.remove()}
function openTimelineChordContextMenu(event,index){
  event?.preventDefault?.();event?.stopPropagation?.();closeTimelineChordContextMenu();const item=current?.chords?.[Number(index)];if(!item)return false;const inactive=!!item.excluded||!!item.deleted,menu=document.createElement('div');menu.id='timelineChordContextMenu';menu.className='lc-context-menu timeline-chord-context-menu';menu.innerHTML=`<div class="lc-context-title">Chord · ${esc(item.chord||'')}</div><button type="button" data-action="edit">Modifica</button><button type="button" data-action="disable" ${inactive?'disabled':''}>Disabilita</button><button type="button" class="danger-action" data-action="delete" ${item.deleted?'disabled':''}>Cancella</button><button type="button" data-action="enable" ${inactive?'':'disabled'}>Riabilita</button>`;document.body.appendChild(menu);
  menu.querySelectorAll('[data-action]').forEach(btn=>btn.addEventListener('click',()=>{if(btn.disabled)return;const action=btn.dataset.action;closeTimelineChordContextMenu();timelineChordContextAction(action,Number(index))}));const x=Math.max(8,Math.min(Number(event?.clientX||0),window.innerWidth-menu.offsetWidth-8)),y=Math.max(8,Math.min(Number(event?.clientY||0),window.innerHeight-menu.offsetHeight-8));menu.style.left=`${x}px`;menu.style.top=`${y}px`;return false;
}
async function timelineChordContextAction(action,index){
  const item=current?.chords?.[Number(index)];if(!item)return;if(action==='edit'){const marker=document.querySelector(`.timeline-chord-marker[data-chord-index="${Number(index)}"]`);if(marker)return beginTimelineChordInlineEdit({preventDefault(){},stopPropagation(){},currentTarget:marker},index);return}checkpointHistory();ensureEventSnapshot(item);if(action==='disable'){item.deleted=false;item.excluded=true}else if(action==='delete'){item.deleted=true}else if(action==='enable'){item.deleted=false;item.excluded=false}projectDirty=true;await saveMetaQuickEdit();refreshTimelineChordLane();markDirty(0);
}
async function addTimelineChordAtPlayhead(){
  if(!current)return;const chord=prompt('Nuovo chord alla posizione corrente','C');if(chord===null)return;const value=String(chord).trim();if(!value)return toast('Il chord non può essere vuoto');checkpointHistory();current.chords=current.chords||[];current.chords.push({time_ms:Math.max(0,Math.round(playCursorMs||0)),chord:value,excluded:false,deleted:false,manual_override:true});current.chords.sort((a,b)=>Number(a.time_ms||0)-Number(b.time_ms||0));projectDirty=true;await saveMetaQuickEdit();refreshTimelineChordLane();markDirty(0);toast(`Chord aggiunto a ${lyricsChordsEditorPosition(playCursorMs||0)}`);
}
document.addEventListener('click',e=>{if(!e.target.closest?.('#timelineChordContextMenu'))closeTimelineChordContextMenu()});

function inspectorHtml(){
  if(current?.inspector_visible===false)return '';
  const close='<button class="inspector-close" type="button" onclick="closeInspectorPanel()" title="Chiudi pannello Plugins" aria-label="Chiudi pannello Plugins">×</button>';
  const t=selectedTrack();
  if(!t)return `<aside class="inspector" id="inspector"><div class="inspector-tabs"><button class="inspector-tab active">Inspector</button><button class="inspector-tab">Stems</button><button class="inspector-tab">Metadata</button>${close}</div><div class="inspector-body"><p class="hint">Import a track to open the inspector.</p></div></aside>`;
  const i=current.tracks.indexOf(t);
  return `<aside class="inspector" id="inspector"><div class="inspector-tabs"><button class="inspector-tab active">Inspector</button><button class="inspector-tab">Stems</button><button class="inspector-tab">Metadata</button>${close}</div><div class="inspector-body"><div class="inspector-track-title"><span>◉</span>${esc(t.name)}<label class="tool" style="margin-left:auto;min-width:auto;height:28px">Replace<input type="file" accept="audio/*,.mp3,.wav" hidden onchange="replaceTrack('${t.id}',this)"></label></div><div class="inspector-row"><label>Volume</label><input class="track-volume-range" data-volume-track="${t.id}" type="range" min="-60" max="12" step="0.5" value="${t.volume_db}" oninput="setTrackVolume('${t.id}',this.value)"><input class="valuebox volume-number" id="ins-db-${t.id}" data-volume-number="${t.id}" type="number" min="-60" max="12" step="0.1" value="${Number(t.volume_db).toFixed(1)}" oninput="setTrackVolume('${t.id}',this.value)" aria-label="Volume ${esc(t.name)} in dB" title="Volume in dB"></div><div class="inspector-row"><label>Pan</label><input type="range" min="-1" max="1" step="0.01" value="${t.pan||0}" oninput="setTrackPan('${t.id}',this.value)"><div class="valuebox" id="pan-${t.id}">${Number(t.pan||0).toFixed(2)}</div></div><div class="inspector-row"><label>Type</label><select class="model-input" data-i="${i}" data-k="type">${['drums','bass','guitars','keyboards','orchestra','winds','melody','click','choirs','other'].map(x=>`<option ${x===t.type?'selected':''}>${x}</option>`).join('')}</select><div class="valuebox">${t.duration_ms?fmtTime(t.duration_ms/1000):'--'}</div></div><div class="inspector-row"><label>MTA Slot</label><select onchange="setTrackMtaSlot('${t.id}',this.value)"><option value="" ${!t.mta_slot?'selected':''}>Auto</option>${Array.from({length:mtaSlotLimit()},(_,n)=>`<option value="${n+1}" ${Number(t.mta_slot)===n+1?'selected':''}>${n+1}</option>`).join('')}</select><div class="valuebox">${t.mta_slot?`Slot ${t.mta_slot}`:'Auto'}</div></div>${insertPanelHtml(t,false,t.id)}<div class="panel-section"><div class="section-title">Track export</div><div class="track-export-actions"><button onclick="exportTrack('${t.id}','wav')">WAV</button><button onclick="exportTrack('${t.id}','mp3')">MP3</button><button onclick="exportTrack('${t.id}','flac')">FLAC</button></div></div><div class="panel-section"><div class="collapsed-row">› Send</div><div class="collapsed-row">› Track Automation</div><div class="collapsed-row">› Advanced</div></div></div></aside>`;
}
function closeInspectorPanel(){if(!current)return;current.inspector_visible=false;render();markDirty(80)}

function insertPanelHtml(owner,isMaster,trackId=''){const inserts=owner.inserts||owner.master_inserts||[];return `<div class="panel-section"><div class="panel-section-title"><span>⌄ Inserts</span><span>${inserts.length}/16</span></div><div class="insert-list">${inserts.map((x,n)=>insertHtml(x,n,isMaster,trackId)).join('')||'<div class="hint" style="padding:7px">No inserts configured.</div>'}</div>${insertAddHtml(isMaster,trackId)}</div>`}
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
        <input class="plugin-param geq-slider" data-key="${k}" type="range" min="${v.min}" max="${v.max}" step="${v.step}" value="${value}" oninput="$('#geq-val-${k}').textContent=Number(this.value).toFixed(1);scheduleLivePluginParamCommit(${isMaster},'${id}','${trackId}')">
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
function scheduleLivePluginParamCommit(isMaster,id,trackId=''){
  const key=`param:${isMaster?'master':trackId}:${id}`;
  clearTimeout(liveFxRefreshTimers[key]);
  liveFxRefreshTimers[key]=setTimeout(()=>{delete liveFxRefreshTimers[key];commitPluginEditorParams(isMaster,id,trackId)},65);
}
function livePluginControlChanged(key,value,source,isMaster,id,trackId=''){
  syncPluginControl(key,value,source);
  scheduleLivePluginParamCommit(isMaster,id,trackId);
}
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
    :Object.entries(schema).map(([k,v])=>{const value=Number(params[k]??v.default);return `<label class="plugin-field plugin-field-knob"><span>${esc(k.replaceAll('_',' '))}</span><div class="plugin-control-pair"><div class="plugin-knob-shell" style="--knob-turn:${-135+((value-Number(v.min))/(Number(v.max)-Number(v.min)||1))*270}deg" title="${esc(k.replaceAll('_',' '))}"><input class="plugin-knob" data-knob-key="${k}" type="range" min="${v.min}" max="${v.max}" step="${v.step}" value="${value}" oninput="livePluginControlChanged('${k}',this.value,'knob',${isMaster},'${id}','${trackId}')"></div><input class="plugin-param plugin-number" id="plugin-param-${k}" data-key="${k}" type="number" min="${v.min}" max="${v.max}" step="${v.step}" value="${value}" oninput="livePluginControlChanged('${k}',this.value,'number',${isMaster},'${id}','${trackId}')" onblur="commitPluginEditorParams(${isMaster},'${id}','${trackId}')" onkeydown="pluginNumberKey(event,${isMaster},'${id}','${trackId}')"></div><small>${v.min} … ${v.max}</small></label>`}).join('');
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
  return `<div class="mixer-resizer" id="mixerResizer" title="Trascina per ridimensionare il mixer" role="separator" aria-orientation="horizontal" tabindex="0"><span></span></div><div class="mixer-pane" id="mixer">
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
  return `<div class="export-dialog"><div class="export-title">Final output</div>${over?`<div class="export-warning">Project has more tracks than ${current.target}. MTA export will ask how to merge tracks into ${limit} output slots.</div>`:''}<div class="export-format-grid"><button class="format-option" onclick="doExport('mta')"><span>▧ MTA (${current.target==='DAW'?'MTA8 / MTA16':current.target})</span><span>Configura ›</span></button><button class="format-option" onclick="doExport('wav')"><span>♫ WAV</span><span>24 bit / PCM ›</span></button><button class="format-option" onclick="doExport('mp3')"><span>♫ MP3</span><span>Configura bitrate ›</span></button><button class="format-option" onclick="doExport('flac')"><span>♫ FLAC</span><span>Lossless ›</span></button><button class="format-option ${current.lyrics?.length?'':'disabled'}" ${current.lyrics?.length?'onclick="openKaraokeExport()"':'disabled'}><span>▣ MP4 Karaoke</span><span>${current.lyrics?.length?'Configura ›':'Lyrics richieste'}</span></button></div><div class="export-dialog-tools"><button id="exportPreviewStart" class="utility-btn secondary" onclick="previewExportMaster()">▶ Render &amp; Preview Master</button><button id="exportPreviewStop" class="utility-btn secondary export-preview-stop" onclick="stopExportPreview()" disabled>■ Stop anteprima</button><button class="utility-btn secondary" onclick="showMtaAnalysis()">⌁ MTA format analysis</button></div><div class="utility-actions"><button class="utility-btn secondary" onclick="closeUtilityModal()">Annulla</button></div></div>`;
}
let lyricsChordsEditorDraft=null;
let lyricsChordsEditorLyricsDraft=null;
let lyricsChordsEditorSelected=-1;
function editorDraftLyrics(){return lyricsChordsEditorLyricsDraft||current?.lyrics||[]}
function editorLineWords(line,lineIndex){
  const actual=(line?.words||[]).filter(w=>String(w.text||'').trim());
  if(actual.length)return actual.map((w,i)=>({...JSON.parse(JSON.stringify(w)),text:String(w.text||'').trim(),start_ms:Number(w.start_ms??line.time_ms??0),end_ms:Number(w.end_ms??w.start_ms??line.time_ms??0),index:i}));
  const lyrics=editorDraftLyrics(),tokens=String(line?.text||'').trim().split(/\s+/).filter(Boolean),next=lyrics?.[lineIndex+1];
  const start=Number(line?.time_ms||0),end=Number(line?.end_ms||next?.time_ms||start+Math.max(1200,tokens.length*420)),span=Math.max(1,end-start);
  return tokens.map((text,i)=>({text,start_ms:Math.round(start+span*i/Math.max(1,tokens.length)),end_ms:Math.round(start+span*(i+1)/Math.max(1,tokens.length)),syllables:[],index:i}));
}
function editorAutoAnchor(chord){
  const lyrics=editorDraftLyrics();if(!lyrics.length)return{line:0,word:0};
  let li=0;
  for(let i=0;i<lyrics.length;i++){const next=lyrics[i+1]?.time_ms??(lyrics[i].end_ms||Infinity);if(chord.time_ms>=lyrics[i].time_ms&&chord.time_ms<next){li=i;break}if(chord.time_ms>=lyrics[i].time_ms)li=i}
  const words=editorLineWords(lyrics[li],li);if(!words.length)return{line:li,word:0};
  let wi=0,best=Infinity;
  words.forEach((w,i)=>{const mid=(Number(w.start_ms)+Number(w.end_ms))/2,d=Math.abs(mid-Number(chord.time_ms||0));if(d<best){best=d;wi=i}});
  return{line:li,word:wi};
}
function editorChordAnchor(chord){
  const lyrics=editorDraftLyrics();
  if(chord?.manual_anchor&&chord.anchor_line_time_ms!=null&&chord.anchor_word_index!=null){const li=lyrics.findIndex(l=>Number(l.time_ms)===Number(chord.anchor_line_time_ms));if(li>=0)return{line:li,word:Number(chord.anchor_word_index)}}
  return editorAutoAnchor(chord);
}
function lyricsChordsEditorHtml(){
  const lyrics=editorDraftLyrics(),chords=lyricsChordsEditorDraft||[];
  const byLine=new Map();chords.forEach((ch,ci)=>{const a=editorChordAnchor(ch);const key=`${a.line}:${a.word}`;if(!byLine.has(key))byLine.set(key,[]);byLine.get(key).push({ch,ci})});
  const rows=lyrics.map((line,li)=>{const words=editorLineWords(line,li);const wordHtml=words.map((w,wi)=>{const chips=(byLine.get(`${li}:${wi}`)||[]).map(({ch,ci})=>`<button type="button" draggable="true" class="lc-chord ${lyricsChordsEditorSelected===ci?'selected':''} ${ch.manual_anchor?'manual':'auto'} ${ch.excluded?'excluded':''}" data-chord-index="${ci}" onclick="event.stopPropagation();selectLyricsChord(${ci})" ondragstart="dragLyricsChord(event,${ci})" title="${ch.excluded?'Escluso dall’output':(ch.manual_anchor?'Associazione manuale':'Posizione automatica')} · ${fmtTime(Number(ch.time_ms||0)/1000)}">${esc(transposeChordLabel(ch.chord,current.pitch_semitones||0))}</button>`).join('');const split=wi<words.length-1?`<button type="button" class="lc-split-word" onclick="event.stopPropagation();splitLyricsEditorLine(${li},${wi+1})" title="Dividi la riga dopo questa parola">↵</button>`:'';return `<span class="lc-word" data-line-index="${li}" data-word-index="${wi}" ondragover="event.preventDefault()" ondrop="dropLyricsChord(event,${li},${wi})" onclick="assignSelectedLyricsChord(${li},${wi})"><span class="lc-chord-slot">${chips}</span><span class="lc-token">${esc(w.text)}</span>${split}</span>`}).join('');const merge=li<lyrics.length-1?`<button type="button" class="utility-btn compact secondary lc-merge" onclick="mergeLyricsEditorLine(${li})" title="Accorpa con la riga successiva">Accorpa ↓</button>`:'';return `<div class="lc-line"><div class="lc-time">${fmtTime(Number(line.time_ms||0)/1000)}</div><div class="lc-words">${wordHtml}</div><div class="lc-line-actions">${merge}</div></div>`}).join('');
  const selected=lyricsChordsEditorSelected>=0?chords[lyricsChordsEditorSelected]:null;
  const excludeLabel=selected?.excluded?'Reincludi chord selezionato':'Escludi chord selezionato';
  return `<div class="lyrics-chords-editor"><div class="workflow-note"><b>Editor Lyrics + Chords</b><br>Trascina un accordo sopra una parola o selezionalo e fai clic sulla parola. Il simbolo ↵ divide una riga dopo quella parola; <b>Accorpa ↓</b> unisce la riga con la successiva. Gli accordi esclusi restano recuperabili nel progetto ma non vengono usati in playback, PDF o eventi sincronizzati MTA.</div><div class="lc-toolbar"><button type="button" class="utility-btn secondary" onclick="resetLyricsChordAnchors()">Ripristina posizioni automatiche</button><button type="button" class="utility-btn secondary" onclick="toggleSelectedLyricsChordExcluded()" ${selected?'':'disabled'}>${excludeLabel}</button><button type="button" class="utility-btn secondary" onclick="includeAllLyricsChords()">Reincludi tutti</button><button type="button" class="utility-btn primary accent" onclick="saveLyricsChordsEditor()">Salva editor e sincronizzazione MTA</button></div><div class="lc-scroll">${rows||'<div class="hint">Lyrics non disponibili.</div>'}</div></div>`;
}
function openLyricsChordsEditor(){if(!current?.lyrics?.length||!current?.chords?.length)return toast('Servono sia lyrics sia chords');lyricsChordsEditorLyricsDraft=JSON.parse(JSON.stringify(current.lyrics));lyricsChordsEditorDraft=JSON.parse(JSON.stringify(current.chords));lyricsChordsEditorSelected=-1;showUtilityModal('Editor Lyrics + Chords',lyricsChordsEditorHtml());document.querySelector('.utility-modal')?.classList.add('lyrics-chords-editor-modal')}
function refreshLyricsChordsEditor(){const body=document.querySelector('.utility-modal .lyrics-chords-editor');if(!body)return;body.outerHTML=lyricsChordsEditorHtml()}
function selectLyricsChord(index){lyricsChordsEditorSelected=Number(index);refreshLyricsChordsEditor()}
function dragLyricsChord(event,index){lyricsChordsEditorSelected=Number(index);event.dataTransfer?.setData('text/plain',String(index));if(event.dataTransfer)event.dataTransfer.effectAllowed='move'}
function assignLyricsChord(index,lineIndex,wordIndex){const ch=lyricsChordsEditorDraft?.[Number(index)],line=editorDraftLyrics()?.[Number(lineIndex)],word=editorLineWords(line||{},Number(lineIndex))[Number(wordIndex)];if(!ch||!line||!word)return;ch.excluded=false;ch.manual_anchor=true;ch.anchor_line_time_ms=Number(line.time_ms||0);ch.anchor_word_index=Number(wordIndex);ch.anchor_word_text=String(word.text||'');lyricsChordsEditorSelected=Number(index);refreshLyricsChordsEditor()}
function assignSelectedLyricsChord(lineIndex,wordIndex){if(lyricsChordsEditorSelected<0)return;assignLyricsChord(lyricsChordsEditorSelected,lineIndex,wordIndex)}
function dropLyricsChord(event,lineIndex,wordIndex){event.preventDefault();const raw=event.dataTransfer?.getData('text/plain'),idx=raw!==''?Number(raw):lyricsChordsEditorSelected;if(Number.isFinite(idx))assignLyricsChord(idx,lineIndex,wordIndex)}
function toggleSelectedLyricsChordExcluded(){if(lyricsChordsEditorSelected<0||!lyricsChordsEditorDraft?.[lyricsChordsEditorSelected])return;const ch=lyricsChordsEditorDraft[lyricsChordsEditorSelected];ch.excluded=!ch.excluded;refreshLyricsChordsEditor()}
function includeAllLyricsChords(){if(!lyricsChordsEditorDraft)return;lyricsChordsEditorDraft.forEach(ch=>ch.excluded=false);refreshLyricsChordsEditor()}
function chooseLyricsChordAnchor(index){
  const ch=lyricsChordsEditorDraft?.[Number(index)];if(!ch)return;
  const options=[];(editorDraftLyrics()||[]).forEach((line,li)=>{if(line.deleted||line.disabled)return;editorLineWords(line,li).forEach((w,wi)=>options.push(`<option value="${li}:${wi}">${li+1}. ${esc(w.text)} · ${fmtTime(Number(line.time_ms||0)/1000)}</option>`))});
  if(!options.length)return toast('Non ci sono parole lyrics disponibili');
  showUtilityModal('Associa chord a parola',`<div class="form-grid"><p>Puoi associare il chord <b>${esc(ch.chord)}</b> a una parola di qualsiasi linea lyrics.</p><label>Parola<select id="lcAnchorChoice">${options.join('')}</select></label><div class="form-actions"><button class="utility-btn primary" onclick="applyLyricsChordAnchorChoice(${Number(index)})">Associa</button><button class="utility-btn secondary" onclick="openLyricsChordsEditor()">Annulla</button></div></div>`);
}
function applyLyricsChordAnchorChoice(index){const raw=$('#lcAnchorChoice')?.value||'';const [li,wi]=raw.split(':').map(Number);openLyricsChordsEditor();setTimeout(()=>assignLyricsChord(index,li,wi),0)}
function resetLyricsChordAnchors(){if(!lyricsChordsEditorDraft)return;lyricsChordsEditorDraft.forEach(ch=>{ch.manual_anchor=false;ch.anchor_line_time_ms=null;ch.anchor_word_index=null;ch.anchor_word_text=''});lyricsChordsEditorSelected=-1;refreshLyricsChordsEditor()}
function editorWordPayload(word){return{text:String(word?.text||''),start_ms:Number(word?.start_ms||0),end_ms:Number(word?.end_ms??word?.start_ms??0),syllables:JSON.parse(JSON.stringify(word?.syllables||[]))}}
function splitLyricsEditorLine(lineIndex,splitIndex){
  const lyrics=editorDraftLyrics(),li=Number(lineIndex),line=lyrics?.[li];if(!line)return;
  const words=editorLineWords(line,li),cut=Number(splitIndex);if(!Number.isFinite(cut)||cut<=0||cut>=words.length)return toast('Scegli un punto interno alla riga');
  const left=words.slice(0,cut).map(editorWordPayload),right=words.slice(cut).map(editorWordPayload),oldTime=Number(line.time_ms||0),nextTime=Number(lyrics[li+1]?.time_ms||Infinity);
  let newTime=Math.max(oldTime+1,Number(right[0]?.start_ms||oldTime+1));if(Number.isFinite(nextTime))newTime=Math.min(newTime,Math.max(oldTime+1,nextTime-1));
  const originalEnd=line.end_ms!=null?Number(line.end_ms):null;
  const first={...JSON.parse(JSON.stringify(line)),text:left.map(w=>w.text).join(' '),words:left,end_ms:Math.max(oldTime,newTime-1)};
  const second={...JSON.parse(JSON.stringify(line)),time_ms:newTime,text:right.map(w=>w.text).join(' '),words:right,end_ms:originalEnd!=null?Math.max(newTime,originalEnd):null};
  lyrics.splice(li,1,first,second);
  (lyricsChordsEditorDraft||[]).forEach(ch=>{if(!ch.manual_anchor||Number(ch.anchor_line_time_ms)!==oldTime)return;const wi=Number(ch.anchor_word_index||0);if(wi>=cut){ch.anchor_line_time_ms=newTime;ch.anchor_word_index=wi-cut;ch.anchor_word_text=String(right[Math.max(0,Math.min(wi-cut,right.length-1))]?.text||'')}else ch.anchor_word_text=String(left[Math.max(0,Math.min(wi,left.length-1))]?.text||'')});
  refreshLyricsChordsEditor();
}
function mergeLyricsEditorLine(lineIndex){
  const lyrics=editorDraftLyrics(),li=Number(lineIndex),a=lyrics?.[li],b=lyrics?.[li+1];if(!a||!b)return;
  const aw=editorLineWords(a,li).map(editorWordPayload),bw=editorLineWords(b,li+1).map(editorWordPayload),aTime=Number(a.time_ms||0),bTime=Number(b.time_ms||0),offset=aw.length;
  lyrics.splice(li,2,{...JSON.parse(JSON.stringify(a)),text:[a.text,b.text].filter(Boolean).join(' ').replace(/\s+/g,' ').trim(),words:[...aw,...bw],end_ms:b.end_ms!=null?Number(b.end_ms):(a.end_ms!=null?Number(a.end_ms):null)});
  (lyricsChordsEditorDraft||[]).forEach(ch=>{if(!ch.manual_anchor)return;if(Number(ch.anchor_line_time_ms)===bTime){const wi=Number(ch.anchor_word_index||0);ch.anchor_line_time_ms=aTime;ch.anchor_word_index=offset+wi;ch.anchor_word_text=String(bw[Math.max(0,Math.min(wi,bw.length-1))]?.text||ch.anchor_word_text||'')}else if(Number(ch.anchor_line_time_ms)===aTime){const wi=Number(ch.anchor_word_index||0);ch.anchor_word_text=String(aw[Math.max(0,Math.min(wi,aw.length-1))]?.text||ch.anchor_word_text||'')}});
  refreshLyricsChordsEditor();
}
async function saveLyricsChordsEditor(){
  if(!current||!lyricsChordsEditorDraft||!lyricsChordsEditorLyricsDraft)return;
  current.lyrics=JSON.parse(JSON.stringify(lyricsChordsEditorLyricsDraft)).sort((a,b)=>Number(a.time_ms||0)-Number(b.time_ms||0));
  current.chords=JSON.parse(JSON.stringify(lyricsChordsEditorDraft)).sort((a,b)=>Number(a.time_ms||0)-Number(b.time_ms||0));
  try{const saved=await api('/api/projects/'+current.id,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(current)});current=saved;projectDirty=false;lastHistoryState=projectSnapshot();await syncNativeProjectFile(saved.id);closeUtilityModal();render();toast('Editor Lyrics + Chords salvato: override applicati anche agli eventi MTA')}catch(e){toast(e.message)}
}

function metaPanelBodyHtml(expanded=false){
  const config={lyrics:['text','Lyrics'],chords:['chord','Chords'],markers:['label','Markers']},[key,label]=config[mixerMetaTab]||config.lyrics,rows=current[mixerMetaTab]||[];const displayValue=x=>mixerMetaTab==='chords'?transposeChordLabel(x[key],current.pitch_semitones||0):x[key];
  const resetButton=mixerMetaTab==='lyrics'?`<button class="tool danger" onclick="resetTimedData('lyrics')">Reset lyrics</button>`:mixerMetaTab==='chords'?`<button class="tool danger" onclick="resetTimedData('chords')">Reset chords</button>`:'';
  const hasLyrics=!!(current.lyrics||[]).length,hasChords=(current.chords||[]).some(ch=>!ch.excluded);
  const lyricsExports=mixerMetaTab==='lyrics'&&hasLyrics?`<button class="tool" onclick="downloadProjectLyrics(false)">TXT Lyrics</button>${hasChords?`<button class="tool" onclick="downloadProjectLyrics(true)">TXT Lyrics + Chords</button><button class="tool" onclick="downloadProjectChordPro()">ChordPro Lyrics + Chords</button><button class="tool accent" onclick="openLyricsChordsEditor()">Editor Lyrics + Chords</button>`:''}<label class="tool meta-color-tool" title="Colore chords nel PDF"><span>Chord color</span><input id="lyricsPdfChordColor${expanded?'Expanded':''}" type="color" value="#7B1FA2"></label><button class="tool" onclick="previewProjectLyricsPdf()">Anteprima PDF ${hasChords?'Lyrics + Chords':'Lyrics'}</button><button class="tool" onclick="downloadProjectLyricsPdf()">Scarica PDF ${hasChords?'Lyrics + Chords':'Lyrics'}</button>`:'';
  return `<div class="meta-tabs-content ${expanded?'meta-expanded-content':''}"><div class="meta-list">${rows.map(x=>`<div class="meta-line"><time>${fmtTime(x.time_ms/1000)}</time><span>${esc(displayValue(x))}</span></div>`).join('')||`<div class="hint">No synchronized ${label.toLowerCase()} yet.</div>`}</div><div class="meta-actions"><button class="tool" onclick="editTimed('${mixerMetaTab}')">Edit ${label.toLowerCase()}</button>${resetButton}${lyricsExports}</div>${expanded?'':`<textarea id="lyrics" hidden>${esc(linesToText(current.lyrics,'text'))}</textarea><textarea id="chords" hidden>${esc(linesToText(current.chords,'chord'))}</textarea><textarea id="markers" hidden>${esc(linesToText(current.markers,'label'))}</textarea>`}</div>`;
}
function metaPaneHtml(){
  return `<div class="meta-pane" id="metaPane"><div class="dock-tabs meta-dock-tabs"><button class="dock-tab ${mixerMetaTab==='lyrics'?'active':''}" onclick="showMetaPanel('lyrics')">Lyrics</button><button class="dock-tab ${mixerMetaTab==='chords'?'active':''}" onclick="showMetaPanel('chords')">Chords</button><button class="dock-tab ${mixerMetaTab==='markers'?'active':''}" onclick="showMetaPanel('markers')">Markers</button><button class="dock-expand" onclick="openExpandedMetaPanel()" title="Espandi in finestra dedicata">⛶</button><button class="dock-close" onclick="toggleMixerPanel('meta')" title="Nascondi Lyrics/Chords/Markers">×</button></div>${metaPanelBodyHtml(false)}</div>`;
}
function openExpandedMetaPanel(){
  if(!current)return;
  const label={lyrics:'Lyrics',chords:'Chords',markers:'Markers'}[mixerMetaTab]||'Lyrics';
  showUtilityModal(`Lyrics / Chords / Markers · ${label}`,`<div class="expanded-meta-window"><div class="dock-tabs meta-dock-tabs"><button class="dock-tab ${mixerMetaTab==='lyrics'?'active':''}" onclick="showExpandedMetaTab('lyrics')">Lyrics</button><button class="dock-tab ${mixerMetaTab==='chords'?'active':''}" onclick="showExpandedMetaTab('chords')">Chords</button><button class="dock-tab ${mixerMetaTab==='markers'?'active':''}" onclick="showExpandedMetaTab('markers')">Markers</button><button class="dock-close" onclick="closeUtilityModal()" title="Torna alla dimensione standard">↙</button></div><div id="expandedMetaBody">${metaPanelBodyHtml(true)}</div></div>`);
  document.querySelector('.utility-modal')?.classList.add('meta-expanded-modal');
}
function showExpandedMetaTab(tab){mixerMetaTab=tab;if(current){current.mixer_meta_tab=tab;markDirty(250)};const body=$('#expandedMetaBody');if(body)body.innerHTML=metaPanelBodyHtml(true);}

function mixerHeightBounds(){
  const main=document.querySelector('.main-area');
  const available=Math.max(180,Math.floor(main?.getBoundingClientRect().height||window.innerHeight||700));
  const min=180;
  const editorMin=Math.min(260,Math.max(120,Math.floor(available*.28)));
  const max=Math.max(min,Math.min(900,available-editorMin));
  return{min,max};
}
function applyMixerHeight(value,{persist=false}={}){
  if(!current)return;
  const {min,max}=mixerHeightBounds();
  const requested=Number(value||current.mixer_height_px||262);
  const height=Math.max(min,Math.min(max,Number.isFinite(requested)?requested:262));
  const main=document.querySelector('.main-area');
  if(main)main.style.setProperty('--mixer-height',`${height}px`);
  const dock=$('#mixerDock');if(dock)dock.style.height=`${height}px`;
  if(persist&&Number(current.mixer_height_px)!==height){current.mixer_height_px=Math.round(height);markDirty(180)}
  return height;
}
function updateMixerDockLayout(){
  const dock=$('#mixerDock');if(!dock||!current)return;
  const meta=!!current.metadata_panel_visible;
  dock.classList.toggle('meta-hidden',!meta);
  dock.classList.toggle('sidepanels-hidden',!meta);
  dock.style.gridTemplateColumns=meta?'minmax(0,1fr) 320px':'minmax(0,1fr)';
  applyMixerHeight(current.mixer_height_px||262);
  const mixer=$('#mixer');if(mixer)mixer.style.width='100%';
}
function bindMixerResizer(){
  const handle=$('#mixerResizer');if(!handle||!current)return;
  const finish=()=>{
    if(!mixerResizeState)return;
    document.body.classList.remove('mixer-resizing');
    const height=applyMixerHeight(mixerResizeState.height,{persist:true});
    mixerResizeState=null;
    if(height)current.mixer_height_px=Math.round(height);
  };
  handle.addEventListener('pointerdown',e=>{
    if(e.button!==0&&e.pointerType!=='touch')return;
    e.preventDefault();handle.setPointerCapture?.(e.pointerId);
    mixerResizeState={startY:e.clientY,startHeight:applyMixerHeight(current.mixer_height_px||262)||262,height:Number(current.mixer_height_px||262)};
    document.body.classList.add('mixer-resizing');
  });
  handle.addEventListener('pointermove',e=>{
    if(!mixerResizeState)return;
    mixerResizeState.height=mixerResizeState.startHeight-(e.clientY-mixerResizeState.startY);
    mixerResizeState.height=applyMixerHeight(mixerResizeState.height)||mixerResizeState.height;
  });
  handle.addEventListener('pointerup',finish);handle.addEventListener('pointercancel',finish);
  handle.addEventListener('keydown',e=>{
    if(!['ArrowUp','ArrowDown','Home','End'].includes(e.key))return;
    e.preventDefault();const {min,max}=mixerHeightBounds();let next=Number(current.mixer_height_px||262);
    if(e.key==='ArrowUp')next+=20;else if(e.key==='ArrowDown')next-=20;else if(e.key==='Home')next=min;else next=max;
    const height=applyMixerHeight(next,{persist:true});if(height)current.mixer_height_px=Math.round(height);
  });
}
window.addEventListener('resize',()=>{if(current)requestAnimationFrame(()=>applyMixerHeight(current.mixer_height_px||262))});
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
function collect(){if(!current)return;$$('.model-input').forEach(el=>{const t=current.tracks[+el.dataset.i];if(t)t[el.dataset.k]=el.value});/* Timed lyrics/chords/markers are structured project events. Hidden legacy textareas are display mirrors only and must never overwrite word timing, manual anchors, disabled/deleted flags, snapshots or MTA overrides. */}
function projectSnapshot(){return current?JSON.parse(JSON.stringify(current)):null}
function resetSessionHistory(){undoStack=[];redoStack=[];historyProjectId=current?.id||null;lastHistoryState=projectSnapshot();timelineClipboard=null;updateEditActionState()}
function ensureSessionHistory(){if((current?.id||null)!==historyProjectId)resetSessionHistory();else if(!lastHistoryState&&current)lastHistoryState=projectSnapshot()}
function checkpointHistory(){if(!current)return;ensureSessionHistory();if(JSON.stringify(current)!==JSON.stringify(lastHistoryState)){undoStack.push(lastHistoryState);if(undoStack.length>100)undoStack.shift();redoStack=[];lastHistoryState=projectSnapshot();updateEditActionState()}}
async function persistCurrentProject(showToast=false){if(!current)return;collect();const saved=await api('/api/projects/'+current.id,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(current)});if(current&&current.id===saved.id)current=saved;projectDirty=false;lastHistoryState=projectSnapshot();$('#headerProjectName').textContent=current?.title||'—';if(showToast)toast('Progetto salvato')}
async function restoreHistorySnapshot(snapshot,label){if(!snapshot||!current)return;current=JSON.parse(JSON.stringify(snapshot));selectedTrackId=current.tracks.some(t=>t.id===selectedTrackId)?selectedTrackId:(current.tracks[0]?.id||null);projectDirty=true;render();await persistCurrentProject(false);lastHistoryState=projectSnapshot();updateEditActionState();toast(label)}
async function undoEdit(){ensureSessionHistory();checkpointHistory();if(!undoStack.length)return toast('Nessuna operazione da annullare');const target=undoStack.pop();redoStack.push(projectSnapshot());await restoreHistorySnapshot(target,'Undo')}
async function redoEdit(){ensureSessionHistory();if(!redoStack.length)return toast('Nessuna operazione da ripristinare');undoStack.push(projectSnapshot());const target=redoStack.pop();await restoreHistorySnapshot(target,'Redo')}
function editTrackIds(){let ids=selectedTrackIds();if(!ids.length&&selectedTrackId)ids=[selectedTrackId];return ids}
function selectionBounds(){return[Math.round(Math.min(sel.a,sel.b)),Math.round(Math.max(sel.a,sel.b))]}
function clipId(){return'clip_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,9)}
function selectedClipFragments(){if(!current)return[];const[a,b]=selectionBounds();if(b-a<2)return[];const ids=new Set(editTrackIds()),out=[];for(const t of current.tracks){if(!ids.has(t.id))continue;const delay=trackDelayMs(t);for(const c of t.clips||[]){const cs=Number(c.timeline_start_ms||0)+delay,ce=cs+(c.source_end_ms-c.source_start_ms),is=Math.max(a,cs),ie=Math.min(b,ce);if(ie>is)out.push({track_id:t.id,offset_ms:is-a,source_start_ms:c.source_start_ms+(is-cs),source_end_ms:c.source_start_ms+(ie-cs)})}}return out}
function removeRangeFromTracks(a,b,trackIds,ripple=false){
  const ids=new Set(trackIds),duration=Math.max(0,b-a);
  for(const t of current.tracks){
    if(!ids.has(t.id))continue;
    const delay=trackDelayMs(t),next=[];
    for(const c of t.clips||[]){
      const raw=Number(c.timeline_start_ms||0),cs=raw+delay,ce=cs+(c.source_end_ms-c.source_start_ms);
      if(ce<=a){next.push(c);continue}
      if(cs>=b){next.push(ripple?{...c,timeline_start_ms:raw-duration}:c);continue}
      if(cs<a)next.push({...c,id:clipId(),source_end_ms:c.source_start_ms+(a-cs)});
      if(ce>b){
        const visibleStart=ripple?a:b;
        next.push({...c,id:clipId(),source_start_ms:c.source_start_ms+(b-cs),timeline_start_ms:visibleStart-delay});
      }
    }
    t.clips=next.sort((x,y)=>x.timeline_start_ms-y.timeline_start_ms);
  }
}
function splitSelectedTracksAt(ms){
  if(!current)return;
  const ids=selectedTrackIds();if(!ids.length)return toast('Seleziona almeno una traccia');
  const at=Math.max(0,Math.round(ms));let count=0;checkpointHistory();
  for(const t of current.tracks){
    if(!ids.includes(t.id))continue;
    const delay=trackDelayMs(t),out=[];
    for(const c of t.clips||[]){
      const raw=Number(c.timeline_start_ms||0),cs=raw+delay,ce=cs+(c.source_end_ms-c.source_start_ms);
      if(at<=cs||at>=ce){out.push(c);continue}
      const sourceCut=c.source_start_ms+(at-cs);
      out.push({...c,id:clipId(),source_end_ms:sourceCut});
      out.push({...c,id:clipId(),source_start_ms:sourceCut,timeline_start_ms:at-delay});
      count++;
    }
    t.clips=out.sort((x,y)=>x.timeline_start_ms-y.timeline_start_ms);
  }
  if(!count)return toast('Nessun clip attraversa il punto di split nelle tracce selezionate');
  projectDirty=true;render();markDirty();toast(`Split applicato a ${count} clip nelle tracce selezionate`);
}

function beginTimelineClipDrag(event,trackId,clipId){
  if(timelineTool!=='select'||event.button!==0)return;
  const track=trackById(trackId),clip=track?.clips?.find(c=>String(c.id)===String(clipId));
  if(!track||!clip)return;
  event.preventDefault();event.stopPropagation();
  if(!selectedTrackIdSet.has(trackId)){
    selectedTrackId=trackId;selectedTrackIdSet=new Set([trackId]);
    updateSel();
  }
  const group=!!event.shiftKey;
  const ids=group?new Set(selectedTrackIds()):new Set([trackId]);
  const items=[];
  for(const t of current.tracks||[]){
    if(!ids.has(t.id))continue;
    for(const c of t.clips||[]){
      if(!group&&!(t.id===trackId&&String(c.id)===String(clipId)))continue;
      const el=document.querySelector(`.clip-block[data-track-id="${CSS.escape(String(t.id))}"][data-clip-id="${CSS.escape(String(c.id))}"]`);
      items.push({track:t,clip:c,start:Number(c.timeline_start_ms||0),el});
    }
  }
  if(!items.length)return;
  const minStart=Math.min(...items.map(x=>x.start));
  timelineClipDrag={pointerId:event.pointerId,startX:event.clientX,items,minDelta:-minStart,delta:0,group,primaryTrackId:trackId,moved:false};
  event.currentTarget?.setPointerCapture?.(event.pointerId);
  document.body.classList.add('moving-timeline-clip');
  const move=ev=>{
    const d=timelineClipDrag;if(!d||ev.pointerId!==d.pointerId)return;
    ev.preventDefault();
    let delta=Math.round((ev.clientX-d.startX)/pxPerSec*1000);
    delta=Math.max(d.minDelta,delta);
    d.delta=delta;d.moved=d.moved||Math.abs(delta)>=2;
    const px=delta/1000*pxPerSec;
    for(const item of d.items)if(item.el)item.el.style.transform=`translateX(${px}px)`;
  };
  const finish=ev=>{
    const d=timelineClipDrag;if(!d||ev.pointerId!==d.pointerId)return;
    window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',cancel);
    document.body.classList.remove('moving-timeline-clip');timelineClipDrag=null;
    for(const item of d.items)if(item.el)item.el.style.transform='';
    if(!d.moved||!d.delta)return;
    checkpointHistory();
    for(const item of d.items)item.clip.timeline_start_ms=Math.max(0,item.start+d.delta);
    for(const t of current.tracks||[])if(ids.has(t.id))t.clips=(t.clips||[]).sort((a,b)=>a.timeline_start_ms-b.timeline_start_ms);
    projectDirty=true;render();markDirty(80);
    if(d.group)toast(ids.size>1?'Segmenti delle tracce selezionate spostati sulla timeline':'Segmenti della traccia spostati sulla timeline');
    else toast('Segmento spostato sulla timeline');
  };
  const cancel=ev=>{
    const d=timelineClipDrag;if(!d||ev.pointerId!==d.pointerId)return;
    window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',cancel);
    document.body.classList.remove('moving-timeline-clip');timelineClipDrag=null;
    for(const item of d.items)if(item.el)item.el.style.transform='';
  };
  window.addEventListener('pointermove',move,{passive:false});window.addEventListener('pointerup',finish);window.addEventListener('pointercancel',cancel);
}
function setTimelineTool(tool){
  if(!['select','split','range'].includes(tool))return;
  timelineTool=tool;render();
}
function toggleRippleTool(){rippleEnabled=!rippleEnabled;render();toast(rippleEnabled?'Ripple attivo sulle tracce selezionate':'Ripple disattivato')}

function copyTimelineSelection(){const[a,b]=selectionBounds(),parts=selectedClipFragments();if(b-a<2)return toast('Seleziona prima un intervallo nella timeline');if(!parts.length)return toast('La selezione non contiene audio nelle tracce selezionate');timelineClipboard={duration_ms:b-a,parts};updateEditActionState();toast('Selezione copiata')}
function cutTimelineSelection(){const[a,b]=selectionBounds(),ids=editTrackIds(),parts=selectedClipFragments();if(b-a<2)return toast('Seleziona prima un intervallo nella timeline');if(!ids.length||!parts.length)return toast('La selezione non contiene audio nelle tracce selezionate');checkpointHistory();timelineClipboard={duration_ms:b-a,parts};removeRangeFromTracks(a,b,ids,rippleEnabled);projectDirty=true;render();markDirty();updateEditActionState();toast(rippleEnabled?'Selezione tagliata con ripple':'Selezione tagliata')}
function pasteTimelineSelection(){if(!current||!timelineClipboard?.parts?.length)return toast('Clipboard timeline vuota');checkpointHistory();const dest=Math.max(0,Math.round(playCursorMs||Math.min(sel.a,sel.b)||0));for(const x of timelineClipboard.parts){const t=trackById(x.track_id);if(!t)continue;t.clips=t.clips||[];t.clips.push({id:clipId(),source_start_ms:x.source_start_ms,source_end_ms:x.source_end_ms,timeline_start_ms:dest+x.offset_ms});t.clips.sort((a,b)=>a.timeline_start_ms-b.timeline_start_ms)}projectDirty=true;render();markDirty();toast('Selezione incollata')}
function removeTimelineSelection(){if(!current)return;const[a,b]=selectionBounds(),ids=editTrackIds();if(b-a<2)return toast('Seleziona prima un intervallo nella timeline');if(!ids.length)return toast('Seleziona almeno una traccia');checkpointHistory();removeRangeFromTracks(a,b,ids,rippleEnabled);projectDirty=true;render();markDirty();toast(rippleEnabled?'Parte rimossa con ripple':'Parte di traccia rimossa')}
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
    await syncNativeProjectFile(current?.id);
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
function selectTrack(id,event=null){
  captureUiState();
  const multi=!!(event&&(event.ctrlKey||event.metaKey));
  if(multi){
    if(selectedTrackIdSet.has(id)){
      if(selectedTrackIdSet.size>1)selectedTrackIdSet.delete(id);
    }else selectedTrackIdSet.add(id);
    selectedTrackId=selectedTrackIdSet.has(id)?id:([...selectedTrackIdSet][0]||id);
  }else{selectedTrackIdSet=new Set([id]);selectedTrackId=id}
  render();
}
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
  if(renderedMasterRefreshPromise){renderedMasterRefreshQueued=true;return}
  renderedMasterRefreshQueued=false;
  renderedMasterRefreshPromise=(async()=>{
    const previous=playAudio,cursor=playCursorMs,token=++playbackToken;
    try{
      collect();
      await persistCurrentProject(false);
      const audio=new Audio(`/api/projects/${current.id}/preview-mix?t=${Date.now()}`);
      await new Promise((resolve,reject)=>{audio.addEventListener('loadedmetadata',resolve,{once:true});audio.addEventListener('error',()=>reject(new Error('Anteprima renderizzata non disponibile')),{once:true});audio.load()});
      if(token!==playbackToken){setRenderPlaybackPreparing(false);return}
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
    }finally{
      renderedMasterRefreshPromise=null;
      if(renderedMasterRefreshQueued){renderedMasterRefreshQueued=false;setTimeout(()=>refreshRenderedMasterForMixState(),0)}
    }
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
    // Keep the old decoder audible while the processed replacement is built.
    // The replacement joins the central transport clock muted, then crossfades.
    const replacement=await makeTrackPlayback(track,true,false,true,true);installPlaybackRecovery(replacement);
    const expected=transportClockRunning?transportMediaSeconds():playCursorMs/1000/tempoRatio();
    replacement.audio.currentTime=Math.min(expected,Math.max(0,(replacement.audio.duration||0)-0.01));
    await waitForMediaBuffer(replacement.audio,track.name,1600);
    await replacement.audio.play();
    const locked=transportClockRunning?transportMediaSeconds():expected;
    try{replacement.audio.currentTime=Math.min(locked,Math.max(0,(replacement.audio.duration||locked)-0.005))}catch(e){}
    const now=audioCtx?.currentTime||0,target=playbackGainForTrack(track,replacement);
    replacement.gainNode.gain.cancelScheduledValues(now);replacement.gainNode.gain.setValueAtTime(0,now);replacement.gainNode.gain.linearRampToValueAtTime(target,now+.018);
    if(oldItem.gainNode){const oldNow=audioCtx?.currentTime||now,oldValue=oldItem.gainNode.gain.value;oldItem.gainNode.gain.cancelScheduledValues(oldNow);oldItem.gainNode.gain.setValueAtTime(oldValue,oldNow);oldItem.gainNode.gain.linearRampToValueAtTime(0,oldNow+.018)}
    trackPlaybacks.splice(oldIndex,1,replacement);
    if(wasClock)playAudio=replacement.audio;
    setTimeout(()=>{try{oldItem.audio.pause();oldItem.audio.removeAttribute('src');oldItem.audio.load()}catch(e){}},24);
  }catch(e){console.warn('Aggiornamento live FX traccia fallito',trackId,e)}
}
function queueLiveFxRefresh(isMaster,trackId='',delay=70){
  if(!playAudio&&!trackPlaybacks.length)return;
  if(renderedMasterPlayback){queueRenderedMasterRefresh(delay);return}
  if(isMaster){
    // Master inserts operate on the summed signal. In stem-render mode keep the
    // transport running and rebuild processed stems without stopping playback;
    // track controls themselves remain fully live in WebAudio.
    if(renderedStemPlayback){
      for(const t of current?.tracks||[]){
        clearTimeout(liveFxRefreshTimers[t.id]);
        liveFxRefreshTimers[t.id]=setTimeout(()=>{delete liveFxRefreshTimers[t.id];refreshDynamicTrackPlayback(t.id)},delay);
      }
    }
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
// Waveform renderer is defined later with zoom-aware high-resolution envelope support.
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
    if(timelineTool==='split'){e.preventDefault();splitSelectedTracksAt(downMs);setPlayCursor(downMs);return}
    if(timelineTool==='select'){sel={a:0,b:0};updateSel();setPlayCursor(downMs);return}
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
function updateSel(){const a=Math.min(sel.a,sel.b),b=Math.max(sel.a,sel.b),ids=new Set(selectedTrackIds()),visible=Math.abs(b-a)>2;$$('.lane-selection').forEach(s=>{const active=visible&&ids.has(s.dataset.selectionTrack);s.style.display=active?'block':'none';s.style.left=`${a/1000*pxPerSec}px`;s.style.width=`${Math.max(1,(b-a)/1000*pxPerSec)}px`});if($('#selectionInfo'))$('#selectionInfo').textContent=`${(a/1000).toFixed(3)} → ${(b/1000).toFixed(3)} s`;if($('#selectedTrackCount'))$('#selectedTrackCount').textContent=tr(`${ids.size} selected`,`${ids.size} selezionat${ids.size===1?'a':'e'}`)}

async function deleteTracksByIds(ids){
  if(!current||!ids?.length)return;
  const names=ids.map(id=>trackById(id)?.name).filter(Boolean);
  if(!confirm(`Eliminare ${ids.length===1?'la traccia':'le tracce'} ${names.join(', ')} dal progetto?`))return;
  clearTimeout(autosaveTimer);autosaveTimer=null;
  collect();
  const before=JSON.parse(JSON.stringify(current));
  const wanted=new Set(ids.map(String));
  current.tracks=(current.tracks||[]).filter(t=>!wanted.has(String(t.id)));
  selectedTrackIdSet=new Set([...selectedTrackIdSet].filter(id=>!wanted.has(String(id))));
  if(selectedTrackId&&wanted.has(String(selectedTrackId)))selectedTrackId=current.tracks[0]?.id||null;
  if(selectedTrackId&&!selectedTrackIdSet.size)selectedTrackIdSet=new Set([selectedTrackId]);
  render();
  try{
    const saved=await api(`/api/projects/${before.id}/delete-tracks`,{
      method:'POST',
      headers:{'content-type':'application/json'},
      body:JSON.stringify({track_ids:ids,project:before})
    });
    current=saved;projectDirty=false;lastHistoryState=projectSnapshot();
    if(selectedTrackId&&!current.tracks.some(t=>t.id===selectedTrackId))selectedTrackId=current.tracks[0]?.id||null;
    render();
    void syncNativeProjectFile(saved.id);
    void refresh();
    toast(ids.length===1?'Traccia eliminata':'Tracce eliminate');
  }catch(e){
    current=before;selectedTrackId=current.tracks?.[0]?.id||null;selectedTrackIdSet=selectedTrackId?new Set([selectedTrackId]):new Set();render();toast('Cancellazione tracce fallita: '+e.message);
  }
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
  const a=Math.round(Math.min(sel.a,sel.b)),b=Math.round(Math.max(sel.a,sel.b)),ids=selectedTrackIds();
  if(b-a<2)return toast('Seleziona prima un intervallo nella timeline');
  if(!ids.length)return toast('Seleziona almeno una traccia');
  await save();
  current=await api(`/api/projects/${current.id}/delete-range`,{
    method:'POST',
    headers:{'content-type':'application/json'},
    body:JSON.stringify({start_ms:a,end_ms:b,track_ids:ids,ripple:rippleEnabled})
  });
  sel={a:0,b:0};render();toast(rippleEnabled?'Intervallo eliminato con ripple sulle tracce selezionate':'Intervallo eliminato dalle tracce selezionate');
}

function showMediaProgress(title,pct,message,detail='',cancelJobId=''){
  const raw=Number(pct),indeterminate=Number.isFinite(raw)&&raw<0,p=indeterminate?35:Math.max(0,Math.min(100,raw||0));
  setMobileBusy(indeterminate||p<100);
  const cancel=cancelJobId?`<div class="utility-actions"><button class="utility-btn danger-action ai-model-action-btn" onclick="cancelMediaJob('${esc(cancelJobId)}')">Annulla estrazione</button></div>`:'';
  const partial=detail?`<div class="workflow-note media-live-output">${esc(detail)}</div>`:'';
  showUtilityModal(title,`<div class="stem-progress-card"><div class="stem-progress-head"><b>${esc(title)}</b><span>${indeterminate?'…':p+'%'}</span></div><div class="stem-progress ${indeterminate?'indeterminate':''}"><div class="stem-progress-fill" style="width:${p}%"></div></div><div class="stem-progress-message">${esc(message||'')}</div>${partial}${cancel}</div>`);
}
function mediaPartialText(job){
  const p=job?.partial;if(!p?.items?.length)return '';
  if(p.kind==='lyrics')return p.items.map(x=>x.text||'').filter(Boolean).join('\n');
  if(p.kind==='chords')return p.items.map(x=>{const ms=Number(x.time_ms||0),m=Math.floor(ms/60000),sec=Math.floor(ms/1000)%60;return `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}  ${x.chord||''}`}).join('\n');
  return '';
}
async function cancelMediaJob(jobId){try{await api(`/api/media-jobs/${jobId}/cancel`,{method:'POST'});toast('Annullamento richiesto…')}catch(e){toast(e.message)}}
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
    const live=mediaPartialText(job);
    showMediaProgress(title,job.progress,job.message,live||job.error||'',job.cancel_supported&&['queued','running'].includes(job.status)?jobId:'');
    if(job.status==='completed'){setMobileBusy(false);await onDone(job);return}
    if(job.status==='failed'||job.status==='cancelled'){setMobileBusy(false);toast(job.status==='cancelled'?'Estrazione annullata':(job.error||'Operazione fallita'));return}
    mediaProgressTimer=setTimeout(()=>pollMediaJob(jobId,title,onDone),500);
  }catch(e){setMobileBusy(false);toast(e.message)}
}
async function blobToDataUrl(blob){return await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result||''));reader.onerror=()=>reject(reader.error||new Error('Impossibile leggere il file generato'));reader.readAsDataURL(blob)})}
async function saveGeneratedBlob(blob,filename,mime='application/octet-stream'){
  const dot=filename.lastIndexOf('.'),ext=(dot>=0?filename.slice(dot+1):'').toLowerCase();
  const saveableExts=['pdf','txt','cho','wav','mp3','flac'];
  if(currentUser?.native_single_user&&window.pywebview?.api?.save_generated_file&&saveableExts.includes(ext)){
    const dataUrl=await blobToDataUrl(blob);
    const saved=await window.pywebview.api.save_generated_file(filename.replace(/\.[^.]+$/,''),ext,dataUrl);
    if(saved?.ok){toast(`File salvato in ${saved.path}`);return true}
    if(saved?.cancelled)return true;
  }
  if(typeof window.showSaveFilePicker==='function'&&saveableExts.includes(ext)){
    try{
      const labels={pdf:'PDF Document',cho:'ChordPro',txt:'Text File',wav:'WAV Audio',mp3:'MP3 Audio',flac:'FLAC Audio'};
      const handle=await window.showSaveFilePicker({suggestedName:filename,types:[{description:labels[ext]||'Generated file',accept:{[mime||'application/octet-stream']:[`.${ext}`]}}]});
      const writable=await handle.createWritable();await writable.write(blob);await writable.close();toast(`File salvato: ${filename}`);return true;
    }catch(e){if(e?.name==='AbortError')return true;throw e}
  }
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),1500);return true;
}
async function saveGeneratedBlobToNativePath(blob,path){
  if(!path||!window.pywebview?.api?.save_generated_file_to_path)return false;
  const dataUrl=await blobToDataUrl(blob);
  const saved=await window.pywebview.api.save_generated_file_to_path(path,dataUrl);
  if(!saved?.ok)throw new Error('Salvataggio file nativo non riuscito');
  return true;
}
async function downloadWithProgress(url,filename,title,share=false,mime='application/octet-stream',nativeOutputPath=''){
  showMediaProgress(title,2,'Preparazione download');
  if(isMobileClient()&&mobileSaveRemoteFile(url,filename,mime,share)){
    setMobileBusy(false);$('#utilityBackdrop')?.classList.add('hidden');return;
  }
  const r=await fetch(url);
  if(!r.ok)throw new Error(await r.text());
  const total=Number(r.headers.get('content-length')||0),reader=r.body?.getReader(),chunks=[];let loaded=0,blob;
  if(reader){
    while(true){const {done,value}=await reader.read();if(done)break;chunks.push(value);loaded+=value.length;if(total)showMediaProgress(title,90+Math.round(loaded/total*10),'Download del file')}
    blob=new Blob(chunks,{type:mime||r.headers.get('content-type')||'application/octet-stream'});
  }else blob=await r.blob();
  if(nativeOutputPath){
    const saved=await saveGeneratedBlobToNativePath(blob,nativeOutputPath);
    if(!saved)await saveGeneratedBlob(blob,filename,mime||r.headers.get('content-type')||'application/octet-stream');
  }else await saveGeneratedBlob(blob,filename,mime||r.headers.get('content-type')||'application/octet-stream');
  setMobileBusy(false);$('#utilityBackdrop')?.classList.add('hidden');
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
      <div class="workflow-note warning"><b>Nota sui tempi di elaborazione:</b> separazione stem, estrazione lyrics e analisi chords possono richiedere parecchio tempo in base alla durata del brano, ai modelli scelti e all’hardware disponibile.</div><label class="workflow-check"><input id="stemSplitBackingVocals" type="checkbox" onchange="updateBackingModelRow()"> Separa anche voce principale e backing vocals (secondo passaggio AI)</label><label class="workflow-field hidden" id="backingModelRow"><span>Modello Lead / Backing Vocals</span><select id="stemBackingVocalModel">${backingModels}<option value="ffmpeg-center-side">Fallback DSP center/side</option></select><button type="button" onclick="downloadSelectedBackingModel()">Scarica modello</button></label>
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
async function downloadStemTextModel(kind){const cat=textModelCatalog();try{let modelId;if(kind==='lyrics'){modelId=$('#stemLyricsModel')?.value;if(!modelId)return}else{const id=$('#stemChordsEngine')?.value,e=(cat.chords?.engines||[]).find(x=>x.id===id);if(!e?.model_id)return toast('Questo motore non richiede un modello');modelId=e.model_id}await startModelDownload(kind,modelId,async()=>{pluginInfo=await api('/api/plugins');toast(currentUser?.native_single_user?'Modello scaricato localmente':'Modello scaricato sul server');updateStemChordEngineDisclosure()})}catch(e){toast(e.message)}}
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
  const label=kind==='lyrics'?'Lyrics':'Chords',param=kind==='lyrics'?'model':'engine';let query=[];if(choice)query.push(`${param}=${encodeURIComponent(choice)}`);if(kind==='lyrics'&&$('#lyricsAdvancedAlignment')?.checked)query.push('advanced_alignment=true');const suffix=query.length?'?'+query.join('&'):'';const job=await api(`/api/projects/${projectId}/tracks/${trackId}/extract-${kind}-jobs${suffix}`,{method:'POST'});
  for(;;){
    const state=await api(`/api/media-jobs/${job.id}`);
    showMediaProgress(`Estrazione ${label}`,state.progress,state.message,mediaPartialText(state),state.cancel_supported&&['queued','running'].includes(state.status)?job.id:'');
    if(state.status==='completed')return state;
    if(state.status==='failed'||state.status==='cancelled')throw new Error(state.error||(state.status==='cancelled'?`Estrazione ${kind} annullata`:`Estrazione ${kind} non riuscita`));
    await new Promise(resolve=>setTimeout(resolve,500));
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
  const lyricsModel=$('#stemLyricsModel')?.value||textModelCatalog().lyrics?.default_model||'turbo';
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
  if(!peaks.length){ctx.fillStyle='#6d8294';ctx.fillText('waveform unavailable',10,Math.max(16,c.height/2));return}
  const color=t.color||'#2f81f7',mid=c.height/2,scale=Math.max(4,c.height*.43);
  // r207 signed min/max cache: [min0,max0,min1,max1,...]. Legacy projects
  // contain positive absolute peaks only and remain fully drawable until their
  // waveform revision causes an automatic high-resolution regeneration.
  const signedEnvelope=peaks.length>=4096&&peaks.length%2===0&&peaks.some(v=>Number(v)<0);
  const bins=signedEnvelope?peaks.length/2:peaks.length;
  const durationMs=Math.max(1,Number(t.duration_ms||0));
  const sampleBin=(position,fromBin,toBin)=>{
    const a=Math.max(fromBin,Math.min(toBin-1,Math.floor(position)));
    const b=Math.max(fromBin,Math.min(toBin-1,a+1));
    const f=Math.max(0,Math.min(1,position-a));
    if(signedEnvelope){
      return [Number(peaks[a*2]||0)*(1-f)+Number(peaks[b*2]||0)*f,Number(peaks[a*2+1]||0)*(1-f)+Number(peaks[b*2+1]||0)*f];
    }
    const v=Number(peaks[a]||0)*(1-f)+Number(peaks[b]||0)*f;return[-v,v];
  };
  for(const clip of t.clips||[]){
    const sourceStart=Math.max(0,Number(clip.source_start_ms||0));
    const sourceEnd=Math.max(sourceStart+1,Number(clip.source_end_ms||durationMs));
    const tl=Math.max(0,effectiveClipStartMs(t,clip))/1000*pxPerSec;
    const tw=(sourceEnd-sourceStart)/1000*pxPerSec;if(tw<=0)continue;
    const firstBin=Math.max(0,Math.min(bins-1,Math.floor(sourceStart/durationMs*bins)));
    const lastBin=Math.max(firstBin+1,Math.min(bins,Math.ceil(sourceEnd/durationMs*bins)));
    const sourceBins=Math.max(1,lastBin-firstBin);
    // Match visible detail to the screen: zoomed out pixels aggregate all extrema
    // falling in the pixel; zoomed in columns interpolate between cached bins.
    const columns=Math.max(1,Math.ceil(tw));
    const xStep=tw/columns,tops=[],bottoms=[];
    for(let col=0;col<columns;col++){
      const from=firstBin+col*sourceBins/columns,to=firstBin+(col+1)*sourceBins/columns;
      let lo=0,hi=0;
      if(to-from>=1){
        const a=Math.max(firstBin,Math.floor(from)),b=Math.min(lastBin,Math.max(a+1,Math.ceil(to)));
        lo=1;hi=-1;
        for(let i=a;i<b;i++){
          if(signedEnvelope){lo=Math.min(lo,Number(peaks[i*2]||0));hi=Math.max(hi,Number(peaks[i*2+1]||0))}
          else{const v=Math.max(0,Number(peaks[i]||0));lo=Math.min(lo,-v);hi=Math.max(hi,v)}
        }
        if(lo>hi){lo=hi=0}
      }else [lo,hi]=sampleBin(from,firstBin,lastBin);
      // Tiny visual interpolation avoids staircase edges without altering transient height.
      if(col>0){lo=lo*.82+bottoms[col-1].v*.18;hi=hi*.82+tops[col-1].v*.18}
      const x=tl+(col+.5)*xStep;
      tops.push({x,y:mid-Math.max(-1,Math.min(1,hi))*scale,v:hi});
      bottoms.push({x,y:mid-Math.max(-1,Math.min(1,lo))*scale,v:lo});
    }
    if(!tops.length)continue;
    ctx.save();
    ctx.globalAlpha=.28;ctx.fillStyle=color;ctx.beginPath();ctx.moveTo(tops[0].x,tops[0].y);
    for(let i=1;i<tops.length;i++)ctx.lineTo(tops[i].x,tops[i].y);
    for(let i=bottoms.length-1;i>=0;i--)ctx.lineTo(bottoms[i].x,bottoms[i].y);
    ctx.closePath();ctx.fill();
    ctx.globalAlpha=.9;ctx.strokeStyle=color;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(tops[0].x,tops[0].y);
    for(let i=1;i<tops.length;i++)ctx.lineTo(tops[i].x,tops[i].y);ctx.stroke();
    ctx.globalAlpha=.62;ctx.beginPath();ctx.moveTo(bottoms[0].x,bottoms[0].y);
    for(let i=1;i<bottoms.length;i++)ctx.lineTo(bottoms[i].x,bottoms[i].y);ctx.stroke();ctx.restore();
  }
}
function clampZoom(v){return Math.max(MIN_ZOOM_PX_PER_SEC,Math.min(MAX_ZOOM_PX_PER_SEC,Number(v)||DEFAULT_ZOOM_PX_PER_SEC))}
function zoomPercent(v=pxPerSec){return Math.round(clampZoom(v)/DEFAULT_ZOOM_PX_PER_SEC*100)}
function syncZoomControls(v=pxPerSec,presetValue=null){
  const z=clampZoom(v),slider=$('#topZoom'),display=$('#zoomDisplay'),preset=$('#zoomPreset');
  if(slider)slider.value=String(Math.round(z));
  if(display)display.textContent=`${zoomPercent(z)}%`;
  if(preset){
    if(presetValue!==null)preset.value=presetValue;
    else preset.value=Math.abs(z-DEFAULT_ZOOM_PX_PER_SEC)<.5?'pct:100':'custom';
  }
}
function beginZoomPreview(){
  if(!current||zoomPreviewState)return;
  const pane=$('#timelinePane'),lanes=$('#lanes'),ruler=$('#ruler');
  zoomPreviewState={baseZoom:pxPerSec,baseWidth:widthPx(),scrollLeft:pane?.scrollLeft||0,anchorX:(pane?.scrollLeft||0)+(pane?.clientWidth||0)/2};
  if(lanes)lanes.classList.add('zoom-preview-active');if(ruler)ruler.classList.add('zoom-preview-active');
}
function previewZoom(v,presetValue=null){
  if(!current)return;const next=clampZoom(v);if(!zoomPreviewState)beginZoomPreview();const st=zoomPreviewState;if(!st)return;
  const scale=next/st.baseZoom,newWidth=Math.max(980,projectEnd()/1000*next+180),lanes=$('#lanes'),pane=$('#timelinePane'),ruler=$('#ruler');
  if(lanes){lanes.style.width=`${newWidth}px`;$$('.lane').forEach(l=>{l.style.width=`${st.baseWidth}px`;l.style.transformOrigin='left top';l.style.transform=`scaleX(${scale})`})}
  if(ruler){ruler.style.transformOrigin='left top';ruler.style.transform=`scaleX(${scale})`}
  const playhead=$('#playhead');if(playhead)playhead.style.left=`${playCursorMs/1000*next}px`;
  if(pane){const centerRatio=st.anchorX/Math.max(1,st.baseWidth);pane.scrollLeft=Math.max(0,centerRatio*newWidth-pane.clientWidth/2);uiState.timelineLeft=pane.scrollLeft}
  syncZoomControls(next,presetValue);
}
function commitZoom(v,presetValue=null){
  if(!current)return;const next=clampZoom(v);pxPerSec=next;current.timeline_zoom_px_per_sec=pxPerSec;markDirty(150);zoomPreviewState=null;render();syncZoomControls(next,presetValue);
}
function setZoom(v){commitZoom(v)}
function stepZoom(direction){
  if(!current)return;const factor=direction>0?1.12:1/1.12;const next=clampZoom(pxPerSec*factor);previewZoom(next,'custom');requestAnimationFrame(()=>commitZoom(next,'custom'));
}
function resetZoomDefault(event){event?.preventDefault?.();event?.stopPropagation?.();previewZoom(DEFAULT_ZOOM_PX_PER_SEC,'pct:100');requestAnimationFrame(()=>commitZoom(DEFAULT_ZOOM_PX_PER_SEC,'pct:100'))}
function zoomPaneWidth(){return Math.max(320,$('#timelinePane')?.clientWidth||980)}
function timeSignatureParts(){const [n,d]=String(current?.time_signature||'4/4').split('/').map(Number);return [Math.max(1,n||4),Math.max(1,d||4)]}
function zoomForVisibleSeconds(seconds){return clampZoom(zoomPaneWidth()/Math.max(.05,Number(seconds)||1))}
function zoomPresetValue(spec){
  if(spec==='fit')return zoomForVisibleSeconds(Math.max(1,projectEnd()/1000));
  const [kind,raw]=String(spec||'').split(':'),n=Math.max(.01,Number(raw)||1);
  if(kind==='pct')return clampZoom(DEFAULT_ZOOM_PX_PER_SEC*n/100);
  if(kind==='seconds')return zoomForVisibleSeconds(n);
  const bpm=Math.max(1,Number(current?.bpm||120)),quarter=60/bpm;
  if(kind==='beats')return zoomForVisibleSeconds(quarter*n);
  if(kind==='bars'){const [num,den]=timeSignatureParts(),barSeconds=quarter*num*4/den;return zoomForVisibleSeconds(barSeconds*n)}
  return pxPerSec;
}
function applyZoomPreset(spec){if(!current||spec==='custom')return;const next=zoomPresetValue(spec);previewZoom(next,spec);requestAnimationFrame(()=>commitZoom(next,spec))}

function tempoRatio(){const base=Number(current?.base_bpm||current?.bpm||120);return Math.max(.25,Math.min(4,Number(current?.bpm||base)/base))}
function setProjectBpm(v){
  if(!current)return;const n=Math.round(Math.max(30,Math.min(300,Number(v)||current.bpm)));
  if(!current.base_bpm)current.base_bpm=current.bpm||n;
  current.bpm=n;$('#transportBpm').textContent=String(n);if($('#transportBpmInput'))$('#transportBpmInput').value=String(n);markDirty();stopPlayback();
}
async function setProjectTimeSignature(value,recalculate=true){
  if(!current)return;const allowed=['2/4','3/4','4/4','5/4','6/8','7/8','9/8','12/8'];const sig=allowed.includes(String(value))?String(value):'4/4';
  if(current.time_signature===sig&&!recalculate)return;current.time_signature=sig;markDirty(20);
  if(!recalculate)return render();
  const track=(current.tracks||[]).find(t=>t.type!=='metronome')||(current.tracks||[])[0];
  if(!track){render();return}
  showMediaProgress('Ricalcolo BPM',10,`Tempo impostato a ${sig}. Ricalcolo BPM…`);
  try{const result=await api(`/api/projects/${current.id}/tracks/${track.id}/estimate-bpm?time_signature=${encodeURIComponent(sig)}`,{method:'POST'});current.bpm=Number(result.bpm);current.base_bpm=Number(result.bpm);current.time_signature=sig;render();markDirty(20);$('#utilityBackdrop')?.classList.add('hidden');toast(`Tempo ${sig} · BPM ${Math.round(current.bpm)}`)}catch(e){$('#utilityBackdrop')?.classList.add('hidden');render();toast('Tempo aggiornato; ricalcolo BPM non riuscito: '+e.message)}
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

function togglePlaybackLyrics(){if(!current)return;current.show_lyrics_playback=!current.show_lyrics_playback;updateTransportToggleButtons();markDirty();updateTimedPlaybackOverlay(playCursorMs)}
function togglePlaybackChords(){if(!current)return;current.show_chords_playback=!current.show_chords_playback;updateTransportToggleButtons();refreshTimelineChordLane();markDirty();updateTimedPlaybackOverlay(playCursorMs)}
function appDisplayPreference(key,defaultValue=false){const value=localStorage.getItem(`mta.${key}`);return value==null?defaultValue:value==='true'}
function setAppDisplayPreference(key,value){localStorage.setItem(`mta.${key}`,value?'true':'false')}
function timedItemTriplet(items,timeMs){
  const visible=(items||[]).filter(item=>item&&!item.excluded&&!item.disabled&&!item.deleted).slice().sort((a,b)=>Number(a.time_ms||0)-Number(b.time_ms||0));
  if(!visible.length)return {previous:null,current:null,next:null,index:-1};
  let index=-1;for(let i=0;i<visible.length;i++){if(Number(visible[i].time_ms||0)<=timeMs)index=i;else break}
  return {previous:index>0?visible[index-1]:null,current:index>=0?visible[index]:null,next:index+1<visible.length?visible[index+1]:null,index};
}
function activeTimedItem(items,timeMs){return timedItemTriplet(items,timeMs).current}
function timedOverlayTripletHtml(previous,current,next,formatter){
  const item=(value,role)=>`<span class="timed-overlay-item ${role}">${esc(value?formatter(value):'')}</span>`;
  return `${item(previous,'previous')}${item(current,'current')}${item(next,'next')}`;
}
function clearTimedPlaybackOverlay(){
  const overlay=$('#liveTimedOverlay'),lyricBox=$('#liveLyricBox'),chordBox=$('#liveChordBox');
  if(lyricBox){lyricBox.textContent='';lyricBox.innerHTML='';lyricBox.classList.add('hidden');lyricBox.classList.remove('with-neighbors')}
  if(chordBox){chordBox.textContent='';chordBox.innerHTML='';chordBox.classList.add('hidden');chordBox.classList.remove('with-neighbors')}
  overlay?.classList.add('hidden');
}
function updateTimedPlaybackOverlay(timeMs){
  syncTimedMetaPanel(timeMs);
  const overlay=$('#liveTimedOverlay'),lyricBox=$('#liveLyricBox'),chordBox=$('#liveChordBox');if(!overlay||!lyricBox||!chordBox)return;
  const running=playbackActuallyRunning()||playbackPaused;const showL=!!current?.show_lyrics_playback&&running,showC=!!current?.show_chords_playback&&running;
  if(!showL&&!showC){overlay.classList.add('hidden');lyricBox.classList.add('hidden');chordBox.classList.add('hidden');return}
  overlay.classList.remove('hidden');
  if(showC){
    const t=timedItemTriplet(current?.chords,timeMs),showNeighbors=appDisplayPreference('showPreviousNextChords',false),format=c=>transposeChordLabel(c.chord,current?.pitch_semitones||0);
    chordBox.innerHTML=showNeighbors?timedOverlayTripletHtml(t.previous,t.current,t.next,format):esc(t.current?format(t.current):'—');
    chordBox.classList.toggle('with-neighbors',showNeighbors);chordBox.classList.remove('hidden');
  }else chordBox.classList.add('hidden');
  if(showL){
    const t=timedItemTriplet(current?.lyrics,timeMs);let lyric=t.current;if(lyric&&lyric.end_ms!=null&&timeMs>Number(lyric.end_ms)+350)lyric=null;
    const showNeighbors=appDisplayPreference('showPreviousNextLyrics',false);
    if(showNeighbors){const previous=lyric?t.previous:null,next=lyric?t.next:(t.current?t.next:null);lyricBox.innerHTML=timedOverlayTripletHtml(previous,lyric,next,l=>l.text||' ')}else lyricBox.textContent=lyric?.text||' ';
    lyricBox.classList.toggle('with-neighbors',showNeighbors);lyricBox.classList.remove('hidden');
  }else lyricBox.classList.add('hidden');
}
function toggleRealtimeMeters(){
  if(!current)return;current.realtime_meter_enabled=!current.realtime_meter_enabled;$('#realtimeBtn')?.classList.toggle('active',current.realtime_meter_enabled);$$('.meter-realtime,.peak-led').forEach(x=>x.classList.toggle('hidden',!current.realtime_meter_enabled));markDirty();
  if(!current.realtime_meter_enabled)resetVuMeters();
  if(playAudio||trackPlaybacks.length){const pos=playCursorMs;stopPlayback();setPlayCursor(pos);previewMaster()}
}
function updateTransportToggleButtons(){
  $('#renderBtn')?.classList.toggle('active',!!current?.render_preview_enabled);
  $('#followBtn')?.classList.toggle('active',!!current?.follow_playback_enabled);
  $('#showLyricsBtn')?.classList.toggle('active',!!current?.show_lyrics_playback);
  $('#showChordsBtn')?.classList.toggle('active',!!current?.show_chords_playback);
  updateTimedPlaybackOverlay(playCursorMs);
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
function waveformMeterLevel(track,timeMs){
  const peaks=Array.isArray(track?.waveform_peaks)?track.waveform_peaks:[];if(!peaks.length)return 0;
  const duration=Math.max(1,Number(track.duration_ms||projectDurationMs()||1));
  const local=Math.max(0,Number(timeMs)-Number(track.delay_ms||0));
  const index=Math.max(0,Math.min(peaks.length-1,Math.floor(local/duration*peaks.length)));
  let peak=0;for(let i=Math.max(0,index-2);i<=Math.min(peaks.length-1,index+2);i++)peak=Math.max(peak,Math.abs(Number(peaks[i]||0)));
  const db=20*Math.log10(Math.max(1e-4,peak*dbToGain(Number(track.volume_db||0)+Number(current?.master_volume_db||0))));
  return Math.max(0,Math.min(100,(db+60)/60*100));
}
function updateVuMeters(token=meterRunToken){
  if(token!==meterRunToken)return;
  if(!current?.realtime_meter_enabled||!playbackActuallyRunning()){
    resetVuMeters();
    meterRaf=null;
    return;
  }
  let masterLeftEnergy=0,masterRightEnergy=0;
  const seenTrackMeters=new Set();
  for(const item of trackPlaybacks){
    const analysers=item.analysers||[];
    if(!analysers.length)continue;
    seenTrackMeters.add(item.trackId);
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
  // Render mode intentionally has no per-track media elements (to prevent
  // doubled/echoed playback). Drive track meters from saved waveform envelopes
  // at the transport cursor; this also provides a robust fallback if a native
  // WebView fails to feed an analyser for an individual track.
  for(const track of current?.tracks||[]){
    if(seenTrackMeters.has(track.id))continue;
    const level=trackAudibleNow(track)?waveformMeterLevel(track,playCursorMs):0;
    if(Number(track.channels)===1){setVu(`#vu-${track.id}-M`,level)}else{setVu(`#vu-${track.id}-L`,level);setVu(`#vu-${track.id}-R`,level)}
    latchPeak(`#peak-${track.id}`,level);masterLeftEnergy+=level*level;masterRightEnergy+=level*level;
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
function canDirectPlayTrack(track,renderFilters=true){
  if(!track||!track.filename)return false;
  if(trackDelayMs(track)!==0)return false;
  if(renderFilters&&(track.inserts||[]).some(x=>x.enabled))return false;
  if(Math.abs(Number(current?.pitch_semitones||0))>.001)return false;
  const base=Number(current?.base_bpm||current?.bpm||120),bpm=Number(current?.bpm||base);if(Math.abs(bpm-base)>.01)return false;
  const clips=track.clips||[];if(!clips.length)return true;if(clips.length!==1)return false;
  const c=clips[0],dur=Number(track.duration_ms||0);return Number(c.timeline_start_ms||0)===0&&Number(c.source_start_ms||0)===0&&(!dur||Math.abs(Number(c.source_end_ms||0)-dur)<100);
}
function playbackSourceForTrack(track,renderFilters=false){
  const direct=canDirectPlayTrack(track,renderFilters);
  return {direct,url:direct?`/api/projects/${current.id}/audio/${encodeURIComponent(track.filename)}`:`/api/projects/${current.id}/preview-track/${track.id}?render=${renderFilters?'true':'false'}`};
}
function playbackWarmStateSignature(){
  if(!current)return '';
  return JSON.stringify({id:current.id,bpm:current.bpm,base:current.base_bpm,pitch:current.pitch_semitones,tracks:(current.tracks||[]).map(t=>[t.id,t.filename,t.duration_ms,t.delay_ms||0,t.clips])});
}
function clearPlaybackWarmCache(){
  clearTimeout(playbackWarmTimer);playbackWarmTimer=null;
  for(const entry of playbackWarmCache.values())try{entry.audio.pause();entry.audio.removeAttribute('src');entry.audio.load()}catch(e){}
  playbackWarmCache.clear();playbackWarmProjectId=null;playbackWarmSignature='';
}
function schedulePlaybackPrewarm(delay=120){
  clearTimeout(playbackWarmTimer);
  if(!current||playAudio||trackPlaybacks.length||playbackBuffering)return;
  playbackWarmTimer=setTimeout(()=>{playbackWarmTimer=null;void prewarmPlaybackSources()},delay);
}
async function prewarmPlaybackSources(){
  if(!current||playAudio||trackPlaybacks.length||playbackBuffering)return;
  const sig=playbackWarmStateSignature();
  if(playbackWarmProjectId===current.id&&playbackWarmSignature===sig&&playbackWarmCache.size===(current.tracks||[]).length)return;
  clearPlaybackWarmCache();playbackWarmProjectId=current.id;playbackWarmSignature=sig;
  for(const track of current.tracks||[]){
    const source=playbackSourceForTrack(track,false),audio=new Audio(source.url);audio.preload='auto';
    playbackWarmCache.set(track.id,{audio,url:source.url,direct:source.direct});
    try{audio.load()}catch(e){}
  }
}
function takeWarmPlaybackAudio(track,renderFilters){
  const source=playbackSourceForTrack(track,renderFilters),entry=!renderFilters?playbackWarmCache.get(track.id):null;
  if(entry&&entry.url===source.url){playbackWarmCache.delete(track.id);return {audio:entry.audio,direct:entry.direct,url:entry.url}}
  const audio=new Audio(source.url);audio.preload='auto';return {audio,direct:source.direct,url:source.url};
}
function ensureTransportAudioContext(){audioCtx=audioCtx||new(window.AudioContext||window.webkitAudioContext)();return audioCtx}
function transportMediaSeconds(){
  const base=transportClockCursorMs/1000/tempoRatio();
  if(!transportClockRunning||!audioCtx)return base;
  return Math.max(0,base+(audioCtx.currentTime-transportClockStartCtx));
}
function startTransportClock(cursorMs=playCursorMs){const ctx=ensureTransportAudioContext();transportClockCursorMs=cursorMs;transportClockStartCtx=ctx.currentTime;transportClockRunning=true}
function pauseTransportClock(){if(transportClockRunning){playCursorMs=transportMediaSeconds()*1000*tempoRatio();transportClockCursorMs=playCursorMs;transportClockRunning=false}}
function reanchorTransportClock(cursorMs=playCursorMs){transportClockCursorMs=cursorMs;if(audioCtx)transportClockStartCtx=audioCtx.currentTime}
async function makeTrackPlayback(track,renderFilters,silent=false,respectMuteSolo=true,startupMuted=false){
  const warm=takeWarmPlaybackAudio(track,renderFilters),audio=warm.audio,direct=warm.direct;
  const channels=direct?(Number(track.channels)===1?1:2):(renderFilters?effectiveTrackChannels(track):(Number(track.channels)===1?1:2));
  const graph=await attachPlaybackGraph(audio,track,channels,silent,false,respectMuteSolo);
  const targetGain=playbackGainForTrack(track,{respectMuteSolo});
  if(startupMuted)graph.gainNode.gain.setValueAtTime(0,audioCtx?.currentTime||0);
  await new Promise((resolve,reject)=>{const ready=()=>resolve();audio.addEventListener('loadedmetadata',ready,{once:true});audio.addEventListener('error',()=>reject(new Error(`Preview non disponibile: ${track.name}`)),{once:true});audio.load();if(audio.readyState>=1)resolve()});
  audio.currentTime=Math.min(playCursorMs/1000/tempoRatio(),Math.max(0,(audio.duration||0)-0.01));
  audio.addEventListener('ended',()=>requestAnimationFrame(()=>{if(!playbackActuallyRunning())resetVuMeters()}));
  return {trackId:track.id,audio,analysers:graph.analysers,channels,silent,respectMuteSolo,meterData:{},gainNode:graph.gainNode,panner:graph.panner,direct,targetGain,startupMuted};
}
function waitForMediaBuffer(audio,label='traccia',timeoutMs=2600){
  // Low-latency transport only waits for a decodable frame near the cursor.
  // Deep buffering happens in the background and must never gate Play.
  const enough=()=>{if(audio.readyState<2)return false;try{const pos=audio.currentTime||0;for(let i=0;i<audio.buffered.length;i++){if(audio.buffered.start(i)<=pos+.03&&audio.buffered.end(i)-pos>=Math.min(.40,Math.max(.12,(audio.duration||.40)-pos)))return true}}catch(e){}return audio.readyState>=3};
  if(enough())return Promise.resolve();
  return new Promise((resolve,reject)=>{let done=false;const finish=()=>{if(done)return;done=true;cleanup();resolve()},fail=()=>{if(done)return;done=true;cleanup();audio.readyState>=2?resolve():reject(new Error(`Buffering non riuscito: ${label}`))},check=()=>{if(enough())finish()},cleanup=()=>{clearTimeout(timer);clearInterval(poll);audio.removeEventListener('canplay',check);audio.removeEventListener('progress',check);audio.removeEventListener('error',fail)},poll=setInterval(check,35),timer=setTimeout(fail,timeoutMs);audio.addEventListener('canplay',check);audio.addEventListener('progress',check);audio.addEventListener('error',fail,{once:true});audio.load()});
}
function stopDynamicSyncMonitor(){
  if(dynamicSyncTimer){clearInterval(dynamicSyncTimer);dynamicSyncTimer=null}
  dynamicSyncClock=null;
}
function dynamicClockAudio(){
  if(renderedMasterPlayback&&renderedMasterAudio)return renderedMasterAudio;
  const active=trackPlaybacks.find(item=>item.audio&&!item.audio.paused&&!item.audio.ended&&item.audio.readyState>=2);
  return active?.audio||playAudio||trackPlaybacks[0]?.audio||null;
}
function alignDynamicTracks(force=false){
  if(renderedMasterPlayback||playbackPaused||!trackPlaybacks.length||!transportClockRunning)return;
  const ref=transportMediaSeconds();
  for(const item of trackPlaybacks){
    const audio=item.audio;if(audio.paused||audio.ended)continue;
    audio.playbackRate=1;
    // Never perform periodic corrective seeks during healthy playback: they are
    // audible as regular drop-outs. Re-lock only at explicit transport events or
    // after the decoder reported a real stall/underrun.
    if(!force&&!item.needsRelock)continue;
    if(audio.readyState<2||audio.seeking)continue;
    try{
      const drift=audio.currentTime-ref;
      if(force||Math.abs(drift)>.060){audio.currentTime=Math.min(ref,Math.max(0,(audio.duration||ref)-0.005))}
      item.needsRelock=false;
    }catch(e){}
  }
}
function installPlaybackRecovery(item){
  if(!item?.audio||item.recoveryInstalled)return;
  item.recoveryInstalled=true;
  const mark=()=>{item.needsRelock=true};
  const recover=()=>{if(item.needsRelock&&!playbackPaused&&transportClockRunning)requestAnimationFrame(()=>alignDynamicTracks(false))};
  item.audio.addEventListener('waiting',mark);
  item.audio.addEventListener('stalled',mark);
  item.audio.addEventListener('suspend',()=>{if(item.audio.readyState<3)mark()});
  item.audio.addEventListener('canplay',recover);
  item.audio.addEventListener('playing',recover);
}
function startDynamicSyncMonitor(){
  // The AudioContext transport clock is authoritative. No polling/periodic seeks.
  stopDynamicSyncMonitor();dynamicSyncClock=trackPlaybacks.find(x=>x.audio&&!x.audio.ended)||null;
}
function releaseStartupMute(items){
  const now=audioCtx?.currentTime||0;
  for(const item of items){if(!item.gainNode)continue;const track=trackById(item.trackId),target=playbackGainForTrack(track,item);item.gainNode.gain.cancelScheduledValues(now);item.gainNode.gain.setValueAtTime(0,now);item.gainNode.gain.linearRampToValueAtTime(target,now+.008);item.startupMuted=false}
}
function queueInitialTrackFxUpgrades(){
  if(renderedMasterPlayback||renderedStemPlayback)return;
  for(const track of current?.tracks||[]){if((track.inserts||[]).some(x=>x.enabled))setTimeout(()=>refreshDynamicTrackPlayback(track.id),20)}
}
async function startDynamicTrackPreview(renderFilters=false,silentMeters=false,token=playbackToken){
  playbackBuffering=true;const tracks=current.tracks||[],slowTimer=setTimeout(()=>{if(token===playbackToken)showMediaProgress('Preparazione audio',18,'Avvio decoder…')},220);
  try{
    const items=await Promise.all(tracks.map(t=>makeTrackPlayback(t,renderFilters,silentMeters,true,true)));if(token!==playbackToken)return null;items.forEach(installPlaybackRecovery);
    await Promise.all(items.map((item,i)=>waitForMediaBuffer(item.audio,tracks[i]?.name||`traccia ${i+1}`,1600)));if(token!==playbackToken)return null;
    const sec=playCursorMs/1000/tempoRatio();
    for(const item of items){item.audio.pause();item.audio.playbackRate=1;item.needsRelock=false;item.lastHardSync=0;item.audio.currentTime=Math.min(sec,Math.max(0,(item.audio.duration||0)-0.01))}
    trackPlaybacks.push(...items);if(audioCtx?.state==='suspended')try{await audioCtx.resume()}catch(e){}
    // Start all muted, establish one AudioContext transport epoch, then reveal
    // audio only after the first hard lock. This avoids audible start skew.
    startTransportClock(playCursorMs);
    const starts=items.map(item=>item.audio.play());
    await Promise.all(starts);if(token!==playbackToken){for(const item of items)try{item.audio.pause()}catch(e){};return null}
    alignDynamicTracks(true);releaseStartupMute(items);
    dynamicSyncClock=items.find(x=>x.audio&&!x.audio.ended)||items[0]||null;startDynamicSyncMonitor();$('#utilityBackdrop')?.classList.add('hidden');if(current.realtime_meter_enabled&&!meterRaf)startVuMeterLoop();
    if(!renderFilters)queueInitialTrackFxUpgrades();
    return dynamicSyncClock?.audio||null;
  }finally{clearTimeout(slowTimer);if(token===playbackToken)playbackBuffering=false}
}

function stopPlayback(){
  ++playbackToken;
  playbackBuffering=false;
  playbackPaused=false;
  transportClockRunning=false;transportClockCursorMs=playCursorMs;
  meterRunToken++;
  if(playRaf){cancelAnimationFrame(playRaf);playRaf=null}
  if(meterRaf){cancelAnimationFrame(meterRaf);meterRaf=null}
  if(playAudio){playAudio.pause();playAudio.currentTime=0;playAudio=null}
  for(const item of trackPlaybacks){try{item.audio.pause();item.audio.currentTime=0;item.audio.removeAttribute('src');item.audio.load()}catch(e){}}
  trackPlaybacks=[];masterMeterAnalysers=null;masterPlaybackGainNode=null;
  renderedMasterPlayback=false;renderedStemPlayback=false;renderedMasterDirty=false;renderedMasterRefreshPromise=null;renderedMasterRefreshQueued=false;renderedMasterBaseVolumeDb=0;renderedMasterAudio=null;
  stopDynamicSyncMonitor();
  for(const key of Object.keys(liveFxRefreshTimers)){clearTimeout(liveFxRefreshTimers[key]);delete liveFxRefreshTimers[key]}
  resetVuMeters();
  requestAnimationFrame(resetVuMeters);
  if($('#playMaster')){$('#playMaster').textContent='▶';$('#playMaster').title='Play / Preview'}
  updateTimedPlaybackOverlay(playCursorMs);
  schedulePlaybackPrewarm(120);
}
function pausePlayback(){
  if(!playAudio&&!trackPlaybacks.length)return;
  pauseTransportClock();
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
  startTransportClock(playCursorMs);
  await Promise.all(audios.map(audio=>audio.play()));
  playbackPaused=false;
  if(!renderedMasterPlayback){alignDynamicTracks(true);startDynamicSyncMonitor()}
  if($('#playMaster')){$('#playMaster').textContent='❚❚';$('#playMaster').title='Pausa'}
  playRaf=requestAnimationFrame(movePlayhead);
  if(current?.realtime_meter_enabled&&!meterRaf)meterRaf=requestAnimationFrame(updateVuMeters);
}
function goTransportStart(){
  setPlayCursor(0);reanchorTransportClock(0);
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
  setPlayCursor(Math.max(0,playCursorMs+deltaMs));reanchorTransportClock(playCursorMs);
  const sec=playCursorMs/1000/tempoRatio();
  if(renderedMasterAudio)try{renderedMasterAudio.currentTime=sec}catch(e){}
  if(playAudio)try{playAudio.currentTime=sec}catch(e){}
  for(const item of trackPlaybacks)try{item.audio.currentTime=sec}catch(e){}
  alignDynamicTracks(true);
  if(current?.follow_playback_enabled)followPlayhead(playCursorMs/1000*pxPerSec,true);
  updateTimedPlaybackOverlay(playCursorMs);
}
function syncExportPreviewControls(){
  const start=$('#exportPreviewStart'),stop=$('#exportPreviewStop');
  const active=!!(playAudio||trackPlaybacks.length||playbackPaused||playbackBuffering);
  if(start){start.disabled=active;start.textContent=active?'Anteprima in riproduzione…':'▶ Render & Preview Master'}
  if(stop)stop.disabled=!active;
}
async function previewExportMaster(){
  syncExportPreviewControls();
  try{await previewMaster()}finally{syncExportPreviewControls()}
}
function stopExportPreview(){
  stopPlayback();
  syncExportPreviewControls();
  toast('Anteprima interrotta');
}

async function previewTrack(id){
  const t=trackById(id);if(!t)return;stopPlayback();
  try{const item=await makeTrackPlayback(t,true,false,false);trackPlaybacks=[item];playAudio=item.audio;await item.audio.play();requestAnimationFrame(movePlayhead);if(current.realtime_meter_enabled)startVuMeterLoop()}catch(e){toast(e.message)}
}
async function previewMaster(){
  if(!current||!current.tracks.length)return;
  try{
    collect();stopPlayback();const token=++playbackToken;
    const needsRenderedMaster=!!current.render_preview_enabled;
    if(needsRenderedMaster){
      // Render mode uses one processed stem per track rather than one immutable
      // master file. Track inserts are server-rendered, while fader/pan/mute/solo
      // stay downstream in WebAudio and therefore react immediately during play.
      setRenderPlaybackPreparing(true);
      renderedMasterPlayback=false;renderedStemPlayback=true;renderedMasterDirty=false;renderedMasterAudio=null;
      playAudio=await startDynamicTrackPreview(true,false,token);if(token!==playbackToken)return;
      setRenderPlaybackPreparing(false);
    }else{
      renderedMasterPlayback=false;renderedStemPlayback=false;renderedMasterDirty=false;renderedMasterAudio=null;
      playAudio=await startDynamicTrackPreview(false,false,token);if(token!==playbackToken)return;
    }
    if(!playAudio)return;playbackPaused=false;$('#playMaster').textContent='❚❚';$('#playMaster').title='Pausa';
    if(current?.follow_playback_enabled)followPlayhead(playCursorMs/1000*pxPerSec,true);
    requestAnimationFrame(movePlayhead);
    toast(needsRenderedMaster?'Anteprima Master: volume e insert applicati':'Anteprima dinamica tracce');
  }catch(e){setRenderPlaybackPreparing(false);stopPlayback();toast(e.message)}
}
function movePlayhead(){
  const clock=dynamicClockAudio();
  if(!clock||clock.paused)return;
  playCursorMs=(renderedMasterPlayback?clock.currentTime:transportMediaSeconds())*1000*tempoRatio();
  const playheadX=playCursorMs/1000*pxPerSec;
  if($('#playhead'))$('#playhead').style.left=playheadX+'px';
  followPlayhead(playheadX);
  if($('#transportTime'))$('#transportTime').textContent=fmtTime(playCursorMs/1000,true);
  updateTimedPlaybackOverlay(playCursorMs);
  playRaf=requestAnimationFrame(movePlayhead);
}
function selectExport(format){exportFormat=format;if(current){current.export_format=format;markDirty(150)}}
function openTrackMp3ExportDialog(id){
  if(!current)return;
  const track=trackById(id);if(!track)return;
  const artist=current.artist||'';
  const composer=(current.authors||[]).join(', ');
  showUtilityModal('Export traccia MP3',`
    <div class="stem-workflow track-mp3-export-config">
      <div class="workflow-grid">
        <label class="workflow-field"><span>Bitrate</span><select id="trackMp3Bitrate"><option value="128">128 kbps</option><option value="192">192 kbps</option><option value="256">256 kbps</option><option value="320" selected>320 kbps</option></select></label>
        <label class="workflow-field"><span>Sample rate</span><select id="trackMp3SampleRate"><option value="44100" selected>44.1 kHz</option><option value="48000">48 kHz</option></select></label>
      </div>
      <div class="section-title">Metadata MP3 / ID3</div>
      <div class="workflow-grid">
        <label class="workflow-field"><span>Titolo</span><input id="trackMp3Title" maxlength="300" value="${esc(track.name||current.title||'')}"></label>
        <label class="workflow-field"><span>Artista</span><input id="trackMp3Artist" maxlength="300" value="${esc(artist)}"></label>
        <label class="workflow-field"><span>Album / progetto</span><input id="trackMp3Album" maxlength="300" value="${esc(current.title||'')}"></label>
        <label class="workflow-field"><span>Autore / compositore</span><input id="trackMp3Composer" maxlength="300" value="${esc(composer)}"></label>
        <label class="workflow-field"><span>Genere</span><input id="trackMp3Genre" maxlength="120" value=""></label>
        <label class="workflow-field"><span>Anno / data</span><input id="trackMp3Date" maxlength="40" placeholder="2026"></label>
      </div>
      <label class="workflow-field"><span>Commento</span><textarea id="trackMp3Comment" maxlength="1000" rows="3"></textarea></label>
      <div class="workflow-note">I metadata sono precompilati dai dati disponibili nel progetto e possono essere modificati prima dell'export. Dopo Conferma verrà chiesto dove salvare il file.</div>
      <div class="utility-actions"><button class="utility-btn primary" onclick="confirmTrackMp3Export('${id}')">Conferma e scegli destinazione</button><button class="utility-btn secondary" onclick="closeUtilityModal()">Annulla</button></div>
    </div>`);
}
function confirmTrackMp3Export(id){
  const metadata={
    title:$('#trackMp3Title')?.value||'',artist:$('#trackMp3Artist')?.value||'',album:$('#trackMp3Album')?.value||'',
    composer:$('#trackMp3Composer')?.value||'',genre:$('#trackMp3Genre')?.value||'',date:$('#trackMp3Date')?.value||'',comment:$('#trackMp3Comment')?.value||''
  };
  const options={format:'mp3',mp3_bitrate_kbps:Number($('#trackMp3Bitrate')?.value||320),sample_rate:Number($('#trackMp3SampleRate')?.value||44100),metadata};
  closeUtilityModal();void exportTrack(id,'mp3',options);
}
async function exportTrack(id,format,options=null){
  if(!current)return;
  const track=trackById(id);
  const ext=String(format||'wav').toLowerCase();
  if(ext==='mp3'&&!options){openTrackMp3ExportDialog(id);return}
  const safeTrackName=String(track?.name||'track').replace(/[^A-Za-z0-9._ -]+/g,'_').trim()||'track';
  let nativeOutputPath='';
  try{
    // Ask for the destination only after codec/metadata configuration has been confirmed.
    if(currentUser?.native_single_user&&window.pywebview?.api?.choose_export_save_path){
      const chosen=await window.pywebview.api.choose_export_save_path(safeTrackName,ext);
      if(!chosen?.ok)return;
      nativeOutputPath=chosen.path||'';
    }
    await save();
    const requestBody=options||{format:ext};
    const job=await api(`/api/projects/${current.id}/tracks/${encodeURIComponent(id)}/track-export-jobs`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(requestBody)});
    showMediaProgress('Export traccia',job.progress,job.message);
    pollMediaJob(job.id,'Export traccia',async completed=>{
      const result=completed.result||{};
      const mime={wav:'audio/wav',mp3:'audio/mpeg',flac:'audio/flac'}[ext]||'application/octet-stream';
      await downloadWithProgress(result.download_url,result.filename||`${safeTrackName}.${ext}`,'Export traccia',false,mime,nativeOutputPath);
      toast(nativeOutputPath?`Export traccia salvato in ${nativeOutputPath}`:'Export traccia completato');
    });
  }catch(e){setMobileBusy(false);toast(e.message)}
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
  const normalizeParams=['wav','mp3','flac'].includes(format)?`<div class="export-normalize-panel"><label class="workflow-check"><input id="exportNormalize" type="checkbox" onchange="toggleExportNormalizeTarget()"><span>Normalizza prima dell’export</span></label><label id="exportNormalizeTargetRow" class="workflow-field export-normalize-target" hidden><span>Picco target (dBFS)</span><input id="exportNormalizeDb" type="number" min="-30" max="0" step="0.1" value="-1.0"><small>0 dBFS è il massimo digitale; -1 dBFS è un valore tipico per evitare clipping.</small></label></div>`:'';
  showUtilityModal('Esporta progetto',`
    <div class="stem-workflow">
      <label class="workflow-field"><span>Formato</span><input value="${format==='mta'?current.target:format.toUpperCase()}" disabled></label>
      <label class="workflow-field"><span>Nome file</span><div class="export-name-row"><input id="exportFileName" maxlength="180" value="${esc(safe)}"><span>.${ext}</span></div></label>
      ${mtaTargetField}
      ${mtaProfileField}
      ${audioParams}
      ${normalizeParams}
      <div class="workflow-note">${format==='mta'?'Il profilo MTA controlla l’ordine fisico delle tracce Click/Melody nel file. MTA8 mantiene le posizioni specifiche del dispositivo; per MTA16 il default derivato dal corpus è Click 1 / Melody 9. Se servono stream intermedi vengono creati slot silenziosi. ':''}${currentUser?.native_single_user?'Dopo Conferma verrà aperto il selettore del filesystem per scegliere la cartella di destinazione.':isMobileClient()?'L’app mobile userà il selettore file del sistema operativo. Puoi anche condividere direttamente l’output.':'Il browser chiederà dove salvare il file secondo le impostazioni di download del browser.'}</div>
      <div class="utility-actions">
        <button class="utility-btn primary" onclick="confirmConfiguredExport('${format}',false)">Conferma export</button>
        ${isMobileClient()?`<button class="utility-btn secondary" onclick="confirmConfiguredExport('${format}',true)">Condividi…</button>`:''}
        <button class="utility-btn secondary" type="button" onclick="closeUtilityModal()">Annulla</button>
      </div>
    </div>`);
}
function toggleExportNormalizeTarget(){const enabled=!!$('#exportNormalize')?.checked;const row=$('#exportNormalizeTargetRow');if(row)row.hidden=!enabled}
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
    normalize_audio:!!$('#exportNormalize')?.checked,
    normalize_peak_db:Number($('#exportNormalizeDb')?.value||-1),
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
    const channel=String(info.release_channel||'stable').toLowerCase()==='early'?'early':'stable';
    const revisionLabel=channel==='early'?`r${info.revision||''}`:'stable';
    const releaseLabel=channel==='early'?(info.release||`${info.version||''}-r${info.revision||''}`):(info.version||'');
    showUtilityModal('Informazioni',`
      <div class="about-card">
        <div class="about-photo" aria-hidden="true"></div>
        <div class="about-info-panel">
          <img src="/static/logo.svg" alt="MTA Audio Editor" class="about-logo">
          <h3>${esc(info.name||'MTA Audio Editor')}</h3>
          <dl>
            <dt>Versione</dt><dd>${esc(info.version||'')}</dd>
            <dt>Revisione</dt><dd>${esc(revisionLabel)}</dd>
            <dt>Release</dt><dd>${esc(releaseLabel)}</dd>
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
function focusInspector(){if(!requireOpenProject('aprire i plugin'))return;if(current.inspector_visible===false){current.inspector_visible=true;render();markDirty(80)}const el=$('#inspector');if(!el)return toast('Seleziona una traccia per visualizzare i plugin');el.scrollIntoView({behavior:'smooth',block:'nearest'});el.classList.add('nav-focus-pulse');setTimeout(()=>el.classList.remove('nav-focus-pulse'),900)}

async function readSystemClipboard(){
  let value='';
  try{value=String(await navigator.clipboard?.readText?.()||'')}catch(_e){}
  if(value)return value;
  if(currentUser?.native_single_user){
    try{const bridge=await waitForNativeApi();const result=await bridge?.read_clipboard?.();value=String(result?.text||'')}catch(e){console.warn('Native clipboard read failed',e)}
  }
  return value;
}
async function pasteSystemClipboardTo(id){
  const input=$(id);if(!input)return;
  const text=await readSystemClipboard();
  if(!text)return toast('Clipboard vuota o non accessibile');
  const start=Number.isFinite(input.selectionStart)?input.selectionStart:input.value.length,end=Number.isFinite(input.selectionEnd)?input.selectionEnd:start;
  input.value=input.value.slice(0,start)+text+input.value.slice(end);
  const pos=start+text.length;try{input.setSelectionRange(pos,pos)}catch(_e){}
  input.dispatchEvent(new Event('input',{bubbles:true}));input.focus();
}
function openYoutubeImport(){
  if(!current)return toast('Apri prima un progetto');
  const refs=current.tracks.map(t=>`<option value="${t.id}">${esc(t.name)}</option>`).join('');
  showUtilityModal('Import audio da YouTube',`<div class="youtube-import-dialog">
    <section class="youtube-import-section">
      <div class="youtube-import-section-title"><b>1. Sorgente</b><span>Importa solo l'audio di un singolo video YouTube.</span></div>
      <label class="workflow-field"><span>URL YouTube</span><div class="youtube-input-row"><input id="youtubeImportUrl" type="url" inputmode="url" autocomplete="off" placeholder="https://www.youtube.com/watch?v=…"><button class="utility-btn secondary youtube-paste-btn" type="button" onclick="pasteSystemClipboardTo('#youtubeImportUrl')">Incolla</button></div></label>
      <label class="workflow-field"><span>Nome traccia <small>(opzionale)</small></span><div class="youtube-input-row"><input id="youtubeImportName" type="text" maxlength="200" placeholder="Usa il titolo YouTube"><button class="utility-btn secondary youtube-paste-btn" type="button" onclick="pasteSystemClipboardTo('#youtubeImportName')">Incolla</button></div></label>
    </section>
    <section class="youtube-import-section">
      <div class="youtube-import-section-title"><b>2. Posizionamento</b><span>Imposta sincronizzazione e posizione nella timeline.</span></div>
      <div class="youtube-options-grid">
        <label class="workflow-field"><span>Sincronizzazione</span><select id="youtubeImportSync"><option value="manual">Manuale</option><option value="auto">Automatica</option></select></label>
        <label class="workflow-field"><span>Offset</span><div class="youtube-offset-row"><input id="youtubeImportOffset" type="number" value="0"><span>ms</span></div></label>
      </div>
      <label class="workflow-field"><span>Traccia di riferimento</span><select id="youtubeImportRef"><option value="">Prima traccia disponibile</option>${refs}</select></label>
    </section>
    <section class="youtube-import-section youtube-rights-section">
      <label class="youtube-rights-check"><input id="youtubeImportRights" type="checkbox"><span>Confermo di essere autorizzato a scaricare/importare l'audio di questo contenuto.</span></label>
      <p class="hint">Playlist non supportate. Il server deve poter raggiungere YouTube.</p>
    </section>
    <div class="utility-actions youtube-import-actions"><button class="utility-btn secondary" type="button" onclick="closeUtilityModal()">Annulla</button><button class="utility-btn primary" type="button" onclick="startYoutubeImport()">▶ Importa audio</button></div>
  </div>`);
  document.querySelector('.utility-modal')?.classList.add('youtube-import-modal');
  setTimeout(()=>$('#youtubeImportUrl')?.focus(),50);
}
async function startYoutubeImport(){
  if(!current)return;
  const url=String($('#youtubeImportUrl')?.value||'').trim();
  if(!url)return toast('Inserisci un URL YouTube');
  if(!$('#youtubeImportRights')?.checked)return toast('Devi confermare di disporre dei diritti necessari');
  const body={url,name:String($('#youtubeImportName')?.value||'').trim(),sync_mode:$('#youtubeImportSync')?.value||'manual',offset_ms:parseInt($('#youtubeImportOffset')?.value||'0')||0,reference_track_id:$('#youtubeImportRef')?.value||'',confirm_rights:true};
  const button=document.querySelector('.youtube-import-actions .primary');
  const previousText=button?.textContent||'Importa audio';
  if(button){button.disabled=true;button.textContent='Avvio import…'}
  try{
    await save();
    const job=await api(`/api/projects/${current.id}/youtube-import-jobs`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
    showMediaProgress('Import YouTube',job.progress,job.message,'Download ed estrazione della sola traccia audio.');
    pollMediaJob(job.id,'Import YouTube',async completed=>{
      current=await api(`/api/projects/${current.id}`);selectedTrackId=completed.result?.track_id||current.tracks.at(-1)?.id;render();await refresh();
      $('#utilityBackdrop').classList.add('hidden');toast(`Audio YouTube importato${current.tracks.length===1?` · BPM ${current.bpm}`:''}`);
    });
  }catch(e){if(button){button.disabled=false;button.textContent=previousText}toast(e.message)}
}
function focusImport(){$('#newTrackFile')?.click()}

function editProjectMeta(){
  if(!current)return;
  const signatures=['2/4','3/4','4/4','5/4','6/8','7/8','9/8','12/8'];
  const targets=['MTA8','MTA16','DAW'];
  const profiles=[['auto','Auto'],['merish5_xynthia2','Merish5 / Xynthia2'],['bbeat_divo','B.Beat / Divo'],['mlive_mta16_default','M-Live MTA16'],['merish5_plus_mta16','Merish5+ MTA16'],['generic','Generic']];
  const row=(label,control)=>`<tr><th>${esc(label)}</th><td>${control}</td></tr>`;
  const input=(id,value,max=300,type='text')=>`<input id="${id}" type="${type}" value="${esc(value??'')}" maxlength="${max}" class="project-meta-input">`;
  const select=(id,value,options)=>`<select id="${id}" class="project-meta-input">${options.map(([v,l])=>`<option value="${esc(v)}" ${String(value)===String(v)?'selected':''}>${esc(l)}</option>`).join('')}</select>`;
  showUtilityModal('Modifica metadata progetto',`<div class="table-scroll"><table class="users-table project-meta-editor"><tbody>${[
    row('Titolo',input('projectMetaTitle',current.title,200)),
    row('Titolo originale',input('projectMetaOriginalTitle',current.original_title||'',300)),
    row('Autori / compositori',input('projectMetaAuthors',(current.authors||[]).join(', '),1000)),
    row('Artista / interprete',input('projectMetaArtist',current.artist||'',200)),
    row('Tonalità / Key',input('projectMetaKey',current.key||'',40)),
    row('BPM',`<input id="projectMetaBpm" type="number" min="30" max="300" step="1" value="${esc(String(Math.round(Number(current.bpm)||120)))}" class="project-meta-input">`),
    row('Time signature',select('projectMetaTimeSignature',current.time_signature||'4/4',signatures.map(x=>[x,x]))),
    row('Tipo progetto',select('projectMetaTarget',current.target||'MTA8',targets.map(x=>[x,x]))),
    row('Profilo MTA',select('projectMetaDeviceProfile',current.mta_device_profile||'auto',profiles)),
    row('Società repertorio',input('projectMetaRightsSocieties',(current.rights_societies||[]).join(', '),500)),
  ].join('')}</tbody></table></div><p class="hint">Tutti i campi vengono salvati insieme nel progetto. Se modifichi il time signature, i BPM vengono ricalcolati usando la nuova metrica.</p><div class="utility-actions"><button class="utility-btn primary" onclick="saveProjectMetaEditor()">Save</button><button class="utility-btn secondary" onclick="closeUtilityModal()">Annulla</button></div>`);
}
async function saveProjectMetaEditor(){
  if(!current)return;
  const title=($('#projectMetaTitle')?.value||'').trim();
  if(!title){toast('Il titolo del progetto non può essere vuoto');return}
  const newSig=$('#projectMetaTimeSignature')?.value||'4/4',oldSig=current.time_signature||'4/4';
  current.title=title.slice(0,200);
  current.original_title=($('#projectMetaOriginalTitle')?.value||'').trim().slice(0,300);
  current.authors=($('#projectMetaAuthors')?.value||'').split(/[,;\n]/).map(x=>x.trim()).filter(Boolean).slice(0,64);
  current.artist=($('#projectMetaArtist')?.value||'').trim().slice(0,200);
  current.key=($('#projectMetaKey')?.value||'').trim().slice(0,40);
  const bpm=Math.max(30,Math.min(300,Number($('#projectMetaBpm')?.value)||Number(current.bpm)||120));
  current.bpm=Math.round(bpm);if(!current.base_bpm)current.base_bpm=current.bpm;
  current.target=$('#projectMetaTarget')?.value||current.target||'MTA8';
  current.mta_device_profile=$('#projectMetaDeviceProfile')?.value||'auto';
  current.rights_societies=($('#projectMetaRightsSocieties')?.value||'').split(/[,;\n]/).map(x=>x.trim().toUpperCase()).filter(Boolean).slice(0,16);
  current.time_signature=newSig;
  try{
    if(newSig!==oldSig){
      const track=(current.tracks||[]).find(t=>t.type!=='metronome')||(current.tracks||[])[0];
      if(track){
        showMediaProgress('Ricalcolo BPM',10,`Tempo impostato a ${newSig}. Ricalcolo BPM…`);
        try{const result=await api(`/api/projects/${current.id}/tracks/${track.id}/estimate-bpm?time_signature=${encodeURIComponent(newSig)}`,{method:'POST'});current.bpm=Number(result.bpm)||current.bpm;current.base_bpm=current.bpm}catch(e){toast('Metadata salvati; ricalcolo BPM non riuscito: '+e.message)}
      }
    }
    await api('/api/projects/'+current.id,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(current)});
    projectDirty=false;closeUtilityModal();render();toast('Metadata progetto salvati');
  }catch(e){toast(e.message)}
}
async function downloadProjectLyrics(withChords=false){if(!current)return;if(!(current.lyrics||[]).length)return toast('Il progetto non contiene lyrics');if(withChords&&!(current.chords||[]).some(ch=>!ch.excluded))return toast('Il progetto non contiene chords attivi');const ext='txt';const safeName=(current.title||'lyrics').replace(/[\/:*?"<>|]+/g,'_').trim()||'lyrics';try{await downloadWithProgress(`/api/projects/${current.id}/lyrics.txt?chords=${withChords?'true':'false'}`,`${safeName}.${ext}`,withChords?'Download lyrics + chords':'Download lyrics',false,'text/plain')}catch(e){toast(e.message)}}
async function downloadProjectChordPro(){if(!current)return;if(!(current.lyrics||[]).length)return toast('Il progetto non contiene lyrics');if(!(current.chords||[]).some(ch=>!ch.excluded))return toast('Il progetto non contiene chords attivi');const safeName=(current.title||'lyrics').replace(/[\/:*?"<>|]+/g,'_').trim()||'lyrics';try{await downloadWithProgress(`/api/projects/${current.id}/lyrics.chordpro`,`${safeName}.cho`,'Download ChordPro',false,'text/plain')}catch(e){toast(e.message)}}
function lyricsPdfUrl(preview=false){const color=$('#lyricsPdfChordColorExpanded')?.value||$('#lyricsPdfChordColor')?.value||'#7B1FA2';return `/api/projects/${current.id}/lyrics.pdf?chord_color=${encodeURIComponent(color)}${preview?'&preview=true':''}`}
async function downloadProjectLyricsPdf(){
  if(!current)return;if(!(current.lyrics||[]).length)return toast('Il progetto non contiene lyrics');
  const safeName=(current.title||'lyrics').replace(/[\/:*?"<>|]+/g,'_').trim()||'lyrics';
  try{await downloadWithProgress(lyricsPdfUrl(false),`${safeName}.pdf`,(current.chords||[]).some(ch=>!ch.excluded)?'Salva PDF Lyrics + Chords':'Salva PDF Lyrics',false,'application/pdf')}catch(e){toast(e.message)}
}
async function previewProjectLyricsPdf(){
  if(!current)return;if(!(current.lyrics||[]).length)return toast('Il progetto non contiene lyrics');
  const hasChords=(current.chords||[]).some(ch=>!ch.excluded),title=hasChords?'Anteprima PDF · Lyrics + Chords + Markers':'Anteprima PDF · Lyrics + Markers';
  try{
    showMediaProgress(title,12,'Generazione del PDF reale…');
    const color=$('#lyricsPdfChordColorExpanded')?.value||$('#lyricsPdfChordColor')?.value||'#7B1FA2';
    const previewUrl=`/api/projects/${current.id}/lyrics.pdf.preview?chord_color=${encodeURIComponent(color)}&t=${Date.now()}`;
    const probe=await fetch(previewUrl,{credentials:'same-origin'});if(!probe.ok)throw new Error(await probe.text());
    const previewHtml=await probe.text(),parsed=new DOMParser().parseFromString(previewHtml,'text/html');
    const pages=parsed.querySelector('.pages');if(!pages||!pages.querySelector('img'))throw new Error('Anteprima PDF vuota');
    showUtilityModal(title,`<div class="pdf-preview-toolbar"><button class="utility-btn secondary pdf-preview-return" type="button" onclick="closeLyricsPdfPreview()">← Torna all'editor</button><button class="utility-btn primary pdf-preview-save" type="button" onclick="downloadProjectLyricsPdf()">Salva PDF Lyrics + Chords + Markers</button></div><div class="pdf-preview-wrap"><div class="pdf-rendered-pages">${pages.innerHTML}</div></div><div class="utility-actions pdf-preview-actions"><button class="utility-btn secondary pdf-preview-return" type="button" onclick="closeLyricsPdfPreview()">← Torna all'editor</button><button class="utility-btn primary pdf-preview-save" type="button" onclick="downloadProjectLyricsPdf()">Salva PDF Lyrics + Chords + Markers</button></div>`);
    document.querySelector('.utility-modal')?.classList.add('pdf-real-preview-modal');
    hideMediaProgress();
  }catch(e){hideMediaProgress();toast(e.message)}
}
function closeLyricsPdfPreview(){
  const backdrop=$('#utilityBackdrop');if(backdrop)backdrop.classList.add('hidden');
  document.querySelector('.utility-modal')?.classList.remove('pdf-real-preview-modal');
  if(lyricsPdfPreviewObjectUrl){URL.revokeObjectURL(lyricsPdfPreviewObjectUrl);lyricsPdfPreviewObjectUrl=null}
  forceNativeViewportTop();
  requestAnimationFrame(()=>{forceNativeViewportTop();$('#mixer')?.focus?.({preventScroll:true});document.querySelector('.main')?.scrollTo?.({top:0,left:0,behavior:'instant'})});
}

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
let metadataSearchCandidates=[];
let metadataSearchPage=0;
const metadataSearchPageSize=10;
const metadataSearchDetailCache=new Map();
function metadataCandidateBasicDetails(r){
  const ids=[];(r.isrcs||[]).forEach(x=>ids.push(`ISRC: ${x}`));if(r.mbid)ids.push(`MusicBrainz: ${r.mbid}`);
  return [r.title?`Titolo: ${r.title}`:'',(r.performers||[]).length?`Interprete/i: ${(r.performers||[]).join(', ')}`:'',r.first_release_date?`Prima pubblicazione: ${r.first_release_date}`:'',r.disambiguation?`Note: ${r.disambiguation}`:'',ids.join(' · ')].filter(Boolean).join('\n');
}
function metadataCandidateDetailHtml(r,full=null){
  const data=full||r,ids={...(full?.identifiers||{})};if(!full)(r.isrcs||[]).forEach((x,i)=>ids[`ISRC${i?` ${i+1}`:''}`]=x);if(r.mbid&&!ids.MUSICBRAINZ_RECORDING)ids.MUSICBRAINZ_RECORDING=r.mbid;
  const row=(label,value)=>value?`<div><b>${esc(label)}</b><span>${esc(String(value))}</span></div>`:'';
  return `<div class="metadata-hover-card">${row('Titolo',data.title||r.title)}${row('Titolo originale',data.original_title)}${row('Autori / compositori',(data.authors||[]).join(', '))}${row('Interpreti',(data.performers||r.performers||[]).join(', '))}${row('Prima pubblicazione',r.first_release_date)}${row('IS / identificativi',Object.entries(ids).map(([k,v])=>`${k}: ${v}`).join(' · '))}${row('Note',r.disambiguation)}<div class="metadata-hover-hint">Dettagli MusicBrainz caricati al passaggio del mouse.</div></div>`;
}
function renderProjectMetadataSearchPage(){
  const el=$('#metadataSearchResults');if(!el)return;const total=metadataSearchCandidates.length;if(!total){el.innerHTML='<p class="hint">Nessun risultato trovato. Puoi verificare anche i repertori SIAE e Soundreef/LEA dal pannello repertorio.</p>';return}
  const pages=Math.max(1,Math.ceil(total/metadataSearchPageSize));metadataSearchPage=Math.max(0,Math.min(metadataSearchPage,pages-1));const from=metadataSearchPage*metadataSearchPageSize,rows=metadataSearchCandidates.slice(from,from+metadataSearchPageSize);
  el.innerHTML=`<div class="metadata-results-scroll"><table class="users-table metadata-results-table"><thead><tr><th>Scegli</th><th>Titolo</th><th>Interprete</th><th>Dettagli rapidi</th></tr></thead><tbody>${rows.map((r,offset)=>{const i=from+offset;return `<tr class="metadata-result-row" tabindex="0" onmouseenter="showMetadataCandidateDetails(${i},this)" onfocus="showMetadataCandidateDetails(${i},this)" onmouseleave="hideMetadataCandidateDetails(this)" onblur="hideMetadataCandidateDetails(this)"><td><button class="utility-btn compact primary" onclick="event.stopPropagation();applyProjectMetadataCandidate(${i})">Usa</button></td><td><b>${esc(r.title||'')}</b></td><td>${esc((r.performers||[]).join(', '))}</td><td>${esc([r.first_release_date,r.disambiguation,(r.isrcs||[]).join(', ')].filter(Boolean).join(' · '))}<div class="metadata-hover-host">${metadataCandidateDetailHtml(r,metadataSearchDetailCache.get(r.mbid))}</div></td></tr>`}).join('')}</tbody></table></div><div class="metadata-pagination"><span>Risultati ${from+1}–${Math.min(total,from+metadataSearchPageSize)} di ${total}</span>${pages>1?`<button class="utility-btn compact secondary" ${metadataSearchPage<=0?'disabled':''} onclick="changeMetadataSearchPage(-1)">← Precedenti</button><b>Pagina ${metadataSearchPage+1}/${pages}</b><button class="utility-btn compact secondary" ${metadataSearchPage>=pages-1?'disabled':''} onclick="changeMetadataSearchPage(1)">Successivi →</button>`:''}</div>`;
}
function changeMetadataSearchPage(delta){metadataSearchPage+=Number(delta)||0;renderProjectMetadataSearchPage()}
function hideMetadataCandidateDetails(row){row?.classList.remove('show-metadata-details')}
async function showMetadataCandidateDetails(index,row){
  const candidate=metadataSearchCandidates?.[Number(index)];if(!candidate||!row)return;row.classList.add('show-metadata-details');const host=row.querySelector('.metadata-hover-host');if(!host)return;const cached=metadataSearchDetailCache.get(candidate.mbid);if(cached){host.innerHTML=metadataCandidateDetailHtml(candidate,cached);return}host.innerHTML=metadataCandidateDetailHtml(candidate,null).replace('Dettagli MusicBrainz caricati al passaggio del mouse.','Caricamento autori e identificativi…');
  try{const full=await api(`/api/projects/${current.id}/metadata-resolve/${encodeURIComponent(candidate.mbid)}`);metadataSearchDetailCache.set(candidate.mbid,full);if(row.classList.contains('show-metadata-details'))host.innerHTML=metadataCandidateDetailHtml(candidate,full)}catch(e){if(row.classList.contains('show-metadata-details'))host.innerHTML=metadataCandidateDetailHtml(candidate,null).replace('Dettagli MusicBrainz caricati al passaggio del mouse.','Dettagli estesi non disponibili.')}
}
async function openProjectMetadataSearch(){
  if(!current)return;metadataSearchCandidates=[];metadataSearchPage=0;metadataSearchDetailCache.clear();
  showUtilityModal('Cerca dati brano online',`<div class="stem-workflow"><div class="workflow-note">Ricerca per titolo nei cataloghi online. MusicBrainz fornisce risultati strutturati; passa il mouse su un risultato per vedere autori, interpreti e identificativi utili alla scelta.</div><label class="workflow-field"><span>Titolo</span><input id="metadataSearchTitle" value="${esc(current.title||'')}"></label><label class="workflow-field"><span>Interprete opzionale</span><input id="metadataSearchArtist" value="${esc(current.artist||'')}"></label><div class="utility-actions"><button class="utility-btn primary" onclick="performProjectMetadataSearch()">Cerca</button><button class="utility-btn secondary" onclick="closeUtilityModal()">Chiudi</button></div><div id="metadataSearchResults"></div></div>`);
}
async function performProjectMetadataSearch(){
  try{const data=await api(`/api/projects/${current.id}/metadata-search`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({title:$('#metadataSearchTitle')?.value||'',artist:$('#metadataSearchArtist')?.value||''})});metadataSearchCandidates=data.results||[];metadataSearchPage=0;metadataSearchDetailCache.clear();renderProjectMetadataSearchPage()}catch(e){toast(e.message)}
}
async function applyProjectMetadataCandidate(index){
  const row=metadataSearchCandidates?.[Number(index)];if(!row)return;try{const full=metadataSearchDetailCache.get(row.mbid)||await api(`/api/projects/${current.id}/metadata-resolve/${encodeURIComponent(row.mbid)}`);metadataSearchDetailCache.set(row.mbid,full);current.title=full.title||row.title||current.title;current.original_title=full.original_title||current.original_title||current.title;current.artist=(full.performers||row.performers||[]).join(', ')||current.artist;current.authors=full.authors||current.authors||[];const rec={uid:`MUSICBRAINZ:${full.mbid||row.mbid}`,society:'MUSICBRAINZ',title:full.title||row.title||'',original_title:full.original_title||'',authors:full.authors||[],performers:full.performers||row.performers||[],publishers:[],identifiers:full.identifiers||{},source_url:full.source_url||row.source_url||''};current.rights_records=[...(current.rights_records||[]).filter(x=>x.uid!==rec.uid),rec].slice(0,32);await api('/api/projects/'+current.id,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(current)});projectDirty=false;closeUtilityModal();render();toast('Autori e interpreti inseriti nelle informazioni del progetto');}catch(e){toast(e.message)}
}
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
async function recalculateBpmFromTrack(trackId){
  if(!current)return;const track=trackById(trackId);if(!track)return;
  showMediaProgress('Ricalcolo BPM',10,`Analisi ritmica di ${track.name}…`);
  try{const result=await api(`/api/projects/${current.id}/tracks/${trackId}/estimate-bpm`,{method:'POST'});current.bpm=Number(result.bpm);current.base_bpm=Number(result.bpm);render();markDirty(50);$('#utilityBackdrop')?.classList.add('hidden');if(result.time_signature)current.time_signature=result.time_signature;toast(`BPM ricalcolati da ${track.name}: ${Math.round(Number(result.bpm))} · ${current.time_signature||'4/4'}`)}catch(e){$('#utilityBackdrop')?.classList.add('hidden');toast('Ricalcolo BPM: '+e.message)}
}
function timedEditorConfig(kind){return {lyrics:{key:'text',label:'Lyrics',end:true,valueLabel:'Testo'},chords:{key:'chord',label:'Chords',end:false,valueLabel:'Accordo'},markers:{key:'label',label:'Markers',end:false,valueLabel:'Etichetta'}}[kind]||null}
function timedEditorTime(ms){const n=Math.max(0,Number(ms)||0),m=Math.floor(n/60000),s=(n%60000)/1000;return `${m}:${s.toFixed(3).padStart(6,'0')}`}
function parseTimedEditorTime(value){const raw=String(value??'').trim();if(!raw)return 0;if(raw.includes(':')){const parts=raw.split(':').map(x=>x.trim());if(parts.length===2){const m=Number(parts[0]),s=Number(parts[1]);if(Number.isFinite(m)&&Number.isFinite(s)&&m>=0&&s>=0)return Math.max(0,Math.round((m*60+s)*1000))}if(parts.length===3){const h=Number(parts[0]),m=Number(parts[1]),s=Number(parts[2]);if([h,m,s].every(Number.isFinite)&&h>=0&&m>=0&&s>=0)return Math.max(0,Math.round((h*3600+m*60+s)*1000))}}const seconds=Number(raw.replace(',','.'));return Number.isFinite(seconds)&&seconds>=0?Math.round(seconds*1000):NaN}
function timedEditorRow(kind,item={},idx=0,originalIndex=null){const cfg=timedEditorConfig(kind),start=timedEditorTime(item.time_ms||0),end=cfg.end?(item.end_ms==null?'':timedEditorTime(item.end_ms)):'';const original=originalIndex==null?'':String(originalIndex);const split=(kind==='lyrics'||kind==='chords')?`<button class="timed-row-action" type="button" onclick="splitTimedEditorRow(this,'${kind}')" title="Dividi riga">Dividi</button>`:'';return `<tr class="timed-editor-row" data-index="${idx}" data-original-index="${original}"><td class="timed-editor-index">${idx+1}</td><td><input class="timed-start" value="${esc(start)}" inputmode="decimal" aria-label="Tempo iniziale"></td>${cfg.end?`<td><input class="timed-end" value="${esc(end)}" inputmode="decimal" placeholder="auto" aria-label="Tempo finale"></td>`:''}<td class="timed-editor-value"><textarea class="timed-value" rows="2" aria-label="${esc(cfg.valueLabel)}">${esc(item[cfg.key]||'')}</textarea></td><td class="timed-row-actions"><button class="timed-row-action" type="button" onclick="insertTimedEditorRow(this,'${kind}','above')" title="Inserisci riga sopra">＋ sopra</button><button class="timed-row-action" type="button" onclick="insertTimedEditorRow(this,'${kind}','below')" title="Inserisci riga sotto">＋ sotto</button>${split}<button class="timed-row-delete" type="button" onclick="removeTimedEditorRow(this)" title="Elimina riga">Elimina</button></td></tr>`}
function renumberTimedEditorRows(){document.querySelectorAll('#timedEditorRows .timed-editor-row').forEach((row,i)=>{row.dataset.index=String(i);const cell=row.querySelector('.timed-editor-index');if(cell)cell.textContent=String(i+1)})}
function timedRowStart(row){return parseTimedEditorTime(row?.querySelector('.timed-start')?.value)}
function timedRowEnd(row){const raw=String(row?.querySelector('.timed-end')?.value||'').trim();return raw?parseTimedEditorTime(raw):NaN}
function suggestedTimedRow(kind,row,where){const cfg=timedEditorConfig(kind),prev=where==='above'?row?.previousElementSibling:row,next=where==='above'?row:row?.nextElementSibling;const prevStart=timedRowStart(prev),prevEnd=timedRowEnd(prev),nextStart=timedRowStart(next);let left=Number.isFinite(prevEnd)?prevEnd:(Number.isFinite(prevStart)?prevStart:0),right=Number.isFinite(nextStart)?nextStart:left+2000;if(right<left)right=left+1000;let start=Math.max(0,Math.round((left+right)/2));if(where==='above'&&!prev)start=Math.max(0,Number.isFinite(nextStart)?nextStart-1000:0);if(where==='below'&&!next)start=Math.max(0,Number.isFinite(prevEnd)?prevEnd:(Number.isFinite(prevStart)?prevStart+1000:0));const item={time_ms:start};if(cfg?.end)item.end_ms=Number.isFinite(nextStart)&&nextStart>start?nextStart:start+1000;return item}
function insertTimedEditorRow(button,kind,where='below'){const row=button?.closest('.timed-editor-row'),body=$('#timedEditorRows');if(!row||!body)return;const item=suggestedTimedRow(kind,row,where),html=timedEditorRow(kind,item,0,null);if(where==='above')row.insertAdjacentHTML('beforebegin',html);else row.insertAdjacentHTML('afterend',html);renumberTimedEditorRows();const inserted=where==='above'?row.previousElementSibling:row.nextElementSibling;inserted?.querySelector('.timed-value')?.focus();inserted?.scrollIntoView({block:'nearest'})}
function addTimedEditorRow(kind){const body=$('#timedEditorRows');if(!body)return;if(body.lastElementChild){const fake=body.lastElementChild.querySelector('.timed-row-action');if(fake)return insertTimedEditorRow(fake,kind,'below')}body.insertAdjacentHTML('beforeend',timedEditorRow(kind,{time_ms:0},0,null));renumberTimedEditorRows();body.lastElementChild?.querySelector('.timed-value')?.focus()}
function splitTimedEditorRow(button,kind){if(kind!=='lyrics'&&kind!=='chords')return;const row=button?.closest('.timed-editor-row');if(!row)return;const start=timedRowStart(row),rawEnd=timedRowEnd(row),nextStart=timedRowStart(row.nextElementSibling);if(!Number.isFinite(start))return toast('Tempo iniziale non valido');let end=Number.isFinite(rawEnd)?rawEnd:(Number.isFinite(nextStart)&&nextStart>start?nextStart:start+2000);if(end<=start)end=start+1000;const middle=Math.round((start+end)/2);if(kind==='lyrics'){const endInput=row.querySelector('.timed-end');if(endInput)endInput.value=timedEditorTime(middle);row.insertAdjacentHTML('afterend',timedEditorRow('lyrics',{time_ms:middle,end_ms:end,text:''},0,null))}else{row.insertAdjacentHTML('afterend',timedEditorRow('chords',{time_ms:middle,chord:''},0,null))}renumberTimedEditorRows();const inserted=row.nextElementSibling;inserted?.querySelector('.timed-value')?.focus();inserted?.scrollIntoView({block:'nearest'})}
function removeTimedEditorRow(button){const row=button?.closest('.timed-editor-row');if(!row)return;const value=String(row.querySelector('.timed-value')?.value||'').trim();if(value&&!window.confirm('Eliminare questa riga? La modifica sarà applicata solo premendo Salva.'))return;row.remove();renumberTimedEditorRows()}
function saveTimedEditor(kind){if(!current)return;const cfg=timedEditorConfig(kind);if(!cfg)return;const old=current[kind]||[],out=[];for(const [i,row] of [...document.querySelectorAll('#timedEditorRows .timed-editor-row')].entries()){const start=parseTimedEditorTime(row.querySelector('.timed-start')?.value);if(!Number.isFinite(start))return toast(`Tempo non valido alla riga ${i+1}`);let end=null;if(cfg.end){const raw=String(row.querySelector('.timed-end')?.value||'').trim();if(raw){end=parseTimedEditorTime(raw);if(!Number.isFinite(end)||end<start)return toast(`Tempo finale non valido alla riga ${i+1}`)}}const value=String(row.querySelector('.timed-value')?.value||'').trim();if(!value)continue;const item={time_ms:start,[cfg.key]:value};if(cfg.end)item.end_ms=end;const originalIndex=Number(row.dataset.originalIndex),prev=Number.isInteger(originalIndex)&&originalIndex>=0?old[originalIndex]:null;if(kind==='lyrics'&&prev&&Number(prev.time_ms)===start&&Number(prev.end_ms??-1)===Number(end??-1)&&String(prev.text||'')===value)item.words=prev.words||[];else if(kind==='lyrics')item.words=[];out.push(item)}out.sort((a,b)=>a.time_ms-b.time_ms);current[kind]=out;render();markDirty(50);closeUtilityModal();toast(`${cfg.label} aggiornati`)}
function focusTimedEditorAtTimeline(){const rows=[...document.querySelectorAll('#timedEditorRows .timed-editor-row')];if(!rows.length)return;const targetMs=Math.max(0,Number(playCursorMs||0));let best=null,bestDistance=Infinity;for(const row of rows){const ms=parseTimedEditorTime(row.querySelector('.timed-start')?.value);if(!Number.isFinite(ms))continue;const distance=Math.abs(ms-targetMs);if(distance<bestDistance){bestDistance=distance;best=row}}if(!best)return;rows.forEach(row=>row.classList.remove('timed-current-row'));best.classList.add('timed-current-row');requestAnimationFrame(()=>best.scrollIntoView({block:'center',inline:'nearest'}))}
function editTimed(kind){if(!current)return;const cfg=timedEditorConfig(kind);if(!cfg)return;const rows=(current[kind]||[]).map((item,i)=>timedEditorRow(kind,item,i,i)).join('');showUtilityModal(`Edit ${cfg.label}`,`<div class="timed-editor" data-kind="${kind}"><div class="timed-editor-toolbar"><p>Modifica separatamente i tempi e ${kind==='lyrics'?'il testo':'il valore'}. I tempi accettano <code>mm:ss.mmm</code> oppure secondi. Usa <b>+ sopra</b>/<b>+ sotto</b> per inserire righe in qualsiasi punto${(kind==='lyrics'||kind==='chords')?' oppure <b>Dividi</b> per spezzare temporalmente un segmento':''}.</p><button class="utility-btn secondary timed-add-bottom" type="button" onclick="addTimedEditorRow('${kind}')">＋ Aggiungi in fondo</button></div><div class="timed-editor-table-wrap"><table class="timed-editor-table"><thead><tr><th>#</th><th>Inizio</th>${cfg.end?'<th>Fine</th>':''}<th>${esc(cfg.valueLabel)}</th><th>Azioni</th></tr></thead><tbody id="timedEditorRows">${rows||timedEditorRow(kind,{time_ms:0},0,null)}</tbody></table></div>${kind==='lyrics'?'<p class="hint">Le righe possono essere inserite, divise o eliminate prima di Salva. Se modifichi testo o timing di una riga, il timing parola-per-parola di quella sola riga viene rimosso per evitare un karaoke incoerente.</p>':kind==='chords'?'<p class="hint">Gli accordi possono essere inseriti, divisi o eliminati prima di Salva. Dividi crea un nuovo punto accordo a metà dell’intervallo corrente.</p>':''}<div class="utility-actions timed-editor-actions"><button class="utility-btn primary" type="button" onclick="saveTimedEditor('${kind}')">Salva</button><button class="utility-btn secondary" type="button" onclick="closeUtilityModal()">Annulla</button></div></div>`);document.querySelector('.utility-modal')?.classList.add('timed-editor-modal');requestAnimationFrame(focusTimedEditorAtTimeline)}




window.addEventListener('pointerdown',e=>{
  const menu=$('#trackContextMenu');
  if(menu&&!menu.contains(e.target))closeTrackContextMenu();
});
window.addEventListener('keydown',e=>{
  const target=e.target;
  const editable=target instanceof HTMLInputElement||target instanceof HTMLTextAreaElement||target instanceof HTMLSelectElement||target?.isContentEditable;
  if((e.ctrlKey||e.metaKey)&&!e.altKey){
    // Preserve native editing shortcuts (Cmd/Ctrl+C/X/V/A/Z) inside form fields,
    // including the YouTube URL/name inputs. Outside fields they remain DAW shortcuts.
    if(editable)return;
    const key=e.key.toLowerCase();if(key==='z'){e.preventDefault();if(e.shiftKey)redoEdit();else undoEdit();return}if(key==='y'){e.preventDefault();redoEdit();return}if(key==='x'){e.preventDefault();cutTimelineSelection();return}if(key==='c'){e.preventDefault();copyTimelineSelection();return}if(key==='v'){e.preventDefault();pasteTimelineSelection();return}if(key==='s'){e.preventDefault();save();return}
  }
  if(e.key==='Escape'){closeTrackContextMenu();return}

  if(!(e.code==='Space'||e.key===' '||e.key==='Spacebar'))return;
  if(editable)return;
  if(e.repeat)return;e.preventDefault();e.stopPropagation();
  if(playAudio||trackPlaybacks.length||playbackPaused||playbackBuffering)stopPlayback();else previewMaster();
},true);

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
  $('#utilityTitle').textContent=trDynamic(title);$('#utilityBody').innerHTML=html;$('#utilityBackdrop').classList.remove('hidden');applyInterfaceLanguage($('#utilityBackdrop'));
}
function closeUtilityModal(){if(document.querySelector('.utility-modal.lyrics-chords-editor-modal')&&lyricsChordsEditorHasChanges())return closeLyricsChordsEditor();if(activeStemJob){toast('La separazione è in corso: usa Annulla separazione se vuoi interromperla.');return}if(document.querySelector('.utility-modal .export-dialog')&&(playAudio||trackPlaybacks.length||playbackPaused||playbackBuffering))stopPlayback();$('#utilityBackdrop').classList.add('hidden');document.querySelector('.utility-modal')?.classList.remove('sample-editor-modal','meta-expanded-modal','pdf-html-preview-modal','timed-editor-modal','youtube-import-modal','lyrics-chords-editor-modal');sampleEditorState=null;clearTimeout(sampleEditorPreviewTimer);sampleEditorPreviewTimer=null;forceNativeViewportTop()}
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
    ['BPM',String(Math.round(Number(current.bpm||0)))],
    ['Time signature',current.time_signature||'4/4'],
    ['Tonalità',effectiveProjectKey()||'—'],
    ['Auto-save',autosaveEnabled?'Attivo':'Disattivato'],
  ];
  const rights=(current.rights_records||[]);
  const rightsRows=rights.length?`<h4>Dati repertorio / provider diritti</h4><div class="table-scroll"><table class="users-table"><thead><tr><th>Provider</th><th>Opera</th><th>Dati registrati</th></tr></thead><tbody>${rights.map(r=>`<tr><td><b>${esc(r.society||'—')}</b></td><td>${esc(r.original_title||r.title||'—')}</td><td>${esc(rightsRecordSummary(r))}</td></tr>`).join('')}</tbody></table></div>`:'<p class="hint">Nessun dato repertorio registrato nel progetto.</p>';
  showUtilityModal('Info progetto',`<div class="utility-actions"><button class="utility-btn" onclick="editProjectMeta()">Modifica titolo / autore / BPM e metadata</button><button class="utility-btn secondary" onclick="openProjectMetadataSearch()">Cerca autori/interpreti online</button><button class="utility-btn secondary" onclick="openRightsSearch()">Cerca repertorio autori</button></div><div class="table-scroll"><table class="users-table project-info-table"><tbody>${rows.map(([k,v])=>`<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join('')}</tbody></table></div>${rightsRows}`);
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
  const showChordNeighbors=appDisplayPreference('showPreviousNextChords',false),showLyricNeighbors=appDisplayPreference('showPreviousNextLyrics',false);
  showUtilityModal('Settings',`<div class="form-grid web-settings"><label class="workflow-check"><input id="webAutosaveEnabled" type="checkbox" ${enabled?'checked':''}> Auto-save project changes</label><label class="workflow-check"><input id="showPreviousNextChords" type="checkbox" ${showChordNeighbors?'checked':''}> Show previous and next chords</label><label class="workflow-check"><input id="showPreviousNextLyrics" type="checkbox" ${showLyricNeighbors?'checked':''}> Show previous and next lyrics</label><p class="hint">Quando abilitate, le viste Lyrics/Chords sopra la timeline mostrano precedente, corrente e successivo; l'evento corrente resta evidenziato. Le preferenze dell'editor sono salvate in questa app/browser.</p><div class="form-actions"><button type="button" onclick="openAiModelManager()">Manage Lyrics / Chords models</button><button type="button" onclick="rescanSharedMedia()">Rescan / GC shared media</button><button type="button" onclick="location.href='/account'">Account / Profile</button>${currentUser?.role==='admin'?`<button type="button" onclick="location.href='/settings'">Server administration</button>`:''}<button class="accent" onclick="saveWebSettings()">Save</button></div></div>`);
}
async function rescanSharedMedia(){try{const r=await api('/api/storage/shared/rescan?delete_unreferenced=true',{method:'POST'});toast(`Shared media: ${r.assets||0} asset, ${r.deleted||0} eliminati, ${r.references||0} riferimenti`)}catch(e){toast('Rescan shared media fallito: '+e.message)}}
function saveWebSettings(){const enabled=$('#webAutosaveEnabled')?.checked!==false;localStorage.setItem('mtaWebAutosaveEnabled',enabled?'true':'false');setAppDisplayPreference('showPreviousNextChords',$('#showPreviousNextChords')?.checked===true);setAppDisplayPreference('showPreviousNextLyrics',$('#showPreviousNextLyrics')?.checked===true);autosaveEnabled=enabled;if(autosaveEnabled&&projectDirty)markDirty(50);updateTimedPlaybackOverlay(playCursorMs);closeUtilityModal();toast('Settings salvati')}
async function showNativeSettings(){
  if(!currentUser?.native_single_user){if(currentUser?.role==='admin'){location.href='/settings';return}return}
  const apiBridge=await waitForNativeApi();
  if(!apiBridge?.get_native_settings){toast('Bridge nativo non disponibile. Riprova tra un istante.');return}
  try{
    const cfg=await apiBridge.get_native_settings();
    const showChordNeighbors=appDisplayPreference('showPreviousNextChords',false),showLyricNeighbors=appDisplayPreference('showPreviousNextLyrics',false);
    showUtilityModal('Settings',`<div class="form-grid native-settings"><label>Maximum import/upload size (MB)<input id="nativeMaxUploadMb" type="number" min="1" max="10240" step="1" value="${Number(cfg.max_upload_mb)||1024}"></label><label class="workflow-check"><input id="nativeAutosaveEnabled" type="checkbox" ${cfg.autosave_enabled!==false?'checked':''}> Auto-save project changes</label><label class="workflow-check"><input id="showPreviousNextChords" type="checkbox" ${showChordNeighbors?'checked':''}> Show previous and next chords</label><label class="workflow-check"><input id="showPreviousNextLyrics" type="checkbox" ${showLyricNeighbors?'checked':''}> Show previous and next lyrics</label><label>Language<select id="nativeLanguage"><option value="auto" ${!['it','en'].includes(cfg.language)?'selected':''}>Auto (system) · ${esc(cfg.system_language||'en')}</option><option value="it" ${cfg.language==='it'?'selected':''}>Italiano</option><option value="en" ${cfg.language==='en'?'selected':''}>English</option></select></label><label>Update channel<select id="nativeUpdateChannel"><option value="stable" ${cfg.update_channel!=='early'?'selected':''}>Stable · GitHub tags/releases only</option><option value="early" ${cfg.update_channel==='early'?'selected':''}>Early release · include latest main packages</option></select></label><p>Stable checks only tagged GitHub releases. Early release also checks the rolling <b>early-main</b> package produced from main.</p><p class="hint">Con le opzioni previous/next attive, la vista sopra la timeline scorre mostrando l'evento precedente e successivo attenuati e quello corrente evidenziato.</p><div class="form-actions"><button type="button" onclick="checkNativeAppUpdate(true)">Check for updates</button><button type="button" onclick="openNativeModelManager()">Manage Demucs models</button><button type="button" onclick="openAiModelManager()">Manage Lyrics / Chords models</button><button type="button" onclick="rescanSharedMedia()">Rescan / GC shared media</button><button class="accent" onclick="saveNativeSettings()">Save</button></div></div>`);
  }catch(err){toast('Impossibile leggere le impostazioni native: '+err.message)}
}
async function saveNativeSettings(){
  const value=Number($('#nativeMaxUploadMb')?.value);
  if(!Number.isInteger(value)||value<1||value>10240){toast('Inserisci un valore intero tra 1 e 10240 MB');return}
  try{
    const apiBridge=await waitForNativeApi();if(!apiBridge?.set_native_settings)return toast('Bridge nativo non disponibile');
    const enabled=$('#nativeAutosaveEnabled')?.checked!==false;const channel=$('#nativeUpdateChannel')?.value==='early'?'early':'stable';const language=['it','en'].includes($('#nativeLanguage')?.value)?$('#nativeLanguage').value:'auto';const result=await apiBridge.set_native_settings(value,enabled,channel,language);uiLanguage=result.language==='auto'?(String(result.system_language||'en').toLowerCase().startsWith('it')?'it':'en'):result.language;applyInterfaceLanguage();setAppDisplayPreference('showPreviousNextChords',$('#showPreviousNextChords')?.checked===true);setAppDisplayPreference('showPreviousNextLyrics',$('#showPreviousNextLyrics')?.checked===true);autosaveEnabled=result.autosave_enabled!==false;if(autosaveEnabled&&projectDirty)markDirty(50);updateTimedPlaybackOverlay(playCursorMs);
    closeUtilityModal();toast(`Impostazioni salvate · limite import/upload ${result.max_upload_mb} MB`);
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

async function openAiModelManager(){try{const d=await api('/api/ai-models'),l=d.lyrics||{},c=d.chords||{};const btn=(kind,id,label,action='download',danger=false)=>`<button class="utility-btn ai-model-action-btn ${danger?'danger-action':'secondary'}" onclick="manageAiModel('${kind}','${esc(id)}','${action}')">${esc(label)}</button>`;const lrows=(l.models||[]).map(m=>`<tr><td>${esc(m.display_name)}</td><td>OpenAI Whisper</td><td>${m.installed?'Installato':'On-demand'}</td><td><div class="ai-model-actions">${btn('lyrics',m.id,m.installed?'Verifica / riscarica':'Scarica')}${m.installed?btn('lyrics',m.id,'Elimina','delete',true):''}</div></td></tr>`).join('');const crows=(c.models||[]).map(m=>`<tr><td>${esc(m.display_name)}</td><td>${esc(m.engine)}</td><td>${m.installed?'Installato':'On-demand'}</td><td><div class="ai-model-actions">${btn('chords',m.id,m.installed?'Verifica / riscarica':'Scarica')}${m.installed?btn('chords',m.id,'Elimina','delete',true):''}</div><small>${esc(m.license||'')}</small></td></tr>`).join('');showUtilityModal(`AI models · ${d.storage==='local'?'locale':'server'}`,`<h3>Lyrics</h3><div class="table-scroll"><table><thead><tr><th>Modello</th><th>Motore</th><th>Stato</th><th>Azioni</th></tr></thead><tbody>${lrows}</tbody></table></div><h3>Chords</h3><div class="table-scroll"><table><thead><tr><th>Modello</th><th>Motore</th><th>Stato</th><th>Azioni</th></tr></thead><tbody>${crows}</tbody></table></div><p class="hint">Nella web app i modelli sono conservati sul server; nelle applicazioni native sono conservati localmente. I profili Fast/Accurate/Maximum scelgono automaticamente i recognizer disponibili. ChordFormer e BTC-HCQT sono scaricabili on-demand; Chordino e MTA Chromagram non richiedono pesi AI.${d.accelerator?.device?`<br>Acceleratore AI: <b>${esc(d.accelerator.device)}</b>${d.accelerator.hardware_accelerated?' · attivo':' · CPU fallback'}`:''}</p>`)}catch(e){toast(e.message)}}
async function pollModelDownloadJob(jobId,title,onDone){
  try{const job=await api(`/api/media-jobs/${jobId}`);showMediaProgress(title,job.progress,job.message,job.error||'');if(job.status==='completed'){setMobileBusy(false);await onDone(job);return}if(job.status==='failed'){setMobileBusy(false);toast(job.error||'Download modello fallito');return}setTimeout(()=>pollModelDownloadJob(jobId,title,onDone),500)}catch(e){setMobileBusy(false);toast(e.message)}
}
async function startModelDownload(kind,id,onDone){
  const title=`Download modello ${kind==='lyrics'?'Lyrics':'Chords'}`;
  const job=await api(`/api/ai-models/${kind}/${encodeURIComponent(id)}/download-jobs`,{method:'POST'});
  showMediaProgress(title,job.progress,job.message);pollModelDownloadJob(job.id,title,onDone||(()=>{}));
}
async function manageAiModel(kind,id,action){try{if(action==='delete'){await api(`/api/ai-models/${kind}/${encodeURIComponent(id)}`,{method:'DELETE'});pluginInfo=await api('/api/plugins');openAiModelManager();return}await startModelDownload(kind,id,async()=>{pluginInfo=await api('/api/plugins');openAiModelManager();toast('Modello pronto')})}catch(e){toast(e.message)}}
async function openNativeModelManager(){const b=await waitForNativeApi();if(!b?.list_local_models)return toast('Native model manager unavailable');try{const d=await b.list_local_models(),profiles=d.catalog?.model_profiles||[],local=new Set((d.local||[]).map(x=>x.id.replace(/\.server-model$/,'')));const rows=profiles.map(p=>`<tr><td>${esc(p.display_name||p.model)}</td><td>${p.stem_count||'—'}</td><td>${local.has(p.model)?'Installed':'On demand'}</td><td><button onclick="nativeModelUpdate('${esc(p.model)}')">${local.has(p.model)?'Force update':'Download'}</button>${local.has(p.model)?` <button onclick="nativeModelDelete('${esc(p.model)}')">Delete local</button>`:''}</td></tr>`).join('');showUtilityModal('Demucs models',`<div class="table-scroll"><table><thead><tr><th>Model</th><th>Stems</th><th>Local</th><th>Actions</th></tr></thead><tbody>${rows}</tbody></table></div><p>Missing models are downloaded automatically when requested for splitting.</p>`) }catch(e){toast(e.message)}}
async function nativeModelUpdate(id){const b=await waitForNativeApi();try{await b.update_local_model(id);toast('Model updated: '+id);openNativeModelManager()}catch(e){toast(e.message)}}
async function nativeModelDelete(id){const b=await waitForNativeApi();try{await b.delete_local_model(id);toast('Local model deleted: '+id);openNativeModelManager()}catch(e){toast(e.message)}}

// ---------------------------------------------------------------------------
// r167: authoritative synchronized-event editor, PDF typography and render-live
// ---------------------------------------------------------------------------
let lyricsChordsEditorMarkersDraft=null;
let lyricsChordsEditorOriginalDraft=null;
let renderLiveFallbackActive=false;

function eventIsActive(ev,kind='lyrics'){
  if(!ev||ev.deleted)return false;
  if(kind==='chords')return !ev.excluded;
  return !ev.disabled;
}
function activeTimedItem(items,timeMs){let active=null;for(const item of items||[]){if(!eventIsActive(item,item?.chord!=null?'chords':'lyrics'))continue;if(Number(item.time_ms||0)>timeMs)break;active=item}return active}
function ensureEventSnapshot(ev){
  if(!ev)return;
  if(!ev.source_snapshot){const snap=JSON.parse(JSON.stringify(ev));delete snap.source_snapshot;snap.manual_override=false;ev.source_snapshot=snap}
  ev.manual_override=true;
}
function newOverrideEvent(payload){return {...payload,manual_override:true,source_snapshot:{__new__:true}}}
function restoreDraftEvent(kind,index){
  const arrays={lyrics:lyricsChordsEditorLyricsDraft,chords:lyricsChordsEditorDraft,markers:lyricsChordsEditorMarkersDraft},arr=arrays[kind],i=Number(index),ev=arr?.[i];if(!ev)return;
  const snap=ev.source_snapshot;
  if(snap?.__new__){arr.splice(i,1)}
  else if(snap){arr[i]={...JSON.parse(JSON.stringify(snap)),source_snapshot:null,manual_override:false}}
  else if(kind==='chords'){ev.manual_anchor=false;ev.anchor_line_time_ms=null;ev.anchor_word_index=null;ev.anchor_word_text='';ev.excluded=false;ev.deleted=false;ev.manual_override=false}
  else{ev.disabled=false;ev.deleted=false;ev.manual_override=false}
  if(kind==='chords')lyricsChordsEditorSelected=-1;
  refreshLyricsChordsEditor();
}
function lyricsChordsEditorPosition(ms){const n=Math.max(0,Math.round(Number(ms)||0)),m=Math.floor(n/60000),sec=Math.floor((n%60000)/1000),msec=n%1000;return `${m}:${String(sec).padStart(2,'0')}.${String(msec).padStart(3,'0')}`}
function parseLyricsChordsEditorPosition(value){const raw=String(value??'').trim().replace(',','.');const m=raw.match(/^(\d+):([0-5]\d)(?:\.(\d{1,3}))?$/);if(!m)return NaN;const minutes=Number(m[1]),seconds=Number(m[2]),fraction=(m[3]||'0').padEnd(3,'0');return Math.max(0,minutes*60000+seconds*1000+Number(fraction))}
function restoreLyricsChordsEditorModal(){showUtilityModal('Editor Lyrics + Chords + Markers',lyricsChordsEditorHtml());const modal=document.querySelector('.utility-modal');modal?.classList.remove('meta-expanded-modal');modal?.classList.add('lyrics-chords-editor-modal')}
function lyricsChordsEditorArrays(kind){return {lyrics:lyricsChordsEditorLyricsDraft,chords:lyricsChordsEditorDraft,markers:lyricsChordsEditorMarkersDraft}[kind]||null}
function lyricsChordsEditorEvent(kind,index){return lyricsChordsEditorArrays(kind)?.[Number(index)]||null}
function closeLyricsChordsContextMenu(){document.querySelector('#lyricsChordsContextMenu')?.remove()}
function openLyricsChordsContextMenu(event,kind,index){
  event?.preventDefault?.();event?.stopPropagation?.();closeLyricsChordsContextMenu();
  const ev=kind==='editor'?{}:lyricsChordsEditorEvent(kind,index);if(!ev)return false;
  const disabled=kind==='chords'?!!ev.excluded:!!ev.disabled,deleted=!!ev.deleted;
  const labels={editor:'editor',lyrics:'linea lyrics',chords:'chord',markers:'marker'},menu=document.createElement('div');menu.id='lyricsChordsContextMenu';menu.className='lc-context-menu';menu.setAttribute('role','menu');
  const items=kind==='editor'?[['add-marker','+ Marker']]:[
    ['edit','Modifica'],
    ['toggle',disabled?'Abilita':'Disabilita'],
    ['merge','Accorpa con il successivo'],
    ['delete','Elimina'],
    ['restore','Ripristina'],
  ];
  if(kind==='lyrics')items.splice(3,0,['add-marker','+ Marker']);
  menu.innerHTML=`<div class="lc-context-title">${labels[kind]||'Evento'}</div>${items.map(([a,l])=>`<button type="button" role="menuitem" class="${a==='delete'?'danger-action':''}" data-lc-action="${a}">${l}</button>`).join('')}`;
  document.body.appendChild(menu);menu.querySelectorAll('[data-lc-action]').forEach(btn=>btn.addEventListener('click',()=>{const a=btn.dataset.lcAction;closeLyricsChordsContextMenu();lyricsChordsContextAction(a,kind,Number(index))}));
  const x=Math.max(8,Math.min(Number(event?.clientX||0),window.innerWidth-menu.offsetWidth-8)),y=Math.max(8,Math.min(Number(event?.clientY||0),window.innerHeight-menu.offsetHeight-8));menu.style.left=`${x}px`;menu.style.top=`${y}px`;return false;
}
function lyricsChordsContextAction(action,kind,index){
  if(action==='edit')return editDraftEvent(kind,index);
  if(action==='toggle')return toggleDraftEvent(kind,index);
  if(action==='merge')return mergeDraftEvent(kind,index);
  if(action==='delete')return deleteDraftEvent(kind,index);
  if(action==='restore')return restoreDraftEvent(kind,index);
  if(action==='add-marker')return addMarkerEditorEvent(kind==='lyrics'?index:null);
}
document.addEventListener('click',e=>{if(!e.target.closest?.('#lyricsChordsContextMenu'))closeLyricsChordsContextMenu()});
function editDraftEvent(kind,index){
  const arr=lyricsChordsEditorArrays(kind),ev=arr?.[Number(index)];if(!ev)return;
  const labels={lyrics:'Lyrics',chords:'Chord',markers:'Marker'},key=kind==='lyrics'?'text':kind==='chords'?'chord':'label';
  const value=String(ev[key]||'');
  const colorField=kind==='markers'?`<label class="field lc-marker-color-edit">Colore marker<input id="lcEventEditColor" type="color" value="${esc(ev.color||'#204A87')}"></label>`:'';
  showUtilityModal(`Modifica ${labels[kind]||'evento'}`,`<div class="lc-event-edit-dialog"><div class="workflow-note"><b>Formato posizione:</b> <code>m:ss.mmm</code> oppure <code>mm:ss.mmm</code>. Il primo zero dei minuti è facoltativo; i millisecondi accettano da 1 a 3 cifre.</div><div class="lc-event-edit-table-wrap"><table class="lc-event-edit-table"><thead><tr><th>Posizione</th><th>Testo</th></tr></thead><tbody><tr><td><input id="lcEventEditPosition" value="${esc(lyricsChordsEditorPosition(ev.time_ms||0))}" inputmode="decimal" aria-label="Posizione"></td><td><textarea id="lcEventEditText" rows="3" aria-label="Testo">${esc(value)}</textarea></td></tr></tbody></table></div>${colorField}<div class="utility-actions"><button class="utility-btn primary" onclick="applyDraftEventEdit('${kind}',${Number(index)})">Salva modifica</button><button class="utility-btn secondary" onclick="restoreLyricsChordsEditorModal()">Annulla</button></div></div>`);
}
function applyDraftEventEdit(kind,index){
  const arr=lyricsChordsEditorArrays(kind),ev=arr?.[Number(index)];if(!ev)return restoreLyricsChordsEditorModal();
  const ms=parseLyricsChordsEditorPosition($('#lcEventEditPosition')?.value),text=String($('#lcEventEditText')?.value??'').trim();if(!Number.isFinite(ms))return toast('Posizione non valida: usa m:ss.mmm o mm:ss.mmm, con 1-3 cifre per i millisecondi');if(!text)return toast('Il testo non può essere vuoto');
  const oldTime=Number(ev.time_ms||0);ensureEventSnapshot(ev);ev.time_ms=ms;if(kind==='lyrics'){if(String(ev.text||'')!==text)ev.words=[];ev.text=text;updateLyricsLineAnchors(oldTime,ms)}else if(kind==='chords')ev.chord=text;else{ev.label=text;const color=String($('#lcEventEditColor')?.value||ev.color||'#204A87');if(/^#[0-9a-fA-F]{6}$/.test(color))ev.color=color}arr.sort((a,b)=>Number(a.time_ms||0)-Number(b.time_ms||0));restoreLyricsChordsEditorModal();
}
function editLyricsLineTime(index){
  const ev=lyricsChordsEditorEvent('lyrics',index);if(!ev)return;
  showUtilityModal('Modifica posizione linea',`<div class="lc-event-edit-dialog"><div class="workflow-note"><b>Formato posizione:</b> <code>m:ss.mmm</code> oppure <code>mm:ss.mmm</code>; millisecondi da 1 a 3 cifre.</div><label class="field">Posizione<input id="lcLineTimePosition" value="${esc(lyricsChordsEditorPosition(ev.time_ms||0))}" inputmode="decimal" autofocus></label><div class="utility-actions"><button class="utility-btn primary" onclick="applyLyricsLineTime(${Number(index)})">Salva posizione</button><button class="utility-btn secondary" onclick="restoreLyricsChordsEditorModal()">Annulla</button></div></div>`)
}
function updateLyricsLineAnchors(oldTime,newTime){if(Number(oldTime)===Number(newTime))return;(lyricsChordsEditorDraft||[]).forEach(ch=>{if(ch.manual_anchor&&Number(ch.anchor_line_time_ms)===Number(oldTime)){ensureEventSnapshot(ch);ch.anchor_line_time_ms=Number(newTime)}})}
function applyLyricsLineTime(index){const ev=lyricsChordsEditorEvent('lyrics',index),ms=parseLyricsChordsEditorPosition($('#lcLineTimePosition')?.value);if(!ev)return restoreLyricsChordsEditorModal();if(!Number.isFinite(ms))return toast('Posizione non valida: usa m:ss.mmm o mm:ss.mmm');const oldTime=Number(ev.time_ms||0);ensureEventSnapshot(ev);ev.time_ms=ms;updateLyricsLineAnchors(oldTime,ms);(lyricsChordsEditorLyricsDraft||[]).sort((a,b)=>Number(a.time_ms||0)-Number(b.time_ms||0));restoreLyricsChordsEditorModal()}
function toggleDraftEvent(kind,index){
  const arr=lyricsChordsEditorArrays(kind),ev=arr?.[Number(index)];if(!ev)return;ensureEventSnapshot(ev);
  if(kind==='chords')ev.excluded=!ev.excluded;else ev.disabled=!ev.disabled;
  refreshLyricsChordsEditor();
}
function deleteDraftEvent(kind,index){
  const arr=lyricsChordsEditorArrays(kind),ev=arr?.[Number(index)];if(!ev)return;ensureEventSnapshot(ev);ev.deleted=true;if(kind==='chords'&&lyricsChordsEditorSelected===Number(index))lyricsChordsEditorSelected=-1;refreshLyricsChordsEditor();
}
function mergeDraftEvent(kind,index){
  if(kind==='lyrics')return mergeLyricsEditorLine(index);
  const arr=lyricsChordsEditorArrays(kind),i=Number(index),ev=arr?.[i];if(!ev||ev.deleted)return;
  let j=i+1;while(j<arr.length&&arr[j]?.deleted)j++;const next=arr[j];if(!next)return toast(`Nessun ${kind==='chords'?'chord':'marker'} successivo da accorpare`);
  ensureEventSnapshot(ev);ensureEventSnapshot(next);
  if(kind==='chords'){
    ev.chord=[String(ev.chord||'').trim(),String(next.chord||'').trim()].filter(Boolean).join(' / ');ev.excluded=!!ev.excluded&&!!next.excluded;next.deleted=true;
  }else{
    ev.label=[String(ev.label||'').trim(),String(next.label||'').trim()].filter(Boolean).join(' / ');const ends=[ev.end_ms,next.end_ms,next.time_ms].filter(v=>v!=null&&Number.isFinite(Number(v))).map(Number);if(ends.length)ev.end_ms=Math.max(...ends);ev.disabled=!!ev.disabled&&!!next.disabled;next.deleted=true;
  }
  refreshLyricsChordsEditor();
}
function addLyricsEditorLine(){
  const text=prompt('Nuova lyric (usa "." per una sezione strumentale senza testo)','');if(text===null)return;
  const t=prompt('Tempo iniziale in secondi',String(Math.max(0,playCursorMs||0)/1000));if(t===null||!Number.isFinite(Number(t)))return;
  lyricsChordsEditorLyricsDraft=lyricsChordsEditorLyricsDraft||[];lyricsChordsEditorLyricsDraft.push(newOverrideEvent({time_ms:Math.max(0,Math.round(Number(t)*1000)),end_ms:null,text:text||'.',words:[],disabled:false,deleted:false}));lyricsChordsEditorLyricsDraft.sort((a,b)=>a.time_ms-b.time_ms);refreshLyricsChordsEditor();
}
function addChordEditorEvent(){
  const chord=prompt('Nuovo chord','C');if(!chord)return;const t=prompt('Tempo chord in secondi',String(Math.max(0,playCursorMs||0)/1000));if(t===null||!Number.isFinite(Number(t)))return;
  lyricsChordsEditorDraft=lyricsChordsEditorDraft||[];lyricsChordsEditorDraft.push(newOverrideEvent({time_ms:Math.max(0,Math.round(Number(t)*1000)),chord,manual_anchor:false,anchor_line_time_ms:null,anchor_word_index:null,anchor_word_text:'',excluded:false,deleted:false}));lyricsChordsEditorDraft.sort((a,b)=>a.time_ms-b.time_ms);refreshLyricsChordsEditor();
}
function addMarkerEditorEvent(lineIndex=null){
  const line=lineIndex==null?null:editorDraftLyrics()?.[Number(lineIndex)],def=line?Number(line.time_ms||0):Math.max(0,playCursorMs||0),color=current?.lyrics_pdf_style?.markers?.color||'#204A87';
  showUtilityModal('Nuovo marker',`<div class="lc-event-edit-dialog"><div class="workflow-note"><b>Formato tempo:</b> <code>m:ss.mmm</code> o <code>mm:ss.mmm</code>. Il tempo di inizio è obbligatorio; quello di fine è opzionale.</div><div class="lc-marker-edit-grid"><label>Inizio<input id="lcMarkerStart" value="${esc(lyricsChordsEditorPosition(def))}" inputmode="decimal"></label><label>Fine (opzionale)<input id="lcMarkerEnd" value="" placeholder="es. 1:24.500" inputmode="decimal"></label><label>Testo<input id="lcMarkerLabel" value="Instrumental"></label><label>Colore<input id="lcMarkerColor" type="color" value="${esc(color)}"></label></div><div class="utility-actions"><button class="utility-btn primary" onclick="applyNewMarkerEditorEvent()">Aggiungi marker</button><button class="utility-btn secondary" onclick="restoreLyricsChordsEditorModal()">Annulla</button></div></div>`)
}
function applyNewMarkerEditorEvent(){
  const start=parseLyricsChordsEditorPosition($('#lcMarkerStart')?.value),endRaw=String($('#lcMarkerEnd')?.value||'').trim(),end=endRaw?parseLyricsChordsEditorPosition(endRaw):null,label=String($('#lcMarkerLabel')?.value||'').trim(),color=String($('#lcMarkerColor')?.value||'#204A87');
  if(!Number.isFinite(start))return toast('Tempo iniziale non valido');if(endRaw&&!Number.isFinite(end))return toast('Tempo finale non valido');if(end!=null&&end<start)return toast('Il tempo finale non può precedere quello iniziale');if(!label)return toast('Inserisci il testo del marker');
  lyricsChordsEditorMarkersDraft=lyricsChordsEditorMarkersDraft||[];lyricsChordsEditorMarkersDraft.push(newOverrideEvent({time_ms:start,end_ms:end,label,color:/^#[0-9a-fA-F]{6}$/.test(color)?color:'#204A87',disabled:false,deleted:false}));lyricsChordsEditorMarkersDraft.sort((a,b)=>a.time_ms-b.time_ms);restoreLyricsChordsEditorModal();
}
function addInstrumentalSection(){
  const t=prompt('Inizio sezione strumentale (secondi)',String(Math.max(0,playCursorMs||0)/1000));if(t===null||!Number.isFinite(Number(t)))return;const ms=Math.max(0,Math.round(Number(t)*1000));const label=prompt('Nome sezione','Instrumental')||'Instrumental';
  lyricsChordsEditorLyricsDraft=lyricsChordsEditorLyricsDraft||[];lyricsChordsEditorMarkersDraft=lyricsChordsEditorMarkersDraft||[];
  const color=prompt('Colore sezione (#RRGGBB)',current?.lyrics_pdf_style?.markers?.color||'#204A87')||'#204A87';
  lyricsChordsEditorLyricsDraft.push(newOverrideEvent({time_ms:ms,end_ms:null,text:'.',words:[],disabled:false,deleted:false}));lyricsChordsEditorMarkersDraft.push(newOverrideEvent({time_ms:ms,end_ms:null,label,color:/^#[0-9a-fA-F]{6}$/.test(color)?color:'#204A87',disabled:false,deleted:false}));lyricsChordsEditorLyricsDraft.sort((a,b)=>a.time_ms-b.time_ms);lyricsChordsEditorMarkersDraft.sort((a,b)=>a.time_ms-b.time_ms);refreshLyricsChordsEditor();
}
function splitLyricsEditorLine(lineIndex,splitIndex){
  const lyrics=editorDraftLyrics(),li=Number(lineIndex),line=lyrics?.[li];if(!line)return;const words=editorLineWords(line,li),cut=Number(splitIndex);if(cut<=0||cut>=words.length)return toast('Scegli un punto interno alla riga');ensureEventSnapshot(line);
  const left=words.slice(0,cut).map(editorWordPayload),right=words.slice(cut).map(editorWordPayload),oldTime=Number(line.time_ms||0),nextTime=Number(lyrics[li+1]?.time_ms||Infinity);let newTime=Math.max(oldTime+1,Number(right[0]?.start_ms||oldTime+1));if(Number.isFinite(nextTime))newTime=Math.min(newTime,Math.max(oldTime+1,nextTime-1));const originalEnd=line.end_ms!=null?Number(line.end_ms):null;
  line.text=left.map(w=>w.text).join(' ');line.words=left;line.end_ms=Math.max(oldTime,newTime-1);line.manual_override=true;
  const second=newOverrideEvent({time_ms:newTime,end_ms:originalEnd!=null?Math.max(newTime,originalEnd):null,text:right.map(w=>w.text).join(' '),words:right,disabled:false,deleted:false});lyrics.splice(li+1,0,second);
  (lyricsChordsEditorDraft||[]).forEach(ch=>{if(!ch.manual_anchor||Number(ch.anchor_line_time_ms)!==oldTime)return;ensureEventSnapshot(ch);const wi=Number(ch.anchor_word_index||0);if(wi>=cut){ch.anchor_line_time_ms=newTime;ch.anchor_word_index=wi-cut;ch.anchor_word_text=String(right[Math.max(0,Math.min(wi-cut,right.length-1))]?.text||'')}else ch.anchor_word_text=String(left[Math.max(0,Math.min(wi,left.length-1))]?.text||'')});refreshLyricsChordsEditor();
}
function mergeLyricsEditorLine(lineIndex){
  const lyrics=editorDraftLyrics(),li=Number(lineIndex),a=lyrics?.[li];if(!a||a.deleted)return;let bi=li+1;while(bi<lyrics.length&&lyrics[bi]?.deleted)bi++;const b=lyrics?.[bi];if(!b)return toast('Nessuna linea lyrics successiva da accorpare');ensureEventSnapshot(a);ensureEventSnapshot(b);
  const aw=editorLineWords(a,li).map(editorWordPayload),bw=editorLineWords(b,bi).map(editorWordPayload),aTime=Number(a.time_ms||0),bTime=Number(b.time_ms||0),offset=aw.length;
  a.text=[a.text,b.text].filter(Boolean).join(' ').replace(/\s+/g,' ').trim();a.words=[...aw,...bw];a.end_ms=b.end_ms!=null?Number(b.end_ms):(a.end_ms!=null?Number(a.end_ms):null);a.manual_override=true;b.deleted=true;b.manual_override=true;
  (lyricsChordsEditorDraft||[]).forEach(ch=>{if(!ch.manual_anchor)return;if(Number(ch.anchor_line_time_ms)===bTime){ensureEventSnapshot(ch);const wi=Number(ch.anchor_word_index||0);ch.anchor_line_time_ms=aTime;ch.anchor_word_index=offset+wi;ch.anchor_word_text=String(bw[Math.max(0,Math.min(wi,bw.length-1))]?.text||ch.anchor_word_text||'')}});refreshLyricsChordsEditor();
}
function assignLyricsChord(index,lineIndex,wordIndex){const ch=lyricsChordsEditorDraft?.[Number(index)],line=editorDraftLyrics()?.[Number(lineIndex)],word=editorLineWords(line||{},Number(lineIndex))[Number(wordIndex)];if(!ch||!line||!word)return;ensureEventSnapshot(ch);ch.manual_anchor=true;ch.anchor_line_time_ms=Number(line.time_ms||0);ch.anchor_word_index=Number(wordIndex);ch.anchor_word_text=String(word.text||'');ch.excluded=false;ch.deleted=false;lyricsChordsEditorSelected=Number(index);refreshLyricsChordsEditor()}
function assignSelectedLyricsChord(lineIndex,wordIndex){if(lyricsChordsEditorSelected<0)return;assignLyricsChord(lyricsChordsEditorSelected,lineIndex,wordIndex)}
function selectLyricsChord(index){lyricsChordsEditorSelected=Number(index);refreshLyricsChordsEditor()}
function dragLyricsChord(event,index){lyricsChordsEditorSelected=Number(index);event.dataTransfer?.setData('text/plain',String(index));if(event.dataTransfer)event.dataTransfer.effectAllowed='move'}
function dropLyricsChord(event,lineIndex,wordIndex){event.preventDefault();const idx=Number(event.dataTransfer?.getData('text/plain')||lyricsChordsEditorSelected);if(Number.isInteger(idx))assignLyricsChord(idx,lineIndex,wordIndex)}
function toggleSelectedLyricsChordExcluded(){if(lyricsChordsEditorSelected<0)return;toggleDraftEvent('chords',lyricsChordsEditorSelected)}
function includeAllLyricsChords(){(lyricsChordsEditorDraft||[]).forEach(ch=>{if(ch.excluded){ensureEventSnapshot(ch);ch.excluded=false}});refreshLyricsChordsEditor()}
function openLyricsChordAnchorDialog(index){const ch=lyricsChordsEditorDraft?.[Number(index)],lyrics=editorDraftLyrics();if(!ch||!lyrics?.length)return toast('Nessuna lyric disponibile');const options=[];lyrics.forEach((line,li)=>editorLineWords(line,li).forEach((w,wi)=>options.push(`<option value="${li}:${wi}">${esc(lyricsChordsEditorPosition(line.time_ms))} · ${esc(w.text)}</option>`)));showUtilityModal('Associa chord a una parola',`<div class="form-grid"><p><b>${esc(ch.chord)}</b></p><label>Parola<select id="lcAnchorChoice">${options.join('')}</select></label><div class="form-actions"><button class="utility-btn primary" onclick="applyLyricsChordAnchorChoice(${Number(index)})">Associa</button><button class="utility-btn secondary" onclick="openLyricsChordsEditor()">Annulla</button></div></div>`)}
function applyLyricsChordAnchorChoice(index){const raw=$('#lcAnchorChoice')?.value||'';const [li,wi]=raw.split(':').map(Number);openLyricsChordsEditor();setTimeout(()=>assignLyricsChord(index,li,wi),0)}
function resetLyricsChordAnchors(){if(!lyricsChordsEditorDraft)return;lyricsChordsEditorDraft.forEach(ch=>{if(ch.manual_anchor){ensureEventSnapshot(ch);ch.manual_anchor=false;ch.anchor_line_time_ms=null;ch.anchor_word_index=null;ch.anchor_word_text=''}});lyricsChordsEditorSelected=-1;refreshLyricsChordsEditor()}

function lyricsChordsEditorHtml(){
  const lyrics=editorDraftLyrics()||[],chords=lyricsChordsEditorDraft||[],markers=lyricsChordsEditorMarkersDraft||[];
  const byLine=new Map();chords.forEach((ch,ci)=>{const a=editorChordAnchor(ch);const key=`${a.line}:${a.word}`;if(!byLine.has(key))byLine.set(key,[]);byLine.get(key).push({ch,ci})});
  const markerForLine=li=>{const line=lyrics[li],prev=li?Number(lyrics[li-1]?.time_ms||-1):-1;return markers.map((m,mi)=>({m,mi})).filter(x=>Number(x.m.time_ms)>prev&&Number(x.m.time_ms)<=Number(line?.time_ms||0))};
  const rows=lyrics.map((line,li)=>{const lineCtx=`oncontextmenu="return openLyricsChordsContextMenu(event,'lyrics',${li})"`;if(line.deleted)return `<div class="lc-line lc-deleted" ${lineCtx}><button type="button" class="lc-time lc-time-edit" onclick="event.stopPropagation();editLyricsLineTime(${li})" title="Modifica posizione">${esc(lyricsChordsEditorPosition(line.time_ms||0))}</button><div class="lc-words"><del>${esc(line.text||'')}</del></div></div>`;const words=editorLineWords(line,li);const markersHere=markerForLine(li).map(({m,mi})=>`<span class="lc-marker-chip ${m.disabled?'disabled':''} ${m.deleted?'deleted':''}" style="border-color:${esc(m.color||'#204A87')};color:${esc(m.color||'#204A87')}" ondblclick="event.stopPropagation();lcRememberScroll();editDraftEvent('markers',${mi})" oncontextmenu="return openLyricsChordsContextMenu(event,'markers',${mi})" title="Doppio click: modifica marker · Click destro: menu marker">⚑ ${esc(m.label)}${m.end_ms!=null?` · ${esc(lyricsChordsEditorPosition(m.time_ms))}–${esc(lyricsChordsEditorPosition(m.end_ms))}`:''}</span>`).join('');const wordHtml=words.map((w,wi)=>{const chips=(byLine.get(`${li}:${wi}`)||[]).map(({ch,ci})=>`<span class="lc-chord-wrap ${ch.excluded?'excluded':''} ${ch.deleted?'deleted':''}"><button type="button" draggable="${ch.deleted?'false':'true'}" class="lc-chord ${lyricsChordsEditorSelected===ci?'selected':''} ${ch.manual_anchor?'manual':'auto'} ${ch.excluded?'excluded':''} ${ch.deleted?'deleted':''}" onclick="event.stopPropagation();${ch.deleted?'':'selectLyricsChord('+ci+')'}" oncontextmenu="return openLyricsChordsContextMenu(event,'chords',${ci})" ondragstart="dragLyricsChord(event,${ci})" title="Click destro: menu chord">${esc(transposeChordLabel(ch.chord,current.pitch_semitones||0))}</button></span>`).join('');const split=wi<words.length-1?`<button type="button" class="lc-split-word" onclick="event.stopPropagation();splitLyricsEditorLine(${li},${wi+1})" title="Dividi qui">↵</button>`:'';return `<span class="lc-word ${line.disabled?'disabled':''}" ondragover="event.preventDefault()" ondrop="dropLyricsChord(event,${li},${wi})" onclick="assignSelectedLyricsChord(${li},${wi})"><span class="lc-chord-slot">${chips}</span><span class="lc-token">${esc(w.text)}</span>${split}</span>`}).join('');return `<div class="lc-line ${line.disabled?'lc-disabled':''}" ${lineCtx}><div class="lc-marker-row">${markersHere}</div><button type="button" class="lc-time lc-time-edit" onclick="event.stopPropagation();editLyricsLineTime(${li})" title="Modifica posizione">${esc(lyricsChordsEditorPosition(line.time_ms||0))}</button><div class="lc-words">${wordHtml||`<span class="lc-token">${esc(line.text||'.')}</span>`}</div></div>`}).join('');
  const selected=lyricsChordsEditorSelected>=0?chords[lyricsChordsEditorSelected]:null;
  return `<div class="lyrics-chords-editor"><div class="lc-editor-fixed-toolbar"><div class="workflow-note"><b>Editor Lyrics + Chords + Markers</b><br>Questa vista contiene solo l'editor combinato Lyrics + Chords + Markers. Click destro su una linea lyrics, su un singolo chord o su un marker per Modifica, Disabilita/Abilita, Accorpa, Elimina e Ripristina. Dal menu contestuale di una linea puoi anche aggiungere un marker. Clicca direttamente sul tempo della linea per modificarlo nel formato <code>m:ss.mmm</code>/<code>mm:ss.mmm</code>.</div><div class="lc-toolbar"><button class="utility-btn primary lc-save-btn" onclick="saveLyricsChordsEditor()">Salva</button><button class="utility-btn secondary" onclick="addLyricsEditorLine()">+ Lyrics</button><button class="utility-btn secondary" onclick="addChordEditorEvent()">+ Chord</button><button class="utility-btn secondary" onclick="addInstrumentalSection()">+ Instrumental</button><button class="utility-btn secondary" onclick="resetLyricsChordAnchors()">Reset anchor automatici</button><button class="utility-btn secondary" onclick="openLyricsPdfStylePanel()">Stile PDF</button></div></div><div class="lc-editor-scroll" oncontextmenu="if(event.target===this)return openLyricsChordsContextMenu(event,'editor',-1)"><div class="lc-grid">${rows||'<div class="workflow-note">Nessuna lyric: aggiungi una lyric o una sezione instrumental. I marker si inseriscono dal menu contestuale delle linee.</div>'}</div>${selected?`<div class="workflow-note">Chord selezionato: <b>${esc(selected.chord)}</b>. Clicca una parola per ancorarlo.</div>`:''}</div><div class="utility-actions lc-editor-footer"><button class="utility-btn primary lc-save-btn" onclick="saveLyricsChordsEditor()">Salva</button><button class="utility-btn secondary" onclick="closeLyricsChordsEditor()">Annulla</button></div></div>`;
}
function openLyricsChordsEditor(){if(!current)return;lyricsChordsEditorLyricsDraft=JSON.parse(JSON.stringify(current.lyrics||[]));lyricsChordsEditorDraft=JSON.parse(JSON.stringify(current.chords||[]));lyricsChordsEditorMarkersDraft=JSON.parse(JSON.stringify(current.markers||[]));lyricsChordsEditorOriginalDraft={lyrics:JSON.parse(JSON.stringify(current.lyrics||[])),chords:JSON.parse(JSON.stringify(current.chords||[])),markers:JSON.parse(JSON.stringify(current.markers||[]))};lyricsChordsEditorSelected=-1;restoreLyricsChordsEditorModal()}
function lyricsChordsEditorHasChanges(){if(!lyricsChordsEditorOriginalDraft)return false;const compact=v=>JSON.stringify(v||[]);return compact(lyricsChordsEditorLyricsDraft)!==compact(lyricsChordsEditorOriginalDraft.lyrics)||compact(lyricsChordsEditorDraft)!==compact(lyricsChordsEditorOriginalDraft.chords)||compact(lyricsChordsEditorMarkersDraft)!==compact(lyricsChordsEditorOriginalDraft.markers)}
function closeLyricsChordsEditor(){if(!lyricsChordsEditorHasChanges()){lyricsChordsEditorOriginalDraft=null;return closeUtilityModal()}showLyricsChordsClosePrompt()}
function showLyricsChordsClosePrompt(){const host=document.querySelector('.lyrics-chords-editor');if(!host){restoreLyricsChordsEditorModal();return setTimeout(showLyricsChordsClosePrompt,0)}host.querySelector('.lc-close-confirm')?.remove();const box=document.createElement('div');box.className='lc-close-confirm';box.innerHTML=`<div class="lc-close-confirm-card"><h3>Modifiche non salvate</h3><p>Salvare le modifiche a Lyrics + Chords + Markers prima di chiudere?</p><div class="utility-actions"><button class="utility-btn primary" onclick="saveLyricsChordsEditor()">Sì, salva</button><button class="utility-btn danger-action" onclick="discardLyricsChordsEditorChanges()">No, scarta</button><button class="utility-btn secondary" onclick="cancelLyricsChordsEditorClose()">Annulla</button></div></div>`;host.appendChild(box)}
function cancelLyricsChordsEditorClose(){document.querySelector('.lc-close-confirm')?.remove()}
function discardLyricsChordsEditorChanges(){lyricsChordsEditorOriginalDraft=null;closeUtilityModal()}

async function saveLyricsChordsEditor(){if(!current)return;current.lyrics=JSON.parse(JSON.stringify(lyricsChordsEditorLyricsDraft||[])).sort((a,b)=>Number(a.time_ms||0)-Number(b.time_ms||0));current.chords=JSON.parse(JSON.stringify(lyricsChordsEditorDraft||[])).sort((a,b)=>Number(a.time_ms||0)-Number(b.time_ms||0));current.markers=JSON.parse(JSON.stringify(lyricsChordsEditorMarkersDraft||[])).sort((a,b)=>Number(a.time_ms||0)-Number(b.time_ms||0));try{const saved=await api('/api/projects/'+current.id,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(current)});current=saved;projectDirty=false;lastHistoryState=projectSnapshot();lyricsChordsEditorOriginalDraft=null;await syncNativeProjectFile(saved.id);closeUtilityModal();render();toast('Override Lyrics/Chords/Markers salvati e applicati agli eventi MTA')}catch(e){toast(e.message)}}


// ---------------------------------------------------------------------------
// r183: granular Lyrics + Chords + Markers editing / resilient PDF preview
// ---------------------------------------------------------------------------
let lyricsChordsEditorScrollTop=0;
let lyricsChordsEditorUndoStack=[];
let lyricsChordsEditorRedoStack=[];
let lyricsChordsEditorHistoryState='';
let lyricsChordsEditorClipboard=null;
let lyricsChordsEditorFocus=null;
let lyricsChordsSaving=false;

function lcSnapshot(){return JSON.stringify({lyrics:lyricsChordsEditorLyricsDraft||[],chords:lyricsChordsEditorDraft||[],markers:lyricsChordsEditorMarkersDraft||[]})}
function lcApplySnapshot(raw){const x=JSON.parse(raw);lyricsChordsEditorLyricsDraft=x.lyrics||[];lyricsChordsEditorDraft=x.chords||[];lyricsChordsEditorMarkersDraft=x.markers||[];lyricsChordsEditorHistoryState=lcSnapshot()}
function lcCommitHistory(){const now=lcSnapshot();if(lyricsChordsEditorHistoryState&&now!==lyricsChordsEditorHistoryState){lyricsChordsEditorUndoStack.push(lyricsChordsEditorHistoryState);if(lyricsChordsEditorUndoStack.length>100)lyricsChordsEditorUndoStack.shift();lyricsChordsEditorRedoStack=[]}lyricsChordsEditorHistoryState=now}
function undoLyricsChordsEditor(){if(!lyricsChordsEditorUndoStack.length)return toast('Nessuna operazione da annullare');const now=lcSnapshot(),prev=lyricsChordsEditorUndoStack.pop();lyricsChordsEditorRedoStack.push(now);lcApplySnapshot(prev);refreshLyricsChordsEditor()}
function redoLyricsChordsEditor(){if(!lyricsChordsEditorRedoStack.length)return toast('Nessuna operazione da ripristinare');const now=lcSnapshot(),next=lyricsChordsEditorRedoStack.pop();lyricsChordsEditorUndoStack.push(now);lcApplySnapshot(next);refreshLyricsChordsEditor()}
function lcRememberScroll(){const el=document.querySelector('.lc-editor-scroll');if(el)lyricsChordsEditorScrollTop=el.scrollTop}
function lcRestoreScroll(){requestAnimationFrame(()=>{const el=document.querySelector('.lc-editor-scroll');if(el)el.scrollTop=lyricsChordsEditorScrollTop})}
function lcEditorArray(kind){return {lyrics:lyricsChordsEditorLyricsDraft,chords:lyricsChordsEditorDraft,markers:lyricsChordsEditorMarkersDraft}[kind]}
function copyLyricsChordsItem(){const f=lyricsChordsEditorFocus;if(!f)return toast('Seleziona una linea, un chord o un marker');const ev=lcEditorArray(f.kind)?.[f.index];if(!ev)return;lyricsChordsEditorClipboard={kind:f.kind,event:JSON.parse(JSON.stringify(ev))};toast('Elemento copiato')}
function cutLyricsChordsItem(){const f=lyricsChordsEditorFocus;if(!f)return toast('Seleziona una linea, un chord o un marker');copyLyricsChordsItem();const ev=lcEditorArray(f.kind)?.[f.index];if(!ev)return;ensureEventSnapshot(ev);ev.deleted=true;refreshLyricsChordsEditor()}
function pasteLyricsChordsItem(){if(!lyricsChordsEditorClipboard)return toast('Clipboard editor vuota');const {kind,event}=lyricsChordsEditorClipboard,arr=lcEditorArray(kind);if(!arr)return;const x=JSON.parse(JSON.stringify(event));x.time_ms=Math.max(0,Number(x.time_ms||0)+1);x.deleted=false;if(kind==='chords')x.excluded=false;else x.disabled=false;x.source_snapshot={__new__:true};x.manual_override=true;arr.push(x);arr.sort((a,b)=>Number(a.time_ms||0)-Number(b.time_ms||0));lyricsChordsEditorFocus={kind,index:arr.indexOf(x)};refreshLyricsChordsEditor()}

function editorWordUnits(word){const syll=(word?.syllables||[]).filter(s=>String(s.text||'').trim());if(syll.length)return syll.map((s,i)=>({text:String(s.text),syllable:i,start_ms:Number(s.start_ms??word.start_ms??0),end_ms:Number(s.end_ms??s.start_ms??word.end_ms??0)}));return [{text:String(word?.text||''),syllable:null,start_ms:Number(word?.start_ms||0),end_ms:Number(word?.end_ms||word?.start_ms||0)}]}
function editorChordAnchor(chord){
  const lyrics=editorDraftLyrics();
  if(chord?.manual_anchor&&chord.anchor_line_time_ms!=null){const li=lyrics.findIndex(l=>Number(l.time_ms)===Number(chord.anchor_line_time_ms));if(li>=0)return{line:li,word:Number(chord.anchor_word_index||0),syllable:chord.anchor_syllable_index==null?null:Number(chord.anchor_syllable_index),charOffset:chord.anchor_char_offset==null?null:Number(chord.anchor_char_offset),kind:String(chord.anchor_kind||'word'),order:Number(chord.anchor_order||0)}}
  const a=editorAutoAnchor(chord);return{...a,syllable:null,charOffset:null,kind:'word',order:0};
}
function assignLyricsChord(index,lineIndex,wordIndex,syllableIndex=null,kind='word',order=null,charOffset=null){const ch=lyricsChordsEditorDraft?.[Number(index)],line=editorDraftLyrics()?.[Number(lineIndex)];if(!ch||!line)return;const words=editorLineWords(line,Number(lineIndex)),word=words[Math.max(0,Math.min(Number(wordIndex)||0,Math.max(0,words.length-1)))];ensureEventSnapshot(ch);ch.manual_anchor=true;ch.anchor_line_time_ms=Number(line.time_ms||0);ch.anchor_kind=kind;ch.anchor_word_index=kind==='end'?Math.max(0,words.length-1):Math.max(0,Number(wordIndex)||0);ch.anchor_word_text=word?String(word.text||''):'';ch.anchor_syllable_index=kind==='word'&&syllableIndex!=null?Number(syllableIndex):null;ch.anchor_char_offset=kind==='word'&&syllableIndex==null&&charOffset!=null?Math.max(0,Number(charOffset)||0):null;ch.anchor_order=order==null?Number(ch.anchor_order||0):Math.max(0,Number(order)||0);ch.excluded=false;ch.deleted=false;lyricsChordsEditorSelected=Number(index);lyricsChordsEditorFocus={kind:'chords',index:Number(index)};refreshLyricsChordsEditor()}
function assignSelectedLyricsChord(lineIndex,wordIndex,syllableIndex=null,kind='word',charOffset=null){if(lyricsChordsEditorSelected<0)return;assignLyricsChord(lyricsChordsEditorSelected,lineIndex,wordIndex,syllableIndex,kind,null,charOffset)}
function lcWordCharOffset(event){const el=event.currentTarget?.querySelector?.('.lc-lyrics-inline')||event.currentTarget;if(!el)return null;const text=String(el.textContent||''),r=el.getBoundingClientRect?.();if(!text||!r||!r.width)return null;const x=Math.max(0,Math.min(r.width,Number(event.clientX||r.left)-r.left));return Math.max(0,Math.min(text.length,Math.round(text.length*x/r.width)))}
function assignSelectedLyricsChordPart(event,lineIndex,wordIndex,syllableIndex=null){if(lyricsChordsEditorSelected<0)return;event.preventDefault();event.stopPropagation();const charOffset=syllableIndex==null?lcWordCharOffset(event):null;assignLyricsChord(lyricsChordsEditorSelected,lineIndex,wordIndex,syllableIndex,'word',null,charOffset)}
function dropLyricsChord(event,lineIndex,wordIndex,syllableIndex=null,kind='word'){event.preventDefault();event.stopPropagation();const raw=event.dataTransfer?.getData('text/plain'),idx=raw!==''?Number(raw):lyricsChordsEditorSelected;if(Number.isFinite(idx)){const charOffset=kind==='word'&&syllableIndex==null?lcWordCharOffset(event):null;assignLyricsChord(idx,lineIndex,wordIndex,syllableIndex,kind,null,charOffset)}}
function dropLyricsChordOnChord(event,targetIndex){event.preventDefault();event.stopPropagation();const raw=event.dataTransfer?.getData('text/plain'),idx=raw!==''?Number(raw):lyricsChordsEditorSelected,target=lyricsChordsEditorDraft?.[Number(targetIndex)];if(!Number.isFinite(idx)||!target||idx===Number(targetIndex))return;const a=editorChordAnchor(target),targetOrder=Number(target.anchor_order||0);(lyricsChordsEditorDraft||[]).forEach((ch,ci)=>{if(ci===idx||ci===Number(targetIndex))return;const ca=editorChordAnchor(ch);if(lcAnchorKey(ca)===lcAnchorKey(a)&&Number(ch.anchor_order||0)>targetOrder){ensureEventSnapshot(ch);ch.anchor_order=Number(ch.anchor_order||0)+1}});assignLyricsChord(idx,a.line,a.word,a.syllable,a.kind,targetOrder+1)}
function lcAnchorKey(a){return `${a.line}:${a.kind}:${a.word}:${a.syllable==null?'x':a.syllable}`}
function openLyricsWordContextMenu(event,lineIndex,wordIndex){event.preventDefault();event.stopPropagation();closeLyricsChordsContextMenu();lyricsChordsEditorFocus={kind:'lyrics',index:Number(lineIndex)};const menu=document.createElement('div');menu.id='lyricsChordsContextMenu';menu.className='lc-context-menu';menu.innerHTML=`<div class="lc-context-title">Parola</div><button type="button" role="menuitem" onclick="closeLyricsChordsContextMenu();splitLyricsEditorLine(${Number(lineIndex)},${Number(wordIndex)+1})">Dividi qui</button>`;document.body.appendChild(menu);const x=Math.max(8,Math.min(event.clientX,window.innerWidth-menu.offsetWidth-8)),y=Math.max(8,Math.min(event.clientY,window.innerHeight-menu.offsetHeight-8));menu.style.left=`${x}px`;menu.style.top=`${y}px`;return false}


function lyricsInlineKey(event){if(event.key==='Enter'){event.preventDefault();event.currentTarget.blur();return false}if(event.key==='Escape'){event.preventDefault();event.currentTarget.textContent=event.currentTarget.dataset.originalText||'';event.currentTarget.blur();return false}return true}
function lcReanchorDeletedUnit(line,wordIndex,syllableIndex,remainingSyllables,remainingWords){
  const lineTime=Number(line.time_ms||0), wi=Number(wordIndex), si=syllableIndex==null?null:Number(syllableIndex);
  (lyricsChordsEditorDraft||[]).forEach(ch=>{
    if(!ch.manual_anchor||Number(ch.anchor_line_time_ms)!==lineTime||String(ch.anchor_kind||'word')!=='word')return;
    let cwi=Number(ch.anchor_word_index||0), csi=ch.anchor_syllable_index==null?null:Number(ch.anchor_syllable_index);
    ensureEventSnapshot(ch);
    if(si!=null&&cwi===wi){
      if(csi!=null&&csi>si)ch.anchor_syllable_index=csi-1;
      else if(csi===si){
        if(remainingSyllables>0)ch.anchor_syllable_index=si>0?si-1:0;
        else if(wi>0){ch.anchor_word_index=wi-1;ch.anchor_syllable_index=null;ch.anchor_word_text=String(remainingWords[wi-1]?.text||'')}
        else if(remainingWords.length>1){ch.anchor_word_index=1;ch.anchor_syllable_index=null;ch.anchor_word_text=String(remainingWords[1]?.text||'')}
        else {ch.anchor_kind='start';ch.anchor_word_index=0;ch.anchor_syllable_index=null;ch.anchor_word_text=''}
      }
      return;
    }
    if(si==null){
      if(cwi>wi)ch.anchor_word_index=cwi-1;
      else if(cwi===wi){
        if(wi>0){ch.anchor_word_index=wi-1;ch.anchor_syllable_index=null;ch.anchor_word_text=String(remainingWords[wi-1]?.text||'')}
        else if(remainingWords.length){ch.anchor_word_index=0;ch.anchor_syllable_index=null;ch.anchor_word_text=String(remainingWords[0]?.text||'')}
        else {ch.anchor_kind='start';ch.anchor_word_index=0;ch.anchor_syllable_index=null;ch.anchor_word_text=''}
      }
    }
  })
}
function commitLyricsInlineUnit(lineIndex,wordIndex,syllableIndex,value){
  const line=lyricsChordsEditorLyricsDraft?.[Number(lineIndex)];if(!line)return;
  let words=(line.words||[]).filter(w=>String(w.text||'').trim()).map(w=>JSON.parse(JSON.stringify(w)));
  if(!words.length)words=editorLineWords(line,Number(lineIndex)).map(w=>JSON.parse(JSON.stringify(w)));
  const wi=Number(wordIndex),word=words[wi];if(!word)return;const text=String(value??'').replace(/\s+/g,' ').trim();
  const original=syllableIndex==null?String(word.text||''):String(word.syllables?.[Number(syllableIndex)]?.text||'');if(text===original)return;
  ensureEventSnapshot(line);
  if(syllableIndex!=null&&Array.isArray(word.syllables)&&word.syllables.length){
    const si=Number(syllableIndex);if(text){word.syllables[si].text=text}else{word.syllables.splice(si,1);lcReanchorDeletedUnit(line,wi,si,word.syllables.length,words)}
    word.text=word.syllables.length?word.syllables.map(x=>String(x.text||'')).join(''):String(word.text||'');
    if(!word.syllables.length&&!text){words.splice(wi,1);lcReanchorDeletedUnit(line,wi,null,0,words)}
  }else if(text){word.text=text;word.syllables=[]}else{words.splice(wi,1);lcReanchorDeletedUnit(line,wi,null,0,words)}
  line.words=words;line.text=words.map(w=>String(w.text||'').trim()).filter(Boolean).join(' ');if(!line.text)line.text='.';
  lyricsChordsEditorFocus={kind:'lyrics',index:Number(lineIndex)};refreshLyricsChordsEditor();
}
function openLyricsChordsContextMenu(event,kind,index){event?.preventDefault?.();event?.stopPropagation?.();lcRememberScroll();closeLyricsChordsContextMenu();const ev=kind==='editor'?{}:lyricsChordsEditorEvent(kind,index);if(!ev)return false;if(kind!=='editor')lyricsChordsEditorFocus={kind,index:Number(index)};const disabled=kind==='chords'?!!ev.excluded:!!ev.disabled,labels={editor:'editor',lyrics:'linea lyrics',chords:'chord',markers:'marker'},menu=document.createElement('div');menu.id='lyricsChordsContextMenu';menu.className='lc-context-menu';const items=kind==='editor'?[['add-marker','+ Marker'],['paste','Incolla']]:[['edit','Modifica'],['copy','Copia'],['cut','Taglia'],['paste','Incolla'],['toggle',disabled?'Abilita':'Disabilita'],['merge','Accorpa con il successivo'],['delete','Elimina'],['restore','Ripristina']];if(kind==='lyrics')items.splice(6,0,['add-marker','+ Marker']);menu.innerHTML=`<div class="lc-context-title">${labels[kind]||'Evento'}</div>${items.map(([a,l])=>`<button type="button" role="menuitem" class="${a==='delete'?'danger-action':''}" data-lc-action="${a}">${l}</button>`).join('')}`;document.body.appendChild(menu);menu.querySelectorAll('[data-lc-action]').forEach(btn=>btn.addEventListener('click',()=>{const a=btn.dataset.lcAction;closeLyricsChordsContextMenu();if(a==='copy')return copyLyricsChordsItem();if(a==='cut')return cutLyricsChordsItem();if(a==='paste')return pasteLyricsChordsItem();lyricsChordsContextAction(a,kind,Number(index))}));const x=Math.max(8,Math.min(Number(event?.clientX||0),window.innerWidth-menu.offsetWidth-8)),y=Math.max(8,Math.min(Number(event?.clientY||0),window.innerHeight-menu.offsetHeight-8));menu.style.left=`${x}px`;menu.style.top=`${y}px`;return false}

function lyricsChordsEditorHtml(){
  const lyrics=editorDraftLyrics(),chords=lyricsChordsEditorDraft||[],byAnchor=new Map();
  chords.forEach((ch,ci)=>{const a=editorChordAnchor(ch),key=lcAnchorKey(a);if(!byAnchor.has(key))byAnchor.set(key,[]);byAnchor.get(key).push({ch,ci,a})});
  for(const list of byAnchor.values())list.sort((x,y)=>Number(x.ch.anchor_order||0)-Number(y.ch.anchor_order||0)||Number(x.ch.time_ms||0)-Number(y.ch.time_ms||0));
  const chip=({ch,ci})=>`<span class="lc-chord-wrap ${ch.excluded?'excluded':''} ${ch.deleted?'deleted':''}"><button type="button" draggable="${ch.deleted?'false':'true'}" class="lc-chord ${lyricsChordsEditorSelected===ci?'selected':''} ${ch.manual_anchor?'manual':'auto'}" onclick="event.stopPropagation();selectLyricsChord(${ci})" oncontextmenu="return openLyricsChordsContextMenu(event,'chords',${ci})" ondragstart="dragLyricsChord(event,${ci})" ondragover="event.preventDefault()" ondrop="dropLyricsChordOnChord(event,${ci})" ondblclick="event.stopPropagation();lcRememberScroll();editDraftEvent('chords',${ci})" title="Doppio click: modifica chord · Click destro: menu chord · trascina qui per sequenza">${esc(transposeChordLabel(ch.chord,current.pitch_semitones||0))}</button></span>`;
  const markersFor=(li)=>{const start=Number(lyrics[li]?.time_ms||0),end=Number(lyrics[li+1]?.time_ms||Infinity);return (lyricsChordsEditorMarkersDraft||[]).map((m,mi)=>({m,mi})).filter(({m})=>Number(m.time_ms||0)>=start&&Number(m.time_ms||0)<end)};
  const rows=lyrics.map((line,li)=>{const words=editorLineWords(line,li),lineCtx=`oncontextmenu="return openLyricsChordsContextMenu(event,'lyrics',${li})"`;const startCh=(byAnchor.get(`${li}:start:0:x`)||[]).map(chip).join(''),endKey=`${li}:end:${Math.max(0,words.length-1)}:x`,endCh=(byAnchor.get(endKey)||[]).map(chip).join('');const markers=markersFor(li).map(({m,mi})=>`<span class="lc-marker-chip ${m.disabled?'disabled':''} ${m.deleted?'deleted':''}" ondblclick="event.stopPropagation();lcRememberScroll();editDraftEvent('markers',${mi})" oncontextmenu="return openLyricsChordsContextMenu(event,'markers',${mi})" title="Doppio click: modifica marker · Click destro: menu marker">⚑ ${esc(m.label)}</span>`).join('');const wordHtml=words.map((w,wi)=>{const units=editorWordUnits(w),wordLevel=(byAnchor.get(`${li}:word:${wi}:x`)||[]).map(chip).join(''),unitHtml=units.map((u,si)=>{const syll=u.syllable==null?null:si,key=`${li}:word:${wi}:${syll==null?'x':syll}`,syllableChips=(byAnchor.get(key)||[]).map(chip).join(''),chips=(si===0?wordLevel:'')+syllableChips;return `<span class="lc-syllable-anchor" ondragover="event.preventDefault()" ondrop="dropLyricsChord(event,${li},${wi},${syll==null?'null':syll},'word')" onclick="assignSelectedLyricsChordPart(event,${li},${wi},${syll==null?'null':syll})"><span class="lc-chord-slot">${chips}</span><span class="lc-syllable lc-lyrics-inline" contenteditable="true" spellcheck="false" data-original-text="${esc(u.text)}" onclick="if(lyricsChordsEditorSelected>=0){assignSelectedLyricsChordPart(event,${li},${wi},${syll==null?'null':syll})}else event.stopPropagation()" ondblclick="event.stopPropagation();lcRememberScroll();editDraftEvent('lyrics',${li})" onkeydown="return lyricsInlineKey(event)" onblur="commitLyricsInlineUnit(${li},${wi},${syll==null?'null':syll},this.textContent)">${esc(u.text)}</span></span>`}).join('');return `<span class="lc-word" ondblclick="event.stopPropagation();lcRememberScroll();editDraftEvent('lyrics',${li})" oncontextmenu="return openLyricsWordContextMenu(event,${li},${wi})">${unitHtml}</span>`}).join('');return `<div class="lc-line ${line.disabled?'lc-disabled':''} ${line.deleted?'lc-deleted':''}" ${lineCtx}><div class="lc-marker-row">${markers}</div><button type="button" class="lc-time lc-time-edit" onclick="event.stopPropagation();lcRememberScroll();editLyricsLineTime(${li})">${esc(lyricsChordsEditorPosition(line.time_ms||0))}</button><div class="lc-content"><div class="lc-edge-anchor lc-edge-start" ondragover="event.preventDefault()" ondrop="dropLyricsChord(event,${li},0,null,'start')" onclick="assignSelectedLyricsChord(${li},0,null,'start')"><span class="lc-chord-slot">${startCh}</span><span>◂</span></div><div class="lc-words">${wordHtml||`<span class="lc-token">${esc(line.text||'.')}</span>`}</div><div class="lc-edge-anchor lc-edge-end" ondragover="event.preventDefault()" ondrop="dropLyricsChord(event,${li},${Math.max(0,words.length-1)},null,'end')" onclick="assignSelectedLyricsChord(${li},${Math.max(0,words.length-1)},null,'end')"><span class="lc-chord-slot">${endCh}</span><span>▸</span></div></div></div>`}).join('');
  const selected=lyricsChordsEditorSelected>=0?chords[lyricsChordsEditorSelected]:null;
  return `<div class="lyrics-chords-editor"><div class="lc-editor-fixed-toolbar"><div class="workflow-note"><b>Editor Lyrics + Chords + Markers</b> · questa vista contiene solo l'editor combinato Lyrics + Chords + Markers. Formato tempo: <code>m:ss.mmm</code>/<code>mm:ss.mmm</code>. Gli anchor ◂/▸ rappresentano inizio/fine riga. Trascina/clicca un chord su una sillaba o su una posizione interna della parola, oppure su un anchor o un altro chord. Click destro su una parola: <b>Dividi qui</b>.</div><div class="lc-toolbar"><button class="utility-btn" onclick="undoLyricsChordsEditor()" ${lyricsChordsEditorUndoStack.length?'':'disabled'}>Undo</button><button class="utility-btn" onclick="redoLyricsChordsEditor()" ${lyricsChordsEditorRedoStack.length?'':'disabled'}>Redo</button><button class="utility-btn" onclick="cutLyricsChordsItem()">Taglia</button><button class="utility-btn" onclick="copyLyricsChordsItem()">Copia</button><button class="utility-btn" onclick="pasteLyricsChordsItem()">Incolla</button><button class="utility-btn primary lc-save-btn" onclick="saveLyricsChordsEditor()">Salva</button><button class="utility-btn secondary" onclick="addLyricsEditorLine()">+ Lyrics</button><button class="utility-btn secondary" onclick="addChordEditorEvent()">+ Chord</button><button class="utility-btn secondary" onclick="addInstrumentalSection()">+ Instrumental</button><button class="utility-btn secondary" onclick="resetLyricsChordAnchors()">Reset anchor</button><button class="utility-btn secondary" onclick="openLyricsPdfStylePanel()">Stile PDF</button></div></div><div class="lc-editor-scroll" oncontextmenu="if(event.target===this)return openLyricsChordsContextMenu(event,'editor',-1)"><div class="lc-grid">${rows||'<div class="workflow-note">Nessuna lyric.</div>'}</div>${selected?`<div class="workflow-note">Chord selezionato: <b>${esc(selected.chord)}</b></div>`:''}</div><div class="utility-actions lc-editor-footer"><button class="utility-btn primary" onclick="saveLyricsChordsEditor()">Salva</button><button class="utility-btn secondary" onclick="closeLyricsChordsEditor()">Chiudi</button></div></div>`
}
function refreshLyricsChordsEditor(){lcRememberScroll();lcCommitHistory();const body=document.querySelector('.utility-modal .lyrics-chords-editor');if(!body)return restoreLyricsChordsEditorModal();body.outerHTML=lyricsChordsEditorHtml();lcRestoreScroll()}
function restoreLyricsChordsEditorModal(){lcCommitHistory();showUtilityModal('Editor Lyrics + Chords + Markers',lyricsChordsEditorHtml());const modal=document.querySelector('.utility-modal');modal?.classList.remove('meta-expanded-modal');modal?.classList.add('lyrics-chords-editor-modal');lcRestoreScroll()}
function openLyricsChordsEditor(){if(!current)return;lyricsChordsEditorLyricsDraft=JSON.parse(JSON.stringify(current.lyrics||[]));lyricsChordsEditorDraft=JSON.parse(JSON.stringify(current.chords||[]));lyricsChordsEditorMarkersDraft=JSON.parse(JSON.stringify(current.markers||[]));lyricsChordsEditorOriginalDraft={lyrics:JSON.parse(JSON.stringify(current.lyrics||[])),chords:JSON.parse(JSON.stringify(current.chords||[])),markers:JSON.parse(JSON.stringify(current.markers||[]))};lyricsChordsEditorSelected=-1;lyricsChordsEditorFocus=null;lyricsChordsEditorScrollTop=0;lyricsChordsEditorUndoStack=[];lyricsChordsEditorRedoStack=[];lyricsChordsEditorHistoryState=lcSnapshot();restoreLyricsChordsEditorModal()}
function selectLyricsChord(index){const next=Number(index);if(lyricsChordsEditorSelected===next){lyricsChordsEditorSelected=-1;if(lyricsChordsEditorFocus?.kind==='chords'&&Number(lyricsChordsEditorFocus.index)===next)lyricsChordsEditorFocus=null}else{lyricsChordsEditorSelected=next;lyricsChordsEditorFocus={kind:'chords',index:next}}refreshLyricsChordsEditor()}
function resetLyricsChordAnchors(){(lyricsChordsEditorDraft||[]).forEach(ch=>{if(ch.manual_anchor){ensureEventSnapshot(ch);ch.manual_anchor=false;ch.anchor_line_time_ms=null;ch.anchor_word_index=null;ch.anchor_word_text='';ch.anchor_kind='word';ch.anchor_syllable_index=null;ch.anchor_char_offset=null;ch.anchor_order=0}});lyricsChordsEditorSelected=-1;refreshLyricsChordsEditor()}

function closeLyricsChordsEditor(){if(lyricsChordsSaving)return toast('Salvataggio in corso… attendere');if(!lyricsChordsEditorHasChanges()){lyricsChordsEditorOriginalDraft=null;return closeUtilityModal()}showLyricsChordsClosePrompt()}
function showLyricsChordsSaving(){const host=document.querySelector('.lyrics-chords-editor')||document.querySelector('.utility-card');if(!host)return;host.querySelector('.lc-saving-overlay')?.remove();const x=document.createElement('div');x.className='lc-saving-overlay';x.innerHTML='<div class="lc-saving-card"><div class="lc-saving-spinner"></div><b>Salvataggio in corso…</b><p>Attendere: Lyrics, Chords e Markers vengono persistiti nel progetto.</p></div>';host.appendChild(x)}
async function saveLyricsChordsEditor(){if(!current||lyricsChordsSaving)return;lyricsChordsSaving=true;lcRememberScroll();showLyricsChordsSaving();current.lyrics=JSON.parse(JSON.stringify(lyricsChordsEditorLyricsDraft||[])).sort((a,b)=>Number(a.time_ms||0)-Number(b.time_ms||0));current.chords=JSON.parse(JSON.stringify(lyricsChordsEditorDraft||[])).sort((a,b)=>Number(a.time_ms||0)-Number(b.time_ms||0));current.markers=JSON.parse(JSON.stringify(lyricsChordsEditorMarkersDraft||[])).sort((a,b)=>Number(a.time_ms||0)-Number(b.time_ms||0));try{const saved=await api('/api/projects/'+current.id,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(current)});await syncNativeProjectFile(saved.id);current=saved;projectDirty=false;lastHistoryState=projectSnapshot();lyricsChordsEditorOriginalDraft=null;closeUtilityModal();render();toast('Lyrics/Chords/Markers salvati nel progetto')}catch(e){document.querySelector('.lc-saving-overlay')?.remove();toast('Salvataggio non riuscito: '+e.message)}finally{lyricsChordsSaving=false}}

function defaultLyricsPdfStyle(){return {title:{style:'bold',size:18,color:'#111111'},subtitle:{style:'normal',size:11,color:'#333333'},bpm:{style:'normal',size:11,color:'#333333'},lyrics:{style:'normal',size:11,color:'#111111'},chords:{style:'bold',size:9,color:'#7B1FA2'},markers:{style:'bold',size:12,color:'#204A87'},line_spacing:8}}
function normalizeLyricsPdfStyle(){current.lyrics_pdf_style=current.lyrics_pdf_style||defaultLyricsPdfStyle();const d=defaultLyricsPdfStyle();for(const k of ['title','subtitle','bpm','lyrics','chords','markers'])current.lyrics_pdf_style[k]={...d[k],...(current.lyrics_pdf_style[k]||{})};current.lyrics_pdf_style.line_spacing=Math.max(0,Math.min(48,Number(current.lyrics_pdf_style.line_spacing??d.line_spacing)||0));return current.lyrics_pdf_style}
function pdfStyleRow(key,label){const s=normalizeLyricsPdfStyle()[key];return `<div class="pdf-style-row"><b>${label}</b><label>Tipo<select data-pdf-style="${key}" data-field="style"><option value="normal" ${s.style==='normal'?'selected':''}>Normal</option><option value="bold" ${s.style==='bold'?'selected':''}>Bold</option><option value="italic" ${s.style==='italic'?'selected':''}>Italic</option></select></label><label>Size<input type="number" min="6" max="48" step="0.5" value="${Number(s.size)}" data-pdf-style="${key}" data-field="size"></label><label>Colore<input type="color" value="${esc(s.color)}" data-pdf-style="${key}" data-field="color"></label></div>`}
function openLyricsPdfStylePanel(){if(!current)return;const style=normalizeLyricsPdfStyle();showUtilityModal('Stile PDF Lyrics + Chords',`<div class="pdf-style-panel"><div class="workflow-note">Le impostazioni vengono salvate nel progetto e sono condivise da anteprima e PDF finale.</div>${pdfStyleRow('title','Titolo')}${pdfStyleRow('subtitle','Sottotitolo / artista / tonalità')}${pdfStyleRow('bpm','BPM')}${pdfStyleRow('lyrics','Lyrics')}${pdfStyleRow('chords','Chords')}${pdfStyleRow('markers','Markers / sezioni')}<div class="pdf-style-row pdf-line-spacing"><b>Interlinea lyrics</b><label>Distanza tra una riga di lyrics e gli accordi/lyrics della riga successiva<input id="lyricsPdfLineSpacing" type="number" min="0" max="48" step="1" value="${Number(style.line_spacing)}"></label><span class="hint">0 = compatta · 8 = default · valori maggiori aumentano lo spazio verticale.</span></div><div class="utility-actions"><button class="utility-btn primary" onclick="saveLyricsPdfStylePanel()">Salva stile</button><button class="utility-btn secondary" onclick="closeUtilityModal()">Annulla</button></div></div>`)}
async function saveLyricsPdfStylePanel(){if(!current)return;const style=normalizeLyricsPdfStyle();$$('[data-pdf-style]').forEach(el=>{const k=el.dataset.pdfStyle,f=el.dataset.field;if(!style[k])return;style[k][f]=f==='size'?Math.max(6,Math.min(48,Number(el.value)||11)):el.value});style.line_spacing=Math.max(0,Math.min(48,Number($('#lyricsPdfLineSpacing')?.value??style.line_spacing)||0));current.lyrics_pdf_style=style;markDirty(20);try{await save();closeUtilityModal();toast('Stile PDF salvato nel progetto')}catch(e){toast(e.message)}}
async function extractMarkersFromTrack(trackId){if(!current)return;const t=trackById(trackId)||(selectedTrack()||current.tracks?.[0]);if(!t)return toast('Seleziona una traccia da analizzare');if(!confirm(`Analizzare automaticamente "${t.name}" e creare i marker delle sezioni musicali rilevate? I marker esistenti vicini verranno preservati evitando duplicati.`))return;try{const state=await runTextAnalysisAndWait(current.id,t.id,'markers','');current=await api(`/api/projects/${current.id}`);render();toast(`Marker estratti: ${state?.result?.count||current.markers?.length||0}`)}catch(e){toast(e.message)}}
async function extractMarkersFromSelectedTrack(){const t=selectedTrack()||current?.tracks?.[0];return extractMarkersFromTrack(t?.id||'')}
async function runTextAnalysisAndWait(projectId,trackId,kind,choice=""){
  if(!trackId)return null;const labels={lyrics:'Lyrics',chords:'Chords',markers:'Markers / sezioni'},label=labels[kind]||kind;let query=[];if(choice&&kind!=='markers')query.push(`${kind==='lyrics'?'model':'engine'}=${encodeURIComponent(choice)}`);if(kind==='lyrics'&&$('#lyricsAdvancedAlignment')?.checked)query.push('advanced_alignment=true');const suffix=query.length?'?'+query.join('&'):'';const job=await api(`/api/projects/${projectId}/tracks/${trackId}/extract-${kind}-jobs${suffix}`,{method:'POST'});for(;;){const state=await api(`/api/media-jobs/${job.id}`);showMediaProgress(`Estrazione ${label}`,state.progress,state.message,mediaPartialText(state),state.cancel_supported&&['queued','running'].includes(state.status)?job.id:'');if(state.status==='completed')return state;if(state.status==='failed'||state.status==='cancelled')throw new Error(state.error||(state.status==='cancelled'?`Estrazione ${kind} annullata`:`Estrazione ${kind} non riuscita`));await new Promise(resolve=>setTimeout(resolve,500))}}

let metaPlaybackScrollIndex={lyrics:-1,chords:-1};
function metaEventInactive(kind,item){return !!item?.deleted||(kind==='chords'?!!item?.excluded:!!item?.disabled)}
function metaEventStateClass(kind,item){return `${kind==='lyrics'||kind==='chords'?' meta-editable':''}${item?.deleted?' meta-deleted':''}${kind==='chords'&&item?.excluded?' meta-disabled':''}${kind==='lyrics'&&item?.disabled?' meta-disabled':''}`}
function refreshMetaPanels(){const normal=document.querySelector('#metaPane .meta-tabs-content');if(normal)normal.outerHTML=metaPanelBodyHtml(false);const expanded=$('#expandedMetaBody');if(expanded)expanded.innerHTML=metaPanelBodyHtml(true);syncTimedMetaPanel(playCursorMs)}
async function saveMetaQuickEdit(){if(!current)return;try{const saved=await api('/api/projects/'+current.id,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(current)});current=saved;projectDirty=false;lastHistoryState=projectSnapshot();await syncNativeProjectFile(saved.id);refreshMetaPanels()}catch(e){toast(e.message||'Salvataggio non riuscito')}}
function metaRawValue(kind,item){return kind==='chords'?String(item?.chord||''):String(item?.text||'')}
function metaDisplayValue(kind,item){return kind==='chords'?transposeChordLabel(item?.chord||'',current?.pitch_semitones||0):String(item?.text||'')}
function beginMetaInlineEdit(event,kind,index,field='value'){
  event?.preventDefault?.();event?.stopPropagation?.();if(!['lyrics','chords'].includes(kind))return false;const item=current?.[kind]?.[Number(index)],host=event?.currentTarget;if(!item||!host)return false;
  const input=document.createElement('input');input.className='meta-inline-input';input.dataset.metaInline='1';input.value=field==='time'?lyricsChordsEditorPosition(item.time_ms||0):metaRawValue(kind,item);host.replaceChildren(input);input.focus();input.select();
  const cancel=()=>refreshMetaPanels();const commit=async()=>{if(input.dataset.committed==='1')return;input.dataset.committed='1';if(!input.isConnected)return;const oldTime=Number(item.time_ms||0),value=String(input.value??'').trim();if(field==='time'){const ms=parseLyricsChordsEditorPosition(value);if(!Number.isFinite(ms)){toast('Timestamp non valido: usa m:ss.mmm o mm:ss.mmm');return cancel()}ensureEventSnapshot(item);item.time_ms=ms;if(kind==='lyrics'&&oldTime!==ms)(current.chords||[]).forEach(ch=>{if(ch.manual_anchor&&Number(ch.anchor_line_time_ms)===oldTime){ensureEventSnapshot(ch);ch.anchor_line_time_ms=ms}})}else{if(!value){toast(kind==='chords'?'Il chord non può essere vuoto':'La lyric non può essere vuota');return cancel()}ensureEventSnapshot(item);if(kind==='chords')item.chord=value;else{if(String(item.text||'')!==value)item.words=[];item.text=value}}current[kind].sort((a,b)=>Number(a.time_ms||0)-Number(b.time_ms||0));await saveMetaQuickEdit()};
  input.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();input.blur()}else if(e.key==='Escape'){e.preventDefault();input.dataset.committed='1';cancel()}});input.addEventListener('blur',commit,{once:true});return false
}
function closeMetaContextMenu(){document.querySelector('#metaContextMenu')?.remove()}
function openMetaContextMenu(event,kind,index){if(!['lyrics','chords'].includes(kind))return false;event?.preventDefault?.();event?.stopPropagation?.();closeMetaContextMenu();const item=current?.[kind]?.[Number(index)];if(!item)return false;const inactive=metaEventInactive(kind,item),menu=document.createElement('div');menu.id='metaContextMenu';menu.className='lc-context-menu meta-context-menu';menu.innerHTML=`<div class="lc-context-title">${kind==='chords'?'Chord':'Lyrics'}</div><button type="button" data-meta-action="edit">Modifica</button><button type="button" data-meta-action="disable" ${inactive?'disabled':''}>Disabilita</button><button type="button" class="danger-action" data-meta-action="delete" ${item.deleted?'disabled':''}>Cancella</button><button type="button" data-meta-action="enable" ${inactive?'':'disabled'}>Riabilita</button>`;document.body.appendChild(menu);menu.querySelectorAll('[data-meta-action]').forEach(btn=>btn.addEventListener('click',()=>{if(btn.disabled)return;const action=btn.dataset.metaAction;closeMetaContextMenu();metaContextAction(action,kind,Number(index),event)}));const x=Math.max(8,Math.min(Number(event?.clientX||0),window.innerWidth-menu.offsetWidth-8)),y=Math.max(8,Math.min(Number(event?.clientY||0),window.innerHeight-menu.offsetHeight-8));menu.style.left=`${x}px`;menu.style.top=`${y}px`;return false}
async function metaContextAction(action,kind,index,event){const item=current?.[kind]?.[Number(index)];if(!item)return;if(action==='edit'){const row=document.querySelector(`.meta-line[data-meta-kind="${kind}"][data-event-index="${Number(index)}"] .meta-value`);if(row)return beginMetaInlineEdit({preventDefault(){},stopPropagation(){},currentTarget:row},kind,index,'value');return}ensureEventSnapshot(item);if(action==='disable'){item.deleted=false;if(kind==='chords')item.excluded=true;else item.disabled=true}else if(action==='delete'){item.deleted=true}else if(action==='enable'){item.deleted=false;if(kind==='chords')item.excluded=false;else item.disabled=false}await saveMetaQuickEdit()}
document.addEventListener('click',e=>{if(!e.target.closest?.('#metaContextMenu'))closeMetaContextMenu()});
function syncTimedMetaPanel(timeMs){if(!current)return;const running=playbackActuallyRunning()||(typeof waPlaybackActive!=='undefined'&&waPlaybackActive&&!waPlaybackPaused);for(const kind of ['lyrics','chords']){const enabled=kind==='lyrics'?!!current.show_lyrics_playback:!!current.show_chords_playback;const rows=[...document.querySelectorAll(`.meta-line[data-meta-kind="${kind}"]`)];rows.forEach(row=>row.classList.remove('active-playback'));if(!enabled||!running){metaPlaybackScrollIndex[kind]=-1;continue}const arr=current[kind]||[];let idx=-1;for(let i=0;i<arr.length;i++){if(!eventIsActive(arr[i],kind))continue;if(Number(arr[i].time_ms||0)<=Number(timeMs||0))idx=i;else break}if(idx<0)continue;const active=rows.filter(row=>Number(row.dataset.eventIndex)===idx);active.forEach(row=>row.classList.add('active-playback'));if(metaPlaybackScrollIndex[kind]!==idx){active.forEach(row=>row.scrollIntoView({block:'nearest',behavior:'auto'}));metaPlaybackScrollIndex[kind]=idx}}}
function metaPanelBodyHtml(expanded=false){
  const config={lyrics:['text','Lyrics'],chords:['chord','Chords'],markers:['label','Markers']},[key,label]=config[mixerMetaTab]||config.lyrics,source=current[mixerMetaTab]||[],rows=source.map((x,index)=>({x,index}));const editable=['lyrics','chords'].includes(mixerMetaTab);const displayValue=x=>mixerMetaTab==='chords'?transposeChordLabel(x[key],current.pitch_semitones||0):x[key];const resetButton=mixerMetaTab==='lyrics'?`<button class="tool danger" onclick="resetTimedData('lyrics')">Reset lyrics</button>`:mixerMetaTab==='chords'?`<button class="tool danger" onclick="resetTimedData('chords')">Reset chords</button>`:'';const hasLyrics=(current.lyrics||[]).some(x=>eventIsActive(x,'lyrics')),hasChords=(current.chords||[]).some(x=>eventIsActive(x,'chords'));const editor=`<button class="tool accent" onclick="openLyricsChordsEditor()">Editor Lyrics + Chords + Markers</button>`;const exports=mixerMetaTab==='lyrics'&&hasLyrics?`<button class="tool" onclick="downloadProjectLyrics(false)">TXT Lyrics</button>${hasChords?`<button class="tool" onclick="downloadProjectLyrics(true)">TXT Lyrics + Chords</button><button class="tool" onclick="downloadProjectChordPro()">ChordPro</button>`:''}<button class="tool" onclick="openLyricsPdfStylePanel()">Stile PDF</button><button class="tool" onclick="previewProjectLyricsPdf()">Anteprima PDF</button><button class="tool" onclick="downloadProjectLyricsPdf()">Salva PDF</button>`:'';const markerExtract=mixerMetaTab==='markers'?`<button class="tool" onclick="extractMarkersFromSelectedTrack()">Estrai markers</button>`:'';const lineHtml=rows.map(({x,index})=>`<div class="meta-line${metaEventStateClass(mixerMetaTab,x)}" data-meta-kind="${mixerMetaTab}" data-event-index="${index}" data-time-ms="${Number(x.time_ms||0)}" ${editable?`oncontextmenu="return openMetaContextMenu(event,'${mixerMetaTab}',${index})"`:''}><time ${editable?`ondblclick="return beginMetaInlineEdit(event,'${mixerMetaTab}',${index},'time')" title="Doppio click per modificare il timestamp"`:''}>${fmtTime(x.time_ms/1000)}</time><span class="meta-value" ${editable?`ondblclick="return beginMetaInlineEdit(event,'${mixerMetaTab}',${index},'value')" title="Doppio click per modificare"`:''}>${esc(displayValue(x))}</span></div>`).join('');return `<div class="meta-tabs-content ${expanded?'meta-expanded-content':''}"><div class="meta-list">${lineHtml||`<div class="hint">No synchronized ${label.toLowerCase()} yet.</div>`}</div><div class="meta-actions"><button class="tool" onclick="editTimed('${mixerMetaTab}')">Edit ${label.toLowerCase()}</button>${resetButton}${markerExtract}${editor}${exports}</div>${expanded?'':`<textarea id="lyrics" hidden>${esc(linesToText(current.lyrics,'text'))}</textarea><textarea id="chords" hidden>${esc(linesToText(current.chords,'chord'))}</textarea><textarea id="markers" hidden>${esc(linesToText(current.markers,'label'))}</textarea>`}</div>`;
}

/* r189 deterministic WebAudio transport: one AudioContext clock, one scheduled source per track. */
let waPlaybackActive=false,waPlaybackPaused=false,waRenderFilters=false,waStartCtxTime=0,waStartCursorMs=0,waMasterBus=null,waDecodedBuffers=new Map();
function waProjectCursorMs(){
  if(!waPlaybackActive||!audioCtx)return playCursorMs;
  if(waPlaybackPaused)return waStartCursorMs;
  return Math.max(0,waStartCursorMs+(audioCtx.currentTime-waStartCtxTime)*1000*tempoRatio());
}
function waMediaOffsetSeconds(cursorMs){return Math.max(0,Number(cursorMs||0)/1000/Math.max(.0001,tempoRatio()))}
function waTrackGain(track){return trackAudibleNow(track)?dbToGain(Number(track?.volume_db||0)):0}
function waDisconnectItem(item,stop=true){
  if(!item)return;
  try{if(stop)item.sourceNode?.stop()}catch(e){}
  for(const node of [item.sourceNode,item.gainNode,item.panner,item.splitter,...(item.analysers||[])])try{node?.disconnect()}catch(e){}
  item.sourceNode=null;
}
function waStopSources(){for(const item of trackPlaybacks)if(item.wa)waDisconnectItem(item,true)}
function waCreateTrackGraph(track,buffer){
  const gainNode=audioCtx.createGain(),panner=audioCtx.createStereoPanner();
  gainNode.gain.value=waTrackGain(track);panner.pan.value=clampPan(track?.pan||0);
  gainNode.connect(panner);panner.connect(waMasterBus);
  const analysers=[];let splitter=null;
  if(current?.realtime_meter_enabled){
    if(Number(track?.channels||buffer?.numberOfChannels||2)===1){const a=audioCtx.createAnalyser();a.fftSize=1024;panner.connect(a);analysers.push(a)}
    else{splitter=audioCtx.createChannelSplitter(2);const l=audioCtx.createAnalyser(),r=audioCtx.createAnalyser();l.fftSize=r.fftSize=1024;panner.connect(splitter);splitter.connect(l,0);splitter.connect(r,1);analysers.push(l,r)}
  }
  return {trackId:track.id,wa:true,buffer,gainNode,panner,analysers,splitter,channels:Number(track?.channels||buffer?.numberOfChannels||2),respectMuteSolo:true,meterData:{}};
}
async function waDecodeTrack(track,renderFilters,cacheBust=false){
  const info=playbackSourceForTrack(track,renderFilters),key=`${current.id}:${track.id}:${renderFilters?1:0}:${info.url}`;
  if(!cacheBust&&waDecodedBuffers.has(key))return waDecodedBuffers.get(key);
  const url=info.url+(info.url.includes('?')?'&':'?')+`wa=${cacheBust?Date.now():'1'}`;
  const resp=await fetch(url);if(!resp.ok)throw new Error(`Audio ${track.name}: ${resp.status}`);
  const ab=await resp.arrayBuffer();const buffer=await audioCtx.decodeAudioData(ab.slice(0));
  waDecodedBuffers.set(key,buffer);return buffer;
}
function waBuildMasterGraph(){
  waMasterBus=audioCtx.createGain();masterPlaybackGainNode=audioCtx.createGain();masterPlaybackGainNode.gain.value=dbToGain(Number(current?.master_volume_db||0));
  waMasterBus.connect(masterPlaybackGainNode);masterPlaybackGainNode.connect(audioCtx.destination);
  masterMeterAnalysers=null;
  if(current?.realtime_meter_enabled){const split=audioCtx.createChannelSplitter(2),l=audioCtx.createAnalyser(),r=audioCtx.createAnalyser();l.fftSize=r.fftSize=1024;masterPlaybackGainNode.connect(split);split.connect(l,0);split.connect(r,1);masterMeterAnalysers=[l,r];masterMeterAnalysers.meterData={};masterMeterAnalysers.splitter=split}
}
function waScheduleItem(item,startAt,cursorMs,fadeIn=false){
  const source=audioCtx.createBufferSource();source.buffer=item.buffer;source.connect(item.gainNode);item.sourceNode=source;
  const offset=Math.min(waMediaOffsetSeconds(cursorMs),Math.max(0,item.buffer.duration-.001));
  const target=waTrackGain(trackById(item.trackId));
  if(fadeIn){item.gainNode.gain.cancelScheduledValues(startAt);item.gainNode.gain.setValueAtTime(0,startAt);item.gainNode.gain.linearRampToValueAtTime(target,startAt+.012)}
  else item.gainNode.gain.setValueAtTime(target,startAt);
  source.start(startAt,offset);
}
function waScheduleAll(cursorMs){
  const startAt=audioCtx.currentTime+.035;waStartCursorMs=Number(cursorMs||0);waStartCtxTime=startAt;waPlaybackPaused=false;
  for(const item of trackPlaybacks)if(item.wa)waScheduleItem(item,startAt,cursorMs,false);
}
async function startWebAudioProjectPlayback(renderFilters=false,cursorMs=playCursorMs){
  audioCtx=audioCtx||new(window.AudioContext||window.webkitAudioContext)();await audioCtx.resume();
  waStopSources();for(const item of trackPlaybacks)if(item.wa)for(const n of [item.gainNode,item.panner,item.splitter,...(item.analysers||[])])try{n?.disconnect()}catch(e){}
  trackPlaybacks=[];try{waMasterBus?.disconnect()}catch(e){};try{masterPlaybackGainNode?.disconnect()}catch(e){};waBuildMasterGraph();
  playbackBuffering=true;showMediaProgress('Preparazione audio',18,'Decodifica tracce…');
  const tracks=current?.tracks||[];const buffers=await Promise.all(tracks.map(t=>waDecodeTrack(t,renderFilters,false)));
  trackPlaybacks=tracks.map((t,i)=>waCreateTrackGraph(t,buffers[i]));
  waPlaybackActive=true;waPlaybackPaused=false;waRenderFilters=!!renderFilters;renderedStemPlayback=!!renderFilters;renderedMasterPlayback=false;playAudio={waClock:true,paused:false,ended:false};
  waScheduleAll(cursorMs);playbackBuffering=false;$('#utilityBackdrop')?.classList.add('hidden');
  if(current?.realtime_meter_enabled)startVuMeterLoop();
  if($('#playMaster')){$('#playMaster').textContent='❚❚';$('#playMaster').title='Pausa'}
  if(playRaf)cancelAnimationFrame(playRaf);playRaf=requestAnimationFrame(movePlayhead);
  return playAudio;
}
function updatePlaybackGains(){
  if(waPlaybackActive){const now=audioCtx?.currentTime||0;for(const item of trackPlaybacks){if(!item.wa)continue;const t=trackById(item.trackId);item.gainNode?.gain.cancelScheduledValues(now);item.gainNode?.gain.setTargetAtTime(waTrackGain(t),now,.006)}return}
  const now=audioCtx?.currentTime||0;for(const item of trackPlaybacks){const track=trackById(item.trackId);if(!track||!item.gainNode)continue;item.gainNode.gain.cancelScheduledValues(now);item.gainNode.gain.setValueAtTime(playbackGainForTrack(track,item),now)}
}
async function refreshDynamicTrackPlayback(trackId){
  if(!waPlaybackActive||waPlaybackPaused){return}
  const track=trackById(trackId),idx=trackPlaybacks.findIndex(x=>x.trackId===trackId&&x.wa);if(!track||idx<0)return;
  try{collect();await persistCurrentProject(false);const buffer=await waDecodeTrack(track,true,true);if(!waPlaybackActive)return;const old=trackPlaybacks[idx],replacement=waCreateTrackGraph(track,buffer),cursor=waProjectCursorMs(),startAt=audioCtx.currentTime+.025;waScheduleItem(replacement,startAt,cursor,true);const now=startAt,targetOld=old.gainNode?.gain.value||0;if(old.gainNode){old.gainNode.gain.cancelScheduledValues(now);old.gainNode.gain.setValueAtTime(targetOld,now);old.gainNode.gain.linearRampToValueAtTime(0,now+.012)}trackPlaybacks.splice(idx,1,replacement);setTimeout(()=>waDisconnectItem(old,true),45)}catch(e){console.warn('Aggiornamento live FX traccia fallito',trackId,e)}
}
function playbackActuallyRunning(){if(waPlaybackActive)return !waPlaybackPaused;const masterRunning=!!(playAudio&&!playAudio.paused&&!playAudio.ended);return masterRunning||trackPlaybacks.some(item=>item.audio&&!item.audio.paused&&!item.audio.ended)}
function stopPlayback(){
  if(waPlaybackActive){playCursorMs=waProjectCursorMs();waStopSources();for(const item of trackPlaybacks)for(const n of [item.gainNode,item.panner,item.splitter,...(item.analysers||[])])try{n?.disconnect()}catch(e){};trackPlaybacks=[];try{waMasterBus?.disconnect()}catch(e){};try{masterPlaybackGainNode?.disconnect()}catch(e){};waMasterBus=null;masterPlaybackGainNode=null;masterMeterAnalysers=null;waPlaybackActive=false;waPlaybackPaused=false;playAudio=null;meterRunToken++;if(playRaf){cancelAnimationFrame(playRaf);playRaf=null}if(meterRaf){cancelAnimationFrame(meterRaf);meterRaf=null}resetVuMeters();if($('#playMaster')){$('#playMaster').textContent='▶';$('#playMaster').title='Play / Preview'};clearTimedPlaybackOverlay();return}
  ++playbackToken;playbackBuffering=false;playbackPaused=false;transportClockRunning=false;transportClockCursorMs=playCursorMs;meterRunToken++;if(playRaf){cancelAnimationFrame(playRaf);playRaf=null}if(meterRaf){cancelAnimationFrame(meterRaf);meterRaf=null}if(playAudio){playAudio.pause();playAudio.currentTime=0;playAudio=null}for(const item of trackPlaybacks){try{item.audio.pause();item.audio.currentTime=0;item.audio.removeAttribute('src');item.audio.load()}catch(e){}}trackPlaybacks=[];masterMeterAnalysers=null;masterPlaybackGainNode=null;renderedMasterPlayback=false;renderedStemPlayback=false;resetVuMeters();clearTimedPlaybackOverlay()
}
function pausePlayback(){if(waPlaybackActive){playCursorMs=waProjectCursorMs();waStartCursorMs=playCursorMs;waPlaybackPaused=true;waStopSources();if(playRaf){cancelAnimationFrame(playRaf);playRaf=null}if($('#playMaster')){$('#playMaster').textContent='▶';$('#playMaster').title='Riprendi'};return}if(!playAudio&&!trackPlaybacks.length)return;pauseTransportClock();if(playAudio)playAudio.pause();for(const item of trackPlaybacks)try{item.audio.pause()}catch(e){};playbackPaused=true}
async function resumePlayback(){if(waPlaybackActive){await audioCtx.resume();waScheduleAll(playCursorMs);if($('#playMaster')){$('#playMaster').textContent='❚❚';$('#playMaster').title='Pausa'};if(!playRaf)playRaf=requestAnimationFrame(movePlayhead);if(current?.realtime_meter_enabled&&!meterRaf)startVuMeterLoop();return}return previewMaster()}
function seekTransport(deltaMs){const target=Math.max(0,playCursorMs+deltaMs);setPlayCursor(target);if(waPlaybackActive){const wasRunning=!waPlaybackPaused;waStopSources();waStartCursorMs=target;playCursorMs=target;if(wasRunning)waScheduleAll(target);updateTimedPlaybackOverlay(playCursorMs);return}reanchorTransportClock(playCursorMs);alignDynamicTracks(true)}
function goTransportStart(){setPlayCursor(0);if(waPlaybackActive){const wasRunning=!waPlaybackPaused;waStopSources();waStartCursorMs=0;if(wasRunning)waScheduleAll(0);return}reanchorTransportClock(0);alignDynamicTracks(true)}
async function previewMaster(){if(!current||!current.tracks.length)return;try{collect();if(waPlaybackActive)stopPlayback();else if(playAudio||trackPlaybacks.length)stopPlayback();const render=!!current.render_preview_enabled;setRenderPlaybackPreparing(render);await startWebAudioProjectPlayback(render,playCursorMs);setRenderPlaybackPreparing(false);toast(render?'Playback WebAudio sincronizzato · FX renderizzati per traccia':'Playback WebAudio sincronizzato')}catch(e){setRenderPlaybackPreparing(false);stopPlayback();toast(e.message)}}
function movePlayhead(){if(waPlaybackActive){if(waPlaybackPaused)return;playCursorMs=waProjectCursorMs();const x=playCursorMs/1000*pxPerSec;if($('#playhead'))$('#playhead').style.left=x+'px';followPlayhead(x);if($('#transportTime'))$('#transportTime').textContent=fmtTime(playCursorMs/1000,true);updateTimedPlaybackOverlay(playCursorMs);playRaf=requestAnimationFrame(movePlayhead);return}const clock=dynamicClockAudio();if(!clock||clock.paused)return;playCursorMs=(renderedMasterPlayback?clock.currentTime:transportMediaSeconds())*1000*tempoRatio();playRaf=requestAnimationFrame(movePlayhead)}
function updateVuMeters(token=meterRunToken){
  if(token!==meterRunToken)return;if(!current?.realtime_meter_enabled||!playbackActuallyRunning()){resetVuMeters();meterRaf=null;return}
  if(waPlaybackActive){for(const item of trackPlaybacks){const a=item.analysers||[];if(item.channels===1){const m=analyserLevel(a[0],item,'m');setVu(`#vu-${item.trackId}-M`,m);latchPeak(`#peak-${item.trackId}`,m)}else{const l=analyserLevel(a[0],item,'l'),r=analyserLevel(a[1],item,'r');setVu(`#vu-${item.trackId}-L`,l);setVu(`#vu-${item.trackId}-R`,r);latchPeak(`#peak-${item.trackId}`,Math.max(l,r))}}if(masterMeterAnalysers?.length===2){const l=analyserLevel(masterMeterAnalysers[0],masterMeterAnalysers,'l'),r=analyserLevel(masterMeterAnalysers[1],masterMeterAnalysers,'r');setVu('#vu-master-L',l);setVu('#vu-master-R',r);latchPeak('#peak-master',Math.max(l,r))}meterRaf=requestAnimationFrame(()=>{if(token===meterRunToken)updateVuMeters(token)});return}
  meterRaf=requestAnimationFrame(()=>{if(token===meterRunToken)updateVuMeters(token)})
}

/* r189 editor-only automatic syllabification. The persisted lyric text is unchanged. */
function editorAutoSyllableParts(token){
  const raw=String(token||'');if(!raw.trim())return [raw];const letters=/[A-Za-zÀ-ÖØ-öø-ÿ]/;let first=0,last=raw.length-1;while(first<raw.length&&!letters.test(raw[first]))first++;while(last>=first&&!letters.test(raw[last]))last--;if(first>last)return[raw];const prefix=raw.slice(0,first),core=raw.slice(first,last+1),suffix=raw.slice(last+1),vowels='aeiouyàèéìòóùAEIOUYÀÈÉÌÒÓÙ';const parts=[];let start=0,seen=false;for(let i=0;i<core.length;i++){const ch=core[i];if(vowels.includes(ch)){seen=true;continue}if(seen&&i+1<core.length&&vowels.includes(core[i+1])){parts.push(core.slice(start,i+1));start=i+1;seen=false}}if(start<core.length)parts.push(core.slice(start));if(!parts.length)parts.push(core);parts[0]=prefix+parts[0];parts[parts.length-1]+=suffix;return parts.filter(Boolean)
}
function editorWordUnits(word){
  const existing=(word?.syllables||[]).filter(s=>String(s.text||'').trim());if(existing.length)return existing.map((s,i)=>({text:String(s.text),syllable:i,start_ms:Number(s.start_ms??word.start_ms??0),end_ms:Number(s.end_ms??s.start_ms??word.end_ms??0),auto:false}));
  const parts=editorAutoSyllableParts(String(word?.text||''));const start=Number(word?.start_ms||0),end=Math.max(start,Number(word?.end_ms||start)),span=Math.max(1,end-start);return parts.map((text,i)=>({text,syllable:i,start_ms:Math.round(start+span*i/parts.length),end_ms:Math.round(start+span*(i+1)/parts.length),auto:true}))
}

/* r189 stable RMS meters with attack/release smoothing; prevents flashing and inert meters. */
function analyserLevel(analyser,cacheOwner,key){
  if(!analyser)return 0;cacheOwner.meterData=cacheOwner.meterData||{};cacheOwner.meterSmooth=cacheOwner.meterSmooth||{};
  const data=cacheOwner.meterData[key]||(cacheOwner.meterData[key]=new Float32Array(analyser.fftSize));analyser.getFloatTimeDomainData(data);
  let sum=0,peak=0;for(const x of data){sum+=x*x;peak=Math.max(peak,Math.abs(x))}const rms=Math.sqrt(sum/Math.max(1,data.length));const db=20*Math.log10(Math.max(1e-6,rms));let pct=Math.max(0,Math.min(100,(db+60)/60*100));
  if(peak>.98)pct=Math.max(pct,99.5);const prev=Number(cacheOwner.meterSmooth[key]||0),coef=pct>prev?.58:.16,smoothed=prev+(pct-prev)*coef;cacheOwner.meterSmooth[key]=smoothed;return smoothed
}

/* Materialize editor-only automatic syllables when a syllable is edited inline. */
function commitLyricsInlineUnit(lineIndex,wordIndex,syllableIndex,value){
  const line=lyricsChordsEditorLyricsDraft?.[Number(lineIndex)];if(!line)return;let words=(line.words||[]).filter(w=>String(w.text||'').trim()).map(w=>JSON.parse(JSON.stringify(w)));if(!words.length)words=editorLineWords(line,Number(lineIndex)).map(w=>JSON.parse(JSON.stringify(w)));const wi=Number(wordIndex),word=words[wi];if(!word)return;
  if(syllableIndex!=null&&(!Array.isArray(word.syllables)||!word.syllables.length)){word.syllables=editorWordUnits(word).map(x=>({start_ms:x.start_ms,end_ms:x.end_ms,text:x.text}))}
  const text=String(value??'').replace(/\s+/g,' ').trim(),si=syllableIndex==null?null:Number(syllableIndex),original=si==null?String(word.text||''):String(word.syllables?.[si]?.text||'');if(text===original)return;ensureEventSnapshot(line);
  if(si!=null&&word.syllables?.length){if(text)word.syllables[si].text=text;else{word.syllables.splice(si,1);lcReanchorDeletedUnit(line,wi,si,word.syllables.length,words)}word.text=word.syllables.map(x=>String(x.text||'')).join('');if(!word.syllables.length&&!text){words.splice(wi,1);lcReanchorDeletedUnit(line,wi,null,0,words)}}else if(text){word.text=text;word.syllables=[]}else{words.splice(wi,1);lcReanchorDeletedUnit(line,wi,null,0,words)}
  line.words=words;line.text=words.map(w=>String(w.text||'').trim()).filter(Boolean).join(' ');if(!line.text)line.text='.';lyricsChordsEditorFocus={kind:'lyrics',index:Number(lineIndex)};refreshLyricsChordsEditor()
}
