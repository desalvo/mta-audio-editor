"""Bounded-memory C++ DSP adapter for render, independent of device transport.

NumPy/SoundFile are imported only during rendering. Settings readiness probes
use a tiny ABI/finite-sample self-test and never import the ML/audio stack.
"""
import ctypes as ct
from functools import lru_cache
import math
from pathlib import Path

BLOCK=4096
FP=ct.POINTER(ct.c_float)


class Core:
    def __init__(self,path):
        self.lib=ct.CDLL(str(path))
        self.lib.mta_transport_abi.restype=ct.c_uint
        if self.lib.mta_transport_abi()!=1:raise RuntimeError('Unsupported C++ device transport ABI')
        self.lib.mta_timeline_abi.restype=ct.c_uint
        if self.lib.mta_timeline_abi()!=1:raise RuntimeError('Unsupported C++ timeline ABI')
        self.lib.mta_render_dsp_abi.restype=ct.c_uint
        if self.lib.mta_render_dsp_abi()!=1:raise RuntimeError('Unsupported C++ render DSP ABI')
        self.lib.mta_render_gain.argtypes=[FP,ct.c_size_t,ct.c_uint,ct.c_float]
        self.lib.mta_render_mix.argtypes=[ct.POINTER(FP),FP,FP,ct.POINTER(ct.c_ubyte),ct.c_size_t,FP,ct.c_size_t]
        self.lib.mta_render_envelope.argtypes=[FP,ct.c_size_t,ct.c_uint,ct.c_ulonglong,ct.c_ulonglong,ct.c_float,ct.c_ulonglong,ct.c_ulonglong]
        for name in ('mta_render_gain','mta_render_mix','mta_render_envelope'):getattr(self.lib,name).restype=ct.c_int
        data=(ct.c_float*2)(0.25,-0.5)
        if self.lib.mta_render_gain(data,1,2,2)!=0 or tuple(data)!=(0.5,-1.0):raise RuntimeError('C++ render DSP self-test failed')

    @staticmethod
    def pointer(a):return a.ctypes.data_as(FP)

    @staticmethod
    def validate(a):
        if a.ndim!=2 or a.dtype.name!='float32' or not a.flags.c_contiguous or not a.flags.aligned or not a.dtype.isnative or not a.flags.writeable or not 1<=a.shape[0]<=BLOCK or not 1<=a.shape[1]<=64:raise ValueError('Invalid C++ PCM block')

    def gain(self,a,gain):
        self.validate(a)
        if self.lib.mta_render_gain(self.pointer(a),len(a),a.shape[1],gain):raise RuntimeError('C++ gain rejected PCM')

    def mix(self,arrays,gains,pans,enabled):
        import numpy as np
        if not arrays or len(arrays)>64 or not (len(arrays)==len(gains)==len(pans)==len(enabled)):raise ValueError('C++ mix supports 1–64 routes')
        n=len(arrays[0]);out=np.empty((n,2),dtype=np.float32)
        if not 1<=n<=BLOCK or any(a.shape!=(n,2) or a.dtype!=np.float32 or not a.flags.c_contiguous or not a.flags.aligned for a in arrays):raise ValueError('Invalid C++ PCM block')
        ptrs=(FP*len(arrays))(*(self.pointer(a) for a in arrays));g=(ct.c_float*len(gains))(*gains);p=(ct.c_float*len(pans))(*pans);e=(ct.c_ubyte*len(enabled))(*enabled)
        if self.lib.mta_render_mix(ptrs,g,p,e,len(arrays),self.pointer(out),n):raise RuntimeError('C++ mixer rejected PCM or route parameters')
        return out

    def envelope(self,a,offset,total,gain,fade_in,fade_out):
        self.validate(a)
        if any(type(v) is not int or not 0<=v<2**63 for v in (offset,total,fade_in,fade_out)):raise ValueError('Invalid C++ frame interval')
        if self.lib.mta_render_envelope(self.pointer(a),len(a),a.shape[1],offset,total,gain,fade_in,fade_out):raise RuntimeError('C++ envelope rejected PCM')


