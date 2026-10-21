"""Model-manager bridge executed only by an operator-configured AI interpreter."""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=('whisper', 'chords-ml', 'backing-vocals'), required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--model-dir')
    args = parser.parse_args()
    from app.ai_models import download_lyrics_model, download_chord_model
    # Libraries may print progress; keep the machine-readable response separate.
    with redirect_stdout(sys.stderr):
        if args.kind == 'backing-vocals':
            from app.ai_backend_models import LEAD_BACKING_MODELS
            model = next((item for item in LEAD_BACKING_MODELS if item['id'] == args.model), None)
            if model is None:
                raise ValueError('Unsupported lead/backing model')
            folder = Path(args.model_dir or '')
            if not folder.is_absolute():
                raise ValueError('Absolute operator model directory required')
            folder.mkdir(parents=True, exist_ok=True)
            from audio_separator.separator import Separator
            separator = Separator(model_file_dir=str(folder), output_dir=str(folder), info_only=True)
            separator.download_model_files(model['filename'])
            if not (folder / model['filename']).is_file():
                raise RuntimeError('Downloaded model is missing')
            if args.model == 'uvr_mdxnet_kara_2':
                from app.uvr_kara_integrity import verify_kara_2
                verify_kara_2(folder / model['filename'])
            document = {'id': args.model, 'installed': True}
        else:
            call = download_lyrics_model if args.kind == 'whisper' else download_chord_model
            document = call(args.model, native=False)
    print(json.dumps(document))


if __name__ == '__main__':
    main()
