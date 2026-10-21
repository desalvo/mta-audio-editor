#!/usr/bin/env python3
"""Compare a real Audio-to-MIDI result to reviewed MusicResult ground truth."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.studio_midi_benchmark import evaluate_files


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path, help='Reviewed MusicResult JSON')
    parser.add_argument('prediction', type=Path, help='Actual MusicResult JSON from audio-to-midi')
    parser.add_argument('--onset-ms',type=float,default=50)
    parser.add_argument('--offset-ms',type=float,default=100)
    parser.add_argument('--min-instruments',type=int,default=10)
    args=parser.parse_args(argv)
    if not 1 <= args.min_instruments <= 128:
        parser.error('--min-instruments must be between 1 and 128')
    report=evaluate_files(args.reference,args.prediction,onset_ms=args.onset_ms,offset_ms=args.offset_ms)
    report['target_instruments']=args.min_instruments
    report['correctly_matched_instruments']=sum(row['instrument']!='unknown' and row['matched_notes']>0
                                               for row in report['by_instrument'])
    report['instrument_target_met']=report['correctly_matched_instruments']>=args.min_instruments
    report['instrument_target_policy']='At least one one-to-one pitch/onset/offset match per identified instrument; counts alone and unassigned parts cannot pass. Overall accuracy still requires review of precision, recall and F1.'
    print(json.dumps(report,indent=2,sort_keys=True))
    return 0 if report['instrument_target_met'] else 2


if __name__=='__main__':
    sys.exit(main())
