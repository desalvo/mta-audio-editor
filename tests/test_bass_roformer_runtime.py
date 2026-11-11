"""Synthetic process/DSP contracts only; never certify neural separation quality."""
import json
import os
from pathlib import Path
import sys
import threading

import numpy as np
import pytest
import soundfile as sf

from app import auth, bass_roformer_runtime as runtime, bass_roformer_install as installer
from app import model_license_policy as policy
from model_rights_fixtures import synthetic_review


@pytest.fixture
def adapter(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path / 'data')
    rights = tmp_path / 'rights.json'
    rights.write_text(json.dumps({runtime.POLICY: synthetic_review('free_only')}))
    monkeypatch.setattr(policy, '_path', lambda: rights)
    source = tmp_path / 'source.wav'
    samples = np.column_stack([np.sin(np.arange(4410) * .03) * .5, np.cos(np.arange(4410) * .02) * .4]).astype('float32')
    sf.write(source, samples, 44100, subtype='FLOAT')
    folder = tmp_path / 'upstream'; folder.mkdir()
    script = folder / 'inference.py'
    script.write_text('''import argparse,pathlib,soundfile as sf
p=argparse.ArgumentParser();p.add_argument('--input_folder');p.add_argument('--store_dir');a,_=p.parse_known_args()
data,rate=sf.read(pathlib.Path(a.input_folder)/'mta_input.wav',always_2d=True,dtype='float32')
out=pathlib.Path(a.store_dir)
for label in ('drums','bass','other','vocals'):sf.write(out/(label+'.wav'),data*.25,rate,subtype='FLOAT')
''')
    monkeypatch.setattr(installer, 'receipt', lambda: {'root':folder, 'python':Path(sys.executable),
        'config':folder/'model.yaml', 'checkpoint_validated':True, 'device':'cpu'})
    checkpoint = tmp_path / 'weights.ckpt'; checkpoint.touch()
    monkeypatch.setattr(runtime, 'verify_checkpoint', lambda _: checkpoint)
    return source, samples, script, rights


@pytest.mark.parametrize('model,count,names', [
    ('bs-roformer-bass',0,['bass','accompaniment']),
    ('bs-roformer-bass',2,['bass','accompaniment']),
    ('bs-roformer-4stem',0,list(runtime.LABELS)),
    ('bs-roformer-4stem',4,list(runtime.LABELS)),
])
def test_actual_child_stages_canonical_float_audio(adapter,tmp_path,model,count,names):
    source, samples, _, _ = adapter
    paths = runtime.infer(source,tmp_path/'out',model,stem_count=count)
    assert [p.stem for p in paths] == names
    for path in paths:
        data, rate = sf.read(path,always_2d=True)
        assert rate == 44100 and data.shape == samples.shape and sf.info(path).subtype == 'FLOAT'
    if model == 'bs-roformer-bass':
        bass, _ = sf.read(paths[0]); remainder, _ = sf.read(paths[1])
        np.testing.assert_allclose(bass+remainder,samples,atol=5e-8)


@pytest.mark.parametrize('count',[1,4,6,True,'2'])
def test_cardinality_never_silently_selects_demucs(count):
    with pytest.raises(ValueError): runtime.validate_options('bs-roformer-bass',count)


def test_unknown_checkpoint_cannot_use_demucs_permission(tmp_path,monkeypatch):
    monkeypatch.setattr(policy,'_path',lambda:tmp_path/'absent.json')
    assert policy.selected('demucs',{'model':'bs-roformer-bass'}) == runtime.POLICY
    with pytest.raises(policy.LicenseDenied): runtime.infer(tmp_path/'missing',tmp_path/'out')
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('bad',['short','rate','nonfinite','missing'])
def test_invalid_worker_audio_never_publishes(adapter,tmp_path,bad):
    source, _, script, _ = adapter
    extra = {'short':"data=data[:-1]",'rate':"rate=48000",'nonfinite':"data[0,0]=float('nan')",'missing':"raise SystemExit(0)"}[bad]
    text=script.read_text().replace("out=pathlib.Path(a.store_dir)",extra+"\nout=pathlib.Path(a.store_dir)")
    script.write_text(text)
    with pytest.raises(RuntimeError): runtime.infer(source,tmp_path/'out')
    assert not list((tmp_path/'out').glob('*.wav'))


