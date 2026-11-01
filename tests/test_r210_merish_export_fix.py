import json
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from app.models import Clip, ProjectExportRequest, Track


def _project(tmp_path,monkeypatch,target='MTA8'):
    from app import storage
    monkeypatch.setattr(storage,'ROOT',(tmp_path/'projects').resolve())
    p=storage.create_project('Test',target=target)
    for i,seconds in enumerate((1,2)):
        name=f't{i}.wav';rate=44100;t=np.arange(rate*seconds)/rate
        sf.write(storage.audio_path(p.id,name),.1*np.sin(2*np.pi*(440+i*100)*t),rate,subtype='PCM_24')
        p.tracks.append(Track(id=f't{i}',name=f'Track {i}',type='drums' if i==0 else 'bass',filename=name,
            duration_ms=seconds*1000,channels=1,clips=[Clip(id=f'c{i}',source_end_ms=seconds*1000)]))
    storage.save_project(p)
    return p


@pytest.mark.parametrize('target',['MTA8','MTA16'])
def test_configured_export_uses_mta_extension_for_both_profiles(tmp_path,monkeypatch,target):
    from app import main
    p=_project(tmp_path,monkeypatch,target)
    req=ProjectExportRequest(format='mta',filename='new song',mta_device_profile='merish5_xynthia2' if target=='MTA8' else 'auto')
    path,filename,mime,actual=main._render_configured_project_export(p.id,req)
    assert path.suffix=='.mta' and filename=='new song.mta' and mime=='application/octet-stream' and actual=='mta'
    assert path.exists()


def test_merish_mta8_has_eight_equal_cbr_stereo_streams(tmp_path,monkeypatch):
    from app import storage
    from app.codec import export_mta
    from app.mta_reverse import deobfuscate_media_copy
    p=_project(tmp_path,monkeypatch)
    result=tmp_path/'result.mta';export_mta(p,result,profile='merish5_xynthia2')
    decoded=tmp_path/'result.mka';deobfuscate_media_copy(result,decoded)
    raw=subprocess.check_output(['ffprobe','-v','error','-show_streams','-count_packets','-of','json',str(decoded)])
    streams=[s for s in json.loads(raw)['streams'] if s['codec_type']=='audio']
    assert len(streams)==8
    assert all(s['codec_name']=='mp3' and s['sample_rate']=='44100' and s['channels']==2 for s in streams)
    assert all(s.get('bit_rate')=='320000' for s in streams)
    assert len({s['nb_read_packets'] for s in streams})==1
    assert streams[6]['tags']['title'].lower()=='melody'
    assert streams[7]['tags']['title'].lower()=='click'
    assert storage.load_project(p.id).tracks[0].duration_ms==1000


def test_native_mta_save_dialog_and_write(tmp_path,monkeypatch):
    from native.mta_audio_editor_native import NativeApi
    monkeypatch.setitem(sys.modules,'webview',types.SimpleNamespace(FileDialog=types.SimpleNamespace(SAVE='save')))
    class Window:
        def create_file_dialog(self,*args,**kwargs):
            assert kwargs['file_types']==('MTA (*.mta)',)
            return str(tmp_path/'test')
    api=NativeApi();api.window=Window()
    result=api.choose_export_save_path('test','mta')
    assert result['ok'] and result['path'].endswith('.mta')
    assert api.save_generated_file_to_path(result['path'],'YQ==')['ok']
    assert Path(result['path']).read_bytes()==b'a'
