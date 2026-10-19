/* Keep unsaved projects and running jobs intact when access policy changes. */
(()=>{'use strict';let busy=false;
async function check(){if(busy||document.hidden)return;busy=true;try{
 const session=await fetch('/api/session').then(r=>r.ok?r.json():null);if(!session||session.native_single_user||session.role==='admin')return;
 const r=await fetch('/api/account/access');if(!r.ok)return;const d=await r.json();let banner=document.getElementById('resourceAccessNotice');
 if(!d.blocked){banner?.remove();return}
 if(!banner){banner=document.createElement('aside');banner.id='resourceAccessNotice';banner.setAttribute('role','alert');Object.assign(banner.style,{position:'fixed',top:'0',left:'0',right:'0',zIndex:'100000',padding:'14px',background:'#653617',color:'#fff',textAlign:'center'});document.body.append(banner)}
 const it=(window.MtaLocale?.language||session.effective_language)==='it';banner.replaceChildren(document.createTextNode(it?'Per nuovi lavori serve un abbonamento attivo. I job in corso proseguono. ':'New work requires an active subscription. Running jobs continue. '));const a=document.createElement('a');a.href='/account#subscriptions';a.target='_blank';a.rel='noopener';a.textContent=it?'Abbonamenti e crediti':'Subscriptions and credits';a.style.color='#fff';banner.append(a);
}catch(_){}finally{busy=false}}
void check();setInterval(check,15000);document.addEventListener('visibilitychange',check);window.addEventListener('focus',check);
})();
