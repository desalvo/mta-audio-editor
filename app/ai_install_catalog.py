"""Installation coverage for every built-in worker; extend with the worker registry."""
ENGINE_GROUPS = {
    'ace-step': 'ace', 'arranger': 'ace', 'remix': 'ace',
    'whisper': 'audio', 'chords-ml': 'audio', 'markers': 'audio',
    'demucs': 'audio', 'drumsep': 'audio', 'backing-vocals': 'audio',
    'sam-audio': 'sam', 'singer-separation': 'sam',
}
IMPORTS = {
    'audio': ['torch', 'torchaudio', 'torchvision', 'demucs.separate', 'whisper',
              'madmom_infer', 'librosa', 'onnxruntime', 'audio_separator.separator'],
    'sam': ['torch', 'torchaudio', 'sam_audio'],
}


def validate_coverage():
    from .ai_worker_registry import WORKER_KINDS
    missing = WORKER_KINDS - ENGINE_GROUPS.keys()
    obsolete = ENGINE_GROUPS.keys() - WORKER_KINDS
    if missing or obsolete:
        raise ValueError(f'AI install catalog mismatch: missing={sorted(missing)}, obsolete={sorted(obsolete)}')
    if set(ENGINE_GROUPS.values()) - {'ace', 'audio', 'sam'}:
        raise ValueError('AI installation recipe missing')
    return dict(ENGINE_GROUPS)
