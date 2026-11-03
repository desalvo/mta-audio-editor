'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('app/static/app.js','utf8');
function fn(name){const pattern=new RegExp('^(?:async )?function '+name+'\\(','m'),start=source.search(pattern);assert(start>=0,name);const rest=source.slice(start),next=rest.search(/\n(?:async )?function \w+\(/);return next<0?rest:rest.slice(0,next)}
const cls={toggle(){},add(){},remove(){}},pane={focus(){},closest:s=>s==='#timelinePane'?pane:null};
const original={id:'p',target:'DAW',tracks:[
 {id:'a',kind:'audio',filename:'a.wav',delay_ms:75,clips:[{id:'a1',source_start_ms:200,source_end_ms:2200,timeline_start_ms:300}]},
 {id:'b',kind:'audio',filename:'b.wav',delay_ms:-50,clips:[{id:'b1',source_start_ms:400,source_end_ms:2400,timeline_start_ms:200}]},
 {id:'c',kind:'audio',filename:'c.wav',delay_ms:0,clips:[{id:'c1',source_start_ms:0,source_end_ms:2000,timeline_start_ms:0}]}],clip_library:[]};
let id=0,changes=0;
const c={console,Set,Math,Number,String,Array,JSON,Promise,current:structuredClone(original),selectedTimelineSegments:new Set(['a:a1']),
 selectedTrackIdSet:new Set(['b']),selectedTrackId:'b',timelineSelectionOnly:true,projectDirty:false,timelineTool:'split',
 undoStack:[],redoStack:[],lastHistoryState:structuredClone(original),timelineClipboard:null,
 MtaTimelineRules:require('../../app/static/timeline_rules.js'),$:(s)=>s==='#timelinePane'?pane:null,$$:()=>[],
 document:{body:{classList:cls},querySelectorAll:()=>[]},trackDelayMs:t=>t.delay_ms||0,
 tr:(en,it)=>it,toast:message=>{c.message=message},render(){},markDirty(){},timingAudioChanged(){changes++},
 clipId:()=> 'new'+(++id),ensureSessionHistory(){},updateSel(){},paintSegmentSelection(){},persistCurrentProject:async()=>{},
 selectedTrackIds:()=>[...c.selectedTrackIdSet],projectSnapshot:()=>structuredClone(c.current)};
vm.createContext(c);
for(const name of ['selectedSegmentItems','splitSelectedTracksAt','timelineJoinPair','joinSelectedTimelineSegments',
 'selectAllTimelineSegments','checkpointHistory','restoreHistorySnapshot','undoEdit','redoEdit','updateEditActionState'])vm.runInContext(fn(name),c);
(async()=>{
 // Selected clips take precedence over an unrelated sidebar selection.
 c.splitSelectedTracksAt(1123);assert.equal(c.current.tracks[0].clips.length,2);assert.equal(c.current.tracks[1].clips.length,1);
 assert.equal(c.current.tracks[0].clips[0].source_end_ms,948);assert.equal(c.current.tracks[0].clips[1].timeline_start_ms,1048);
 assert.equal(c.selectedTimelineSegments.size,2);assert.equal(c.timelineJoinPair().length,2);assert.equal(changes,1);
 await c.undoEdit();assert.equal(c.current.tracks[0].clips.length,1);await c.redoEdit();assert.equal(c.current.tracks[0].clips.length,2);
 // Ctrl+A timeline selection intentionally has no selected sidebar tracks.
 c.current=structuredClone(original);c.selectedTimelineSegments.clear();c.selectAllTimelineSegments();
 assert.equal(c.selectedTrackIdSet.size,0);assert.equal(c.selectedTrackId,null);c.splitSelectedTracksAt(1123);
 assert(c.current.tracks.every(t=>t.clips.length===2));
 assert.equal(c.current.tracks[1].clips[0].source_end_ms,1373);assert.equal(c.current.tracks[1].clips[1].timeline_start_ms,1173);
 // Exact boundary: do not create zero-length clips or checkpoint a no-op.
 const before=JSON.stringify(c.current);c.splitSelectedTracksAt(1123);assert.equal(JSON.stringify(c.current),before);
 // The Unisci payload carries exact current source and timeline identities.
 c.selectedTimelineSegments=new Set(c.current.tracks[0].clips.map(x=>'a:'+x.id));
 c.commitTimelineMedia=async(path,body)=>{c.request={path,body};return {ok:true}};
 await c.joinSelectedTimelineSegments();assert.equal(c.request.path,'timeline/join');
 assert.equal(c.request.body.track_id,'a');assert.equal(c.request.body.parts.length,2);
 assert.equal(c.request.body.parts[0].expected_start_ms,375);assert.equal(c.request.body.parts[1].expected_start_ms,1123);
 // Wrong count, different tracks and gaps are visibly rejected before any API.
 c.request=null;c.selectedTimelineSegments=new Set(['a:'+c.current.tracks[0].clips[0].id,'b:'+c.current.tracks[1].clips[0].id]);
 assert.equal(c.timelineJoinPair(),null);await c.joinSelectedTimelineSegments();assert.equal(c.request,null);
 c.selectedTimelineSegments=new Set(c.current.tracks[0].clips.map(x=>'a:'+x.id));c.current.tracks[0].clips[1].timeline_start_ms++;
 assert.equal(c.timelineJoinPair(),null);c.selectedTimelineSegments.clear();assert.equal(c.timelineJoinPair(),null);
 assert(source.includes('id="toolJoin"'));assert(source.includes("set('#toolJoin',!timelineJoinPair())"));
 assert(fn('openProjectTimelineMenu').includes('splitSelectedTracksAt(playCursorMs)'));
 // Actual keyboard listener: split-tool Ctrl+A -> S without sidebar selection.
 Object.assign(c,{timelineMediaBusy:false,handleBounceShortcut:()=>false,handleGeneratedTrackShortcut:()=>false,
   HTMLInputElement:class{},HTMLTextAreaElement:class{},HTMLSelectElement:class{},
   window:{addEventListener:(name,handler)=>c.keyboard=handler},closeTrackContextMenu(){},
   playCursorMs:1123,editSelectedSegments:action=>c.editAction=action});
 c.document.querySelector=()=>null;c.document.activeElement=pane;
 const listenerStart=source.indexOf("window.addEventListener('keydown',e=>{",source.indexOf("window.addEventListener('pointerdown',e=>{"));
 const listenerEnd=source.indexOf('\n},true);',listenerStart)+9;
 vm.runInContext(source.slice(listenerStart,listenerEnd),c);
 function key(name,extra={}){let prevented=false;c.keyboard({key:name,target:pane,preventDefault(){prevented=true},stopPropagation(){},...extra});assert(prevented)}
 c.current=structuredClone(original);c.selectedTimelineSegments.clear();c.selectedTrackIdSet=new Set(['b']);c.timelineTool='split';
 key('a',{ctrlKey:true});assert.equal(c.selectedTrackIdSet.size,0);assert.equal(c.selectedTimelineSegments.size,3);
 key('s');assert(c.current.tracks.every(t=>t.clips.length===2));assert.equal(c.current.tracks[0].clips[0].source_end_ms,948);
 key('Delete');assert.equal(c.editAction,'remove');
 vm.runInContext(fn('copyTimelineSelection'),c);key('c',{ctrlKey:true});assert.equal(c.editAction,'copy');
 console.log('selected-clip split, Ctrl+A, exact offsets, undo/redo and join payload OK');
})().catch(error=>{console.error(error);process.exitCode=1});
