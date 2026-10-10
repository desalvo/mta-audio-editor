import wave
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest
from app.preview_publish import publish_wav_preview

def write_wave(path: Path):
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(44100)
        output.writeframes(b'\x00\x00' * 100)

def test_atomic_publish_preserves_good_preview_on_failure(tmp_path):
    target=tmp_path/'preview.wav'
    write_wave(target)
    assert not publish_wav_preview(target, lambda _: pytest.fail('unexpected render'))
    target.write_bytes(b'corrupt old preview')
    def fail(path):
        path.write_bytes(b'partial')
        raise RuntimeError('plugin fault')
    with pytest.raises(RuntimeError, match='plugin fault'):
        publish_wav_preview(target, fail)
    assert target.read_bytes()==b'corrupt old preview'
    assert not list(tmp_path.glob('.preview.*.wav'))

def test_invalid_renderer_output_is_never_published(tmp_path):
    target=tmp_path/'cache.wav'
    with pytest.raises(RuntimeError, match='invalid WAV'):
        publish_wav_preview(target, lambda path: path.write_bytes(b'garbage'))
    assert not target.exists()

def test_reuses_one_render_for_concurrent_requests(tmp_path):
    target=tmp_path/'preview.wav'
    calls=[]
    def build(path):
        calls.append(1)
        write_wave(path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(lambda _: int(publish_wav_preview(target, build)), range(16)))==1
    assert len(calls)==1

def test_replaces_corrupt_cache_with_valid_wav(tmp_path):
    target=tmp_path/'preview.wav'
    target.write_bytes(b'invalid')
    assert publish_wav_preview(target, write_wave)
    with wave.open(str(target),'rb') as audio:
        assert audio.getnframes()==100

def test_frontend_busts_fx_preview_url():
    source=(Path(__file__).resolve().parents[1]/'app/static/app.js').read_text()
    assert 'fx=${fxKey}' in source
    assert 'x.enabled,x.params' in source
    assert '(fxHash>>>0).toString(36)' in source