@lru_cache(maxsize=4)
def _load(paths):
    for path in paths:
        if not Path(path).is_file():continue
        try:return Core(path)
        except (OSError,AttributeError,RuntimeError):continue
    return None


def runtime():
    from .native_dsp import _candidate_paths
    core=_load(tuple(str(p) for p in _candidate_paths()))
    if core is None:raise RuntimeError('C++ audio engine unavailable; choose the current engine or install a build with the C++ DSP runtime')
    return core


def core_status():
    try:runtime();return {'available':True,'abi':1,'error':''}
    except RuntimeError as e:return {'available':False,'abi':None,'error':str(e)}


def _linear(db):
    db=float(db)
    if not math.isfinite(db) or not -120<=db<=24:raise ValueError('Invalid mixer gain')
    return 10**(db/20)


def gain_file(source,target,gain_db):
    import soundfile as sf
    core=runtime();gain=_linear(gain_db)
    with sf.SoundFile(str(source)) as src,sf.SoundFile(str(target),'w',samplerate=src.samplerate,channels=src.channels,format='WAV',subtype='FLOAT') as dest:
        while True:
            data=src.read(BLOCK,dtype='float32',always_2d=True)
            if not len(data):break
            core.gain(data,gain);dest.write(data)


def mix_files(sources,target,tracks,sample_rate):
    """Read sample-aligned stereo files; zero-pad short/muted routes without truncation."""
    from contextlib import ExitStack
    import soundfile as sf
    import numpy as np
    if len(sources)!=len(tracks) or not 1<=len(tracks)<=64:raise ValueError('C++ mix supports 1–64 tracks')
    core=runtime();solo=any(t.solo for t in tracks)
    enabled=[not (t.mute or (solo and not t.solo)) for t in tracks]
    gains=[_linear(round(t.volume_db,3)) for t in tracks];pans=[round(float(t.pan),4) for t in tracks]
    with ExitStack() as stack:
        readers=[stack.enter_context(sf.SoundFile(str(p))) for p in sources]
        if any(r.channels!=2 or r.samplerate!=sample_rate for r in readers):raise ValueError('C++ mixer requires negotiated stereo PCM')
        total=max(r.frames for r in readers)
        # Prepared native scheduling also handles short routes and arbitrary seek
        # positions. Clip decoding/file IO remain on this offline Python thread.
        from .cpp_timeline import Timeline
        timeline=stack.enter_context(Timeline([(0,0,r.frames,i) for i,r in enumerate(readers) if r.frames and enabled[i]]))
        dest=stack.enter_context(sf.SoundFile(str(target),'w',samplerate=sample_rate,channels=2,format='WAV',subtype='FLOAT'))
        for offset in range(0,total,BLOCK):
            count=min(BLOCK,total-offset)
            arrays=[np.zeros((count,2),dtype=np.float32) for _ in readers]
            for segment in timeline.query(offset,count):
                reader=readers[segment.route]
                if reader.tell()!=segment.source:reader.seek(segment.source)
                part=reader.read(segment.frames,dtype='float32',always_2d=True)
                arrays[segment.route][segment.offset:segment.offset+len(part)]=part
            dest.write(core.mix(arrays,gains,pans,enabled))


def master_file(source,target,project,total_ms):
    import soundfile as sf
    import numpy as np
    core=runtime();gain=_linear(round(project.master_volume_db,3))
    with sf.SoundFile(str(source)) as src,sf.SoundFile(str(target),'w',samplerate=src.samplerate,channels=src.channels,format='WAV',subtype='FLOAT') as dest:
        bounded=project.timeline_end_ms is not None or project.master_fade_enabled
        total=(int(total_ms)*src.samplerate+500)//1000 if bounded else src.frames
        in_frames=(project.master_fade_in_ms*src.samplerate+500)//1000 if project.master_fade_enabled else 0
        out_frames=(project.master_fade_out_ms*src.samplerate+500)//1000 if project.master_fade_enabled else 0
        for offset in range(0,total,BLOCK):
            count=min(BLOCK,total-offset);data=np.zeros((count,src.channels),dtype=np.float32)
            part=src.read(count,dtype='float32',always_2d=True);data[:len(part)]=part
            core.envelope(data,offset,total,gain,in_frames,out_frames);dest.write(data)
