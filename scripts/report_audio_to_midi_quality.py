"""Create an exportable integrity-bound Audio-to-MIDI quality report from reviewed MusicResult JSON."""
import argparse
import json
from pathlib import Path
import zipfile
from app.studio_midi_benchmark import evaluate_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True, help='Ground-truth MusicResult JSON')
    parser.add_argument('--prediction', type=Path, required=True, help='Predicted MusicResult JSON')
    parser.add_argument('--output', type=Path, required=True, help='New report ZIP')
    args = parser.parse_args()
    report = evaluate_files(args.reference, args.prediction)
    target = args.output.resolve()
    if target.exists() or target.is_symlink():
        parser.error('Output already exists; choose a new report path')
    if target in (args.reference.resolve(), args.prediction.resolve()):
        parser.error('Output must differ from inputs')
    data = json.dumps(report, indent=2, sort_keys=True, allow_nan=False).encode('utf-8')
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('quality-report.json', data)
        z.writestr('README.txt', 'MTA Audio-to-MIDI comparison: strict F1, per-instrument diagnostics and fidelity score.\n100 requires full fidelity across every reference instrument. Audio/MIDI alignment and source authenticity must be independently verified.\n')
    print(json.dumps({'output': str(target), 'fidelity_score_0_100': report['fidelity_score_0_100'], 'status': report['fidelity_score_status']}))

if __name__ == '__main__':
    main()
