/* Native whole-window page zoom. Browser sessions retain browser zoom controls. */
(() => {
  'use strict';
  const levels=[50,67,75,80,90,100,110,125,150,175,200];
  let bridge=null, options={}, percent=100, ready=false, chain=Promise.resolve();
  const valid=n=>Number.isInteger(n)&&n>=50&&n<=200;
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
  function enqueue(resolveNext,{afterPaint=false,force=false}={}){
    chain=chain.then(async()=>{
      if(afterPaint)await new Promise(resolve=>window.requestAnimationFrame(resolve));
      const next=resolveNext();
      if(next===percent&&!force)return true;
      const result=await bridge.set_ui_zoom(next);
      if(!result?.ok)throw new Error(result?.error||'Interface zoom failed');
      if(!valid(result.zoom_percent))throw new Error('Invalid interface zoom response');
      percent=result.zoom_percent;render();
      window.requestAnimationFrame(()=>window.dispatchEvent(new Event('resize')));
      return true;
    }).catch(error=>{options.notify?.(it()?'Impossibile modificare lo zoom dell’interfaccia. Riprova.':'Unable to change interface zoom. Please try again.');return false});
    return chain;
  }
  function change(direction){
    if(!ready)return Promise.resolve(false);
    return enqueue(()=>direction===0?100:direction>0?(levels.find(x=>x>percent)||200):([...levels].reverse().find(x=>x<percent)||50),{force:direction===0});
  }
  async function init(api, config={}){
    if(ready)return true;
    if(!api?.restore_ui_zoom||!api?.set_ui_zoom)return false;
    bridge=api;options=config;let restored=false;
    try{
      const result=await bridge.restore_ui_zoom();
      if(!result?.ok)throw new Error(result?.error||'Interface zoom unavailable');
      if(!valid(result.zoom_percent))throw new Error('Invalid interface zoom response');
      percent=result.zoom_percent;restored=true;
    }catch(error){options.notify?.(it()?'Impossibile ripristinare lo zoom. Usa i controlli Interfaccia per riprovare.':'Unable to restore interface zoom. Use the Interface controls to retry.')}
    // Keep recovery controls/shortcuts available even if restoring a saved
    // value failed while the native engine was still initializing.
    ready=true;render();
    document.addEventListener('keydown',event=>{
        if(!(event.ctrlKey||event.metaKey)||event.altKey)return;
        const direction=['+','='].includes(event.key)||event.code==='NumpadAdd'?1:event.key==='-'||event.code==='NumpadSubtract'?-1:event.key==='0'||event.code==='Numpad0'?0:null;
        if(direction===null)return;
        event.preventDefault();event.stopImmediatePropagation();change(direction);
      },true);
    // Python deliberately leaves the cold default engine untouched. Once the
    // bridge is ready and these controls have painted, synchronize 100% through
    // the GUI-thread API too: WebView2 must disable independent browser zoom
    // before keyboard shortcuts can diverge from the persisted scale. Queue it
    // before user changes, so initialization never resets a newer choice.
    if(restored&&percent===100)await enqueue(()=>percent,{afterPaint:true,force:true});
    return true;
  }
  window.mtaNativeZoom={init,step:change,reset:()=>change(0),get percent(){return percent}};
})();
