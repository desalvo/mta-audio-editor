"""Portable, isolated GM synthesis using the bundled MIT TinySoundFont core.

No devices are opened. Sample data is shared across voices inside a worker;
notes, controllers and effects remain independent for every instrument track.
"""
import ctypes as C
from functools import lru_cache


def library():
    from .cpp_audio import runtime
    lib=runtime().lib
    try:
        lib.mta_gm_abi.restype=C.c_uint
        if lib.mta_gm_abi()!=1:raise RuntimeError('Unsupported portable GM ABI')
    except AttributeError as exc:raise RuntimeError('Install an updated build containing the portable GM engine') from exc
    lib.mta_gm_create.argtypes=[C.c_void_p,C.c_size_t,C.c_char_p,C.c_uint,C.c_uint];lib.mta_gm_create.restype=C.c_void_p
    lib.mta_gm_close.argtypes=[C.c_void_p];lib.mta_gm_close.restype=None
    lib.mta_gm_configure.argtypes=[C.c_void_p,C.c_float,C.c_uint];lib.mta_gm_configure.restype=C.c_int
    lib.mta_gm_program.argtypes=[C.c_void_p,C.c_uint,C.c_uint,C.c_uint];lib.mta_gm_program.restype=C.c_int
    lib.mta_gm_event.argtypes=[C.c_void_p,C.c_uint,C.c_uint,C.c_uint];lib.mta_gm_event.restype=C.c_int
    lib.mta_gm_render.argtypes=[C.c_void_p,C.c_void_p,C.c_uint];lib.mta_gm_render.restype=C.c_int
    lib.mta_gm_reset.argtypes=[C.c_void_p];lib.mta_gm_reset.restype=None
    return lib


@lru_cache(maxsize=1)
def _bank(path,size,mtime):
    # Keep one immutable pinned bank byte buffer while instances are created.
    from pathlib import Path
    return Path(path).read_bytes()


class Synth:
    is_instrument=True

    def __init__(self,params,rate):
        from .gm_instruments import validate,bank_path
        self.handle=None;self.rate=rate;self.params=validate(params);self.lib=library();self.programmed=False
        path=bank_path(self.params['bank_id']);info=path.stat();data=_bank(str(path),info.st_size,info.st_mtime_ns)
        self.handle=self.lib.mta_gm_create(data,len(data),__import__('hashlib').sha256(data).hexdigest().encode('ascii'),rate,int(self.params['polyphony']))
        if not self.handle:raise RuntimeError('Portable GM could not load the reviewed soundbank')
        from pedalboard import Reverb
        self.reverb=Reverb()
        try:self.configure(self.params)
        except BaseException:self.close();raise

    def configure(self,params):
        if self.handle is None:raise RuntimeError('Portable GM synthesizer is closed')
        from .gm_instruments import validate
        values=validate({**self.params,**params})
        if values['bank_id']!=self.params['bank_id']:raise ValueError('Reload the instrument to switch SoundFont banks')
        if not self.programmed or any(values[k]!=self.params[k] for k in ('program','bank')):
            for channel in range(16):
                if self.lib.mta_gm_program(self.handle,channel,128 if channel==9 else int(values['bank']),0 if channel==9 else int(values['program'])):
                    raise ValueError('Soundbank does not contain the selected GM program/bank')
        self.programmed=True
        # TinySoundFont volume is captured by active voices. Apply track gain
        # after rendering so live changes affect sounding notes immediately.
        if self.lib.mta_gm_configure(self.handle,1.,int(values['polyphony'])):raise RuntimeError('Portable GM configuration failed')
        self.reverb.room_size=values['reverb_room'];self.reverb.damping=values['reverb_damping']
        self.reverb.width=min(1.,values['reverb_width']);self.reverb.wet_level=values['reverb_level'];self.reverb.dry_level=1.
        self.params=values

    def reset(self):
        if self.handle is None:raise RuntimeError('Portable GM synthesizer is closed')
        self.lib.mta_gm_reset(self.handle);self.reverb.reset();self.programmed=False;self.configure(self.params)

    def message(self,message):
        from .gm_instruments import validate_midi_packet
        if self.handle is None:
            raise RuntimeError('Portable GM synthesizer is closed')
        data=list(validate_midi_packet(message))
        if data in ([240,126,127,9,1,247],[240,126,127,9,3,247]):self.reset();return
        if not 2<=len(data)<=3 or any(type(v) is not int or not 0<=v<=255 for v in data):raise ValueError('Invalid GM event')
        status=data[0]&240
        if len(data)!=(2 if status in (192,208) else 3):raise ValueError('Invalid GM event length')
        code=self.lib.mta_gm_event(self.handle,data[0],data[1],data[2] if len(data)==3 else 0)
        if code==-2:raise ValueError('Portable GM does not support aftertouch; select FluidSynth or a VSTi')
        if code:raise ValueError('Portable GM event rejected')

    def process(self,messages,*,duration,sample_rate,num_channels=2,buffer_size=512,reset=False):
        import numpy as np
        if self.handle is None:raise RuntimeError('Portable GM synthesizer is closed')
        if sample_rate!=self.rate or num_channels!=2:raise ValueError('GM output format changed')
        from .gm_instruments import schedule_gm_events
        events=schedule_gm_events(messages,duration=duration,rate=self.rate)
        frames=round(duration*self.rate)
        if not 0<frames<=32768:raise ValueError('GM block exceeds limit')
        if reset:self.reset()
        output=np.zeros((frames,2),dtype=np.float32);position=0
        for message,seconds in [*events,(None,duration)]:
            end=max(position,min(frames,round(seconds*self.rate)))
            if end>position and self.lib.mta_gm_render(self.handle,output[position:].ctypes.data,end-position):raise RuntimeError('GM rendering failed')
            if message is not None:self.message(message)
            position=end
        result=self.reverb(output.T.copy(),sample_rate,reset=False)
        if not np.isfinite(result).all():raise RuntimeError('GM produced invalid PCM')
        return result*self.params['gain']

    def close(self):
        if self.handle:self.lib.mta_gm_close(self.handle);self.handle=None

    def __del__(self):self.close()
