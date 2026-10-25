#!/usr/bin/env python3
"""Render a standard MIDI file through MTA's licensed General MIDI backend.

Offline acceptance tool: no audio hardware, network, or server credentials needed.
It requires an installed reviewed FluidR3 bank and FluidSynth or TinySoundFont.
"""
import argparse
from pathlib import Path
import math
import os
import tempfile

MAX_SECONDS = 600
MAX_EVENTS = 200000


def midi_events(path):
    """Return channel packets at absolute seconds, respecting all tempo changes."""
    import mido
    from app.gm_instruments import validate_midi_packet
    midi = mido.MidiFile(str(path))
    if midi.type == 2:
        raise ValueError('Asynchronous type-2 MIDI files need a dedicated timeline')
    if not 1 <= midi.ticks_per_beat <= 32767:
        raise ValueError('Unsupported MIDI ticks per beat')
    tempo, seconds, events = 500000, 0., []
    for event in mido.merge_tracks(midi.tracks):
        ticks_delta = event.time
        if ticks_delta < 0:
            raise ValueError('Negative MIDI delta-time')
        seconds += mido.tick2second(ticks_delta, midi.ticks_per_beat, tempo)
        if not math.isfinite(seconds) or seconds > MAX_SECONDS:
            raise ValueError('MIDI exceeds ten-minute rendering limit')
        if event.type == 'set_tempo':
            if not 1 <= event.tempo <= 0xffffff:
                raise ValueError('Invalid MIDI tempo')
            tempo = event.tempo
        elif not event.is_meta:
            if event.type == 'sysex':
                packet = (240, *event.data, 247)
            else:
                packet = tuple(event.bytes())
            events.append((validate_midi_packet(packet), seconds))
            if len(events) > MAX_EVENTS:
                raise ValueError('MIDI exceeds event budget')
    return events, seconds


def render_file(source, destination, *, rate=48000, tail=1., block_frames=8192, synth_factory=None):
    import numpy as np
    import soundfile as sf
    from app.gm_instruments import Synth
    if type(rate) is not int or not 8000 <= rate <= 192000:
        raise ValueError('Invalid GM output rate')
    if type(block_frames) is not int or not 1 <= block_frames <= 32768:
        raise ValueError('Invalid GM buffer size')
    if not math.isfinite(tail) or not 0 <= tail <= 10:
        raise ValueError('Invalid GM release tail')
    events, duration = midi_events(source)
    if not events:
        raise ValueError('MIDI file has no playable channel events')
    total = math.ceil((duration + tail) * rate)
    if total <= 0 or total > (MAX_SECONDS + 10) * rate:
        raise ValueError('MIDI output exceeds duration budget')
    destination = Path(destination)
    # Write beside the destination so publication can be atomic on its filesystem.
    temporary = None
    synth = (synth_factory or Synth)({'reverb_level':0.25}, rate)
    position = 0
    cursor = 0
    try:
        with tempfile.NamedTemporaryFile(prefix='.mta-gm-', suffix='.wav', dir=str(destination.parent), delete=False) as tmp:
            temporary = Path(tmp.name)
        with sf.SoundFile(str(temporary), mode='w', samplerate=rate, channels=2, subtype='PCM_24') as sink:
            while position < total:
                next_position = min(total, position + block_frames)
                # Work in sample positions to prevent a note-on crossing a block boundary.
                current=[]
                while cursor < len(events) and round(events[cursor][1]*rate) < next_position:
                    packet, at = events[cursor]
                    if round(at*rate) >= position:
                        current.append((packet, max(0., (round(at*rate)-position)/rate)))
                    cursor += 1
                frames=next_position-position
                audio=synth.process(current,duration=frames/rate,sample_rate=rate,num_channels=2)
                array=np.asarray(audio,dtype=np.float32)
                if array.shape != (2,frames) or not np.isfinite(array).all():
                    raise RuntimeError('General MIDI backend returned invalid PCM')
                sink.write(array.T)
                position=next_position
        os.replace(temporary, destination)
        temporary = None
    finally:
        try:
            synth.close()
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return {'sample_rate':rate,'frames':total,'events':len(events),'seconds':total/rate}


def main():
    from sys import path as sys_path
    sys_path.insert(0,str(Path(__file__).resolve().parents[1]))
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('midi',type=Path)
    parser.add_argument('wav',type=Path)
    parser.add_argument('--rate',type=int,default=48000)
    args=parser.parse_args()
    print(render_file(args.midi,args.wav,rate=args.rate))

if __name__ == '__main__':
    main()
