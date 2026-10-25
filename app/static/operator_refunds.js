/* Explicit two-step operator refunds; uncertain operations expose GET-only recovery. */
(function(){
  'use strict';
  const root=document.querySelector('[data-payment-refunds]');if(!root)return;
  const admin=root.dataset.paymentRefunds==='admin';
  const it=()=>String(window.MtaLocale?.language||document.documentElement.lang||'it').toLowerCase().startsWith('it');
  const tr=(a,b)=>it()?a:b;
  const states=()=>({prepared:tr('Preparato: nessun rimborso inviato','Prepared: no refund sent'),uncertain:tr('Esito incerto: verificare, non reinviare','Uncertain outcome: verify, do not resend'),pending:tr('In attesa di verifica e riconciliazione','Awaiting verification and reconciliation'),settled:tr('Rimborso verificato e riconciliato','Refund verified and reconciled'),failed:tr('Fallimento verificato dal provider','Failure verified by provider'),cancelled:tr('Preparazione annullata senza invio','Preparation cancelled without dispatch')});
  let busy=false,offset=0,view=null,refreshQueued=false;
  const title=document.createElement('h2');title.textContent=tr('Rimborsi dei pagamenti','Payment refunds');
  const note=document.createElement('p');note.textContent=admin?tr('Prepara il rimborso, poi conferma separatamente l’invio al metodo di pagamento originale. Dopo un esito incerto è disponibile solo la verifica.','Prepare the refund, then separately confirm dispatch to the original payment method. After an uncertain outcome, only verification is available.'):tr('Stato dei rimborsi dei tuoi pagamenti. Un rimborso in attesa non è ancora confermato.','Refund status for your payments. A pending refund is not yet confirmed.');
  const status=document.createElement('p');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const refresh=document.createElement('button');refresh.type='button';refresh.textContent=tr('Aggiorna rimborsi','Refresh refunds');refresh.dataset.refundRefresh='';
  const content=document.createElement('div');content.dataset.refundContent='';root.replaceChildren(title,note,refresh,status,content);
  function lock(value){busy=value;root.querySelectorAll('button,input,select,textarea').forEach(x=>x.disabled=value);}
  function money(cents){return (cents/100).toLocaleString(it()?'it':'en',{minimumFractionDigits:2,maximumFractionDigits:2})+' EUR';}
  function element(tag,text){const x=document.createElement(tag);if(text!==undefined)x.textContent=text;return x;}
  function field(form,label,name,type){const wrap=element('label',label);const input=element(type==='textarea'?'textarea':'input');input.name=name;if(type!=='textarea')input.type=type;input.required=true;wrap.append(input);form.append(wrap);return input;}
  async function api(path,body){const response=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:body?{'Content-Type':'application/json','X-MTA-Request':'1'}:{},body:body?JSON.stringify(body):undefined});if(!response.ok)throw Error('HTTP '+response.status);return response.json();}
  const endpoint=admin?'/api/admin/payment-refunds':'/api/account/payment-refunds';
  async function load(){view=await api(endpoint+'?limit=25&offset='+offset);render();}
  async function run(action){if(busy)return;lock(true);status.textContent=tr('Verifica in corso…','Checking…');try{await action();await load();status.textContent=tr('Stato aggiornato. Controlla l’esito del rimborso.','Status updated. Check the refund outcome.');}catch(error){content.replaceChildren();view=null;status.textContent=tr('Operazione non confermata. Aggiorna prima di agire di nuovo: ','Operation not confirmed. Refresh before acting again: ')+error.message;}finally{lock(false);if(refreshQueued){refreshQueued=false;void run(async()=>{});}}}
  function act(item,action,reference){const body={expected_revision:item.revision};if(reference)body.provider_reference=reference;return api('/api/admin/payment-refunds/'+encodeURIComponent(item.id)+'/'+action,body);}
  function render(){
    content.replaceChildren();
    if(admin&&view.audit?.verified!==true){content.append(element('p',tr('Registro rimborsi non verificabile: azioni disabilitate.','Refund journal cannot be verified: actions disabled.')));return;}
    if(admin){
      const options=view.targets||[];
      if(options.length){const form=element('form');form.className='settings-form';form.dataset.refundPrepare='';
        const label=element('label',tr('Pagamento e incasso da rimborsare','Payment and capture to refund'));const select=element('select');select.name='target';label.append(select);form.append(label);
        options.forEach((x,i)=>{const option=element('option',x.provider+' · '+x.order_id+' · '+x.target+' · '+money(x.remaining_cents));option.value=String(i);select.append(option);});
        const amount=field(form,tr('Importo EUR','Amount EUR'),'amount','text');amount.inputMode='decimal';amount.pattern='[0-9]+([.,][0-9]{1,2})?';amount.maxLength=14;
        const reason=field(form,tr('Motivo documentato (solo amministratori)','Documented reason (administrators only)'),'reason','textarea');reason.minLength=4;reason.maxLength=500;
        const button=element('button',tr('Prepara rimborso','Prepare refund'));button.type='submit';form.append(button);
        const requestId=crypto.randomUUID();form.onsubmit=e=>{e.preventDefault();if(busy)return;const match=amount.value.trim().match(/^([0-9]+)(?:[.,]([0-9]{1,2}))?$/);if(!match){status.textContent=tr('Inserisci un importo esatto in centesimi.','Enter an exact amount in cents.');return;}
          const cents=Number(match[1])*100+Number((match[2]||'').padEnd(2,'0'));const selected=options[Number(select.value)];if(!selected||!Number.isSafeInteger(cents)||cents<=0||cents>selected.remaining_cents){status.textContent=tr('Importo superiore al residuo o non valido.','Amount exceeds the remainder or is invalid.');return;}
          if(!confirm(tr('Preparare questo rimborso senza ancora inviarlo?','Prepare this refund without sending it yet?')))return;
          run(()=>api(endpoint,{provider:selected.provider,order_id:selected.order_id,target:selected.target,amount_cents:cents,reason:reason.value,request_id:requestId}));};content.append(form);
      }else content.append(element('p',tr('Nessun pagamento riconciliato rimborsabile elencato. Riconcilia prima il pagamento.','No reconciled refundable payment listed. Reconcile the payment first.')));
    }
    for(const item of view.items||[]){const article=element('article');article.dataset.refundId=item.id;article.dataset.refundState=item.state;
      article.append(element('h3',item.provider+' · '+item.order_id),element('p',money(item.amount_cents)+' · '+(states()[item.state]||tr('Esito non verificabile','Unverifiable outcome'))));
      if(admin){article.append(element('p',item.target+(item.provider_reference?' · '+item.provider_reference:'')));
        if(item.reason)article.append(element('p',tr('Motivo: ','Reason: ')+item.reason));
        if(item.audit?.length){const details=element('details');details.append(element('summary',tr('Registro delle azioni','Action audit')));
          for(const event of item.audit)details.append(element('p',String(event.revision)+' · '+(states()[event.state]||event.state)+' · '+tr('Amministratore ','Administrator ')+event.actor_id+' · '+new Date(event.created_at*1000).toISOString()));article.append(details);}
        if(item.state==='prepared'){
          const execute=element('button',tr('Invia rimborso al provider','Send refund to provider'));execute.type='button';execute.dataset.refundExecute='';execute.onclick=()=>{if(!busy&&confirm(tr('Confermi l’invio reale di ','Confirm sending ')+money(item.amount_cents)+tr(' al metodo originale per l’ordine ',' to the original method for order ')+item.order_id+'?'))run(()=>act(item,'execute'));};
          const cancel=element('button',tr('Annulla preparazione','Cancel preparation'));cancel.type='button';cancel.dataset.refundCancel='';cancel.onclick=()=>{if(!busy&&confirm(tr('Annullare la preparazione senza invio?','Cancel preparation without dispatch?')))run(()=>act(item,'cancel'));};article.append(execute,cancel);
        }else if(['uncertain','pending'].includes(item.state)){
          const form=element('form');form.className='settings-form';form.dataset.refundVerify='';
          const input=field(form,tr('ID rimborso del provider da verificare','Provider refund ID to verify'),'reference','text');input.value=item.provider_reference||'';input.maxLength=110;input.autocomplete='off';
          if(item.provider_reference)input.readOnly=true;
          const button=element('button',tr('Verifica esito senza reinvio','Verify outcome without resending'));button.type='submit';form.append(button);
          form.onsubmit=e=>{e.preventDefault();if(!busy)run(()=>act(item,'verify',input.value.trim()));};article.append(form);
        }
      }content.append(article);
    }
    if(!(view.items||[]).length)content.append(element('p',tr('Nessun rimborso in questa pagina.','No refunds on this page.')));
    const nav=element('nav');nav.setAttribute('aria-label',tr('Pagine rimborsi','Refund pages'));
    if(offset>0){const previous=element('button',tr('Precedenti','Previous'));previous.type='button';previous.onclick=()=>run(async()=>{offset=Math.max(0,offset-25);});nav.append(previous);}
    if(offset+25<view.total){const next=element('button',tr('Successivi','Next'));next.type='button';next.onclick=()=>run(async()=>{offset+=25;});nav.append(next);}content.append(nav);
  }
  function labels(){title.textContent=tr('Rimborsi dei pagamenti','Payment refunds');refresh.textContent=tr('Aggiorna rimborsi','Refresh refunds');note.textContent=admin?tr('Prepara il rimborso, poi conferma separatamente l’invio al metodo di pagamento originale. Dopo un esito incerto è disponibile solo la verifica.','Prepare the refund, then separately confirm dispatch to the original payment method. After an uncertain outcome, only verification is available.'):tr('Stato dei rimborsi dei tuoi pagamenti. Un rimborso in attesa non è ancora confermato.','Refund status for your payments. A pending refund is not yet confirmed.');}
  window.addEventListener('mta:language',()=>{labels();if(busy)status.textContent=tr('Verifica in corso…','Checking…');else if(view)render();else run(async()=>{});});
  window.addEventListener('mta:payments-updated',()=>{if(busy)refreshQueued=true;else run(async()=>{});});
  refresh.onclick=()=>run(async()=>{});run(async()=>{});
})();
