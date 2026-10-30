/* Explicit maintenance cutover, original-request retry, private audit/recovery. */
(()=>{
  'use strict';
  const host=document.getElementById('serviceRegimePanel');if(!host)return;
  const it=document.documentElement.lang.startsWith('it');
  const words=it?{
    title:'Cambio di regime in manutenzione',note:'Disponibile per l’autorità locale prima dell’avvio dei checkout commerciali. Storico economico presente, schemi sconosciuti e lavori irrisolti mantengono il blocco. Le sole credenziali configurate non bloccano l’attivazione. Nessun saldo o periodo viene azzerato.',
    target:'Regime di destinazione',nc:'Non commerciale',co:'Commerciale',preview:'Verifica prima del cambio',execute:'Conferma cambio di regime',refresh:'Aggiorna registro',more:'Altre transizioni',retry:'Verifica o riprendi la stessa operazione',recover:'Completa il recupero',
    loading:'Verifica in corso…',working:'Passaggio in corso: verifica, blocco, aggiornamento e controllo dei saldi.',ready:'Verifica locale superata. Controlla destinazione e revisione prima di confermare.',done:'Passaggio completato; saldi, periodi e storico conservati.',
    blocked:'Passaggio non disponibile: completare i prerequisiti o la riconciliazione. Nessuna nuova transizione avviata.',uncertain:'Esito da verificare nel registro. Riprendi soltanto questa stessa operazione; non viene creato un secondo passaggio.',
    empty:'Nessuna transizione registrata.',audit:'Registro dei passaggi',committed:'Aggiornamento registrato; servizio bloccato in attesa del recupero',finalized:'Completato',confirm:'Confermare il passaggio mostrato, conservando saldi e periodi? Il servizio sarà brevemente sospeso.',confirmRecovery:'Completare in avanti questo passaggio già registrato? Saldi e periodi devono ancora coincidere con gli originali.',failed:'Registro non disponibile. Riprova senza avviare un altro passaggio.'
  }:{
    title:'Maintenance regime change',note:'Available on the local authority before commercial checkout starts. Existing monetary history, unknown schemas and unresolved work keep the barrier held. Prepared credentials alone do not block activation. No balance or period is reset.',
    target:'Destination regime',nc:'Non-commercial',co:'Commercial',preview:'Check before changing',execute:'Confirm regime change',refresh:'Refresh transition audit',more:'More transitions',retry:'Check or resume the same operation',recover:'Complete recovery',
    loading:'Checking…',working:'Changing regime: checking, holding admission, updating and verifying balances.',ready:'Local checks passed. Review destination and revision before confirming.',done:'Change completed; balances, periods and history preserved.',
    blocked:'Change unavailable: complete prerequisites or reconciliation. No new transition was started.',uncertain:'Check the outcome in the audit. Resume only this same operation; a second transition will not be created.',
    empty:'No recorded transitions.',audit:'Transition audit',committed:'Update committed; service held pending recovery',finalized:'Completed',confirm:'Confirm the displayed change while preserving balances and periods? Service will pause briefly.',confirmRecovery:'Complete this already committed change by forward recovery? Balances and periods must still match their originals.',failed:'Audit unavailable. Retry without starting another transition.'
  };
  Object.assign(words,it?{
    preflight:'Revisione prima della conferma',ack:'Ho verificato destinazione, obblighi, prove mancanti e impatto mostrati.',scope:'Attivazione senza pagamenti commerciali pregressi. Le credenziali configurate non sono incassi. Il server verifica lo storico e conserva consumi, saldi e periodi. Dopo l’avvio dei checkout, il cambio automatico di regime richiede un percorso finanziario separato; nessuna migrazione legacy è prevista.',
    modeDisabled:'Recupero locale non attivo; verificare la configurazione di manutenzione.',lifecycle:'Avanzamento della transizione',idle:'Nessun passaggio attivo',reserved:'Prenotazione registrata; ingressi bloccati',aborted:'Prenotazione annullata prima del commit',
    evidence:'Prove originali o coerenza non verificabili: mantenere il blocco e richiedere revisione.',legacy:'Passaggio storico: recupero in manutenzione con le prove originali; nessun annullamento disponibile.',
    tracked:'Operazioni registrate ancora aperte (non certifica tutti gli executor)',unavailable:'Avanzamento non disponibile: aggiornare prima di agire.',unknown:'Data o autore non registrati nello storico',
    abort:'Annulla questa prenotazione',confirmAbort:'Annullare soltanto questa prenotazione non ancora committata? Il regime e i saldi restano invariati.'
  }:{
    preflight:'Review before confirmation',ack:'I reviewed the displayed destination, obligations, missing evidence and impact.',scope:'Activation without earlier commercial payments. Configured credentials are not collected money. The server checks history and preserves usage, balances and periods. After checkout starts, automatic regime switching requires a separate financial workflow; legacy migration is not supported.',
    modeDisabled:'Local recovery inactive; review the maintenance configuration.',lifecycle:'Transition progress',idle:'No active transition',reserved:'Reservation recorded; admission held',aborted:'Reservation cancelled before commit',
    evidence:'Original evidence or consistency unverified: keep the barrier held and request review.',legacy:'Historical commit: maintenance recovery with original evidence required; cancellation unavailable.',
    tracked:'Tracked operations still open (does not certify every executor)',unavailable:'Progress unavailable: refresh before acting.',unknown:'Date or actor not recorded in historical evidence',
    abort:'Cancel this reservation',confirmAbort:'Cancel only this reservation before commit? The regime and balances remain unchanged.'
  });
  const box=document.createElement('section');box.dataset.regimeCutover='';box.style.overflowWrap='anywhere';
  const title=document.createElement('h3');title.textContent=words.title;
  const note=document.createElement('p');note.textContent=words.note;
  const label=document.createElement('label');label.textContent=words.target+' ';
  const target=document.createElement('select');target.id='maintenanceCutoverTarget';
  for(const [value,text] of [['NON_COMMERCIAL',words.nc],['COMMERCIAL',words.co]]){const option=document.createElement('option');option.value=value;option.textContent=text;target.append(option);}label.append(target);
  function button(text){const b=document.createElement('button');b.type='button';b.textContent=text;return b;}
  const check=button(words.preview),execute=button(words.execute),retry=button(words.retry),refresh=button(words.refresh),more=button(words.more);
  execute.disabled=true;retry.hidden=true;more.hidden=true;
  const status=document.createElement('p');status.setAttribute('role','status');status.setAttribute('aria-live','polite');status.dataset.cutoverStatus='';
  const review=document.createElement('p');review.dataset.cutoverReview='';
  const preflight=document.createElement('section');preflight.dataset.cutoverPreflight='';
  const preflightTitle=document.createElement('h4');preflightTitle.textContent=words.preflight;
  const scope=document.createElement('p');scope.textContent=words.scope;
  const sections=document.createElement('ul');sections.dataset.preflightSections='';
  const acknowledged=document.createElement('input');acknowledged.type='checkbox';acknowledged.disabled=true;acknowledged.dataset.cutoverAcknowledged='';
  const acknowledgement=document.createElement('label');acknowledgement.append(acknowledged,document.createTextNode(' '+words.ack));
  preflight.append(preflightTitle,scope,sections,acknowledgement);
  const auditTitle=document.createElement('h4');auditTitle.textContent=words.audit;
  const auditStatus=document.createElement('p');auditStatus.setAttribute('role','status');auditStatus.dataset.cutoverAuditStatus='';
  const records=document.createElement('ul');records.dataset.cutoverAudit='';
  const progress=document.createElement('p');progress.dataset.cutoverProgress='';progress.setAttribute('role','status');progress.setAttribute('aria-live','polite');
  const cancel=button(words.abort);cancel.hidden=true;cancel.dataset.cutoverAbort='';
  box.append(title,note,label,check,preflight,review,execute,retry,status,progress,cancel,auditTitle,refresh,auditStatus,records,more);host.append(box);
  const key='mta-pending-regime-cutover';let pending=null,preview=null,busy=false,offset=0,listEpoch=0,listing=false,lifecycle=null,pollTimer=null;
  try{const stored=JSON.parse(sessionStorage.getItem(key)||'null');
    if(stored&&/^[A-Za-z0-9_-]{8,100}$/.test(stored.request_id)&&/^[a-f0-9]{64}$/.test(stored.preview_sha256)&&Number.isSafeInteger(stored.expected_revision)&&stored.expected_revision>=0&&['COMMERCIAL','NON_COMMERCIAL'].includes(stored.target)&&stored.confirm===true)pending={request_id:stored.request_id,target:stored.target,expected_revision:stored.expected_revision,preview_sha256:stored.preview_sha256,confirm:true};
  }catch(_){/* A malformed local hint is never authority to change the server. */}
  function remember(value){pending=value;try{if(value)sessionStorage.setItem(key,JSON.stringify(value));else sessionStorage.removeItem(key);}catch(_){/* Backend identity remains durable. */}controls();}
  function controls(){check.disabled=busy||!!pending;target.disabled=busy||!!pending;execute.disabled=busy||!!pending||!preview||!acknowledged.checked||!lifecycle||lifecycle.phase!=='idle';acknowledged.disabled=busy||!!pending||!preview;retry.hidden=!pending;retry.disabled=busy;refresh.disabled=busy||listing;more.disabled=busy||listing;cancel.disabled=busy||listing;for(const b of box.querySelectorAll('[data-cutover-recovery]'))b.disabled=busy||listing||lifecycle?.active?.id!==b.dataset.cutoverRecovery||lifecycle?.active?.action!=='forward_recovery';}
  async function request(path,body){const response=await fetch('/api/admin/service-regime/cutovers'+path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:body?{'Content-Type':'application/json','X-MTA-Request':'1'}:{},body:body?JSON.stringify(body):undefined});
    if(!response.ok){const error=Error('HTTP '+response.status);error.httpStatus=response.status;throw error;}return response.json();}
  function complete(result){if(result.phase==='finalized'&&result.barrier_held===false){remember(null);status.textContent=words.done;return true;}status.textContent=words.uncertain;return false;}
  async function list(reset=true){
    const epoch=++listEpoch;listing=true;controls();
    if(reset){offset=0;records.replaceChildren();more.hidden=true;}
    auditStatus.textContent=words.loading;
    try{const data=await request('/lifecycle?limit=25&offset='+offset);
      if(epoch!==listEpoch)return;
      if(!Array.isArray(data.items)||!Number.isSafeInteger(data.total))throw Error('Invalid audit');
      showProgress(data);
      if(!data.total){const empty=document.createElement('li');empty.textContent=words.empty;records.append(empty);}
      for(const row of data.items){
        const item=document.createElement('li');item.dataset.cutoverId=row.id;
        const text=document.createElement('span');text.textContent=row.id+' · '+row.source+' → '+row.target+' · '+row.revision+' · '+(words[row.phase]||words.evidence)+' · '+(row.created_at||words.unknown);item.append(text);
        for(const event of row.events||[]){const detail=document.createElement('p');detail.textContent=(words[event.phase]||words.evidence)+' · '+event.actor_id+' · '+event.created_at;item.append(detail);}
        if(pending?.request_id===row.id&&row.phase==='finalized'){complete(row);preview=null;}
        if(row.phase==='committed'&&row.barrier_held===true){const recover=button(words.recover);recover.dataset.cutoverRecovery=row.id;recover.disabled=busy||listing;recover.onclick=async()=>{
          if(busy||lifecycle?.active?.id!==row.id||lifecycle.active.action!=='forward_recovery'||!confirm(words.confirmRecovery+' '+row.id+' · '+row.target+' · '+row.revision))return;
          busy=true;controls();recover.disabled=true;status.textContent=words.working;
          try{const result=await request('/'+encodeURIComponent(row.id)+'/recover',{expected_revision:row.revision,confirm:true});complete(result);await list(true);}
          catch(_){status.textContent=words.uncertain;}finally{busy=false;recover.disabled=false;controls();refresh.focus();}
        };item.append(' ',recover);}records.append(item);
      }
      offset+=data.items.length;more.hidden=offset>=data.total||!data.items.length;auditStatus.textContent='';
    }catch(_){if(epoch===listEpoch){auditStatus.textContent=words.failed;more.hidden=true;lifecycle=null;progress.textContent=words.unavailable;cancel.hidden=true;}}
    finally{if(epoch===listEpoch){listing=false;controls();}}
  }
  function showProgress(data){
    if(data.schema!=='mta-transition-status-1'||!['idle','reserved','committed','blocked'].includes(data.phase)||typeof data.integrity_verified!=='boolean'||!data.fence||typeof data.fence.transitioning!=='boolean')throw Error('Invalid lifecycle');
    lifecycle=data;
    const f=data.fence,counts=f.open_by_kind;
    if(!counts||!['job','checkout','webhook'].every(k=>Number.isSafeInteger(counts[k])&&counts[k]>=0))throw Error('Invalid operation counts');
    progress.textContent=words.lifecycle+': '+(data.phase==='idle'?words.idle:words[data.phase]||words.evidence)+' · '+f.regime+' · '+f.revision+' · '+words.tracked+': '+counts.job+' / '+counts.checkout+' / '+counts.webhook;
    if(data.active)progress.textContent+=' · '+data.active.id+' · '+data.active.source+' → '+data.active.target;
    if(data.reason)progress.textContent+=' · '+(data.reason==='legacy_commit_requires_maintenance'?words.legacy:data.reason==='recovery_mode_disabled'?words.modeDisabled:words.evidence);
    cancel.hidden=!(data.integrity_verified&&data.active?.action==='abort_reservation');
    controls();schedule();
  }
  function schedule(){clearTimeout(pollTimer);if(!document.hidden&&lifecycle&&['reserved','committed'].includes(lifecycle.phase))pollTimer=setTimeout(poll,5000);}
  async function poll(){
    if(busy||listing){schedule();return;}
    const prior=JSON.stringify([lifecycle?.phase,lifecycle?.fence,lifecycle?.active]);
    try{const data=await request('/lifecycle?limit=1&offset=0');showProgress(data);
      if(JSON.stringify([data.phase,data.fence,data.active])!==prior)await list(true);
    }catch(_){lifecycle=null;progress.textContent=words.unavailable;cancel.hidden=true;controls();}
  }
  document.addEventListener('visibilitychange',()=>{clearTimeout(pollTimer);if(!document.hidden)poll();});
  cancel.onclick=async()=>{
    const row=lifecycle?.active;
    if(busy||listing||row?.action!=='abort_reservation'||!confirm(words.confirmAbort+' '+row.id+' · '+row.source_revision))return;
    busy=true;controls();status.textContent=words.working;
    try{await request('/reservations/'+encodeURIComponent(row.id)+'/abort',{expected_revision:row.source_revision,confirm:true});preview=null;review.textContent='';status.textContent=words.aborted;}
    catch(_){status.textContent=words.uncertain;}
    finally{await list(true);busy=false;controls();refresh.focus();}
  };
  async function sendOriginal(){
    if(busy||!pending)return;busy=true;controls();status.textContent=words.working;
    try{const result=await request('',pending);complete(result);}
    catch(error){status.textContent=error.httpStatus===409?words.blocked:words.uncertain;
      if(error.httpStatus===409){try{const row=await request('/'+encodeURIComponent(pending.request_id));complete(row);}
        catch(checkError){if(checkError.httpStatus===404)remember(null);}}
    }
    finally{preview=null;review.textContent='';await list(true);busy=false;controls();}
  }
  function discardReview(){preview=null;acknowledged.checked=false;review.textContent='';sections.replaceChildren();controls();}
  target.onchange=()=>{discardReview();status.textContent='';};
  window.addEventListener('mta-service-drain-changed',discardReview);
  acknowledged.onchange=controls;
  function renderPreflight(data){
    if(data.schema!=='mta-operator-preflight-1'||data.target!==target.value||data.general_transition_authorized!==false||!Array.isArray(data.sections))throw Error('Invalid operator review');
    const names=it?{payment_ledger:'Pagamenti, contestazioni e recuperi',checkout_dispatches:'Checkout e risultati incerti',provider_events:'Eventi autenticati dei provider',financial_observations:'Osservazioni e prove finanziarie',original_subscription_basis:'Quota e surplus originali degli abbonamenti',operator_refunds:'Rimborsi del gestore',worker_claims:'Proprietà dei worker',pull_execution:'Esecuzioni remote assegnate',worker_quiescence:'Quiescenza dei processi',operator_losses:'Perdite a carico del gestore',nc_collection:'Contributi non commerciali',schema_coverage:'Copertura degli schemi',provider_history:'Storico completo dei provider'}:{payment_ledger:'Payments, disputes and recoveries',checkout_dispatches:'Checkouts and uncertain outcomes',provider_events:'Authenticated provider events',financial_observations:'Financial observations and evidence',original_subscription_basis:'Original subscription fee and surplus',operator_refunds:'Operator refunds',worker_claims:'Worker ownership',pull_execution:'Assigned remote executions',worker_quiescence:'Process quiescence',operator_losses:'Operator-funded losses',nc_collection:'Non-commercial contributions',schema_coverage:'Schema coverage',provider_history:'Complete provider history'};
    const states=it?{verified:'Verificato nel registro locale',not_used:'Non utilizzato: nessuna registrazione negli schemi verificati',pending:'Da completare',unverified:'Prova non verificabile',review_required:'Revisione completa necessaria'}:{verified:'Verified in local journal',not_used:'Unused: no records in reviewed schemas',pending:'Outstanding',unverified:'Evidence unverified',review_required:'Complete review required'};
    const actions=it?{reconcile_payment:'Rileggi gli ordini originali dal provider nel pannello finanziario.',recover_checkout:'Verifica il riferimento e l’esito del checkout originale; non creare un secondo pagamento.',review_evidence:'Conserva e verifica le prove originali; un’osservazione non è una quietanza.',original_basis:'Verifica le prove originali della quota e del surplus; non ricostruirli dal prezzo attuale.',refunds:'Completa o rileggi i rimborsi originali nel pannello rimborsi; nuovi dispatch richiedono il servizio aperto.',worker_recovery:'Completa il lavoro originale o il recupero con prova di quiescenza; non presumere la cessazione da un timeout.',nc_collection:'Riconcilia i contributi e gli eventuali rimborsi nel pannello contributi.',schema_review:'Gli schemi sconosciuti richiedono revisione; non eliminare lo storico.',merchant_history:'Le letture su una finestra temporale non certificano lo storico completo del conto.'}:{reconcile_payment:'Read back original orders from the provider in the financial panel.',recover_checkout:'Verify the original checkout reference and outcome; do not create a second payment.',review_evidence:'Preserve and verify original evidence; an observation is not a settlement receipt.',original_basis:'Verify original fee and surplus evidence; do not reconstruct it from the current price.',refunds:'Complete or read back original refunds in the refund panel; new dispatches require open service.',worker_recovery:'Finish original work or recovery with quiescence evidence; a timeout does not prove termination.',nc_collection:'Reconcile contributions and any refunds in the contribution panel.',schema_review:'Unknown schemas require review; do not delete history.',merchant_history:'A requested time window does not certify complete account history.'};
    const countNames=it?{pending:'In attesa',running:'Worker in esecuzione',active_disputes:'Contestazioni aperte',outstanding_dispatches:'Dispatch da verificare',total:'Casi da verificare',unknown_schemas:'Schemi non verificati',records:'Registrazioni storiche'}:{pending:'Pending',running:'Running workers',active_disputes:'Open disputes',outstanding_dispatches:'Dispatches to verify',total:'Cases to verify',unknown_schemas:'Unreviewed schemas',records:'Historical records'};
    const moneyNames=it?{subscription_reversal_due_micro:'Recuperi abbonamenti da incassare',subscription_repayment_refund_due_micro:'Rimborsi dei recuperi dovuti',subscription_risk_micro:'Importi abbonamenti a rischio'}:{subscription_reversal_due_micro:'Subscription recoveries outstanding',subscription_repayment_refund_due_micro:'Repayment refunds due',subscription_risk_micro:'Subscription amounts at risk'};
    const destinations={reconcile_payment:'#regimeFinance',recover_checkout:'#regimeFinance',review_evidence:'#regimeFinance',original_basis:'[data-subscription-evidence]',refunds:'[data-payment-refunds=admin]',worker_recovery:'#workerRecoveryPanel',nc_collection:'[data-nc-contributions=admin]',merchant_history:'[data-merchant-history]'};
    sections.replaceChildren();
    for(const row of data.sections){
      if(!names[row.id]||!states[row.state]||!actions[row.action])throw Error('Unknown review family');
      const item=document.createElement('li');item.dataset.preflightFamily=row.id;
      const heading=document.createElement('strong');heading.textContent=names[row.id]+' · '+states[row.state];item.append(heading);
      const text=document.createElement('p');text.textContent=actions[row.action];item.append(text);
      for(const [key,value] of Object.entries(row.counts||{})){if(!countNames[key])throw Error('Unknown review count');const detail=document.createElement('p');detail.textContent=countNames[key]+': '+(value===null?'?':String(value));item.append(detail);}
      for(const [key,value] of Object.entries(row.amounts_micro||{})){const amount=document.createElement('p');if(!moneyNames[key]||(value!==null&&!/^[0-9]+$/.test(value)))throw Error('Invalid exact amount');amount.textContent=moneyNames[key]+': '+(value===null?(it?'Importo non verificabile':'Amount unverified'):(BigInt(value)/1000000n).toString()+(it?',':'.')+(BigInt(value)%1000000n).toString().padStart(6,'0')+' EUR');item.append(amount);}
      if(row.refund_due_cents!==undefined){const amount=document.createElement('p');const value=row.refund_due_cents;if(value!==null&&!/^[0-9]+$/.test(value))throw Error('Invalid refund amount');amount.textContent=(it?'Rimborsi dovuti: ':'Refunds due: ')+(value===null?'?':(BigInt(value)/100n).toString()+(it?',':'.')+(BigInt(value)%100n).toString().padStart(2,'0')+' EUR');item.append(amount);}
      if(row.id==='original_subscription_basis'){
        const basis=data.original_basis;if(!basis||!Array.isArray(basis.items))throw Error('Original basis review missing');
        for(const entry of basis.items){const detail=document.createElement('p');detail.dataset.preflightCase='';detail.textContent=(entry.order_id||words.unknown)+' · '+(it?'Prova originale da verificare':'Original evidence requires review');item.append(detail);}
        if(Number.isSafeInteger(basis.total)&&basis.offset+basis.items.length<basis.total){const more=button(it?'Altri casi originali':'More original cases');more.dataset.preflightMore='';more.onclick=()=>loadReview(basis.offset+basis.limit);item.append(more);}
      }
      if(destinations[row.action]){const open=button(it?'Apri il pannello di revisione':'Open review panel');open.onclick=()=>{const destination=document.querySelector(destinations[row.action]);if(destination){const tab=destination.closest('[id$=Tab]');if(tab?.hidden)document.querySelector('[data-tab='+tab.id.slice(0,-3)+']')?.click();if(destination.hidden){status.textContent=it?'Pannello non disponibile nel regime corrente: mantenere il blocco e verificare lo storico.':'Panel unavailable in the current regime: retain the barrier and review original history.';return;}destination.scrollIntoView({block:'start'});if(!destination.hasAttribute('tabindex'))destination.tabIndex=-1;destination.focus();}};item.append(open);}
      sections.append(item);
    }
    return data.preview;
  }
  async function loadReview(offset=0){
    if(busy||pending)return;discardReview();busy=true;controls();status.textContent=words.loading;
    try{const result=renderPreflight(await request('/preflight?target='+encodeURIComponent(target.value)+'&limit=50&offset='+offset));
      if(!result){status.textContent=words.blocked;return;}
      if(result.transition_enabled!==true||result.target!==target.value||!Number.isSafeInteger(result.source_revision)||!/^[a-f0-9]{64}$/.test(result.preview_sha256))throw Error('Invalid preview');
      preview=result;review.textContent=result.source+' → '+result.target+' · '+result.source_revision;status.textContent=words.ready;
    }catch(_){status.textContent=words.blocked;}finally{busy=false;controls();}
  }
  check.onclick=()=>loadReview();
  execute.onclick=()=>{if(busy||pending||!preview||!acknowledged.checked||!confirm(words.confirm+' '+review.textContent))return;
    const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);
    remember({request_id:Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join(''),target:preview.target,expected_revision:preview.source_revision,preview_sha256:preview.preview_sha256,confirm:true});sendOriginal();};
  retry.onclick=()=>{if(pending&&!busy&&confirm(words.confirmRecovery+' '+pending.request_id))sendOriginal();};
  refresh.onclick=()=>{if(!busy)list(true);};more.onclick=()=>{if(!busy)list(false);};
  if(pending)status.textContent=words.uncertain;controls();list(true);
})();
