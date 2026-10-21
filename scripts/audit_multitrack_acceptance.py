#!/usr/bin/env python3
"""Fail-closed audit for fixed-protocol multitrack benchmark outputs.

Reports evidence only. It does not invent a project quality threshold or tune
parameters on the evaluation MIDI. Completion requires separately reviewed
quality criteria and independent model inference.
"""
import argparse
import json
from pathlib import Path


def audit(report, *, minimum=10, maximum=16):
    if report.get('protocol') != 'fixed-zero-offset-50ms-onset-100ms-offset':
        raise ValueError('Unrecognized or altered evaluation protocol')
    if not 1 <= minimum <= maximum <= 128:
        raise ValueError('Invalid instrument range')
    models = report.get('models')
    if not isinstance(models, dict) or not models:
        raise ValueError('At least one measured model is required')
    output = {'protocol': report['protocol'], 'required_instrument_range': [minimum, maximum], 'models': {}}
    for name, record in models.items():
        overall = record['overall']
        rows = record['per_program']
        if not isinstance(rows, dict):
            raise ValueError('Missing per-program actual measurements')
        qualifying = []
        for program, metrics in rows.items():
            if program == 'drums':
                continue
            tp = metrics['matched']
            r = metrics['reference_notes']
            p = metrics['predicted_notes']
            if not all(isinstance(value, int) and value >= 0 for value in (tp, r, p)) or tp > min(r, p):
                raise ValueError('Inconsistent note counts')
            if tp > 0:
                qualifying.append(program)
        f1 = overall['f1']
        if not isinstance(f1, (float, int)) or not 0 <= f1 <= 1:
            raise ValueError('Invalid F1 score')
        output['models'][name] = {
            'strict_f1': f1,
            'matched_melodic_programs': len(qualifying),
            'matched_melodic_program_ids': sorted(qualifying, key=lambda x: int(x)),
            'minimum_instrument_evidence': len(qualifying) >= minimum,
            'quality_certified': False,
            'reason': 'Instrument count is only a necessary check; independent musical accuracy acceptance and genuine inference are still required.',
        }
    output['accuracy_10_to_16_certified'] = False
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('comparison', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--minimum-instruments', type=int, default=10)
    parser.add_argument('--maximum-instruments', type=int, default=16)
    args = parser.parse_args(argv)
    result = audit(json.loads(args.comparison.read_text(encoding='utf-8')),
                   minimum=args.minimum_instruments, maximum=args.maximum_instruments)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(result, sort_keys=True))
    return 2  # An audit cannot certify model accuracy without independent acceptance.


if __name__ == '__main__':
    raise SystemExit(main())
