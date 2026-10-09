from pathlib import Path
from unittest.mock import patch
import pytest
from app import main
from app import drumsep_onnx_worker as worker


def test_drumsep_model_metadata_and_layout(tmp_path):
    assert main._DRUMSEP_SHA256 and len(main._DRUMSEP_SHA256) == 64
    assert main._PERCUSSION_METHODS.issuperset({'drumsep-onnx','dsp'})
    assert worker.STEMS == ('kick','snare','cymbals','toms')
    assert worker.WINDOW == 1764000


def test_drumsep_requires_model_file(tmp_path, monkeypatch):
    monkeypatch.setattr(main, '_DRUMSEP_PATH', tmp_path / 'missing.onnx')
    with pytest.raises(RuntimeError, match='not installed'):
        main._drumsep_extract(tmp_path / 'source.wav', tmp_path / 'out', {'snare'})


def test_drumsep_selective_output(tmp_path, monkeypatch):
    model = tmp_path / 'model.onnx'; model.write_bytes(b'test')
    monkeypatch.setattr(main, '_DRUMSEP_PATH', model)
    def fake_run(args, **kwargs):
        dest=Path(args[args.index('--output')+1]); dest.mkdir(parents=True, exist_ok=True)
        for n in ('kick','snare','toms','cymbals'):
            (dest / f'{n}.wav').write_bytes(b'RIFF'+b'0'*100)
        return type('Completed',(),{'returncode':0,'stderr':'','stdout':''})()
    with patch.object(main.subprocess,'run',side_effect=fake_run):
        paths=main._drumsep_extract(tmp_path/'source.wav',tmp_path/'output',{'snare'})
    assert [x.stem for x in paths] == ['snare']


def test_drumsep_ui_and_native_bundle():
    js=Path('app/static/app.js').read_text()
    assert js.count('value="drumsep-onnx"') >= 2
    assert 'downloadDrumSepModel' in js
    assert 'drumsep_onnx_worker.py' in Path('native/mta_audio_editor_native.spec').read_text()
