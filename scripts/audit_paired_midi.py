#!/usr/bin/env python3
"""Read-only provenance and MIDI-ground-truth audit for paired rendered audio.

This does not perform neural inference or certify synchronization/accuracy.
"""
import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
import subprocess

import mido


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as src:
        for piece in iter(lambda: src.read(1024 * 1024), b''):
            h.update(piece)
    return h.hexdigest()


def audit(midi_path, audio_path):
    midi_path, audio_path = Path(midi_path), Path(audio_path)
    for path in (midi_path, audio_path):
        if path.is_symlink() or not path.is_file():
            raise ValueError('Both inputs must be regular files, not symlinks')
    malformed = None
    try:
        score = mido.MidiFile(midi_path, clip=False)
    except ValueError as exc:
        malformed = str(exc)
        score = mido.MidiFile(midi_path, clip=True)
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                            'format=duration:stream=codec_name,sample_rate,channels',
                            '-of', 'json', str(audio_path)], capture_output=True,
                           text=True, check=True, timeout=30)
    audio = json.loads(probe.stdout)
    duration = float(audio['format']['duration'])
    if duration <= 0 or duration > 24 * 3600:
        raise ValueError('Invalid audio duration')
    tempo = 500000
    seconds = 0.0
    ticks = 0
    programs = [0] * 16
    program_changes = defaultdict(list)
    notes = Counter()
    notes_per_channel = Counter()
    active = defaultdict(deque)
    unmatched_ends = 0
    # Merged MIDI messages use delta-ticks even for type-1 files.
    for msg in mido.merge_tracks(score.tracks):
        seconds += mido.tick2second(msg.time, score.ticks_per_beat, tempo)
        ticks += msg.time
        if msg.type == 'set_tempo':
            tempo = msg.tempo
        if msg.type == 'program_change':
            programs[msg.channel] = msg.program
            program_changes[msg.channel].append({'tick': ticks, 'program': msg.program})
        if msg.type == 'note_on' and msg.velocity > 0:
            active[msg.channel, msg.note].append((seconds, programs[msg.channel]))
            notes_per_channel[msg.channel] += 1
            notes[(msg.channel, programs[msg.channel])] += 1
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            q = active[msg.channel, msg.note]
            if q:
                q.popleft()
            else:
                unmatched_ends += 1
    dangling = sum(len(q) for q in active.values())
    # Channel 10 drums (index 9) is excluded from GM melodic program count.
    instruments = sorted({(channel, program) for (channel, program), count in notes.items()
                          if count and channel != 9})
    streams = audio.get('streams', [])
    return {
        'schema': 'mta-paired-audio-midi-audit-1',
        'midi': {'sha256': digest(midi_path), 'bytes': midi_path.stat().st_size,
                 'type': score.type, 'tracks': len(score.tracks),
                 'ticks_per_beat': score.ticks_per_beat,
                 'duration_seconds': round(seconds, 6),
                 'strict_parser_error': malformed,
                 'tolerant_parse_used': malformed is not None,
                 'note_on_count': sum(notes_per_channel.values()),
                 'channels_with_notes': len(notes_per_channel),
                 'distinct_melodic_channel_program_pairs': len(instruments),
                 'distinct_melodic_programs': len({p for _, p in instruments}),
                 'programs_with_notes': [{'channel_1based': ch + 1, 'program_0based': pr,
                                         'notes': notes[ch, pr]}
                                        for ch, pr in sorted(notes)],
                 'program_changes': {str(ch + 1): changes for ch, changes in sorted(program_changes.items())},
                 'unmatched_note_ends': unmatched_ends,
                 'dangling_note_starts': dangling},
        'audio': {'sha256': digest(audio_path), 'bytes': audio_path.stat().st_size,
                  'duration_seconds': duration, 'streams': streams},
        'duration_difference_seconds': round(duration - seconds, 6),
        'limitations': ['MIDI events are symbolic ground truth, not verified audible instrument stems.',
                        'Duration difference is not a measured temporal alignment offset.',
                        'Tolerant MIDI parsing changes invalid data bytes; preserve original.',
                        'No inference or accuracy measurements performed.'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('midi', type=Path)
    parser.add_argument('audio', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = json.dumps(audit(args.midi, args.audio), indent=2)
    if args.output:
        args.output.write_text(report + '\n', encoding='utf-8')
    else:
        print(report)


if __name__ == '__main__':
    main()
