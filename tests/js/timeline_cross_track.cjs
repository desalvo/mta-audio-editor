'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('app/static/app.js','utf8');
const part=(a,b)=>source.slice(source.indexOf(a),source.indexOf(b,source.indexOf(a)));
const handlers=new Map(),cls={toggle(){},remove(){},add(){}};
const project={id:'p',target:'DAW',tracks:[{id:'a',name:'A',filename:'one.wav',clips:[{id:'one',source_start_ms:0,source_end_ms:500,timeline_start_ms:1000}]},{id:'b',name:'B',filename:'two.wav',clips:[]}],clip_library:[{id:'asset',name:'Original',filename:'one.wav',duration_ms:2000}]};
const c={console,Set,Math,Number,String,Array,JSON,Promise,setTimeout,clearTimeout,current:structuredClone(project),timelineTool:'select',timelineClipboard:{parts:[{track_id:'a',filename:'one.wav',source_start_ms:0,source_end_ms:500,offset_ms:0}]},selectedTrackId:null,selectedTrackIdSet:new Set(),selectedTimelineSegments:new Set(['a:one']),timelineSelectionOnly:true,pxPerSec:100,playCursorMs:4000,sel:{a:0,b:0},CSS:{escape:x=>x},MtaTimelineRules:require('../../app/static/timeline_rules.js'),$$:()=>[],$:()=>({scrollLeft:0,focus(){},getBoundingClientRect:()=>({left:0})}),trackDelayMs:t=>t?.delay_ms||0,document:{body:{classList:cls},querySelector:()=>null,querySelectorAll:()=>[],elementFromPoint:()=>({closest:()=>({dataset:{track:'b'}})})},window:{addEventListener:(n,f)=>handlers.set(n,f),removeEventListener:n=>handlers.delete(n)},paintSegmentSelection(){},updateSel(){},drawWave(){},cancelTrackContextLongPress(){},goToTimestamp(){},tr:(a,b)=>b,esc:String,toast:message=>{throw Error(message)}};
c.trackById=id=>c.current.tracks.find(t=>t.id===id);c.selectedSegmentItems=()=>c.current.tracks.flatMap(track=>track.clips.filter(clip=>c.selectedTimelineSegments.has(track.id+':'+clip.id)).map(clip=>({track,clip})));
vm.createContext(c);vm.runInContext(part('let timelineTargetTrackId=null,timelineMediaBusy=false;','function copyTimelineSelection(){'),c);
vm.runInContext(part('async function pasteTimelineSelection(','function editSelectedSegments('),c);
vm.runInContext(part('function beginTimelineClipDrag(','function refreshTimelineToolControls('),c);
c.commitTimelineMedia=async(path,body)=>{c.request={path,body};return {ok:true}};
(async()=>{
 await c.pasteTimelineSelection('b');assert.equal(c.request.path,'timeline/transfer');assert.equal(c.request.body.destination_track_id,'b');assert.equal(c.request.body.parts[0].filename,'one.wav');assert.equal(c.request.body.start_ms,4000);
 c.beginTimelineClipDrag({button:0,pointerId:1,clientX:0,clientY:0,preventDefault(){},stopPropagation(){}},'a','one');
 handlers.get('pointermove')({pointerId:1,clientX:20,clientY:80,preventDefault(){}});handlers.get('pointerup')({pointerId:1,clientX:20,clientY:80});
 await Promise.resolve();assert.equal(c.request.body.action,'move');assert.equal(c.request.body.destination_track_id,'b');assert.equal(c.request.body.start_ms,1200);assert.equal(c.request.body.parts[0].clip_id,'one');assert.equal(c.request.body.parts[0].expected_start_ms,1000);
 await c.insertProjectFileIntoTrack('b','asset',3000);assert.equal(c.request.body.parts[0].filename,'one.wav');assert.equal(c.request.body.parts[0].source_end_ms,2000);assert.equal(c.request.body.start_ms,3000);
 assert(c.timelineCreationMenu('a').includes("createEmptyTimelineTrack('audio','a')"));assert(!c.timelineCreationMenu().includes("createEmptyTimelineTrack('midi'"));c.current.target='DAW_MIDI';assert(c.timelineCreationMenu().includes("createEmptyTimelineTrack('midi'"));
 // Exercise publication history with the production commit helper, then actual undo/redo.
 Object.assign(c,{autosaveBusy:false,autosaveTimer:null,autosaveQueued:false,projectDirty:false,undoStack:[],redoStack:[],projectSnapshot:()=>structuredClone(c.current),flushAutosave:async()=>{},syncNativeProjectFile:async()=>{},persistCurrentProject:async()=>{},ensureSessionHistory(){},checkpointHistory(){},showUtilityModal(){},closeUtilityModal(){},render(){},updateEditActionState(){},timingAudioChanged:ids=>c.invalidated=[...ids]});
 const after=structuredClone(c.current);after.tracks[1].filename='packed.wav';after.tracks[1].clips=[{id:'new',source_start_ms:0,source_end_ms:500,timeline_start_ms:0}];after.clip_library.push({id:'packed',filename:'packed.wav'});
 c.api=async()=>({project:after,track_id:'b',clip_ids:['new'],changed_track_ids:['a','b']});
 vm.runInContext(part('async function commitTimelineMedia(','async function createEmptyTimelineTrack('),c);
 await c.commitTimelineMedia('timeline/transfer',{});assert.equal(c.current.tracks[1].filename,'packed.wav');assert.equal(c.undoStack.length,1);assert(c.undoStack[0].clip_library.some(x=>x.id==='packed'));assert.deepEqual(c.invalidated,['a','b']);assert.equal(c.selectedTrackIdSet.size,0);assert(c.selectedTimelineSegments.has('b:new'));
 c.toast=()=>{};vm.runInContext(part('async function restoreHistorySnapshot(','function editTrackIds()'),c);
 await c.undoEdit();assert.equal(c.current.tracks[1].filename,'two.wav');assert(c.current.clip_library.some(x=>x.filename==='packed.wav'));await c.redoEdit();assert.equal(c.current.tracks[1].filename,'packed.wav');assert.equal(c.current.tracks[1].clips[0].id,'new');
 console.log('paste, pointer transfer, project insertion, creation menu and undo/redo OK');
})().catch(e=>{console.error(e);process.exitCode=1});
