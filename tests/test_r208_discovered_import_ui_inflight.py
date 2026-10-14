"""Recovered results from separate worker kinds have independent import guards."""
from pathlib import Path


def test_discovered_wav_uses_kind_scoped_inflight_key():
    js = (Path(__file__).resolve().parents[1] / 'app/static/app.js').read_text()
    body = js.split('async function importNativeDiscoveredWav(', 1)[1].split('async function importNativeDiscoveredResult(', 1)[0]
    assert 'const key=`discovered:${kind}:${id}:wav`' in body
    assert 'nativePendingImportsInFlight.has(key)' in body
    assert 'nativePendingImportsInFlight.delete(key)' in body
    assert "method:'POST'" in body
    assert 'confirm(' in body
