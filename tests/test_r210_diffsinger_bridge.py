import hashlib
import json
import pytest
from app.diffsinger_bridge import ds_from_request, safe_file

def note(pitch,start,duration,ph):
    return {'pitch':pitch,'start_ms':start,'duration_ms':duration,'syllable':ph}

def test_ds_with_rest_and_pitch():
    ds=ds_from_request({'notes':[note(60,0,500,'a'),note(64,750,250,'e')]})
    assert ds['ph_seq']=='a SP e'
    assert ds['note_seq']=='C4 rest E4'
    assert ds['ph_dur']=='0.500000 0.250000 0.250000'

def test_ds_rejects_overlap_or_undocumented_phonemes():
    with pytest.raises(ValueError):ds_from_request({'notes':[note(60,0,500,'a'),note(62,100,400,'e')]})
    with pytest.raises(ValueError):ds_from_request({'notes':[note(60,0,500,'hello world')]})

def test_asset_requires_digest(tmp_path):
    p=tmp_path/'model.ckpt';p.write_bytes(b'checkpoint')
    assert safe_file(str(p),hashlib.sha256(b'checkpoint').hexdigest())==p
    with pytest.raises(ValueError):safe_file(str(p),'a'*64)


def test_runtime_rejects_checkpoint_outside_experiment(tmp_path,monkeypatch):
    from app.diffsinger_bridge import run
    root=tmp_path/'runtime'; (root/'scripts').mkdir(parents=True)
    (root/'checkpoints'/'singer').mkdir(parents=True)
    (root/'other').mkdir()
    (root/'scripts'/'infer.py').write_text('raise RuntimeError("must not start")')
    python=tmp_path/'python';python.write_bytes(b'interpreter')
    acoustic=root/'other'/'acoustic.ckpt';acoustic.write_bytes(b'acoustic')
    vocoder=root/'other'/'vocoder.ckpt';vocoder.write_bytes(b'vocoder')
    env={'MTA_DIFFSINGER_ROOT':str(root),'MTA_DIFFSINGER_PYTHON':str(python),
         'MTA_DIFFSINGER_PYTHON_SHA256':hashlib.sha256(python.read_bytes()).hexdigest(),
         'MTA_NEURAL_SINGER_CHECKPOINT':str(acoustic),
         'MTA_NEURAL_SINGER_SHA256':hashlib.sha256(acoustic.read_bytes()).hexdigest(),
         'MTA_DIFFSINGER_VOCODER':str(vocoder),
         'MTA_DIFFSINGER_VOCODER_SHA256':hashlib.sha256(vocoder.read_bytes()).hexdigest(),
         'MTA_DIFFSINGER_EXPERIMENT':'singer'}
    for k,v in env.items():monkeypatch.setenv(k,v)
    req=tmp_path/'request.json';req.write_text(json.dumps({'schema':'mta-neural-singing-1','language':'en',
             'notes':[note(60,0,500,'a')]}))
    with pytest.raises(ValueError,match='selected experiment'):
        run(req,tmp_path/'out.wav')


def test_reject_oversized_duration_score():
    from app.diffsinger_bridge import ds_from_request
    with pytest.raises(ValueError):
        ds_from_request({'notes':[note(60,0,31000,'a')]})
