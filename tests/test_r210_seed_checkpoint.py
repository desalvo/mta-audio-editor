"""Checkpoint safety tests; these are not neural acceptance inference."""
import math
import pytest

torch=pytest.importorskip('torch')
from app.seed_checkpoint import validated_state,LEGACY_OUTPUT_KEYS


def model():
    module=torch.nn.Module()
    module.estimator=torch.nn.Module()
    module.estimator.final_mlp=torch.nn.Linear(2,2)
    module.estimator.register_buffer('input_pos',torch.arange(16))
    module.estimator.t_embedder=torch.nn.Module()
    module.estimator.t_embedder.register_buffer('freqs',torch.exp(-math.log(10000)*torch.arange(4,dtype=torch.float32)/4))
    return module


@pytest.mark.parametrize('damage',['missing','shape'])
def test_rejects_uninitialized_learned_weights(damage):
    m=model();state=m.state_dict()
    if damage=='missing':del state['estimator.final_mlp.weight']
    else:state['estimator.final_mlp.weight']=torch.zeros(3,2)
    with pytest.raises(ValueError,match='learned Seed tensor'):validated_state(m,state)


def test_old_deterministic_buffers_and_inactive_keys_are_explicit():
    m=model();state=m.state_dict();del state['estimator.t_embedder.freqs']
    state['estimator.input_pos']=torch.arange(8)
    state.update({key:torch.zeros(1) for key in LEGACY_OUTPUT_KEYS})
    actual=validated_state(m,{'module.'+key:value for key,value in state.items()})
    m.load_state_dict(actual,strict=True)
    assert torch.equal(m.estimator.input_pos,torch.arange(16))


def test_rejects_unknown_keys_and_corrupt_positions():
    m=model();state=m.state_dict();state['unreviewed.weight']=torch.zeros(1)
    with pytest.raises(ValueError,match='Unexpected'):validated_state(m,state)
    del state['unreviewed.weight'];state['estimator.input_pos']=torch.ones(8)
    with pytest.raises(ValueError,match='position buffer'):validated_state(m,state)


def test_prefix_collision_cannot_replace_a_tensor():
    m=model();state=m.state_dict();state['module.estimator.final_mlp.weight']=torch.ones(2,2)
    with pytest.raises(ValueError,match='Duplicate'):validated_state(m,state)


def test_seed_export_prevents_quantization_clipping_without_limiting_shape():
    from app.seed_audio_export import with_headroom
    source=torch.tensor([[0.,2.,-1.,.5]])
    audio,gain=with_headroom(source)
    assert gain==pytest.approx(.49)
    assert torch.allclose(audio,source*gain)
    assert float(audio.abs().max())==pytest.approx(.98)
    quiet=torch.tensor([[0.,.2,-.1]])
    actual,gain=with_headroom(quiet)
    assert gain==1 and torch.equal(actual,quiet)
    with pytest.raises(ValueError,match='invalid audio'):with_headroom(torch.tensor([[float('nan')]]))


def test_seed_headroom_accounts_for_actual_resampling_overshoot():
    import numpy as np
    from scipy.signal import resample_poly
    from app.seed_audio_export import with_headroom
    source=torch.tensor(np.tile([1.,1.,-1.,-1.],1000),dtype=torch.float32).reshape(1,-1)
    assert np.abs(resample_poly(source.numpy(),160,147,axis=-1)).max()>1
    bounded,gain=with_headroom(source,44100)
    assert gain<.98
    assert np.abs(resample_poly(bounded.numpy(),160,147,axis=-1)).max()<=.980001
