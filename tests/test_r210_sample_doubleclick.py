"""Double-click reuses the range captured before timeline click handlers clear it."""
import subprocess
from test_r210_decimal_bpm_shortcuts import function


def test_real_doubleclick_uses_preclick_range():
    setup=r'''const assert=require('assert/strict');let sampleEditor=null,sampleEditorRangeHint=null,sampleEditorPreviewAbort=null,audioCtx={decodeAudioData:async()=>({length:10000,numberOfChannels:1,getChannelData(){return new Float32Array(10000)}})};let sel={a:1000,b:2000};const pxPerSec=100,current={id:'p'},performance={now:()=>100},window={},URL={revokeObjectURL(){}},elements={'#timelinePane':{scrollLeft:0,getBoundingClientRect(){return {left:0}}},'#sampleCanvas':{clientWidth:164},'#sampleAudio':{}};
    function $(id){return elements[id]}function tr(en){return en}function selectedTrackIds(){return ['track']}function esc(value){return value}function showUtilityModal(){}function seDefaults(){return {}}function seEffectHtml(){return ''}function seBind(){}function seDraw(){}function toast(message){throw Error(message)}
    async function api(){return {sample_rate:1000,total_samples:10000,audio_url:'/audio',name:'Track',timeline_offset_ms:0}}
    async function fetch(){return {ok:true,arrayBuffer:async()=>new ArrayBuffer(1)}};
    '''
    check=r'''(async()=>{rememberSampleRange({button:0,clientX:150,target:{closest(){return {dataset:{track:'track'}}}}});assert.deepEqual(sampleEditorRangeHint.range,{a:1000,b:2000});sel={a:0,b:0};await openSampleEditor('track',false,true);assert.deepEqual(sampleEditor.scope,{start:1000,end:2000,restricted:true});assert.equal(elements['#sampleAudio'].src,'/audio?start_sample=1000&end_sample=2000');sampleEditor=null;await openSampleEditor('track',false,false);assert.deepEqual(sampleEditor.scope,{start:0,end:10000,restricted:false});console.log('Double-click retains the selected range after the first click resets timeline selection; normal open does not reuse a stale hint.')})().catch(e=>{console.error(e);process.exitCode=1});'''
    code=setup+'\n'+'\n'.join(function(n) for n in ('rememberSampleRange','seScope','seInitialWindow','seEnvelope','openSampleEditor'))+'\n'+check
    subprocess.run(['node','-e',code],check=True)
