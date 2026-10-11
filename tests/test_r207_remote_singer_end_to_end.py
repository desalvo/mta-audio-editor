"""Singer separation must honor its own optional native remote setting."""
from app import main
from app import native_ai_routing as routing


def test_remote_singer_inference_no_local_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', True)
    monkeypatch.setattr(routing, 'is_remote', lambda kind: kind == 'singer-separation')
    called = []
    def remote(kind, source, options):
        called.append((kind, options))
        return {'audio': {'singer_1.wav': b'RIFFxxxxWAVE', 'singer_2.wav': b'RIFFxxxxWAVE' }, 'json': {}}, 'remote-id'
    monkeypatch.setattr(main, '_native_remote_infer', remote)
    def never_local(*args, **kwargs):
        raise AssertionError('Local SAM inference must not start')
    monkeypatch.setattr(main, '_sam_audio_extract', never_local)
    source = tmp_path / 'source.wav'
    source.write_bytes(b'RIFFxxxxWAVE')
    voices = [{'id':'singer_1', 'name':'First', 'start':0.0,'end':1.0}, {'id':'singer_2','name':'Second','start':2.0,'end':3.0}]
    out = main._extract_singer_stems(source, tmp_path / 'output', 'sam-audio-small', voices)
    assert len(out) == 2 and all(p.read_bytes() == b'RIFFxxxxWAVE' for p in out)
    assert all(kind == 'singer-separation' for kind, _ in called)
    assert called[0][1]['selected'] == 'all' and len(called[0][1]['singers']) == 2


def test_remote_singer_failure_never_starts_local(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', True)
    monkeypatch.setattr(routing, 'is_remote', lambda kind: kind == 'singer-separation')
    monkeypatch.setattr(main, '_native_remote_infer', lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError('offline')))
    monkeypatch.setattr(main, '_sam_audio_extract', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('fallback')))
    import pytest
    with pytest.raises(ConnectionError, match='offline'):
        main._extract_singer_stems(tmp_path/'source.wav', tmp_path/'out', 'sam-audio-small', [{'id':'singer_1','start':0,'end':1}])
