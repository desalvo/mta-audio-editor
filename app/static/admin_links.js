/* Administrative email links select a page; actions still require UI confirmation. */
(()=>{'use strict';
const params=new URLSearchParams(location.search),tabs=new Set(['web','storage','users','smtp','models','aiQueue','diagnostics','legal']);
const section=params.get('section'),uid=params.get('user'),job=params.get('job');
function focus(){
 if(!['pending','archives','users'].includes(section))return;
 const hosts=section==='archives'?['accountArchivesBody']:section==='pending'?['accountPendingBody','usersBody']:['usersBody'];
 for(const id of hosts){const row=[...(document.getElementById(id)?.querySelectorAll('[data-user-id]')||[])].find(r=>r.dataset.userId===uid&&/^[1-9][0-9]{0,18}$/.test(uid||''));if(row){row.classList.add('admin-mail-target');row.tabIndex=-1;row.scrollIntoView({block:'center',behavior:'smooth'});row.focus({preventScroll:true});return;}}
 document.getElementById(hosts[0])?.closest('.table-scroll')?.scrollIntoView({block:'center'});
}
window.mtaAdminLinkFocus=focus;
function init(){const tab=params.get('tab');if(!tabs.has(tab))return;
 if(tab==='aiQueue'&&/^[A-Za-z0-9_-]{1,160}$/.test(job||'')){const input=document.getElementById('queueSearch');if(input)input.value=job;}
 const button=[...document.querySelectorAll('.settings-tabs button')].find(b=>b.dataset.tab===tab);button?.click();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
