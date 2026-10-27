/* Explicit maintenance cutover, original-request retry, private audit/recovery. */
(()=>{
  'use strict';
  const host=document.getElementById('serviceRegimePanel');if(!host)return;
  const it=document.documentElement.lang.startsWith('it');
  const words=it?{
    title:'Cambio di regime in manutenzione',note:'Disponibile soltanto per l’autorità locale e per posizioni interamente verificabili. Provider configurati, storico non riconciliabile e lavori irrisolti mantengono il blocco. Nessun saldo o periodo viene azzerato.',
    target:'Regime di destinazione',nc:'Non commerciale',co:'Commerciale',preview:'Verifica prima del cambio',execute:'Conferma cambio di regime',refresh:'Aggiorna registro',more:'Altre transizioni',retry:'Verifica o riprendi la stessa operazione',recover:'Completa il recupero',
    loading:'Verifica in corso…',working:'Passaggio in corso: verifica, blocco, aggiornamento e controllo dei saldi.',ready:'Verifica locale superata. Controlla destinazione e revisione prima di confermare.',done:'Passaggio completato; saldi, periodi e storico conservati.',
    blocked:'Passaggio non disponibile: completare i prerequisiti o la riconciliazione. Nessuna nuova transizione avviata.',uncertain:'Esito da verificare nel registro. Riprendi soltanto questa stessa operazione; non viene creato un secondo passaggio.',
    empty:'Nessuna transizione registrata.',audit:'Registro dei passaggi',committed:'Aggiornamento registrato; servizio bloccato in attesa del recupero',finalized:'Completato',confirm:'Confermare il passaggio mostrato, conservando saldi e periodi? Il servizio sarà brevemente sospeso.',confirmRecovery:'Completare in avanti questo passaggio già registrato? Saldi e periodi devono ancora coincidere con gli originali.',failed:'Registro non disponibile. Riprova senza avviare un altro passaggio.'
  }:{
    title:'Maintenance regime change',note:'Available only on the local authority with fully verifiable positions. Configured providers, unreconciled history and unresolved work keep the barrier held. No balance or period is reset.',
    target:'Destination regime',nc:'Non-commercial',co:'Commercial',preview:'Check before changing',execute:'Confirm regime change',refresh:'Refresh transition audit',more:'More transitions',retry:'Check or resume the same operation',recover:'Complete recovery',
    loading:'Checking…',working:'Changing regime: checking, holding admission, updating and verifying balances.',ready:'Local checks passed. Review destination and revision before confirming.',done:'Change completed; balances, periods and history preserved.',
    blocked:'Change unavailable: complete prerequisites or reconciliation. No new transition was started.',uncertain:'Check the outcome in the audit. Resume only this same operation; a second transition will not be created.',
    empty:'No recorded transitions.',audit:'Transition audit',committed:'Update committed; service held pending recovery',finalized:'Completed',confirm:'Confirm the displayed change while preserving balances and periods? Service will pause briefly.',confirmRecovery:'Complete this already committed change by forward recovery? Balances and periods must still match their originals.',failed:'Audit unavailable. Retry without starting another transition.'
  };
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
  const auditTitle=document.createElement('h4');auditTitle.textContent=words.audit;
  const auditStatus=document.createElement('p');auditStatus.setAttribute('role','status');auditStatus.dataset.cutoverAuditStatus='';
  const records=document.createElement('ul');records.dataset.cutoverAudit='';
  box.append(title,note,label,check,review,execute,retry,status,auditTitle,refresh,auditStatus,records,more);host.append(box);
  const key='mta-pending-regime-cutover';let pending=null,preview=null,busy=false,offset=0,listEpoch=0,listing=false;
  try{const stored=JSON.parse(sessionStorage.getItem(key)||'null');
    if(stored&&/^[A-Za-z0-9_-]{8,100}$/.test(stored.request_id)&&/^[a-f0-9]{64}$/.test(stored.preview_sha256)&&Number.isSafeInteger(stored.expected_revision)&&stored.expected_revision>=0&&['COMMERCIAL','NON_COMMERCIAL'].includes(stored.target)&&stored.confirm===true)pending={request_id:stored.request_id,target:stored.target,expected_revision:stored.expected_revision,preview_sha256:stored.preview_sha256,confirm:true};
  }catch(_){/* A malformed local hint is never authority to change the server. */}
  function remember(value){pending=value;try{if(value)sessionStorage.setItem(key,JSON.stringify(value));else sessionStorage.removeItem(key);}catch(_){/* Backend identity remains durable. */}controls();}
  function controls(){check.disabled=busy||!!pending;target.disabled=busy||!!pending;execute.disabled=busy||!!pending||!preview;retry.hidden=!pending;retry.disabled=busy;refresh.disabled=busy||listing;more.disabled=busy||listing;for(const b of box.querySelectorAll('[data-cutover-recovery]'))b.disabled=busy||listing;}
  async function request(path,body){const response=await fetch('/api/admin/service-regime/cutovers'+path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:body?{'Content-Type':'application/json','X-MTA-Request':'1'}:{},body:body?JSON.stringify(body):undefined});
    if(!response.ok){const error=Error('HTTP '+response.status);error.httpStatus=response.status;throw error;}return response.json();}
  function complete(result){if(result.phase==='finalized'&&result.barrier_held===false){remember(null);status.textContent=words.done;return true;}status.textContent=words.uncertain;return false;}
  async function list(reset=true){
    const epoch=++listEpoch;listing=true;controls();
    if(reset){offset=0;records.replaceChildren();more.hidden=true;}
    auditStatus.textContent=words.loading;
    try{const data=await request('?limit=25&offset='+offset);
      if(epoch!==listEpoch)return;
      if(!Array.isArray(data.items)||!Number.isSafeInteger(data.total))throw Error('Invalid audit');
      if(!data.total)records.textContent=words.empty;
      for(const row of data.items){
        const item=document.createElement('li');item.dataset.cutoverId=row.id;
        const text=document.createElement('span');text.textContent=row.id+' · '+row.source+' → '+row.target+' · '+row.revision+' · '+(row.phase==='finalized'?words.finalized:words.committed)+' · '+row.created_at;item.append(text);
        for(const event of row.events||[]){const detail=document.createElement('p');detail.textContent=(event.phase==='finalized'?words.finalized:words.committed)+' · '+event.actor_id+' · '+event.created_at;item.append(detail);}
        if(pending?.request_id===row.id&&row.phase==='finalized'){complete(row);preview=null;}
        if(row.phase==='committed'&&row.barrier_held===true){const recover=button(words.recover);recover.dataset.cutoverRecovery='';recover.disabled=busy||listing;recover.onclick=async()=>{
          if(busy||!confirm(words.confirmRecovery+' '+row.id+' · '+row.target+' · '+row.revision))return;
          busy=true;controls();recover.disabled=true;status.textContent=words.working;
          try{const result=await request('/'+encodeURIComponent(row.id)+'/recover',{expected_revision:row.revision,confirm:true});complete(result);await list(true);}
          catch(_){status.textContent=words.uncertain;}finally{busy=false;recover.disabled=false;controls();}
        };item.append(' ',recover);}records.append(item);
      }
      offset+=data.items.length;more.hidden=offset>=data.total||!data.items.length;auditStatus.textContent='';
    }catch(_){if(epoch===listEpoch){auditStatus.textContent=words.failed;more.hidden=true;}}
    finally{if(epoch===listEpoch){listing=false;controls();}}
  }
  async function sendOriginal(){
    if(busy||!pending)return;busy=true;controls();status.textContent=words.working;
    try{const result=await request('',pending);complete(result);}
    catch(error){status.textContent=error.httpStatus===409?words.blocked:words.uncertain;
      if(error.httpStatus===409){try{const row=await request('/'+encodeURIComponent(pending.request_id));complete(row);}
        catch(checkError){if(checkError.httpStatus===404)remember(null);}}
    }
    finally{preview=null;review.textContent='';await list(true);busy=false;controls();}
  }
  target.onchange=()=>{preview=null;review.textContent='';status.textContent='';controls();};
  check.onclick=async()=>{
    if(busy||pending)return;busy=true;preview=null;controls();review.textContent='';status.textContent=words.loading;
    try{const result=await request('/preview?target='+encodeURIComponent(target.value));
      if(result.transition_enabled!==true||result.target!==target.value||!Number.isSafeInteger(result.source_revision)||!/^[a-f0-9]{64}$/.test(result.preview_sha256))throw Error('Invalid preview');
      preview=result;review.textContent=result.source+' → '+result.target+' · '+result.source_revision;status.textContent=words.ready;
    }catch(_){status.textContent=words.blocked;}finally{busy=false;controls();}
  };
  execute.onclick=()=>{if(busy||pending||!preview||!confirm(words.confirm+' '+review.textContent))return;
    const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);
    remember({request_id:Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join(''),target:preview.target,expected_revision:preview.source_revision,preview_sha256:preview.preview_sha256,confirm:true});sendOriginal();};
  retry.onclick=()=>{if(pending&&!busy&&confirm(words.confirmRecovery+' '+pending.request_id))sendOriginal();};
  refresh.onclick=()=>{if(!busy)list(true);};more.onclick=()=>{if(!busy)list(false);};
  if(pending)status.textContent=words.uncertain;controls();list(true);
})();