def test_cancellation_never_publishes(adapter,tmp_path):
    event=threading.Event();event.set()
    with pytest.raises(RuntimeError,match='cancelled'):
        runtime.infer(adapter[0],tmp_path/'out',cancel_event=event)
    assert not list((tmp_path/'out').glob('*.wav'))


def test_revocation_during_worker_refuses_publication(adapter,tmp_path):
    source, _, script, rights = adapter
    script.write_text(script.read_text()+f"\npathlib.Path({str(rights)!r}).write_text('{{\"{runtime.POLICY}\":{{\"mode\":\"disabled\"}}}}')\n")
    with pytest.raises(policy.LicenseDenied): runtime.infer(source,tmp_path/'out')
    assert not list((tmp_path/'out').glob('*.wav'))


def test_checkpoint_integrity_requires_exact_original_bytes(tmp_path):
    path=tmp_path/'wrong.ckpt';path.write_bytes(b'wrong')
    with pytest.raises(ValueError,match='size'): runtime.verify_checkpoint(path)


def test_model_profiles_leave_standard_recommendation_unchanged():
    from app.plugins import DemucsStemSplitter
    status=DemucsStemSplitter.status()
    assert status['recommended_model']=='htdemucs_6s'
    assert {'bs-roformer-bass','bs-roformer-4stem'} <= set(status['models'])
    from app.model_selectors import stem_model,demucs_model
    assert stem_model('bs-roformer-bass')=='bs-roformer-bass'
    with pytest.raises(ValueError): demucs_model('bs-roformer-bass')


def test_registered_adapter_publishes_validated_flat_manifest(adapter,tmp_path):
    from app import ai_unified_adapter
    ai_unified_adapter.infer({'kind':'demucs','model':'bs-roformer-bass','source_audio':str(adapter[0])},tmp_path/'output.wav')
    document=json.loads((tmp_path/'output.manifest.json').read_text())
    assert {item['name'] for item in document['files']}=={'stem_bass.wav','stem_accompaniment.wav'}
    assert all((tmp_path/item['name']).is_file() for item in document['files'])


def test_interval_renders_timeline_gain_and_cuts_before_separation(tmp_path):
    from app.models import Project,Track,Clip
    project=Project(id='test',title='test',sample_rate=44100)
    source=tmp_path/'input.wav'
    sf.write(source,np.ones((44100,2),dtype='float32')*.5,44100,subtype='FLOAT')
    track=Track(id='track',name='source',filename='input.wav',duration_ms=1000,gain_db=-6,
        clips=[Clip(id='clip',source_start_ms=100,source_end_ms=700,timeline_start_ms=200)])
    out=runtime.prepare_track_source(project,track,source,tmp_path,100,500)
    data,rate=sf.read(out,always_2d=True)
    assert rate==44100 and len(data)==17640
    assert np.max(np.abs(data[:4000]))<1e-6
    assert .24 < float(np.mean(data[5000:])) < .26


@pytest.mark.parametrize('when', ['before', 'during'])
@pytest.mark.parametrize('interval', [False, True])
def test_cancelled_track_preparation_never_returns_or_starts_crop(tmp_path, monkeypatch, when, interval):
    from types import SimpleNamespace
    from app import audio_engine, separator_process
    event = threading.Event()
    calls = []
    if when == 'before': event.set()
    def render(*args, **kwargs):
        calls.append('render')
        event.set()
    monkeypatch.setattr(audio_engine, 'render_track', render)
    monkeypatch.setattr(separator_process, 'run', lambda *args, **kwargs: calls.append('crop'))
    monkeypatch.setattr(runtime.shutil, 'which', lambda _: '/usr/bin/ffmpeg')
    with pytest.raises(RuntimeError, match='cancelled'):
        runtime.prepare_track_source(SimpleNamespace(sample_rate=44100), None, tmp_path/'source',
                                     tmp_path, 0, 100 if interval else None, event)
    assert calls == ([] if when == 'before' else ['render'])


@pytest.mark.parametrize('action', ['cancel', 'revoke'])
def test_final_progress_callback_cannot_publish_after_cancellation_or_revocation(adapter, tmp_path, action):
    event = threading.Event()
    def progress(percent, text):
        if percent == 88:
            if action == 'cancel': event.set()
            else: adapter[3].write_text(json.dumps({runtime.POLICY: {'mode': 'disabled'}}))
    output = tmp_path / 'out'
    with pytest.raises((RuntimeError, policy.LicenseDenied)):
        runtime.infer(adapter[0], output, progress=progress, cancel_event=event)
    assert list(output.iterdir()) == []


