"""Complete manifest validation prior to recovered multi-stem publication."""
import io
import json
import zipfile
from types import SimpleNamespace
from fastapi import HTTPException
import pytest
from app import main
from test_r208_recovered_stem_import import archive, configure, wav


def repackage(extra_specs=(), extra_files=(), duplicate_spec=False, encrypted=False):
    spec = {'name': 'vocals.wav', 'type': 'audio/wav'}
    specs = [spec, *extra_specs]
    if duplicate_spec:
        specs.append(dict(spec))
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as out:
        for name, payload in [('vocals.wav', wav()), *extra_files]:
            info = zipfile.ZipInfo(name)
            if encrypted:
                info.flag_bits |= 1
            out.writestr(info, payload)
        out.writestr('manifest.json', json.dumps({'version': 1, 'files': specs}))
    return stream.getvalue()


@pytest.mark.parametrize('payload', [
    repackage(duplicate_spec=True),
    repackage(extra_specs=[{'name': 'info.json', 'type': 'application/json', 'sha256': 'f'*64}], extra_files=[('info.json', b'{}')]),
    repackage(extra_specs=[{'name': 'info.json', 'type': 'application/json'}], extra_files=[('info.json', b'{bad')]),
    repackage(extra_specs=[{'name': 'info.dat', 'type': 'application/json'}], extra_files=[('info.dat', b'{}')]),
    repackage(extra_specs=[{'name': 'notes.bin', 'type': 'text/plain'}], extra_files=[('notes.bin', b'ok')]),
])
def test_invalid_manifest_fails_before_project_mutation(monkeypatch, payload):
    project = configure(monkeypatch, payload)
    called = []
    monkeypatch.setattr('app.ai_recovered_stem_transaction.begin', lambda *args: called.append(args))
    with pytest.raises(HTTPException) as exc:
        main.native_ai_workers_import_recovered_stems(None, 'a' * 32, 'p1')
    assert exc.value.status_code == 422
    assert not called and not project.tracks


def test_producer_rejects_text_extension_not_accepted_by_consumer(tmp_path):
    from app.ai_worker_artifacts import package_artifacts
    (tmp_path / 'notes.bin').write_text('hello')
    (tmp_path / 'output.manifest.json').write_text(json.dumps({'version': 1, 'files': [
        {'name': 'notes.bin', 'type': 'text/plain'},
    ]}))
    with pytest.raises(ValueError, match='Text file extension required'):
        package_artifacts(tmp_path)
