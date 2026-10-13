"""Trusted optional inference backends for the metered AI worker subprocess protocol.

Install this file only through the operator-controlled worker registry. Heavy model
libraries are imported lazily. All paths originate in the private job directory.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
# Subprocess starts in the isolated job workspace, not the repository.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SUPPORTED = {'whisper', 'chords-ml', 'demucs', 'drumsep', 'sam-audio', 'singer-separation', 'backing-vocals'}


def _artifacts(folder: Path, entries: list[tuple[Path, str]]) -> None:
    manifest = []
    for path, media in entries:
        if path.parent.resolve() != folder.resolve() or not path.is_file():
            raise RuntimeError('Worker output must be a regular file in job workspace')
        manifest.append({'name': path.name, 'type': media})
    (folder / 'output.manifest.json').write_text(json.dumps({'version': 1, 'files': manifest}), encoding='utf-8')


def infer(plan: dict, output: Path) -> None:
    kind = plan.get('kind')
    if kind not in SUPPORTED:
        raise ValueError('Unsupported unified inference backend')
    folder = output.parent.resolve()
    source = Path(str(plan.get('source_audio', ''))).resolve()
    if source.parent != folder or source.name != 'source.wav' or not source.is_file():
        raise ValueError('Audio must be staged into the private job workspace')
    if kind == 'whisper':
        from app.music_text import extract_lyrics
        lines = extract_lyrics(source, model_name=str(plan.get('model') or 'turbo'),
                              language=plan.get('language') or None,
                              advanced_alignment=bool(plan.get('advanced_alignment', False)))
        result = folder / 'transcript.json'
        result.write_text(json.dumps({'lines': [v.model_dump(mode='json') for v in lines]}, ensure_ascii=False), encoding='utf-8')
        _artifacts(folder, [(result, 'application/json')]); return
    if kind == 'chords-ml':
        from app.music_text import extract_chords
        chords = extract_chords(source)
        result = folder / 'chords.json'
        result.write_text(json.dumps({'chords': [v.model_dump(mode='json') for v in chords]}, ensure_ascii=False), encoding='utf-8')
        _artifacts(folder, [(result, 'application/json')]); return
    if kind == 'drumsep':
        from app.drumsep_onnx_worker import infer as drumsep_infer
        model = Path(os.environ.get('MTA_AI_DRUMSEP_MODEL', ''))
        if not model.is_file():
            raise RuntimeError('Operator must configure MTA_AI_DRUMSEP_MODEL')
        paths = drumsep_infer(source, model, folder)
        _artifacts(folder, [(p, 'audio/wav') for p in paths]); return
    if kind == 'sam-audio':
        from app.sam_audio_worker import main as _unused  # noqa: F401
        import subprocess
        model = os.environ.get('MTA_AI_SAM_MODEL', '')
        if not model: raise RuntimeError('Operator must configure MTA_AI_SAM_MODEL')
        runner = Path(__file__).with_name('sam_audio_worker.py')
        target = folder / 'separated.wav'
        subprocess.run([sys.executable, str(runner), '--source', str(source), '--output', str(target),
                        '--model', model, '--prompt', str(plan.get('prompt') or 'vocals')], check=True)
        _artifacts(folder, [(target, 'audio/wav')]); return
    if kind == 'demucs':
        import subprocess
        model = str(plan.get('model') or 'htdemucs')
        if not model.replace('_', '').replace('-', '').isalnum() or len(model) > 64:
            raise ValueError('Invalid Demucs model')
        subprocess.run([sys.executable, '-m', 'demucs.separate', '--name', model, '--out', str(folder/'demucs'), str(source)], check=True)
        paths = sorted((folder/'demucs'/model/source.stem).glob('*.wav'))
        if not paths: raise RuntimeError('Demucs produced no stems')
        staged=[]
        for p in paths:
            dest = folder / ('stem_' + p.name)
            p.replace(dest); staged.append((dest, 'audio/wav'))
        _artifacts(folder, staged); return
    if kind == 'singer-separation':
        import subprocess
        singers = plan.get('singers')
        selected = plan.get('selected','all')
        model = str(plan.get('model') or 'sam-audio-small')
        if model not in {'sam-audio-small','sam-audio-base','sam-audio-large'} or not isinstance(singers,list) or not 2<=len(singers)<=8:
            raise ValueError('Invalid singer separation parameters')
        required = {'singer_'+str(i) for i in range(1,len(singers)+1)}
        if selected!='all' and selected not in required: raise ValueError('Unknown singer target')
        for index, item in enumerate(singers,1):
            if not isinstance(item,dict) or item.get('id')!='singer_'+str(index):
                raise ValueError('Invalid singer identifier')
            if not all(isinstance(item.get(k),(int,float)) for k in ('start','end')) or not 0<=item['start']<item['end']<=86400:
                raise ValueError('Invalid singer interval')
        runner=Path(__file__).with_name('sam_audio_worker.py')
        files=[]
        for singer in singers:
            if selected!='all' and selected!=singer['id']:continue
            anchors=[['+',singer['start'],singer['end']]]+[['-',v['start'],v['end']] for v in singers if v['id']!=singer['id']]
            result=folder/(singer['id']+'.wav')
            subprocess.run([sys.executable,str(runner),'--source',str(source),'--output',str(result),
                            '--model','facebook/'+model,'--prompt','singing voice',
                            '--anchors-json',json.dumps(anchors)],check=True)
            files.append((result,'audio/wav'))
        _artifacts(folder,files)
        return
    if kind == 'backing-vocals':
        # A configured audio-separator model is mandatory; no DSP fallback is silently billed as AI.
        from audio_separator.separator import Separator
        model = os.environ.get('MTA_AI_VOCAL_MODEL', '')
        if not model or '/' in model or '\\' in model:
            raise RuntimeError('Operator must configure a safe MTA_AI_VOCAL_MODEL filename')
        separator = Separator(output_dir=str(folder), output_format='WAV', model_file_dir=os.environ.get('MTA_AI_VOCAL_MODELS_DIR', ''))
        separator.load_model(model_filename=model)
        names = separator.separate(str(source))
        paths=[]
        for index, name in enumerate(names):
            source_path = Path(name)
            if not source_path.is_absolute(): source_path = folder/source_path
            if source_path.resolve().parent != folder or not source_path.is_file():
                raise RuntimeError('Unexpected output path from separator')
            dest=folder/f'voice_{index}.wav'
            source_path.replace(dest); paths.append((dest, 'audio/wav'))
        if not paths: raise RuntimeError('Separator produced no audio')
        _artifacts(folder, paths)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.request.read_text(encoding='utf-8'))
    infer(data, args.output)


if __name__ == '__main__':
    main()