@pytest.mark.parametrize('kind', ['file', 'dangling-symlink'])
def test_conflicting_second_output_leaves_no_first_output(adapter, tmp_path, kind):
    output = tmp_path / 'out'; output.mkdir()
    existing = output / 'accompaniment.wav'
    if kind == 'file': existing.write_bytes(b'keep existing audio')
    else: existing.symlink_to(tmp_path / 'absent.wav')
    with pytest.raises(ValueError, match='already exists'):
        runtime.infer(adapter[0], output)
    assert not (output / 'bass.wav').exists()
    if kind == 'file': assert existing.read_bytes() == b'keep existing audio'
    else: assert existing.is_symlink()


def test_failed_second_wav_write_never_publishes_first_output(adapter, tmp_path, monkeypatch):
    write = sf.write
    def fail(path, *args, **kwargs):
        if path.name == 'accompaniment.wav':
            raise OSError('disk full')
        return write(path, *args, **kwargs)
    monkeypatch.setattr(sf, 'write', fail)
    with pytest.raises(OSError, match='disk full'):
        runtime.infer(adapter[0], tmp_path / 'out')
    assert list((tmp_path / 'out').iterdir()) == []


@pytest.mark.parametrize('failure', ['collision', 'disk-error', 'cancel', 'revoke', 'progress'])
def test_publication_failure_rolls_back_only_its_own_outputs(adapter, tmp_path, monkeypatch, failure):
    output = tmp_path / 'out'
    event = threading.Event()
    link = os.link
    def publish(source, target):
        if target.name == 'accompaniment.wav':
            if failure == 'collision': target.write_bytes(b'concurrent owner')
            if failure == 'disk-error': raise OSError('link failed')
        link(source, target)
        if target.name == 'bass.wav' and failure == 'cancel': event.set()
        if target.name == 'accompaniment.wav' and failure == 'revoke':
            adapter[3].write_text(json.dumps({runtime.POLICY: {'mode': 'disabled'}}))
    def progress(percent, text):
        if percent == 88 and failure == 'progress': raise RuntimeError('progress failed')
    monkeypatch.setattr(os, 'link', publish)
    with pytest.raises((OSError, RuntimeError, policy.LicenseDenied)):
        runtime.infer(adapter[0], output, progress=progress, cancel_event=event)
    assert not (output / 'bass.wav').exists()
    if failure == 'collision':
        assert (output / 'accompaniment.wav').read_bytes() == b'concurrent owner'
    else:
        assert list(output.iterdir()) == []


def test_rollback_preserves_a_replaced_output(adapter, tmp_path, monkeypatch):
    output = tmp_path / 'out'
    link = os.link
    def replace(source, target):
        if target.name == 'accompaniment.wav':
            (output / 'bass.wav').unlink()
            (output / 'bass.wav').write_bytes(b'new owner')
            raise OSError('second output failed')
        link(source, target)
    monkeypatch.setattr(os, 'link', replace)
    with pytest.raises(OSError, match='second output failed'):
        runtime.infer(adapter[0], output)
    assert (output / 'bass.wav').read_bytes() == b'new owner'
    assert not (output / 'accompaniment.wav').exists()


def test_nonfinite_canonical_input_never_publishes(adapter, tmp_path, monkeypatch):
    read = sf.read
    def corrupt(path, *args, **kwargs):
        data, rate = read(path, *args, **kwargs)
        if path.name == 'mta_input.wav': data[0, 0] = np.nan
        return data, rate
    monkeypatch.setattr(sf, 'read', corrupt)
    with pytest.raises(RuntimeError, match='input contains'):
        runtime.infer(adapter[0], tmp_path / 'out')
    assert list((tmp_path / 'out').iterdir()) == []


def test_overflowing_residual_never_publishes(adapter, tmp_path, monkeypatch):
    read = sf.read
    def overflow(path, *args, **kwargs):
        data, rate = read(path, *args, **kwargs)
        if path.name == 'mta_input.wav': data[:] = np.finfo('float32').max
        elif path.name == 'bass.wav': data[:] = -np.finfo('float32').max
        return data, rate
    monkeypatch.setattr(sf, 'read', overflow)
    with pytest.raises(RuntimeError, match='accompaniment contains'):
        runtime.infer(adapter[0], tmp_path / 'out')
    assert list((tmp_path / 'out').iterdir()) == []
