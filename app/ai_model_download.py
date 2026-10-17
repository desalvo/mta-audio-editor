"""Model-manager bridge executed only by an operator-configured AI interpreter."""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=('whisper', 'chords-ml'), required=True)
    parser.add_argument('--model', required=True)
    args = parser.parse_args()
    from app.ai_models import download_lyrics_model, download_chord_model
    # Libraries may print progress; keep the machine-readable response separate.
    with redirect_stdout(sys.stderr):
        call = download_lyrics_model if args.kind == 'whisper' else download_chord_model
        document = call(args.model, native=False)
    print(json.dumps(document))


if __name__ == '__main__':
    main()
