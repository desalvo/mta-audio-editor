/* r210: fail-closed service-regime administration panel. No client-side switch. */
(function(){
  'use strict';
  const root=document.getElementById('serviceRegimePanel');
  if(!root)return;
  const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let current='NON_COMMERCIAL';
  let busy=false;
  const locale=()=>String(document.documentElement.lang||'it').toLowerCase().startsWith('en')?'en':'it';
  const translations={
    it:{title:'Regime del servizio',loading:'Verifica contabile in corso…',refresh:'Aggiorna verifiche',current:'Regime attivo',target:'Regime da verificare',nc:'Non commerciale',co:'Commerciale',finance:'Posizioni economiche verificate',reconcile:'Riconcilia dal provider',confirmReconcile:'Leggere lo stato autenticato dal provider e riconciliare questo pagamento nel ledger?',columns:['Provider','Ordine','Valuta','Importo','Rimborsato','Contestato','Pagamento netto'],
      readiness:'Stato della transizione',disabled:'Cambio di regime non ancora abilitato',issues:'Posizioni ancora da risolvere',outbox:'Checkout da riconciliare',reservations:'Prenotazioni di transizione',abort:'Annulla prenotazione',
      confirm:'Annullare questa prenotazione dopo aver verificato la relativa riconciliazione?',error:'Impossibile completare la verifica',none:'Nessuna operazione elencata',caution:'I risultati sono diagnostici: non autorizzano il cambio né eliminano obbligazioni economiche.'},
    en:{title:'Service regime',loading:'Checking accounting readiness…',refresh:'Refresh checks',current:'Active regime',target:'Regime to assess',nc:'Non-commercial',co:'Commercial',finance:'Verified financial positions',reconcile:'Reconcile from provider',confirmReconcile:'Read authenticated provider state and reconcile this payment in the ledger?',columns:['Provider','Order','Currency','Amount','Refunded','Disputed','Net payment'],
      readiness:'Transition readiness',disabled:'Regime switching is not yet enabled',issues:'Unresolved positions',outbox:'Checkouts requiring reconciliation',reservations:'Transition reservations',abort:'Abort reservation',
      confirm:'Abort this reservation after verifying reconciliation status?',error:'Unable to complete verification',none:'No listed operations',caution:'Readiness is diagnostic only: it does not authorize switching or clear economic obligations.'}
  };
  const t=()=>translations[locale()];
  function frame(){const x=t();root.innerHTML=`<h2>${x.title}</h2><p id="regimeActive"></p><label for="regimeTarget">${x.target}</label> <select id="regimeTarget"><option value="NON_COMMERCIAL">${x.nc}</option><option value="COMMERCIAL">${x.co}</option></select> <button type="button" id="regimeRefresh">${x.refresh}</button><p id="regimeReadiness" role="status" aria-live="polite">${x.loading}</p><h3>${x.issues}</h3><pre id="regimeIssues" class="regime-diagnostics"></pre><h3>${x.outbox}</h3><pre id="regimeOutbox" class="regime-diagnostics"></pre><h3>${x.finance}</h3><div id="regimeFinance"></div><h3>${x.reservations}</h3><div id="regimeReservations"></div><p>${x.caution}</p>`;root.querySelector('#regimeRefresh').onclick=refresh;root.querySelector('#regimeTarget').onchange=refresh;}
  async function get(path){const response=await fetch(path,{credentials:'same-origin',cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);return response.json();}
  function describe(value){return escapeHtml(JSON.stringify(value,null,2));}
  async function refresh(){if(busy)return;busy=true;const x=t();root.querySelector('#regimeReadiness').textContent=x.loading;try{
    const state=await get('/api/admin/service-regime');current=state.regime;
    const target=root.querySelector('#regimeTarget').value;
    const [readiness,outbox,reservations,finance]=await Promise.all([
      get('/api/admin/service-regime/combined-readiness?target='+encodeURIComponent(target)),
      get('/api/admin/service-regime/payment-outbox-review?limit=25&offset=0'),
      get('/api/admin/service-regime/transition-reservations'),get('/api/admin/service-regime/payment-ledger?limit=50')]);
    root.querySelector('#regimeActive').textContent=x.current+': '+(current==='COMMERCIAL'?x.co:x.nc);
    root.querySelector('#regimeReadiness').textContent=x.disabled;
    root.querySelector('#regimeIssues').textContent=JSON.stringify(readiness,null,2);
    root.querySelector('#regimeOutbox').textContent=JSON.stringify(outbox,null,2);
    const financial=root.querySelector('#regimeFinance');financial.replaceChildren();
    const table=document.createElement('table');const head=document.createElement('tr');
    for(const column of x.columns){const th=document.createElement('th');th.scope='col';th.textContent=column;head.append(th);}table.append(head);
    for(const position of finance.positions||[]){const line=document.createElement('tr');
      const money=value=>(Number(value)/100).toLocaleString(locale(),{minimumFractionDigits:2,maximumFractionDigits:2});
      for(const value of [position.provider,position.order_id,position.currency,money(position.amount_minor),money(position.refunded_minor),money(position.held_minor),money(position.net_micro/10000)]){const cell=document.createElement('td');cell.textContent=value;line.append(cell);}
      if(position.checkout_outcome){const note=document.createElement('p');note.textContent=position.order_id+' · '+(locale()==='it'?'Checkout chiuso senza incasso: ':'Unpaid checkout closed: ')+position.checkout_outcome;financial.append(note)}
      table.append(line);
    }
    if((finance.positions||[]).length)financial.append(table);else financial.textContent=x.none;
    for(const position of finance.positions||[]){
      const reviews=position.movement_reviews;if(!reviews?.items?.length)continue;
      const panel=document.createElement('details'),summary=document.createElement('summary');panel.dataset.movementReview='';
      summary.textContent=(locale()==='it'?'Movimenti PayPal da verificare · ':'PayPal movements requiring verification · ')+position.order_id;panel.append(summary);
      const note=document.createElement('p');note.textContent=locale()==='it'?'Dati osservati dal provider: l’avvio di un movimento non ne prova il completamento. Nessuno sblocco di fondi deriva da questa tabella. Le commissioni restano separate dai crediti utente.':'Provider observations: initiation does not prove completion. This table never releases funds. Fees remain separate from user credits.';panel.append(note);
      const scroll=document.createElement('div');scroll.tabIndex=0;scroll.setAttribute('role','region');scroll.setAttribute('aria-label',locale()==='it'?'Osservazioni dei movimenti PayPal':'PayPal movement observations');scroll.style.overflowX='auto';
      const table=document.createElement('table'),head=document.createElement('tr');
      for(const label of (locale()==='it'?['Parte','Direzione','Motivo','Importo EUR','Avvio','Fonte']:['Party','Direction','Reason','EUR amount','Initiated','Source'])){const th=document.createElement('th');th.scope='col';th.textContent=label;head.append(th)}table.append(head);
      for(const review of reviews.items){for(const movement of review.observations){const tr=document.createElement('tr');for(const value of [movement.party,movement.direction,movement.reason,movement.amount_minor==null?(locale()==='it'?'Non disponibile':'Unavailable'):(BigInt(movement.amount_minor_text)/100n).toLocaleString(locale())+(locale()==='it'?',':'.')+(BigInt(movement.amount_minor_text)%100n).toString().padStart(2,'0'),movement.initiated_ms==null?'—':new Date(movement.initiated_ms).toLocaleString(locale()),movement.source]){const td=document.createElement('td');td.textContent=value;tr.append(td)}table.append(tr)}
        if(!review.observations.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=6;td.textContent=locale()==='it'?'Payout dichiarato senza dettagli di movimenti verificabili.':'Payout reported without verifiable movement details.';tr.append(td);table.append(tr)}}
      scroll.append(table);panel.append(scroll);if(reviews.truncated){const warning=document.createElement('p');warning.textContent=locale()==='it'?'Vista limitata: lo storico completo resta nel registro riservato.':'Limited view: the complete history remains in the private journal.';panel.append(warning)}financial.append(panel);
    }
    const receivables=document.createElement('p');receivables.id='regimeReceivables';
    const exact=value=>value==null?(locale()==='it'?'Non verificabile':'Unverifiable'):(Number(value)/1e6).toLocaleString(locale(),{minimumFractionDigits:2,maximumFractionDigits:6})+' EUR';
    receivables.textContent=(locale()==='it'?'Recuperi abbonamenti da incassare: ':'Subscription recoveries outstanding: ')+exact(finance.subscription_reversal_due_micro)+' · '+(locale()==='it'?'Rimborsi recuperi dovuti dal gestore: ':'Repayment refunds due from operator: ')+exact(finance.subscription_repayment_refund_due_micro);financial.append(receivables);
    // Reconcile buttons are bound to persistent local orders from the server report.
    const payable=new Map((finance.positions||[]).map(item=>[item.provider+':'+item.order_id,item]));
    for(const item of outbox.items||[]){if(item.state==='confirmed'&&item.provider_reference){const order=item.operation_id.split(':').slice(2).join(':');payable.set(item.provider+':'+order,{provider:item.provider,order_id:order});}}
    let feedback=root.querySelector('#regimeActionStatus');if(!feedback){feedback=document.createElement('p');feedback.id='regimeActionStatus';feedback.setAttribute('role','status');root.append(feedback)}
    for(const position of payable.values()){const button=document.createElement('button');button.type='button';button.textContent=x.reconcile+' · '+position.provider+' · '+position.order_id;
      button.onclick=async()=>{if(!confirm(x.confirmReconcile))return;button.disabled=true;try{const result=await fetch('/api/admin/service-regime/reconcile-payment',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-MTA-Request':'1'},body:JSON.stringify({provider:position.provider,order_id:position.order_id})});if(!result.ok)throw Error('HTTP '+result.status);const receipt=await result.json();await refresh();feedback.textContent=receipt.checkout_closed?(locale()==='it'?'Checkout chiuso senza incasso; nessun credito emesso.':'Unpaid checkout closed; no credits issued.'):(receipt.financial_review_pending?(locale()==='it'?'Ledger aggiornato; prove finanziarie ancora da verificare.':'Ledger updated; unresolved financial evidence remains.'):(receipt.ledger_reconciled?(locale()==='it'?'Ledger riconciliato.':'Ledger reconciled.'):(locale()==='it'?'Esito del provider ancora in attesa; checkout aperto.':'Provider outcome still pending; checkout remains open.')));}catch(error){feedback.textContent=x.error+': '+error.message;}finally{button.disabled=false;}};financial.append(button);}
    for(const item of outbox.items||[]){if(item.state!=='uncertain'||item.provider_reference)continue;
      const order=item.operation_id.split(':').slice(2).join(':');const form=document.createElement('form'),label=document.createElement('label'),input=document.createElement('input'),button=document.createElement('button');
      label.textContent=(locale()==='it'?'ID checkout del provider: ':'Provider checkout ID: ')+item.provider+' · '+order+' ';input.required=true;input.maxLength=180;input.autocomplete='off';input.setAttribute('aria-label',label.textContent);label.append(input);button.type='submit';button.textContent=locale()==='it'?'Verifica riferimento':'Verify reference';form.append(label,button);
      form.onsubmit=async event=>{event.preventDefault();if(!confirm(locale()==='it'?'Verificare questo ID con il provider e associarlo al checkout locale? Non viene eseguito alcun pagamento.':'Verify this ID with the provider and bind it to the local checkout? No payment will be executed.'))return;button.disabled=true;try{const response=await fetch('/api/admin/service-regime/recover-checkout-reference',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-MTA-Request':'1'},body:JSON.stringify({provider:item.provider,order_id:order,provider_reference:input.value.trim()})});if(!response.ok)throw Error('HTTP '+response.status);await refresh();feedback.textContent=locale()==='it'?'Riferimento verificato; il pagamento resta da riconciliare.':'Reference verified; payment remains to reconcile.';}catch(error){feedback.textContent=x.error+': '+error.message;}finally{button.disabled=false;}};financial.append(form);
    }
    const host=root.querySelector('#regimeReservations');host.replaceChildren();
    const items=Array.isArray(reservations.reservations)?reservations.reservations:[];
    if(!items.length)host.textContent=x.none;
    for(const item of items){const line=document.createElement('div');const label=document.createElement('span');label.textContent=`${item.id} (${item.source} → ${item.target}) `;const button=document.createElement('button');button.type='button';button.textContent=x.abort;
      button.disabled=reservations.integrity_verified!==true||reservations.transitioning!==true;
      button.onclick=async()=>{if(!confirm(x.confirm))return;button.disabled=true;try{const r=await fetch('/api/admin/service-regime/abort-transition-reservation',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-MTA-Request':'1'},body:JSON.stringify({transition_id:item.id,expected_revision:item.revision})});if(!r.ok)throw Error('HTTP '+r.status);await refresh();}catch(err){root.querySelector('#regimeReadiness').textContent=x.error+': '+err.message;}finally{button.disabled=false;}};
      line.append(label,button);host.append(line);}
  }catch(err){root.querySelector('#regimeReadiness').textContent=x.error+': '+err.message;root.querySelector('#regimeIssues').textContent='';root.querySelector('#regimeOutbox').textContent='';root.querySelector('#regimeReservations').replaceChildren();root.querySelector('#regimeFinance').replaceChildren();}finally{busy=false;}}
  function merchantPanel(){
    const it=locale()==='it',box=document.createElement('section');box.dataset.merchantHistory='';box.style.overflowWrap='anywhere';
    const title=document.createElement('h3');title.textContent=it?'Storico del conto PayPal':'PayPal account history';box.append(title);
    const note=document.createElement('p');note.textContent=it?'Scegli un intervallo UTC passato, massimo 31 giorni. La lettura non regola pagamenti né autorizza un cambio di regime.':'Choose a past UTC range, at most31 days. Readback never settles payments or authorizes a regime change.';box.append(note);
    const form=document.createElement('form'),fields=[];
    for(const [key,label] of [['start_date',it?'Inizio UTC':'UTC start'],['end_date',it?'Fine UTC':'UTC end']]){
      const wrap=document.createElement('label');wrap.textContent=label+' ';const input=document.createElement('input');input.type='datetime-local';input.step='1';input.required=true;input.name=key;wrap.append(input);form.append(wrap);fields.push(input);
    }
    const submit=document.createElement('button');submit.type='submit';submit.textContent=it?'Leggi storico PayPal':'Read PayPal history';form.append(submit);box.append(form);
    const view=document.createElement('button');view.type='button';view.textContent=it?'Mostra letture salvate':'Show saved readbacks';box.append(view);
    const status=document.createElement('p');status.setAttribute('role','status');status.setAttribute('aria-live','polite');box.append(status);
    const items=document.createElement('div');box.append(items);let offset=0;
    async function show(reset=true){
      if(reset){offset=0;items.replaceChildren();}
      const data=await get('/api/admin/paypal/merchant-history?offset='+offset+'&limit=10');
      if(!data.items.length&&!offset)items.textContent=it?'Nessuna lettura salvata':'No saved readbacks';
      for(const snapshot of data.items){
        const panel=document.createElement('details'),summary=document.createElement('summary');summary.textContent=snapshot.environment+' · '+snapshot.start_date+' / '+snapshot.end_date+' · '+snapshot.records;panel.append(summary);
        let rowOffset=0;const rows=document.createElement('pre'),more=document.createElement('button');rows.style.maxWidth='100%';rows.style.overflowX='auto';rows.tabIndex=0;rows.setAttribute('role','region');rows.setAttribute('aria-label',it?'Osservazioni dello storico PayPal':'PayPal history observations');more.type='button';more.textContent=it?'Carica osservazioni':'Load observations';
        more.onclick=async()=>{more.disabled=true;try{const page=await get('/api/admin/paypal/merchant-history/'+encodeURIComponent(snapshot.id)+'?offset='+rowOffset+'&limit=50');rows.textContent+=(rowOffset?'\n':'')+JSON.stringify(page.items,null,2);rowOffset+=page.items.length;more.hidden=rowOffset>=page.total;}catch(e){status.textContent=(it?'Lettura non disponibile: ':'Readback unavailable: ')+e.message;}finally{more.disabled=false;}};
        panel.append(rows,more);items.append(panel);
      }
      offset+=data.items.length;view.hidden=offset>=data.total;
    }
    view.onclick=async()=>{view.disabled=true;try{await show(offset===0);}catch(e){status.textContent=t().error+': '+e.message;}finally{view.disabled=false;}};
    form.onsubmit=async event=>{event.preventDefault();if(submit.disabled)return;
      if(!confirm(it?'Leggere due volte lo storico autenticato del conto PayPal senza modificare denaro?':'Read authenticated PayPal account history twice without changing money?'))return;
      const values=fields.map(input=>input.value+(input.value.length===16?':00':'')+'Z');submit.disabled=true;fields.forEach(input=>input.disabled=true);
      try{const response=await fetch('/api/admin/paypal/merchant-history',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-MTA-Request':'1'},body:JSON.stringify({start_date:values[0],end_date:values[1],confirm:true})});if(!response.ok)throw Error('HTTP '+response.status);const receipt=await response.json();await show(true);status.textContent=(it?'Osservazioni salvate, non regolate: ':'Observations saved, not settled: ')+receipt.records;}
      catch(e){status.textContent=t().error+': '+e.message;}finally{submit.disabled=false;fields.forEach(input=>input.disabled=false);view.hidden=false;}
    };
    root.append(box);
  }
  frame();merchantPanel();refresh();window.mtaRefreshServiceRegime=refresh;
})();
