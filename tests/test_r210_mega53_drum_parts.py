from pathlib import Path
from unittest.mock import patch
import tempfile
import pytest
from app import mega53_runtime as m


def test_drums_use_same_authorized_inference_pipeline():
    with patch.object(m, 'infer', return_value=[Path('/tmp/kick.wav')]) as run:
        assert m.infer_drums('/tmp/source.wav', '/tmp/output', {'kick'}) == [Path('/tmp/kick.wav')]
    assert run.call_args.kwargs['drum_targets'] == {'kick'}


def test_drum_target_rejects_cymbals():
    # Validation happens after upstream execution; isolate it using a tiny fake executor.
    class FakeProcess:
        returncode = 0
        stderr = None
        def poll(self): return 0
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp); (root/'inference.py').touch(); (root/'config.yaml').touch();(root/'model.ckpt').touch();(root/'audio.wav').touch();(root/'python').touch()
        env = {'MTA_MEGA53_ROOT':str(root), 'MTA_MEGA53_CONFIG':str(root/'config.yaml'), 'MTA_MEGA53_CHECKPOINT':str(root/'model.ckpt'), 'MTA_MEGA53_PYTHON':str(root/'python')}
        with patch.dict('os.environ', env), patch('app.model_license_policy.evaluate_model'), patch.object(m,'verify_mega53_checkpoint',return_value=root/'model.ckpt'), patch.object(m.subprocess,'Popen',return_value=FakeProcess()):
            with pytest.raises(RuntimeError,match='Unsupported Mega 53 drum target'):
                m.infer(root/'audio.wav',root/'out',drum_targets={'cymbals'})
