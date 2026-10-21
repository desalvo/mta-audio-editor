"""Isolated, sample-scheduled General MIDI plugin using dynamic FluidSynth.

FluidSynth is LGPL-2.1; soundbanks carry independent licenses. No device is
opened here and no native/soundbank library runs in the HTTP/UI process.
"""
import ctypes as C
from ctypes.util import find_library
from functools import lru_cache
import hashlib
import math
import os
from pathlib import Path

from . import auth

DEFAULTS = {'bank_id': 'fluidr3-gm', 'program': 0, 'bank': 0, 'gain': .4, 'polyphony': 256,
            'reverb_room': .2, 'reverb_damping': .2, 'reverb_width': .5, 'reverb_level': .25}
LIMITS = {'program': (0, 127), 'bank': (0, 16383), 'gain': (0, 5), 'polyphony': (32, 1024),
          'reverb_room': (0, 1), 'reverb_damping': (0, 1), 'reverb_width': (0, 100), 'reverb_level': (0, 1)}


def library_path():
    configured = os.getenv('MTA_FLUIDSYNTH_LIBRARY', '')
    if configured:
        path = Path(configured)
        if not path.is_absolute() or not path.is_file():
            raise ValueError('Invalid operator-configured FluidSynth library')
        return str(path)
    return find_library('fluidsynth') or find_library('libfluidsynth-3') or ''


def bank_path(bank_id):
    if bank_id != 'fluidr3-gm':
        from .gm_banks import bank_path as reviewed_bank
        return reviewed_bank(bank_id)
    candidates = [auth.data_root() / 'soundfonts' / 'FluidR3_GM.sf2',
                  Path('/usr/share/sounds/sf2/FluidR3_GM.sf2'), Path('/usr/share/soundfonts/FluidR3_GM.sf2')]
    if os.getenv('MTA_GM_SOUNDFONT_DIR'):
        root = Path(os.environ['MTA_GM_SOUNDFONT_DIR'])
        if not root.is_absolute():
            raise ValueError('SoundFont directory must be absolute')
        candidates.insert(0, root / 'FluidR3_GM.sf2')
    for path in candidates:
        if not path.is_symlink() and path.is_file() and 12 < path.stat().st_size <= 1024**3:
            with path.open('rb') as stream:
                header = stream.read(12)
            if header[:4] == b'RIFF' and header[8:] == b'sfbk':
                info=path.stat()
                if _digest(str(path),info.st_size,info.st_mtime_ns)!='74594e8f4250680adf590507a306655a299935343583256f3b722c48a1bc1cb0':
                    raise ValueError('FluidR3 GM checksum mismatch; use the reviewed 3.1 soundbank')
                return path.resolve()
    raise ValueError('FluidR3 GM is not installed. Install fluid-soundfont-gm or the optional GM instrument pack.')


def validate(params):
    if not isinstance(params, dict) or set(params) - set(DEFAULTS):
        raise ValueError('Unsupported General MIDI plugin parameter')
    values = {**DEFAULTS, **params}
    if values['bank_id'] != 'fluidr3-gm':
        from .gm_banks import ID
        if not isinstance(values['bank_id'],str) or not ID.fullmatch(values['bank_id']):
            raise ValueError('Unknown General MIDI soundbank')
    for key, (low, high) in LIMITS.items():
        value = values[key]
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError('Invalid General MIDI parameter: ' + key)
        if key in ('bank', 'program', 'polyphony') and value != int(value):
            raise ValueError('General MIDI parameter must be an integer: ' + key)
    return values


@lru_cache(maxsize=8)
def _digest(path, size, modified):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()



