/* DB is authoritative; reads are synchronous in memory, writes are lazy patches. */
(()=>{'use strict';
const original=window.localStorage,seed=JSON.parse(document.getElementById('mtaPreferenceSeed')?.textContent||'{"values":{}}'),cacheKey='mta.pending-preferences.'+seed.owner;
let values={...seed.values},pending={},inflight={},timer=null,maxTimer=null,busy=false,retry=1000;
// A native profile has one local identity. Migrate its known presentation
// preferences once; never copy unscoped legacy data into a server account.
if(seed.owner==='native'&&!values['mta.preferences.db-migrated.v1'])try{
 const keys=['mta.stem.target','mta.percussion.method','mtaStemCount','mtaStemExecution','mta.sidebar.collapsed.v1','mta.chordExtractionSettings.v1','mta.singer.model','mta.singer.target','mta.singer.count','mta.showPreviousNextChords','mta.showPreviousNextLyrics','mta.useFlacStorage'];
 for(let i=0;i<original.length;i++){const key=original.key(i);if(key?.startsWith('mta.midi.devices.local.'))keys.push(key)}
 for(const key of keys){const value=original.getItem(key);if(value!==null&&!Object.hasOwn(values,key))pending[key]=value}
 pending['mta.preferences.db-migrated.v1']='true';Object.assign(values,pending);
}catch{}
if(seed.owner)try{pending={...pending,...JSON.parse(original.getItem(cacheKey)||'{}')};Object.assign(values,pending);for(const [key,value]of Object.entries(pending))if(value===null)delete values[key]}catch{}
function durable(){try{original.setItem(cacheKey,JSON.stringify({...inflight,...pending}))}catch{}}
function schedule(){clearTimeout(timer);timer=setTimeout(()=>void flush(),800);if(!maxTimer)maxTimer=setTimeout(()=>void flush(),4000)}
async function flush(keepalive=false){
 clearTimeout(timer);timer=null;clearTimeout(maxTimer);maxTimer=null;
 if(!seed.owner||busy||!Object.keys(pending).length)return;
 busy=true;const patch=Object.fromEntries(Object.entries(pending).slice(0,128));for(const key of Object.keys(patch))delete pending[key];inflight=patch;durable();
 try{const response=await fetch('/api/account/preferences',{method:'PATCH',headers:{'Content-Type':'application/json','X-MTA-Request':'1'},body:JSON.stringify({values:patch}),keepalive});if(!response.ok)throw Error('Preferences: '+response.status);retry=1000}
 catch{pending={...patch,...pending};durable();clearTimeout(timer);timer=setTimeout(()=>void flush(),retry);retry=Math.min(30000,retry*2)}
 finally{inflight={};durable();busy=false;if(Object.keys(pending).length&&!timer)schedule()}
}
window.MtaPreferences={
 getItem:key=>Object.hasOwn(values,String(key))?values[String(key)]:null,
 setItem(key,value){key=String(key);value=String(value);if(!/^[A-Za-z0-9_.:/-]{1,240}$/.test(key)||['__proto__','constructor','prototype'].includes(key)||new TextEncoder().encode(value).length>32768)throw Error('Invalid application preference');if(values[key]===value)return;values[key]=value;pending[key]=value;durable();schedule()},
 removeItem(key){key=String(key);if(['__proto__','constructor','prototype'].includes(key))return;delete values[key];pending[key]=null;durable();schedule()},
 flush,
 get pending(){return Object.keys(pending).length},
};
if(Object.keys(pending).length)schedule();
window.addEventListener('pagehide',()=>void flush(true));
window.addEventListener('online',()=>void flush());
})();
