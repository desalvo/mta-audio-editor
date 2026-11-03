"""Generate original diagnostic audio and optional exact-reference metric controls.

This command never loads a model and cannot approve separation quality.
"""
import argparse
import json
from pathlib import Path

from app.percussion_corpus import generate, safe_path, sha256
from app.percussion_metrics import analyze, CRITERIA


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--duration', type=float, default=12)
    parser.add_argument('--controls-report', type=Path)
    args = parser.parse_args()
    manifest = generate(args.output, seed=args.seed, duration_seconds=args.duration)
    summary = {'dataset_id': manifest['id'], 'counts': manifest['counts'],
               'manifest_sha256': sha256(args.output / 'manifest.json'),
               'neural_inference_performed': False, 'human_approval': False}
    if args.controls_report:
        results = []
        for case in manifest['cases']:
            if not case['prepared']:
                continue
            for variant, relative in case['references'].items():
                reference = safe_path(args.output, relative)
                result = analyze(reference, safe_path(args.output, case['input_drums']), reference,
                                 {key: safe_path(args.output, value) for key, value in case['sources'].items()})
                results.append({'case_id': case['id'], 'variant': variant, 'group': case['group'],
                                'category': case['category'], 'control': 'unchanged_ground_truth_reference',
                                'metrics': result})
        report = {'schema': 'mta-percussion-control-evidence-1', **summary, 'criteria': CRITERIA,
                  'controls_run': len(results), 'controls_passed': sum(r['metrics']['technical_pass'] for r in results),
                  'limits': 'Exact-reference diagnostic controls only. No separator ran. These are procedural surrogates, not recordings or model quality evidence.',
                  'results': results}
        args.controls_report.parent.mkdir(parents=True, exist_ok=True)
        args.controls_report.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n')
        summary.update(controls_run=report['controls_run'], controls_passed=report['controls_passed'])
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()

