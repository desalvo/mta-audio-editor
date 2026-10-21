import os,sys,json,time
from pathlib import Path
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
root=Path('mt3_memory_research');source=next(Path('mt3_research').glob('mt3-infer-d8*'))
sys.path[:0]=[str((root/'compat').resolve()),str(source.resolve())]
import torch,numpy as np,soundfile as sf
from transformers import T5Config
from mt3_infer.adapters.mr_mt3 import MRMT3Adapter,vocab_utils
from models.t5_segmem_v2_with_prev import T5SegMemV2WithPrev
from scipy.signal import resample_poly
from math import gcd
print('imports',flush=True);torch.set_num_threads(4)
a=MRMT3Adapter();cfg=T5Config.from_dict(a.model_config);cfg.use_cache=False
state=torch.load(root/'memory-checkpoint.ckpt',map_location='cpu',weights_only=True)['state_dict']
assert all(k.startswith('model.') and isinstance(v,torch.Tensor) and torch.isfinite(v).all() for k,v in state.items())
state={k.removeprefix('model.'):v for k,v in state.items()}
a.model=T5SegMemV2WithPrev(cfg,segmem_num_layers=1,segmem_length=64)
print('strict load',a.model.load_state_dict(state,strict=True),flush=True)
a.model.eval();a._initialize_vocab();a._model_loaded=True
wave,sr=sf.read('mta_work/validation/r210-acceptance-ten-programs.wav',dtype='float32',always_2d=True);wave=wave.mean(axis=1)
g=gcd(sr,16000);wave=resample_poly(wave,16000//g,sr//g).astype('float32')
source_duration=len(wave)/16000
# Match the original InferenceHandler._audio_to_frames exactly, including
# its final zero frame when the source length is divisible by hop width.
wave=np.pad(wave,(0,128-len(wave)%128))
t=time.monotonic();features=a.preprocess(wave,16000)
features['inputs']=(torch.clamp(features['inputs'],-12,5)+12)/17
for i,length in enumerate(features['paddings']):features['inputs'][i,length:,:]=0
# Memory generation needs all contiguous windows in one generate call; batching
# separate calls would discard the previous output context.
with torch.inference_mode():
 tokens=a.model.generate(inputs=features['inputs'],max_length=1024)
post=tokens.cpu().numpy().copy()
for i,seq in enumerate(post):
 eos=np.flatnonzero(seq==a.model.config.eos_token_id)
 if len(eos):post[i,eos[0]:]=-1
post=post[:,1:]-(a.vocab_size-a.codec.num_classes)
outputs={'tokens':post,'frame_times':features['frame_times']}
np.savez(root/'actual-memory-output.npz',**outputs)
preds=[{'est_tokens':tok[tok>=0],'start_time':float(fr[0])} for tok,fr in zip(post,features['frame_times']) if len(tok[tok>=0])]
seq,invalid,dropped=vocab_utils.decode_and_combine_predictions(preds,a.codec)
notes=[vars(n) for n in seq.notes];(root/'actual-memory-notes.json').write_text(json.dumps(notes,indent=2))
sys.path.insert(0,str(Path('mta_work').resolve()))
from app.mrmt3_decode import decode
mta_notes,mta_audit=decode(preds,a.codec,source_duration)
(root/'actual-memory-mta-notes.json').write_text(json.dumps(mta_notes,indent=2)+'\n')
report={'mta_notes':len(mta_notes),'mta_audit':mta_audit,'strict_state':True,'tensor_count':len(state),'elements':sum(v.numel() for v in state.values()),'notes':len(notes),'programs':sorted(set(n['program'] for n in notes)),'invalid_events':invalid,'dropped_events':dropped,'seconds':time.monotonic()-t}
(root/'actual-memory-result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
