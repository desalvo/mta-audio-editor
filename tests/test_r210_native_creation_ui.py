"""Exercise the actual creation JS across save/HTTP/load failures and retries."""
import subprocess
import pytest
from test_r210_decimal_bpm_shortcuts import function


@pytest.mark.parametrize('failure',['bind','create','load','picker','cancel','web'])
@pytest.mark.parametrize('language',['en','it'])
def test_native_creation_errors_are_visible_and_retry_resumes(failure,language):
    setup=r'''
const assert=require('assert/strict');
let projectCreationPending=false,pendingNativeProjectCreation=null,pendingNewProjectPath=null,current=null;
const currentUser={native_single_user:FAILURE!=='web'};
let selectedTrackId=null,choices=0,posts=0,binds=0,loads=0,closes=0,rendered=0,fail=true;
const status={hidden:true,textContent:'',setAttribute(k,v){this[k]=v}};
const button={disabled:false,isConnected:true};
const elements={'#newProjectTitle':{value:'Test'},'#newProjectTarget':{value:'DAW'},'#newProjectSampleRate':{value:'48000'},'#createProjectButton':button,'#newProjectStatus':status};
const $=s=>elements[s];const tr=(en,it)=>LANG==='it'?it:en;const trDynamic=s=>s;
const bridge={choose_project_save_path:async()=>{choices++;return FAILURE==='cancel'?{ok:false,cancelled:true}:FAILURE==='picker'&&fail?{ok:false,cancelled:false,error:'Picker failed'}:{ok:true,cancelled:false,path:'C:\\Progetti caffè\\Test.maeprojz'}},bind_project_path:async()=>{binds++;if(FAILURE==='bind'&&fail)throw Error('Access denied');return {ok:true}}};
async function waitForNativeApi(){return bridge}async function prepareProjectLeave(){return true}
function appDisplayPreference(){return false}function toast(){}
function closeUtilityModal(){closes++}function rememberRecentProject(){}function resetProjectUiForOpen(){}function resetSessionHistory(){}function render(){rendered++}async function refresh(){}function schedulePlaybackPrewarm(){}function focusProjectWorkspace(){}
async function api(url,opt){if(opt?.method==='POST'){posts++;if(FAILURE==='create'&&fail)throw Error('HTTP create failed');return {id:'created'}}loads++;if(FAILURE==='load'&&fail)throw Error('HTTP load failed');return {id:'created',tracks:[]}}
'''
    check=r'''
(async()=>{
 await createProjectFromDialog();assert.equal(projectCreationPending,false);assert.equal(button.disabled,false);
 if(FAILURE==='cancel'){assert.equal(posts,0);assert.equal(binds,0);assert.equal(status.hidden,true);assert.equal(pendingNativeProjectCreation,null);return}
 if(FAILURE==='web'){assert.equal(choices,0);assert.equal(closes,1);assert.equal(current.id,'created');return}
 assert.equal(current,null);assert.equal(closes,0);assert.equal(status.hidden,false);assert.equal(status.role,'alert');assert.ok(status.textContent.startsWith(LANG==='it'?'Creazione del progetto fallita:':'Project creation failed:'));
 assert.equal(posts,FAILURE==='picker'?0:1);assert.equal(choices,1);
 fail=false;await createProjectFromDialog();
 assert.equal(current.id,'created');assert.equal(closes,1);assert.equal(rendered,1);assert.equal(pendingNativeProjectCreation,null);assert.equal(pendingNewProjectPath,null);
 assert.equal(choices,FAILURE==='picker'?2:1);assert.equal(posts,FAILURE==='create'?2:1);assert.equal(binds,FAILURE==='bind'?2:1);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    source=f"const FAILURE={failure!r},LANG={language!r};\n"+setup+'\n'+function('setNewProjectStatus')+'\n'+function('createProjectFromDialog')+check
    subprocess.run(['node','-e',source],check=True)
