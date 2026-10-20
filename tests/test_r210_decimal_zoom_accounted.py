"""Fractional custom zoom survives the real save API and accepted usage is projected."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.models import Project


@pytest.mark.parametrize('zoom', [25, 52.5, 175.61600000000007, 666.6666666667, 1200])
def test_fractional_zoom_put_and_reopen(tmp_path, monkeypatch, zoom):
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH', 'true')
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'false')
    from app import main, storage
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    project = storage.create_project('Custom zoom')
    payload = project.model_dump(mode='json')
    payload['timeline_zoom_px_per_sec'] = zoom
    with TestClient(main.app, headers={'X-MTA-Request': '1'}) as client:
        response = client.put(f'/api/projects/{project.id}', json=payload)
        assert response.status_code == 200, response.text
        assert response.json()['timeline_zoom_px_per_sec'] == zoom
        assert client.get(f'/api/projects/{project.id}').json()['timeline_zoom_px_per_sec'] == zoom
    assert storage.load_project(project.id).timeline_zoom_px_per_sec == zoom


@pytest.mark.parametrize('zoom', [24.9, 1200.01, float('inf'), float('-inf'), float('nan')])
def test_zoom_invalid_range_and_nonfinite_rejected(zoom):
    with pytest.raises(ValidationError):
        Project(id='zoom', title='Zoom', timeline_zoom_px_per_sec=zoom)


def test_custom_zoom_js_commit_and_anchor():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for frontend behavior regression')
    js = Path('app/static/app.js').read_text()
    functions = js[js.index('function clampZoom('):js.index('function tempoRatio(')]
    harness = '''
let current={id:'zoom'}, pxPerSec=70, zoomPreviewState=null, zoomCommitSerial=0;
let uiState={},playCursorMs=0, frames=[], dirty=0;
const MIN_ZOOM_PX_PER_SEC=25,MAX_ZOOM_PX_PER_SEC=1200,DEFAULT_ZOOM_PX_PER_SEC=70;
let pane={scrollLeft:3500,clientWidth:700};
const $=s=>s==='#timelinePane'?pane:null, $$=()=>[];
const widthPx=()=>100000,projectEnd=()=>300000;
const requestAnimationFrame=f=>frames.push(f);
function render(){pane={scrollLeft:0,clientWidth:700};requestAnimationFrame(()=>pane.scrollLeft=0)}
function markDirty(){dirty++}
'''+functions+'''
const values=[];
for(const value of [175.61600000000007,52.5,666.6666666667]){
 const anchor=(pane.scrollLeft+pane.clientWidth/2)/pxPerSec;
 beginZoomPreview();previewZoom(value);commitZoom(value);
 while(frames.length)frames.shift()();
 values.push({value,saved:JSON.parse(JSON.stringify(current)).timeline_zoom_px_per_sec,
 anchor,after:(pane.scrollLeft+pane.clientWidth/2)/pxPerSec});
}
stepZoom(1);while(frames.length)frames.shift()();
console.log(JSON.stringify({values,dirty,step:current.timeline_zoom_px_per_sec}));
'''
    result = subprocess.run([node, '-e', harness], check=True, capture_output=True, text=True)
    output = json.loads(result.stdout)
    for row in output['values']:
        assert row['saved'] == row['value']
        assert row['after'] == pytest.approx(row['anchor'])
    assert output['dirty'] == 4
    assert output['step'] == pytest.approx(666.6666666667 * 1.12)