def validate_midi_packet(packet):
    """Validate a complete channel MIDI message or one supported GM reset."""
    if not isinstance(packet, (bytes, bytearray, tuple, list)) or not packet:
        raise ValueError('Invalid General MIDI packet')
    if any(type(byte) is not int or not 0 <= byte <= 255 for byte in packet):
        raise ValueError('Invalid General MIDI byte')
    data = tuple(packet)
    if data in ((240, 126, 127, 9, 1, 247), (240, 126, 127, 9, 3, 247)):
        return data
    status = data[0]
    if not 128 <= status <= 239:
        raise ValueError('Unsupported General MIDI status')
    kind = status & 240
    expected = 2 if kind in (192, 208) else 3
    if len(data) != expected or any(not 0 <= value <= 127 for value in data[1:]):
        raise ValueError('Invalid General MIDI message length or data byte')
    return data


def schedule_gm_events(messages, *, duration, rate):
    """Bound and normalize a block before passing events to native synthesis."""
    if type(rate) is not int or not 8000 <= rate <= 192000:
        raise ValueError("Invalid GM sample rate")
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid GM block duration')
    if len(messages) > 20000:
        raise ValueError('Too many General MIDI events per block')
    events = []
    for packet, second in messages:
        if type(second) not in (float, int) or not math.isfinite(second) or not 0 <= second <= duration:
            raise ValueError('General MIDI event outside current block')
        events.append((validate_midi_packet(packet), second))
    # Preserve input order for simultaneous note-off/note-on and controller events.
    return sorted(events, key=lambda item: item[1])

def status(bank_id='fluidr3-gm'):
    result = {'id': 'gm_soundfont', 'name': 'FluidSynth / FluidR3 General MIDI', 'engine_license': 'LGPL-2.1-or-later',
              'bank_license': 'MIT', 'programs': 128, 'available': False, 'size_bytes': 0}
    try:
        library = library_path()
        if not library:
            from .gm_portable import library as portable_library
            portable_library()
            result.update(name='TinySoundFont / FluidR3 General MIDI',engine_license='MIT',backend='portable-cpp',aftertouch=False)
        else:result.update(backend='fluidsynth',aftertouch=True)
        path = bank_path(bank_id)
        result['bank_id']=bank_id
        if bank_id!='fluidr3-gm':
            from .gm_banks import descriptor
            reviewed=descriptor(bank_id)
            result.update(name=result['name'].split(' / ')[0]+' / '+reviewed['name'],bank_license=reviewed['license'],
                          programs=None,gm_coverage_verified=False)
        info = path.stat()
        result.update(available=True, size_bytes=info.st_size, sha256=_digest(str(path), info.st_size, info.st_mtime_ns))
    except (ValueError, OSError, RuntimeError) as exc:
        result['error'] = str(exc)
    return result


