/* Persistent local worker recovery; economic reconciliation stays separate. */
(function(){
  'use strict';
  const host=document.getElementById('serviceRegimePanel');if(!host)return;
  const section=document.createElement('section');section.id='workerRecoveryPanel';host.append(section);
  const it=()=>String(document.documentElement.lang||'it').toLowerCase().startsWith('it');
  const text=(a,b)=>it()?a:b;
  let offset=0,busy=false;const limit=50,requests=new Map();
  const requestId=()=>typeof crypto.randomUUID==='function'?crypto.randomUUID():Array.from(crypto.getRandomValues(new Uint8Array(16)),value=>value.toString(16).padStart(2,'0')).join('');
  const title=document.createElement('h3'),note=document.createElement('p'),status=document.createElement('p');
  status.setAttribute('role','status');status.setAttribute('aria-live','polite');status.id='workerRecoveryStatus';
  const refresh=document.createElement('button'),previous=document.createElement('button'),next=document.createElement('button'),list=document.createElement('div');
  for(const button of [refresh,previous,next])button.type='button';
  section.append(title,note,refresh,previous,next,status,list);
  async function load(){if(busy)return;busy=true;refresh.disabled=previous.disabled=next.disabled=true;
    title.textContent=text('Recupero processi AI','AI process recovery');
    note.textContent=text('Arresta soltanto i processi locali registrati di un supervisore certamente terminato. Addebiti, riserve e claim restano da riconciliare.','Stops only registered local processes whose original supervisor has certainly exited. Charges, reservations and claims still require reconciliation.');
    refresh.textContent=text('Aggiorna processi','Refresh processes');previous.textContent=text('Precedenti','Previous');next.textContent=text('Successivi','Next');list.replaceChildren();
    try{const response=await fetch('/api/admin/service-regime/worker-processes?limit='+limit+'&offset='+offset,{credentials:'same-origin',cache:'no-store'});
      if(!response.ok)throw Error('HTTP '+response.status);const data=await response.json();
      if(!data.verified)throw Error(text('Registro non verificabile','Journal unverifiable'));
      status.textContent=text('Processi in attesa di arresto verificato: ','Processes awaiting verified termination: ')+data.pending;
      for(const scope of data.scopes||[]){const row=document.createElement('p'),label=document.createElement('span'),button=document.createElement('button');button.type='button';
        label.textContent=text('Job ','Job ')+scope.job_id+' · '+text('Utente ','User ')+scope.user_id+' · '+(scope.quiescent?text('Processi arrestati; revisione contabile separata. ','Processes stopped; separate financial review. '):text('Arresto non verificato. ','Termination unverified. '));
        button.textContent=text('Verifica e arresta i processi','Verify and stop processes');button.disabled=scope.quiescent===true;
        button.onclick=async()=>{if(!confirm(text('Verificare la morte del supervisore e arrestare ricorsivamente i suoi processi locali? Nessun importo o claim viene chiuso.','Verify supervisor death and recursively stop its local processes? No amount or claim will be settled.')))return;
          button.disabled=true;
          try{if(!requests.has(scope.scope_id))requests.set(scope.scope_id,requestId());const result=await fetch('/api/admin/service-regime/worker-processes/'+encodeURIComponent(scope.scope_id)+'/quiesce',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-MTA-Request':'1'},body:JSON.stringify({request_id:requests.get(scope.scope_id),confirm_stop:true})});
            if(!result.ok)throw Error('HTTP '+result.status);await load();status.textContent=text('Arresto verificato. Claim e riserve economiche conservati per revisione.','Termination verified. Economic claims and reservations retained for review.');
            if(typeof window.mtaRefreshServiceRegime==='function')window.mtaRefreshServiceRegime();
          }catch(error){status.textContent=text('Recupero non completato; claim conservato: ','Recovery incomplete; claim retained: ')+error.message;button.disabled=false;}};
        row.append(label,button);list.append(row);}
      previous.disabled=offset===0;next.disabled=offset+limit>=(data.total||0);
    }catch(error){status.textContent=text('Verifica non disponibile: ','Verification unavailable: ')+error.message;}
    finally{busy=false;refresh.disabled=false;}
  }
  refresh.onclick=()=>load();previous.onclick=()=>{offset=Math.max(0,offset-limit);load();};next.onclick=()=>{offset+=limit;load();};load();
})();
