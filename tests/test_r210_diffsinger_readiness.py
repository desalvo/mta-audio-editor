import hashlib
import importlib.util
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/'scripts'/'check_diffsinger_ready.py'
spec=importlib.util.spec_from_file_location('mta_diffsinger_readiness',SCRIPT)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

def test_empty_config_is_fail_closed():
    outcome=mod.check({})
    assert not outcome['ready_for_inference_attempt']
    assert not outcome['real_audio_validated']
    assert len(outcome['problems'])>=4

def test_missing_authorization_cannot_pass_as_ready(tmp_path):
    root=tmp_path/'ds';(root/'scripts').mkdir(parents=True)
    (root/'scripts'/'infer.py').write_text('pass')
    (root/'checkpoints'/'singer').mkdir(parents=True)
    python=tmp_path/'python';python.write_bytes(b'python')
    acoustic=root/'checkpoints'/'singer'/'model.ckpt';acoustic.write_bytes(b'acoustic')
    vocoder=root/'vocoder.ckpt';vocoder.write_bytes(b'vocoder')
    env={'MTA_DIFFSINGER_ROOT':str(root),'MTA_DIFFSINGER_EXPERIMENT':'singer',
         'MTA_DIFFSINGER_PYTHON':str(python),'MTA_DIFFSINGER_PYTHON_SHA256':hashlib.sha256(python.read_bytes()).hexdigest(),
         'MTA_NEURAL_SINGER_CHECKPOINT':str(acoustic),'MTA_NEURAL_SINGER_SHA256':hashlib.sha256(acoustic.read_bytes()).hexdigest(),
         'MTA_DIFFSINGER_VOCODER':str(vocoder),'MTA_DIFFSINGER_VOCODER_SHA256':hashlib.sha256(vocoder.read_bytes()).hexdigest()}
    outcome=mod.check(env)
    assert not outcome['ready_for_inference_attempt']
    assert any('POLICY_MODEL' in p for p in outcome['problems'])
    assert not outcome['real_audio_validated']

def test_tampered_vocoder_is_rejected(tmp_path):
    p=tmp_path/'bad';p.write_bytes(b'bad')
    env={'MTA_DIFFSINGER_VOCODER':str(p),'MTA_DIFFSINGER_VOCODER_SHA256':'0'*64}
    result=mod.check(env)
    assert any('vocoder' in x and 'checksum' in x for x in result['problems'])
