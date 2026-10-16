#!/usr/bin/env python3
"""Fixed trusted backend entrypoints, profiled in the process doing GPU work."""
from pathlib import Path
import argparse
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.ai_torch_diagnostics import profile_call


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=('demucs', 'sam-audio'), required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--report-dir', type=Path, required=True)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    arguments = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments

    def call():
        previous = sys.argv
        try:
            sys.argv = [args.backend, *arguments]
            try:
                if args.backend == 'demucs':
                    runpy.run_module('demucs.separate', run_name='__main__')
                else:
                    runpy.run_path(str(Path(__file__).with_name('sam_audio_worker.py')), run_name='__main__')
            except SystemExit as error:
                if error.code not in (None, 0):
                    raise
        finally:
            sys.argv = previous

    profile_call(args.report_dir, args.task_id, call)


if __name__ == '__main__':
    main()