class FluidSynth:
    is_instrument = True

    def __init__(self, params, rate):
        self.settings = self.synth = None
        self.programmed = False
        self.rate = rate
        self.params = validate(params)
        library = library_path()
        if not library:
            raise ValueError('FluidSynth shared library is not installed')
        self.lib = C.CDLL(library)
        definitions = {
            'new_fluid_settings': (C.c_void_p, []), 'delete_fluid_settings': (None, [C.c_void_p]),
            'fluid_settings_setnum': (C.c_int, [C.c_void_p, C.c_char_p, C.c_double]),
            'fluid_settings_setint': (C.c_int, [C.c_void_p, C.c_char_p, C.c_int]),
            'new_fluid_synth': (C.c_void_p, [C.c_void_p]), 'delete_fluid_synth': (None, [C.c_void_p]),
            'fluid_synth_sfload': (C.c_int, [C.c_void_p, C.c_char_p, C.c_int]),
            'fluid_synth_program_select': (C.c_int, [C.c_void_p, C.c_int, C.c_int, C.c_int, C.c_int]),
            'fluid_synth_write_float': (C.c_int, [C.c_void_p, C.c_int, C.c_void_p, C.c_int, C.c_int, C.c_void_p, C.c_int, C.c_int]),
            'fluid_synth_noteon': (C.c_int, [C.c_void_p, C.c_int, C.c_int, C.c_int]),
            'fluid_synth_noteoff': (C.c_int, [C.c_void_p, C.c_int, C.c_int]),
            'fluid_synth_cc': (C.c_int, [C.c_void_p, C.c_int, C.c_int, C.c_int]),
            'fluid_synth_program_change': (C.c_int, [C.c_void_p, C.c_int, C.c_int]),
            'fluid_synth_pitch_bend': (C.c_int, [C.c_void_p, C.c_int, C.c_int]),
            'fluid_synth_channel_pressure': (C.c_int, [C.c_void_p, C.c_int, C.c_int]),
            'fluid_synth_key_pressure': (C.c_int, [C.c_void_p, C.c_int, C.c_int, C.c_int]),
            'fluid_synth_all_sounds_off': (C.c_int, [C.c_void_p, C.c_int]),
            'fluid_synth_set_gain': (None, [C.c_void_p, C.c_float]),
            'fluid_synth_set_polyphony': (C.c_int, [C.c_void_p, C.c_int]),
            'fluid_synth_set_reverb_group_roomsize': (C.c_int, [C.c_void_p, C.c_int, C.c_double]),
            'fluid_synth_set_reverb_group_damp': (C.c_int, [C.c_void_p, C.c_int, C.c_double]),
            'fluid_synth_set_reverb_group_width': (C.c_int, [C.c_void_p, C.c_int, C.c_double]),
            'fluid_synth_set_reverb_group_level': (C.c_int, [C.c_void_p, C.c_int, C.c_double]),
        }
        for name, (result, arguments) in definitions.items():
            function = getattr(self.lib, name)
            function.restype, function.argtypes = result, arguments
        try:
            self.settings = self.lib.new_fluid_settings()
            if not self.settings:
                raise RuntimeError('FluidSynth settings allocation failed')
            self.lib.fluid_settings_setnum(self.settings, b'synth.sample-rate', rate)
            self.lib.fluid_settings_setint(self.settings, b'synth.cpu-cores', 1)
            self.lib.fluid_settings_setint(self.settings, b'synth.threadsafe-api', 0)
            self.synth = self.lib.new_fluid_synth(self.settings)
            if not self.synth:
                raise RuntimeError('FluidSynth allocation failed')
            self.bank = self.lib.fluid_synth_sfload(self.synth, os.fsencode(bank_path(self.params['bank_id'])), 1)
            if self.bank < 0:
                raise ValueError('Cannot load licensed General MIDI soundbank')
            self.configure(self.params)
        except BaseException:
            self.close()
            raise

    def configure(self, params):
        values = validate({**self.params, **params})
        if values['bank_id']!=self.params['bank_id']:raise ValueError('Reload the instrument to switch SoundFont banks')
        for channel in range(16) if not self.programmed or any(values[k]!=self.params[k] for k in ('bank','program')) else ():
            if self.lib.fluid_synth_program_select(self.synth, channel, self.bank, 128 if channel == 9 else int(values['bank']), 0 if channel == 9 else int(values['program']))<0:
                raise ValueError('Soundbank does not contain the selected GM program/bank')
        self.programmed=True
        self.lib.fluid_synth_set_gain(self.synth, values['gain'])
        self.lib.fluid_synth_set_polyphony(self.synth, int(values['polyphony']))
        for key, name in [('reverb_room', 'roomsize'), ('reverb_damping', 'damp'), ('reverb_width', 'width'), ('reverb_level', 'level')]:
            getattr(self.lib, 'fluid_synth_set_reverb_group_' + name)(self.synth, -1, values[key])
        self.params = values

    def reset(self):
        for channel in range(16):
            self.lib.fluid_synth_all_sounds_off(self.synth, channel)
            self.lib.fluid_synth_cc(self.synth, channel, 121, 0)
        self.programmed=False
        self.configure(self.params)
        # FluidSynth has a 64-frame output cache and a short click-suppression
        # release ramp after all_sounds_off. Drain 20 ms plus one quantum with
        # no active notes, so a seek cannot emit the previous position's voices.
        # No new MIDI events have been scheduled at this point.
        count=round(self.rate*.02)+64
        left=(C.c_float*count)();right=(C.c_float*count)()
        if self.lib.fluid_synth_write_float(self.synth,count,left,0,1,right,0,1)<0:
            raise RuntimeError('General MIDI reset failed')

    def message(self, packet):
        data = list(validate_midi_packet(packet))
        kind, channel = data[0] & 240, data[0] & 15
        operations = {128: ('noteoff', data[1:2]), 144: ('noteon', data[1:]), 160: ('key_pressure', data[1:]),
                      176: ('cc', data[1:]), 192: ('program_change', data[1:]), 208: ('channel_pressure', data[1:])}
        if kind == 224:
            name, args = 'pitch_bend', [data[1] + (data[2] << 7)]
        elif kind == 240:
            # Do not silently reinterpret vendor SysEx as channel data.
            if data in ([240, 126, 127, 9, 1, 247], [240, 126, 127, 9, 3, 247]):
                self.reset()
                return
            raise ValueError('This GM plugin supports GM reset SysEx; use a VSTi/hardware device for vendor SysEx')
        else:
            name, args = operations[kind]
        if kind==144 and data[2]==0:
            name,args='noteoff',[data[1]]
        result=getattr(self.lib, 'fluid_synth_' + name)(self.synth, channel, *args)
        # Validated note-offs are idempotent MIDI state updates. FluidSynth
        # returns FLUID_FAILED when a one-shot sample has already ended or
        # voice stealing removed it; this must not abort a complete MIDI file.
        # https://www.fluidsynth.org/api/group__midi__messages.html
        if result<0 and name!='noteoff':
            raise ValueError('General MIDI event rejected: ' + name)

    def process(self, messages, *, duration, sample_rate, num_channels=2, buffer_size=512, reset=False):
        import numpy as np
        if sample_rate != self.rate or num_channels != 2:
            raise ValueError('General MIDI output format changed')
        events = schedule_gm_events(messages, duration=duration, rate=self.rate)
        if reset:self.reset()
        count = round(duration * self.rate)
        if not 0 < count <= 32768:
            raise ValueError('General MIDI block exceeds limit')
        result = np.zeros((2, count), dtype=np.float32)
        position = 0
        for message, seconds in [*events, (None, duration)]:
            end = max(position, min(count, round(seconds*self.rate)))
            if end > position:
                left = result[0, position:].ctypes.data_as(C.c_void_p)
                right = result[1, position:].ctypes.data_as(C.c_void_p)
                if self.lib.fluid_synth_write_float(self.synth, end-position, left, 0, 1, right, 0, 1) < 0:
                    raise RuntimeError('General MIDI synthesis failed')
            if message is not None:
                self.message(message)
            position = end
        if not np.isfinite(result).all():
            raise RuntimeError('General MIDI produced non-finite audio')
        return result

    def close(self):
        if self.synth:
            self.lib.delete_fluid_synth(self.synth)
            self.synth = None
        if self.settings:
            self.lib.delete_fluid_settings(self.settings)
            self.settings = None

    def __del__(self):
        self.close()


def worker_resources(project):
    resources=[]
    if any(track.instrument and track.instrument.plugin=='gm_soundfont' for track in project.tracks):
        banks={track.instrument.params.get('bank_id','fluidr3-gm') for track in project.tracks
               if track.instrument and track.instrument.plugin=='gm_soundfont'}
        resources.extend(bank_path(bank_id) if bank_id=='fluidr3-gm' else bank_path(bank_id).parent for bank_id in banks)
        path=library_path()
        if path and Path(path).is_absolute():resources.append(Path(path).parent)
    return resources


class Synth(FluidSynth):
    def __new__(cls,params,rate):
        if not library_path():
            from .gm_portable import Synth as PortableSynth
            return PortableSynth(params,rate)
        return super().__new__(cls)
