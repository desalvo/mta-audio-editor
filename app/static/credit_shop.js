/* Explicit owner checkout; one mutation remains locked across locale refreshes. */
(()=>{'use strict';
const root=document.querySelector('[data-credit-shop]');if(!root)return;
const tr=(en,it)=>window.MtaLocale?.language==='it'?it:en;
const status=root.querySelector('[role=status]'),body=root.querySelector('[data-credit-content]');
const eur=c=>new Intl.NumberFormat(window.MtaLocale?.language,{style:'currency',currency:'EUR'}).format(c/100);
const balance=micro=>new Intl.NumberFormat(window.MtaLocale?.language,{style:'currency',currency:'EUR',minimumFractionDigits:2,maximumFractionDigits:6}).format(micro/1e6);
const refresh=document.createElement('button');refresh.type='button';refresh.dataset.creditRefresh='';root.querySelector('h1').after(refresh);
let generation=0,checkoutBusy=false,catalog=null;
function node(tag,text){const x=document.createElement(tag);x.textContent=text;return x;}
function pendingText(){return tr('A payment action is in progress. Do not start another purchase.','Un’operazione di pagamento è in corso. Non avviare un altro acquisto.');}
function navigate(value,provider){const target=new URL(value),hosts=provider==='stripe'?['checkout.stripe.com']:['www.paypal.com','www.sandbox.paypal.com'];if(target.protocol!=='https:'||!hosts.includes(target.hostname)||target.username||target.password||(target.port&&target.port!=='443')||/[\s\\]/.test(value))throw Error(tr('Invalid payment URL','URL di pagamento non valido'));location.assign(target.href);}
async function api(url,method='GET',data){const r=await fetch(url,{method,credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json','X-MTA-Request':'1'},body:data?JSON.stringify(data):undefined});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:tr('Request failed','Richiesta fallita'));return d;}
async function checkout(provider,cents,requestId,serial){
 if(checkoutBusy||serial!==generation||catalog?.commercial_payments!==true)return;
 if(!confirm(tr('Continue to the payment provider for this purchase?','Continuare sul provider di pagamento per questo acquisto?')+' '+eur(cents)))return;
 checkoutBusy=true;root.setAttribute('aria-busy','true');root.querySelectorAll('button').forEach(x=>x.disabled=true);status.textContent=pendingText();let failed=false;
 try{const result=await api(provider==='stripe'?'/api/account/credits/checkout':'/api/account/paypal/checkout','POST',provider==='stripe'?{amount_cents:cents,request_id:requestId}:{kind:'credits',amount_cents:cents,request_id:requestId});
  if(serial===generation&&result.checkout_url)navigate(result.checkout_url,provider);
 }catch(e){failed=true;body.replaceChildren();status.textContent=tr('Payment outcome requires verification. Use payment history or contact the administrator. ','L’esito del pagamento deve essere verificato. Usare lo storico o contattare l’amministratore. ')+e.message;}
 finally{checkoutBusy=false;root.removeAttribute('aria-busy');refresh.disabled=false;if(!failed)await load();window.dispatchEvent(new Event('mta:payments-refresh'));}
}
async function completeExisting(order,confirmFirst=true){
 if(checkoutBusy||catalog?.commercial_payments!==true)return;
 if(confirmFirst&&!confirm(tr('Complete this existing PayPal payment? This may collect the original amount; no new checkout is created.','Completare questo pagamento PayPal esistente? Può incassare l’importo originale; non crea un nuovo checkout.')+' '+eur(order.amount_cents)))return;
 checkoutBusy=true;root.setAttribute('aria-busy','true');root.querySelectorAll('button').forEach(x=>x.disabled=true);status.textContent=pendingText();let error=null;
 try{const result=await api('/api/account/paypal/'+encodeURIComponent(order.id)+'/capture','POST',{});if(result.status!=='paid')throw Error(tr('Payment remains pending review','Pagamento ancora da verificare'));}
 catch(e){error=e;}
 finally{checkoutBusy=false;await load();root.removeAttribute('aria-busy');refresh.disabled=false;if(error){body.replaceChildren();status.textContent=error.message;}else status.textContent=tr('Payment verified','Pagamento verificato');window.dispatchEvent(new Event('mta:payments-refresh'));}
}
async function load(){
 const serial=++generation;body.replaceChildren();refresh.textContent=tr('Refresh credit availability','Aggiorna disponibilità crediti');
 if(checkoutBusy){status.textContent=pendingText();return;}
 status.textContent=tr('Loading…','Caricamento…');catalog=null;
 try{const d=await api('/api/account/credits');if(serial!==generation)return;
  if(checkoutBusy){body.replaceChildren();status.textContent=pendingText();return;}
  if(typeof d.commercial_payments!=='boolean')throw Error(tr('Service regime unavailable','Regime del servizio non disponibile'));
  catalog=d;status.textContent='';root.querySelector('h1').textContent=d.commercial_payments?tr('Credits for subscription overages','Crediti per extra quota dell’abbonamento'):tr('Historical credit balance','Saldo crediti storico');
  body.append(node('p',(d.commercial_payments?tr('Available balance: ','Saldo disponibile: '):tr('Historical balance: ','Saldo storico: '))+balance(d.credits_micro)));
  if(!d.commercial_payments||d.credit_checkout_pending){status.textContent=!d.commercial_payments?tr('Payments unavailable in the current service regime.','Pagamenti non disponibili nel regime corrente.'):tr('Resolve your pending checkout in the payment history before starting another purchase.','Risolvere il checkout in attesa nello storico prima di un nuovo acquisto.');
   const link=node('a',d.commercial_payments?tr('View payment history below','Consulta sotto lo storico pagamenti'):tr('View cost statements and voluntary transfers','Consulta consuntivi e bonifici volontari'));link.href=d.commercial_payments?'#paymentHistory':'/account#accountLimits';body.append(link);
   if(d.commercial_payments&&d.eligible&&d.paypal?.configured)for(const order of d.paypal_orders||[]){if(order.kind==='credits'&&order.status==='pending'&&order.reference_known&&!order.checkout_url){const card=node('article','');card.className='plan-card';card.append(node('p',tr('Existing PayPal checkout: ','Checkout PayPal esistente: ')+order.id+' · '+eur(order.amount_cents)));const complete=node('button',tr('Complete existing PayPal payment','Completa pagamento PayPal esistente'));complete.type='button';complete.dataset.existingPaymentCapture='';complete.onclick=()=>completeExisting(order);card.append(complete);body.append(card);}}
   return;}
  if(!d.eligible){body.append(node('p',tr('Credit purchases require an active subscription or promotion, permission to subscribe and server credits enabled. Contact the administrator if needed.','Per acquistare crediti servono un abbonamento o una promo attivi, il permesso di abbonarsi e i crediti abilitati sul server. Se necessario, contattare l’amministratore.')));const link=node('a',tr('Manage subscription','Gestione abbonamento'));link.href='/account#subscriptions';body.append(link);return;}
  if(!d.provider.configured&&!d.paypal?.configured){status.textContent=tr('Online payments are not configured. Contact the server administrator for a manual top-up.','I pagamenti online non sono configurati. Contattare l’amministratore per una ricarica manuale.');return;}
  const grid=node('div','');grid.className='plan-grid';
  for(const cents of d.denominations_cents){const card=node('article','');card.className='plan-card';card.append(node('h2',eur(cents)),node('p',(cents*10000/d.credit_value_micro).toLocaleString(window.MtaLocale?.language)+' '+tr('credits','crediti')));
   if(d.provider.configured){const button=node('button',tr('Buy with Stripe','Acquista con Stripe'));button.type='button';const requestId=crypto.randomUUID();button.onclick=()=>checkout('stripe',cents,requestId,serial);card.append(button);}
   if(d.paypal?.configured){const button=node('button',tr('Buy with PayPal','Acquista con PayPal'));button.type='button';button.className='paypal-button';const requestId=crypto.randomUUID();button.onclick=()=>checkout('paypal',cents,requestId,serial);card.append(button);}grid.append(card);
  }body.append(grid,node('p',tr('Credits only cover authorized subscription overages. Payment confirmation is verified by the server; returning from checkout alone does not top up the balance.','I crediti coprono soltanto gli extra quota autorizzati dell’abbonamento. La conferma del pagamento viene verificata dal server; il solo ritorno dal checkout non ricarica il saldo.')));
  body.append(node('p',tr('Recent purchases: ','Acquisti recenti: ')+d.orders.map(o=>eur(o.amount_cents)+' · '+({pending:tr('Pending','In attesa'),paid:tr('Paid','Pagato'),refunded:tr('Refunded','Rimborsato')}[o.status]||o.status)).join(' / ')));
 }catch(e){if(serial!==generation)return;catalog=null;body.replaceChildren();status.textContent=e.message;}
}
async function returned(){
 await load();const order=new URLSearchParams(location.search).get('paypal_order');
 if(!order||!/^[a-f0-9]{32}$/.test(order)||catalog?.commercial_payments!==true)return;
 checkoutBusy=true;root.setAttribute('aria-busy','true');body.replaceChildren();refresh.disabled=true;status.textContent=tr('Verifying PayPal payment…','Verifica pagamento PayPal…');let error=null;
 try{const receipt=await api('/api/account/paypal/'+order+'/capture','POST',{});if(receipt.status!=='paid')throw Error(tr('Payment remains pending review','Pagamento ancora da verificare'));history.replaceState(null,'',location.pathname);}
 catch(e){error=e;}
 finally{checkoutBusy=false;root.removeAttribute('aria-busy');refresh.disabled=false;await load();if(error){body.replaceChildren();status.textContent=error.message;}window.dispatchEvent(new Event('mta:payments-refresh'));}
}
refresh.onclick=load;void returned();window.addEventListener('mta:language',load);window.addEventListener('mta:payments-updated',load);
})();
