/* Native whole-window page zoom. Browser sessions retain browser zoom controls. */
(() => {
  'use strict';
  const levels=[50,67,75,80,90,100,110,125,150,175,200];
  let bridge=null, options={}, percent=100, ready=false, chain=Promise.resolve();
  const root=()=>document.getElementById('nativeUiZoomControls');
  const it=()=>typeof options.language==='function'&&options.language()==='it';
  function render(){
    const host=root();if(!host)return;
    host.hidden=!ready;
    const label=it()?'Zoom interfaccia':'Interface zoom';
    host.setAttribute('aria-label',label);
    host.innerHTML=`<span>${label}</span><div class="native-ui-zoom-buttons"><button type="button" data-zoom="out" aria-label="${it()?'Riduci interfaccia':'Zoom out interface'}" title="Ctrl/Cmd −">−</button><output aria-live="polite">${percent}%</output><button type="button" data-zoom="in" aria-label="${it()?'Ingrandisci interfaccia':'Zoom in interface'}" title="Ctrl/Cmd +">+</button><button type="button" data-zoom="reset" title="Ctrl/Cmd 0">100%</button></div>`;
    host.querySelector('[data-zoom="out"]').onclick=()=>change(-1);
    host.querySelector('[data-zoom="in"]').onclick=()=>change(1);
    host.querySelector('[data-zoom="reset"]').onclick=()=>change(0);
    host.querySelector('[data-zoom="out"]').disabled=percent<=50;
    host.querySelector('[data-zoom="in"]').disabled=percent>=200;
  }
  function change(direction){
    if(!ready)return Promise.resolve(false);
    chain=chain.then(async()=>{
      const next=direction===0?100:direction>0?(levels.find(x=>x>percent)||200):([...levels].reverse().find(x=>x<percent)||50);
      if(next===percent)return true;
      const result=await bridge.set_ui_zoom(next);
      if(!result?.ok)throw new Error(result?.error||'Interface zoom failed');
      percent=result.zoom_percent;render();
      window.requestAnimationFrame(()=>window.dispatchEvent(new Event('resize')));
      return true;
    }).catch(error=>{options.notify?.(it()?'Impossibile modificare lo zoom dell’interfaccia. Riprova.':'Unable to change interface zoom. Please try again.');return false});
    return chain;
  }
  async function init(api, config={}){
    if(ready)return true;
    if(!api?.restore_ui_zoom||!api?.set_ui_zoom)return false;
    bridge=api;options=config;
    try{
      const result=await bridge.restore_ui_zoom();
      if(!result?.ok)throw new Error(result?.error||'Interface zoom unavailable');
      percent=result.zoom_percent;ready=true;render();
      document.addEventListener('keydown',event=>{
        if(!(event.ctrlKey||event.metaKey)||event.altKey)return;
        const direction=['+','='].includes(event.key)?1:event.key==='-'?-1:event.key==='0'?0:null;
        if(direction===null)return;
        event.preventDefault();event.stopImmediatePropagation();change(direction);
      },true);
      return true;
    }catch(error){options.notify?.(it()?'Zoom dell’interfaccia non disponibile in questo motore nativo.':'Interface zoom is unavailable in this native engine.');return false}
  }
  window.mtaNativeZoom={init,step:change,reset:()=>change(0),get percent(){return percent}};
})();
