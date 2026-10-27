const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(require('path').join(__dirname,'../app/static/app.js'),'utf8');
const begin=source.indexOf('async function fetchReadWithBusyRetry('),api=source.indexOf('async function api(url,opt={})',begin);
const helpers=source.slice(begin,source.indexOf('\n',api));
function context(fetch){
  const ctx={fetch,Response,document:{querySelector:()=>null},window:{},setTimeout:f=>{f();return 1},clearTimeout(){},console};
  vm.createContext(ctx);vm.runInContext(helpers,ctx);return ctx;
}
const busy=()=>new Response(JSON.stringify({code:'database_busy',detail:'Busy',retryable:true}),{status:503,headers:{'content-type':'application/json','retry-after':'1'}});
(async()=>{
  let calls=[];let c=context(async(url,opts)=>{calls.push([url,opts?.method||'GET']);return calls.length<3?busy():Response.json({ok:true})});
  assert.equal((await c.api('/api/media-jobs/original')).ok,true);
  assert.deepEqual(calls.map(x=>x[0]),Array(3).fill('/api/media-jobs/original'));
  for(const method of ['POST','PUT','DELETE']){
    calls=[];c=context(async(url,opts)=>{calls.push([url,opts.method]);return busy()});
    await assert.rejects(c.api('/mutation',{method}),e=>e.status===503&&e.code==='database_busy'&&!e.retryableRead);
    assert.equal(calls.length,1);
  }
  calls=[];c=context(async()=>{calls.push(1);return new Response('Internal server error',{status:500})});
  await assert.rejects(c.api('/api/session'));assert.equal(calls.length,1);
  calls=[];c=context(async()=>{calls.push(1);return new Response('{"code":"service_state_unavailable"}',{status:503})});
  await assert.rejects(c.api('/api/session'));assert.equal(calls.length,1);
  calls=[];c=context(async()=>{calls.push(1);return busy()});
  await assert.rejects(c.api('/api/media-jobs/original'),e=>e.retryableRead);assert.equal(calls.length,4);
  // Run the actual polling function. A transient read error retains the job
  // and origin;neither terminal callbacks nor a new export submission run.
  const poll=source.slice(source.indexOf('async function pollMediaJob('),source.indexOf('async function blobToDataUrl('));
  const timers=[],finished=[],done=[],notices=[];let first=true;
  const original={isConnected:true,closest:()=>false};
  const ctx={api:async url=>{assert.equal(url,'/api/media-jobs/original');if(first){first=false;const e=Error('busy');e.retryableRead=true;throw e}return {status:'completed',result:{download_url:'/original.mp3'}}},
    window:{mtaAiJobs:{origin(){},terminal(){},handled(){}}},$:()=>({firstElementChild:original}),
    mediaProgressTimer:null,mediaPartialText:()=>'',showMediaProgress(){},setMobileBusy(){},toast:x=>notices.push(x),tr:x=>x,
    clearTimeout(){},setTimeout:f=>{timers.push(f);return timers.length}};
  vm.createContext(ctx);vm.runInContext(poll,ctx);
  await ctx.pollMediaJob('original','MP3',j=>done.push(j),j=>finished.push(j),original);
  assert.equal(timers.length,1);assert.equal(done.length,0);assert.equal(finished.length,0);assert.equal(notices.length,0);
  await timers.shift()();assert.equal(done.length,1);assert.equal(finished.length,1);
  // Execute the shipped download too: a completed export whose authenticated
  // download is busy stays attached to its original job and saves exactly once.
  const download=source.slice(source.indexOf('async function downloadWithProgress('),source.indexOf('\nasync function addTrack('));
  const saved=[],terminal=[],completion=[],next=[];let busyDownload=true,downloadCalls=0;
  const dc={...ctx,Response,Blob,
    api:async url=>{assert.equal(url,'/api/media-jobs/export-original');return {status:'completed',result:{download_url:'/original.mp3'}}},
    window:{mtaAiJobs:{origin(){},terminal:id=>terminal.push(id),handled(){}}},
    isMobileClient:()=>false,$:()=>({firstElementChild:original,classList:{add(){}}}),
    fetchReadWithBusyRetry:async url=>{assert.equal(url,'/original.mp3');downloadCalls++;if(busyDownload){busyDownload=false;return busy()}return new Response(new Uint8Array([1,2,3]),{headers:{'content-type':'audio/mpeg'}})},
    saveGeneratedBlob:async blob=>saved.push(await blob.arrayBuffer()),
    setTimeout:f=>{next.push(f);return next.length}};
  vm.createContext(dc);vm.runInContext(helpers+poll+download,dc);
  // Keep the controlled read boundary while using production API error parsing.
  dc.fetchReadWithBusyRetry=async url=>{assert.equal(url,'/original.mp3');downloadCalls++;if(busyDownload){busyDownload=false;return busy()}return new Response(new Uint8Array([1,2,3]),{headers:{'content-type':'audio/mpeg'}})};
  dc.api=async url=>{assert.equal(url,'/api/media-jobs/export-original');return {status:'completed',result:{download_url:'/original.mp3'}}};
  await dc.pollMediaJob('export-original','MP3',j=>dc.downloadWithProgress(j.result.download_url,'original.mp3','MP3'),j=>completion.push(j),original,true);
  assert.equal(saved.length,0);assert.equal(terminal.length,0);assert.equal(completion.length,0);assert.equal(next.length,1);
  await next.shift()();assert.equal(downloadCalls,2);assert.equal(saved.length,1);assert.equal(saved[0].byteLength,3);
  assert.deepEqual(terminal,['export-original']);assert.equal(completion.length,1);
  // A general completion callback may have performed writes before a later
  // read fails. It must never be replayed through the export-only opt-in.
  let writes=0;next.length=0;
  await dc.pollMediaJob('export-original','Import',()=>{writes++;const e=Error('busy after mutation');e.retryableRead=true;throw e},null,original);
  assert.equal(writes,1);assert.equal(next.length,0);
  console.log('Read retry,mutation no-replay and original-job polling passed');
})().catch(e=>{console.error(e);process.exitCode=1});
