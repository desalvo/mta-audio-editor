const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('app/static/app.js','utf8');
const piece=(a,b)=>src.slice(src.indexOf(a),src.indexOf(b,src.indexOf(a)));
const heads=[{id:'head-a',classList:{remove(...x){this.removed=x}}},{id:'head-b',classList:{remove(...x){this.removed=x}}}],lanes=[{classList:{remove(...x){this.removed=x}}}];
const ctx={console,Set,Math,Number,String,Array,JSON,HTMLInputElement:class{},HTMLTextAreaElement:class{},HTMLSelectElement:class{},
 current:{target:'MTA16',tracks:[{id:'a',name:'A',type:'melody',volume_db:0,clips:[{id:'1'}]},{id:'b',name:'B',type:'click',volume_db:0,clips:[{id:'2'}]}]},
 selectedTrackId:'a',selectedTrackIdSet:new Set(['a']),selectedTimelineSegments:new Set(),timelineSelectionOnly:false,
 MtaTimelineRules:{key:(t,c)=>t.id+':'+c.id},$$:s=>s==='.track-head'?heads:lanes,$:()=>({focus(){ctx.focused=true}}),updateSel(){},paintSegmentSelection(){},
 TRACK_COLORS:['#123456'],trackHeightPx:()=>78,esc:s=>String(s??''),tr:(a,b)=>b,trackDelayUnit:()=> 'ms',trackDelayInputValue:()=>0,delayUnitOptions:()=>'<option>ms</option>',projectIsMta:()=>ctx.current.target.startsWith('MTA'),mtaSlotLimit:()=>16,metronomeTrackModeLabel:()=> 'Metronomo',
};vm.createContext(ctx);
vm.runInContext(piece('function selectAllTimelineSegments(){','function trackHeightPx('),ctx);ctx.selectAllTimelineSegments();
assert.deepStrictEqual([...ctx.selectedTimelineSegments].sort(),['a:1','b:2']);assert.strictEqual(ctx.selectedTrackIdSet.size,0);assert.strictEqual(ctx.selectedTrackId,null);assert(ctx.timelineSelectionOnly&&ctx.focused);assert(heads.every(h=>h.classList.removed.includes('selected')));
vm.runInContext(piece('function trackHead(t,i){','function closeTrackContextMenu()'),ctx);
for(const [i,t] of ctx.current.tracks.entries()){const html=ctx.trackHead(t,i),row=html.slice(html.indexOf('class="track-delay-row'),html.indexOf('</div>',html.indexOf('class="track-delay-row')));assert(row.includes('track-mta-slot'));assert(row.indexOf('track-mta-slot')<row.indexOf('track-delay-'+t.id));assert(row.includes(`setTrackMtaSlot('${t.id}'`));}
ctx.current.target='DAW';assert(!ctx.trackHead(ctx.current.tracks[0],0).includes('track-mta-slot'));
const listenerStart=src.indexOf("window.addEventListener('keydown',e=>{",src.indexOf('window.addEventListener(\'pointerdown\',e=>{'));const listenerEnd=src.indexOf('\n},true);',listenerStart)+9;assert(listenerStart>=0&&listenerEnd>listenerStart);
const pane={closest:s=>s==='#timelinePane'?pane:null};Object.assign(ctx,{window:{addEventListener:(type,cb)=>ctx.listener=cb},document:{activeElement:pane,body:{},querySelector:()=>null},handleBounceShortcut:()=>false,handleGeneratedTrackShortcut:()=>false,timelineTool:'select',selectedSegmentItems:()=>[{track:{},clip:{}}],pxPerSec:100,playCursorMs:1000,goToTimestamp:n=>ctx.seek=n,moveSelectedSegments:n=>ctx.move=n,closeTrackContextMenu(){},MtaTimelineRules:{step:()=>100,start:()=>0}});
vm.runInContext(src.slice(listenerStart,listenerEnd),ctx);function key(k,shift=false){let prevented=false;ctx.listener({key:k,target:pane,shiftKey:shift,preventDefault(){prevented=true},stopPropagation(){}});assert(prevented)}
key('ArrowRight');assert.strictEqual(ctx.seek,1040);assert.strictEqual(ctx.move,undefined);key('ArrowLeft',true);assert.strictEqual(ctx.move,-10);
console.log('timeline selection, slot placement and keyboard navigation OK');
