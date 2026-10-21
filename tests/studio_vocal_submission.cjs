/* UI submission contract with DOM doubles; not a browser/audio inference test. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
async function verify(language){
 const nodes=new Map(),sent=[];
 const values={studioBackend:'diffsinger',studioVoice:'',studioLanguage:language,studioPronunciation:'espeak',studioPreset:'gentle',studioDynamics:'.75',studioVibrato:'18',studioGate:'1',studioVowel:'A',studioFormant:'1',studioArticulation:'1',studioStart:'100',studioEnd:'600',studioSyllables:'la'};
 const get=id=>{if(!nodes.has(id))nodes.set(id,{value:values[id]??'',checked:id==='studioAutoImport',disabled:false});return nodes.get(id)};
 const bank={dataset:{singerBank:'melody'},value:'',disabled:false};
 const dialog={dataset:{operation:'vocal-synthesis'},isConnected:true,closest:()=>null,
  querySelectorAll:selector=>selector==='[data-studio-source]:checked'?[{value:'melody'}]:selector==='[data-singer-bank]'?[bank]:[]};
 const context={window:{dispatchEvent:()=>{},mtaAiJobs:{origin:()=>{}}},
  document:{getElementById:get,querySelector:()=>dialog},current:{id:'project',tracks:[{id:'melody',name:'Voice',kind:'midi',duration_ms:600}]},
  selectedTrackId:'melody',tr:(en,it)=>en,showUtilityModal:()=>{},projectEnd:()=>600,currentExtractionRange:()=>({start_ms:100,end_ms:600}),
  clearTimeout:()=>{},setTimeout:()=>0,flushAutosave:async()=>{},MtaPreferences:{setItem:()=>{}},toast:error=>{throw Error(error)},
  CustomEvent:class{constructor(name,value){this.name=name;this.value=value}},
  api:async(url,options)=>{
   if(url==='/api/ai/studio/capabilities')return {voicebanks:[{id:'air',name:'Air',installed:false}]};
   if(options?.method==='POST'){sent.push(JSON.parse(options.body));return {job_id:'abc'}}
   return {job:{state:'running',phase:'test'}};
  }};
 vm.createContext(context);vm.runInContext(fs.readFileSync('app/static/ai_studio.js','utf8'),context);
 await context.window.openVocalSynthesis();
 assert.equal(bank.disabled,true);assert.equal(get('studioVoice').disabled,true);
 await get('studioRun').onclick();
 assert.equal(sent.length,1,'Neural backend must not require installed OddVoices banks');
 const request=sent[0];assert.equal(request.settings.backend,'diffsinger');assert.equal(request.settings.language,language);
 assert.equal(request.settings.pronunciation,'espeak');assert.equal(request.settings.expression.vibrato_cents,18);
 assert.equal(request.settings.voice_banks,undefined);assert.deepEqual(request.settings.syllables,['la']);
 assert.equal(request.start_ms,100);assert.equal(request.end_ms,600);
}
(async()=>{for(const language of ['it','en','fr'])await verify(language);process.stdout.write('3 multilingual neural UI submission contracts passed\n')})().catch(error=>{process.stderr.write(error.stack+'\n');process.exitCode=1});
