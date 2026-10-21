"""Reject incomplete Seed weights instead of upstream strict=False filtering.

The reviewed 44k MLP release retains ten unused historical output-layer keys.
Its older state also predates two deterministic position/frequency buffers.
These exceptions never apply to learned parameters.
"""
import math

LEGACY_OUTPUT_KEYS={
    'estimator.'+suffix for suffix in (
        'conv1.weight','conv1.bias','conv2.weight','conv2.bias',
        'res_projection.weight','res_projection.bias',
        't_embedder2.mlp.0.weight','t_embedder2.mlp.0.bias',
        't_embedder2.mlp.2.weight','t_embedder2.mlp.2.bias')}


def validated_state(module, incoming):
    import torch
    state={}
    for name,value in incoming.items():
        name=name.removeprefix('module.')
        if name in state:raise ValueError('Duplicate Seed checkpoint key: '+name)
        state[name]=value
    expected=module.state_dict()
    learned=dict(module.named_parameters())
    extras=set(state)-set(expected)
    if extras:
        if extras!=LEGACY_OUTPUT_KEYS or not hasattr(getattr(module,'estimator',None),'final_mlp'):
            raise ValueError('Unexpected Seed checkpoint keys: '+str(sorted(extras)))
        for name in extras:del state[name]
    for name,target in expected.items():
        value=state.get(name)
        if value is not None and value.shape==target.shape:continue
        if name in learned:raise ValueError('Missing or incompatible learned Seed tensor: '+name)
        if name=='estimator.input_pos':
            valid=lambda t:t.ndim==1 and torch.equal(t,torch.arange(t.numel(),dtype=t.dtype,device=t.device))
            if not valid(target) or (value is not None and not valid(value)):
                raise ValueError('Invalid Seed position buffer')
        elif name=='estimator.t_embedder.freqs' and value is None:
            reference=torch.exp(-math.log(10000)*torch.arange(target.numel(),dtype=torch.float32)/target.numel())
            if not torch.equal(target.cpu(),reference):raise ValueError('Invalid Seed frequency buffer')
        else:raise ValueError('Missing or incompatible Seed buffer: '+name)
        state[name]=target
    return state


def load_checkpoint(model,optimizer,path,load_only_params=True,ignore_modules=None,
                    is_distributed=False,load_ema=False):
    import torch
    if not load_only_params or ignore_modules or is_distributed or load_ema:
        raise ValueError('MTA Seed runner supports complete inference checkpoints only')
    params=torch.load(path,map_location='cpu',weights_only=True)['net']
    # Validate every active module before mutating any model state.
    states={name:validated_state(module,params[name]) for name,module in model.items()}
    for name,module in model.items():
        module.load_state_dict(states[name],strict=True)
        module.eval()
        print(name+' loaded: every active tensor verified (strict=True)')
    return model,optimizer,0,0
