#!/usr/bin/env python3
"""Optional, trusted Basic Pitch ONNX adapter for isolated-source transcription.

Uses the existing metered worker protocol. No downloads, user code, instrument
classification, synthetic filler parts or claimed GPU acceleration.
"""
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import stat
import sys

# Disable ONNX telemetry before the first import/initialization, including the
# installation self-test. The API alone is too late for initialization events.
os.environ['ORT_DISABLE_TELEMETRY'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MODEL_SHA256 = '2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec'


def progress(phase, message):
    value = os.environ.get('MTA_AI_PROGRESS_FILE')
    if value:
        from app.storage import _atomic_json_write
        _atomic_json_write(Path(value), {'phase': phase, 'message': message,
                                        'progress_percent': None, 'progress_estimated': False})


def model_path():
    if importlib.metadata.version('basic-pitch') != '0.4.0':
        raise RuntimeError('Basic Pitch 0.4.0 is required by this adapter')
    from basic_pitch import build_icassp_2022_model_path, FilenameSuffix
    path = build_icassp_2022_model_path(FilenameSuffix.onnx)
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != MODEL_SHA256:
        raise RuntimeError('Basic Pitch ONNX model failed integrity verification')
    return path


def transcribe(source, options):
    from app.music_interchange import MusicPart, MusicResult
    from app.models import MidiNote
    import soundfile as sf
    info = sf.info(str(source))
    if info.channels not in (1, 2) or not 0 < info.duration <= 600 or info.samplerate > 192000:
        raise ValueError('Basic Pitch pilot accepts mono/stereo audio up to 10 minutes and 192 kHz')
    allowed = {'onset_threshold', 'frame_threshold', 'minimum_note_length', 'program', 'name'}
    if not isinstance(options, dict) or set(options)-allowed:
        raise ValueError('Unknown Basic Pitch parameter')
    args = {}
    for name, default, low, high in [('onset_threshold', .5, .05, .95),
                                    ('frame_threshold', .3, .05, .95),
                                    ('minimum_note_length', 127.7, 20, 2000)]:
        value = options.get(name, default)
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError('Invalid Basic Pitch parameter: '+name)
        args[name] = value
    program = options.get('program')
    if program is not None and (type(program) is not int or not 0 <= program <= 127):
        raise ValueError('Instrument program must be supplied explicitly between 0 and 127')
    name = options.get('name', 'Transcribed source')
    if not isinstance(name, str) or not 1 <= len(name) <= 200:
        raise ValueError('Invalid transcription name')
    progress('loading-model', 'Verifying and loading Basic Pitch ONNX on CPU')
    path = model_path()
    import onnxruntime as ort
    ort.disable_telemetry_events()
    from basic_pitch.inference import predict, Model
    # Construct the supported Model wrapper with an explicit bounded CPU session;
    # default ORT threading oversubscribes large hosts and concurrent AI jobs.
    settings = ort.SessionOptions()
    settings.intra_op_num_threads = min(4, os.cpu_count() or 1)
    settings.inter_op_num_threads = 1
    model = Model.__new__(Model)
    model.model_type = Model.MODEL_TYPES.ONNX
    model.model = ort.InferenceSession(str(path), sess_options=settings, providers=['CPUExecutionProvider'])
    if model.model_type != Model.MODEL_TYPES.ONNX:
        raise RuntimeError('This adapter requires the tested ONNX CPU backend')
    progress('transcribing', 'Transcribing the isolated source; total work is not reported by the model')
    _, _, events = predict(str(source), model_or_model_path=model, **args)
    from app.transcription_timing import bound_interval
    notes = [];trimmed=dropped=0
    for index, (start, end, pitch, activation, _) in enumerate(events):
        # Activation scales MIDI velocity; it is deliberately not confidence.
        if not all(math.isfinite(float(v)) for v in (start, end, pitch, activation)) or end <= start:
            raise ValueError('Basic Pitch produced an invalid event')
        interval=bound_interval(float(start),float(end),info.duration)
        if interval is None:
            dropped+=1;continue
        trimmed+=interval!=(start,end)
        start,end=interval
        notes.append(MidiNote(id=f'bp-{index}', start_ms=start*1000, duration_ms=(end-start)*1000,
                              pitch=int(pitch), velocity=max(1, min(127, round(activation*127))),
                              origin='predicted', source_model='basic-pitch-0.4.0-onnx'))
    if not notes:
        from app.music_interchange import no_notes
        return no_notes(['Basic Pitch detected no pitched notes; no tracks were invented.'])
    return MusicResult(parts=[MusicPart(id='source', name=name, instrument='user-assigned' if program is not None else 'unknown',
                                       program=program, notes=notes, source_model='basic-pitch-0.4.0-onnx')],
                       warnings=['Basic Pitch transcribes one source; instrument identity and calibrated confidence are unavailable.',
                                 f'Source audio bounds: {trimmed} note intervals trimmed; {dropped} padding intervals discarded.',
                                 'Pitch bends are not imported by this adapter. Review the unquantized MIDI before use.'])


def infer(plan, output):
    folder = output.parent.resolve(strict=True)
    if plan.get('kind')=='vocal-synthesis':
        from app.studio_score import validate
        from app.vocal_synthesis import render
        from app.ai_unified_adapter import _artifacts
        source=folder/'score.json'
        if plan.get('source_score')!=str(source) or source.is_symlink() or source.stat().st_nlink!=1:raise ValueError('Unsafe score transport')
        _artifacts(folder,render(validate(source.read_bytes()),plan.get('settings',{}),folder,progress));return
    if plan.get('kind')=='vocal-harmony':
        from app.vocal_harmony import arrange
        from app.studio_score import validate
        score_path=folder/'score.json'
        if plan.get('source_score')!=str(score_path) or score_path.is_symlink() or score_path.stat().st_nlink!=1:raise ValueError('Unsafe score transport')
        score=validate(score_path.read_bytes())
        if len(score.music.parts)!=1:raise ValueError('Select a single melody part for vocal harmony')
        result=arrange(score.music.parts[0].notes,score.chords,plan.get('settings',{}))
        target=folder/'music.json';target.write_text(result.model_dump_json(),encoding='utf-8')
        from app.ai_unified_adapter import _artifacts
        _artifacts(folder,[(target,'application/json')]);return
    source = folder/'source.wav'
    if plan.get('kind') not in {'audio-to-midi','audio-to-midi-basic-pitch','audio-to-midi-yourmt3','audio-to-midi-mr-mt3','audio-to-midi-transkun'} or Path(str(plan.get('source_audio', ''))) != source or source.is_symlink():
        raise ValueError('Invalid studio worker request')
    info = source.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 512*1024*1024:
        raise ValueError('Unsafe or oversized studio audio source')
    if plan.get('kind')=='audio-to-midi-transkun':
        from app.transkun_adapter import transcribe as piano_transcribe
        result=piano_transcribe(source,plan.get('options',{}))
    elif plan.get('kind')=='audio-to-midi-mr-mt3' or (plan.get('kind')=='audio-to-midi' and os.getenv('MTA_STUDIO_TRANSCRIBER')=='mr-mt3'):
        from app.mrmt3_adapter import transcribe as mrmt3_transcribe
        result=mrmt3_transcribe(source,plan.get('options',{}))
    elif plan.get('kind')=='audio-to-midi-yourmt3' or (plan.get('kind')=='audio-to-midi' and os.getenv('MTA_STUDIO_TRANSCRIBER')=='yourmt3'):
        from app.yourmt3_adapter import transcribe as mixed_transcribe
        result=mixed_transcribe(source,plan.get('options',{}))
    else:
        result = transcribe(source, plan.get('options', {}))
    progress('writing-results', 'Validating editable MIDI events and publishing the artifact manifest')
    target = folder/'music.json'
    target.write_text(result.model_dump_json(), encoding='utf-8')
    from app.ai_unified_adapter import _artifacts
    _artifacts(folder, [(target, 'application/json')])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--self-test', type=Path)
    args = parser.parse_args()
    if args.self_test:
        import tempfile
        import numpy as np
        import soundfile as sf
        with tempfile.TemporaryDirectory(prefix='mta-bp-test-') as folder:
            source=Path(folder)/'source.wav';rate=44100;t=np.arange(rate*2)/rate
            sf.write(source,.2*np.sin(2*np.pi*440*t),rate)
            result=transcribe(source,{})
            if not any(n.pitch==69 for p in result.parts for n in p.notes):raise RuntimeError('Basic Pitch pitch self-test failed')
        args.self_test.write_text(json.dumps({'model_path':str(model_path()),'sha256':MODEL_SHA256,'device':'cpu','notes':sum(len(p.notes) for p in result.parts)}))
    else:
        if not args.request or not args.output:parser.error('--request and --output are required')
        if args.request.stat().st_size > 256*1024:raise ValueError('Studio request exceeds 256 KiB')
        infer(json.loads(args.request.read_text()), args.output)
