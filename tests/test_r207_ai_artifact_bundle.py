import io
import json
import wave
import zipfile

import pytest
from app.ai_worker_artifacts import package_artifacts


def _wav(path):
    with wave.open(str(path), 'wb') as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(44100)
        writer.writeframes(b'\0\0' * 160)


def test_multitrack_and_transcription(tmp_path):
    _wav(tmp_path / 'vocals.wav')
    _wav(tmp_path / 'instrumental.wav')
    (tmp_path / 'lyrics.json').write_text('{"segments": [{"start": 0, "text": "hello"}]}')
    doc = {'version': 1, 'files': [
        {'name': 'vocals.wav', 'type': 'audio/wav'},
        {'name': 'instrumental.wav', 'type': 'audio/wav'},
        {'name': 'lyrics.json', 'type': 'application/json'},
    ]}
    (tmp_path / 'output.manifest.json').write_text(json.dumps(doc))
    payload, mime = package_artifacts(tmp_path)
    assert mime == 'application/zip'
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert set(archive.namelist()) == {'vocals.wav','instrumental.wav','lyrics.json','manifest.json'}


@pytest.mark.parametrize('name', ['../secret.wav', '/etc/passwd', '.hidden', 'x/y.wav', 'x\\y.wav'])
def test_reject_unsafe_names(tmp_path, name):
    (tmp_path / 'output.manifest.json').write_text(json.dumps({'version': 1, 'files': [{'name': name, 'type': 'audio/wav'}]}))
    with pytest.raises(ValueError):
        package_artifacts(tmp_path)


def test_symlink_and_invalid_json_rejected(tmp_path):
    (tmp_path / 'text.json').symlink_to(tmp_path / 'outside')
    (tmp_path / 'output.manifest.json').write_text(json.dumps({'version': 1, 'files': [{'name': 'text.json', 'type': 'application/json'}]}))
    with pytest.raises(ValueError):
        package_artifacts(tmp_path)
    (tmp_path / 'text.json').unlink()
    (tmp_path / 'text.json').write_text('{bad')
    with pytest.raises(json.JSONDecodeError):
        package_artifacts(tmp_path)
