#!/usr/bin/env python3
"""Offline, fixed-protocol comparison of real Audio-to-MIDI prediction JSON files.

No model inference, network access, offset fitting or threshold modification.
Use predictions from independent inference runs on the same recording.
"""
import argparse
import json
from pathlib import Path

from evaluate_mrmt3_alignment import match, notes_reference


def score(reference, predicted):
    matched = match(reference, predicted)
    matched_agnostic = match(reference, predicted, program_agnostic=True)
    precision = matched / len(predicted) if predicted else 0.0
    recall = matched / len(reference) if reference else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {'matched': matched, 'reference_notes': len(reference),
            'predicted_notes': len(predicted), 'precision': precision,
            'recall': recall, 'f1': f1,
            'matched_ignoring_program_diagnostic': matched_agnostic}


def parse_prediction(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('notes'), list):
        raise ValueError(f'{path}: expected a prediction object with notes list')
    out = []
    for n in data['notes']:
        if not isinstance(n, dict):
            raise ValueError(f'{path}: invalid note object')
        program = 'drums' if n['is_drum'] else int(n['program'])
        pitch = int(n['pitch'])
        start, end = float(n['start_time']), float(n['end_time'])
        from math import isfinite
        if not all(map(isfinite, (start, end))) or start < 0 or end < start or not 0 <= pitch <= 127:
            raise ValueError(f'{path}: invalid note pitch/time')
        if program != 'drums' and not 0 <= program <= 127:
            raise ValueError(f'{path}: invalid GM program')
        out.append((program, pitch, start, end))
    return out


def compare(midi, models):
    reference = notes_reference(midi)
    if not reference:
        raise ValueError('Reference MIDI has no completed notes')
    result = {'protocol': 'fixed-zero-offset-50ms-onset-100ms-offset',
              'note': 'No calibration on the reference MIDI; zero offset is fixed. Program-agnostic matches are diagnostic only.',
              'reference_notes': len(reference), 'reference_programs': len(set(n[0] for n in reference)), 'models': {}}
    for name, path in models.items():
        predicted = parse_prediction(path)
        programs = sorted(set(n[0] for n in reference) | set(n[0] for n in predicted), key=str)
        by_program = {}
        for program in programs:
            r = [n for n in reference if n[0] == program]
            p = [n for n in predicted if n[0] == program]
            by_program[str(program)] = score(r, p)
        result['models'][name] = {'overall': score(reference, predicted),
                                  'predicted_programs': len(set(n[0] for n in predicted)),
                                  'per_program': by_program}
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--midi', required=True, type=Path)
    p.add_argument('--prediction', action='append', required=True, metavar='NAME=PATH')
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args(argv)
    models = {}
    for item in a.prediction:
        name, sep, path = item.partition('=')
        if not sep or not name or not path or name in models:
            p.error('Each --prediction must be a unique NAME=PATH')
        models[name] = Path(path)
    report = compare(a.midi, models)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({name: entry['overall'] for name, entry in report['models'].items()}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
