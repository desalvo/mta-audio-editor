(()=>{
  'use strict';
  const form=document.getElementById('mliveProfileForm'),status=document.getElementById('mliveProfileStatus');
  const file=document.getElementById('mliveImportFile'),button=document.getElementById('mliveImportButton');
  if(!form||!file||!button)return;
  function show(data){form.elements.merish_user_id.value=data.merish_user_id;form.elements.merish_syl_key.value=data.merish_syl_key;}
  async function request(url,options={}){
    const response=await fetch(url,options);
    if(!response.ok){let message='Operazione non riuscita';try{message=(await response.json()).detail||message}catch{}throw Error(message)}
    return response.json();
  }
  async function load(){try{show(await request('/api/account/m-live'));status.textContent='Impostazioni M-Live disponibili.'}catch(error){status.textContent=error.message}}
  form.addEventListener('submit',async event=>{
    event.preventDefault();const key=form.elements.merish_syl_key.value.trim().toLowerCase();
    if(!/^[0-9a-f]{512}$/.test(key)||new Set(key.match(/../g)).size!==256){status.textContent='Parametro SYL non valido: occorrono 256 byte esadecimali distinti.';return}
    try{const data=await request('/api/account/m-live',{method:'PUT',headers:{'Content-Type':'application/json','X-MTA-Request':'1'},body:JSON.stringify({merish_user_id:form.elements.merish_user_id.value.trim(),merish_syl_key:key})});show(data);status.textContent='Impostazioni M-Live salvate.'}catch(error){status.textContent=error.message}
  });
  button.addEventListener('click',()=>file.click());
  file.addEventListener('change',async()=>{
    if(!file.files?.length)return;button.disabled=true;status.textContent='Analisi metadati MTA…';
    const body=new FormData();body.append('file',file.files[0]);
    try{show(await request('/api/account/m-live/import',{method:'POST',headers:{'X-MTA-Request':'1'},body}));status.textContent='Metadati M-Live importati nel profilo.'}catch(error){status.textContent=error.message}
    finally{file.value='';button.disabled=false}
  });
  void load();
})();
