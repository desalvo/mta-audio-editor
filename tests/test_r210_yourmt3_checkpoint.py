"""Reject unreviewed pickle artifacts before any ML imports or decoding."""
from pathlib import Path
import os
import pytest
from app.studio_checkpoint import convert
from app.yourmt3_adapter import verified_runtime


def test_checkpoint_rejects_untrusted_size_and_symlink(tmp_path):
    source=tmp_path/'uploaded.ckpt';source.write_bytes(b'not a trusted checkpoint')
    with pytest.raises(ValueError,match='size'):convert(source,tmp_path/'out.safetensors')
    link=tmp_path/'linked.ckpt'
    try:link.symlink_to(source)
    except OSError:pytest.skip('Symlinks unavailable')
    with pytest.raises(ValueError):convert(link,tmp_path/'out.safetensors')
    assert not (tmp_path/'out.safetensors').exists()


def test_yourmt3_requires_operator_runtime(monkeypatch):
    monkeypatch.delenv('MTA_STUDIO_YOURMT3_RUNTIME',raising=False)
    with pytest.raises(ValueError,match='Configure'):verified_runtime()


@pytest.mark.skipif(not os.getenv('MTA_TEST_YOURMT3_AUDIO'),reason='Opt-in real model/runtime and authorized musical fixture')
def test_real_yourmt3_piano_prediction():
    from app.yourmt3_adapter import transcribe
    result=transcribe(Path(os.environ['MTA_TEST_YOURMT3_AUDIO']),{})
    notes=[n for p in result.parts for n in p.notes]
    assert {60,64,67}.issubset({n.pitch for n in notes})
    assert all(n.confidence is None and n.velocity==96 for n in notes)
    assert any(p.program==0 for p in result.parts)


def test_pinned_download_does_not_publish_corrupt_bytes(tmp_path,monkeypatch):
    import io
    import hashlib
    from scripts.install_studio_yourmt3 import download
    monkeypatch.setattr('urllib.request.urlopen',lambda *args,**kw:io.BytesIO(b'wrong'))
    target=tmp_path/'model.ckpt'
    with pytest.raises(ValueError,match='digest mismatch'):download('model.ckpt',target,5,hashlib.sha256(b'right').hexdigest())
    assert not target.exists() and not target.with_name('model.ckpt.partial').exists()


def test_routing_driver_errors_are_normalized(monkeypatch):
    import sys
    from types import SimpleNamespace
    from app.native_device_io import driver_errors
    class DriverError(Exception):pass
    monkeypatch.setitem(sys.modules,'sounddevice',SimpleNamespace(PortAudioError=DriverError))
    assert DriverError in driver_errors()


def test_offline_source_cache_has_no_network_fallback(tmp_path,monkeypatch):
    import hashlib
    from scripts.install_studio_yourmt3 import download
    def no_network(*args,**kwargs):raise AssertionError('Offline cache must not make network requests')
    monkeypatch.setattr('urllib.request.urlopen',no_network)
    cache=tmp_path/'cache';cache.mkdir();(cache/'source.py').write_bytes(b'reviewed')
    target=tmp_path/'runtime/source.py'
    download('source.py',target,8,hashlib.sha256(b'reviewed').hexdigest(),cache)
    assert target.read_bytes()==b'reviewed'
    with pytest.raises(ValueError):download('../outside.py',target,1,'0'*64,cache)


def test_frozen_harmony_never_launches_application_as_python(tmp_path,monkeypatch):
    from app import studio_catalog as catalog
    import sys
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr(sys,'_MEIPASS',str(tmp_path),raising=False)
    monkeypatch.setattr(catalog,'root',lambda:tmp_path)
    monkeypatch.setattr(catalog,'receipt',lambda:None)
    monkeypatch.delenv('MTA_AI_DEFAULT_PYTHON',raising=False)
    monkeypatch.delenv('MTA_AI_WORKER_VOCAL_HARMONY_PYTHON',raising=False)
    monkeypatch.setattr('shutil.which',lambda name:None)
    assert catalog.python_for('vocal-harmony') is None
    with pytest.raises(RuntimeError,match='Install Python'):catalog.install_basic_pitch(lambda:False,lambda phase:None)


def test_readonly_bundled_adapter_keeps_external_executable_boundary(tmp_path,monkeypatch):
    from app import ai_worker_registry as registry,studio_catalog
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','true')
    monkeypatch.setattr(studio_catalog,'available',lambda kind:True)
    monkeypatch.setattr(registry.os,'access',lambda path,mode:False)
    monkeypatch.delenv('MTA_AI_WORKER_AUDIO_TO_MIDI_EXECUTABLE',raising=False)
    assert registry.resolve_worker('audio-to-midi').name=='ai_studio_adapter.py'
    external=tmp_path/'external.py';external.write_text('raise RuntimeError("not a trusted executable")')
    monkeypatch.setenv('MTA_AI_WORKER_AUDIO_TO_MIDI_EXECUTABLE',str(external))
    assert registry.resolve_worker('audio-to-midi') is None
