/* Explicit administration navigation and semantics; no mutation permissions. */
(()=>{'use strict';
const tr=(en,it)=>(window.MtaLocale?.language||document.documentElement.lang||'en').startsWith('it')?it:en;
const main=document.querySelector('main');if(!main)return;
main.id=main.id||'adminMain';main.tabIndex=-1;
const skip=document.createElement('a');skip.className='admin-skip';skip.href='#'+main.id;skip.textContent=tr('Skip to administration content','Vai al contenuto amministrativo');document.body.prepend(skip);
const tabs=document.querySelector('.settings-tabs');
if(tabs){
 tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label',tr('Administration sections','Sezioni amministrative'));
 const buttons=[...tabs.querySelectorAll('button[data-tab]')];
 const update=()=>{for(const b of buttons){const panel=document.getElementById(b.dataset.tab+'Tab'),active=b.classList.contains('active');b.id='admin-tab-'+b.dataset.tab;b.setAttribute('role','tab');b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1;if(panel){b.setAttribute('aria-controls',panel.id);panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',b.id)}}};
 for(const b of buttons){b.addEventListener('click',update);b.addEventListener('keydown',e=>{const available=buttons.filter(x=>!x.hidden&&!x.disabled),i=available.indexOf(b);let next;
  if(e.key==='ArrowRight')next=available[(i+1)%available.length];if(e.key==='ArrowLeft')next=available[(i-1+available.length)%available.length];if(e.key==='Home')next=available[0];if(e.key==='End')next=available.at(-1);if(next){e.preventDefault();next.click();next.focus()}})}update();
}
function semantics(){
 for(const region of document.querySelectorAll('.table-scroll,.scroll,pre,#readiness,#agent,#usage,.dump-options,.aj-scroll')){
  region.tabIndex=0;region.setAttribute('role','region');
  const table=region.querySelector('table'),head=table?[...table.querySelectorAll('thead th')].map(x=>x.textContent.trim()).filter(Boolean).slice(0,4).join(' · '):'';
  const section=region.closest('section'),title=section?.querySelector('h2,h3')?.textContent.trim();
  region.setAttribute('aria-label',head?tr('Scrollable table','Tabella scorrevole')+': '+head:tr('Scrollable details','Dettagli scorrevoli')+(title?': '+title:''));
 }
}
semantics();new MutationObserver(semantics).observe(document.body,{childList:true,subtree:true,characterData:true});
window.addEventListener('mta:language',()=>{skip.textContent=tr('Skip to administration content','Vai al contenuto amministrativo');tabs?.setAttribute('aria-label',tr('Administration sections','Sezioni amministrative'));semantics()});
})();
