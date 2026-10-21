#!/usr/bin/env python3
"""Read-only deployment readiness check for MTA DiffSinger. Does not download weights."""
import argparse
import json
import os
from pathlib import Path
import sys


def check_lyric_profiles(environ, value, asset):
    """Actually exercise G2P through each selected reviewed language profile.

    This is a dependency/phone inventory check, not an acoustic quality test.
    It uses the pinned external runtime when the parent lacks eSpeak.
    """
    from app.vocal_phonemizer import load_profile, phonemize_configured_score
    rows = []
    for language in value['languages']:
        if language == 'vocalise':
            continue
        binding = {**value['bindings'], **value.get('language_bindings', {}).get(language, {})}
        relative = binding['phonemes']
        environment = {**environ, 'MTA_DIFFSINGER_PHONEMES': str(asset(relative)),
                       'MTA_DIFFSINGER_PHONEMES_SHA256': value['files'][relative]['sha256']}
        profile = load_profile(environment['MTA_DIFFSINGER_PHONEMES'],
                               environment['MTA_DIFFSINGER_PHONEMES_SHA256'],
                               environ.get('MTA_NEURAL_SINGER_SHA256'))
        if profile['language'] != language:
            raise ValueError('Selected lyric profile language mismatch: ' + language)
        request = {'language': language, 'notes': [{'id': 'readiness', 'pitch': 60, 'velocity': 96,
                   'start_ms': 0, 'duration_ms': 500, 'syllable': 'la'}]}
        result = phonemize_configured_score(request, profile, environment)
        rows.append({'language': language, 'phones': result['notes'][0]['phonemes'],
                     'profile_sha256': environment['MTA_DIFFSINGER_PHONEMES_SHA256'],
                     'mode': profile.get('pronunciation_mode', 'operator-reviewed')})
    return rows


def check(environ):
    from app.diffsinger_bridge import safe_file
    from app.model_license_policy import evaluate_model
    problems=[]
    model=environ.get('MTA_NEURAL_SINGER_POLICY_MODEL','')
    if not model:
        problems.append('MTA_NEURAL_SINGER_POLICY_MODEL is unset')
    else:
        try:
            from unittest.mock import patch
            with patch.dict(os.environ,environ,clear=False):
                evaluate_model(model)
        except Exception as exc:
            problems.append('Model license/admission policy refused execution: '+str(exc))
    try:
        with __import__('unittest.mock',fromlist=['patch']).patch.dict(os.environ,environ,clear=False):
            evaluate_model(environ.get('MTA_DIFFSINGER_VOCODER_POLICY_MODEL','diffsinger-vocoder'))
    except Exception as exc:
        problems.append('Vocoder license/admission refused execution: '+str(exc))
    if environ.get('MTA_DIFFSINGER_FORMAT')=='openutau-onnx':
        lyric_profiles=[]
        try:
            from unittest.mock import patch
            from app.diffsinger_onnx import inventory
            with patch.dict(os.environ,environ,clear=False):
                value,asset=inventory()
            safe_file(environ.get('MTA_DIFFSINGER_PYTHON',''),environ.get('MTA_DIFFSINGER_PYTHON_SHA256',''))
            for binding,key in (('acoustic','MTA_NEURAL_SINGER_CHECKPOINT'),('vocoder','MTA_DIFFSINGER_VOCODER')):
                if asset(value['bindings'][binding]).resolve()!=Path(environ.get(key,'')).resolve():
                    problems.append('Selected '+binding+' does not match pinned ONNX inventory')
            if value['policies']['singer']!=model or value['policies']['vocoder']!=environ.get('MTA_DIFFSINGER_VOCODER_POLICY_MODEL','diffsinger-vocoder'):
                problems.append('Selected policies do not match pinned ONNX inventory')
            try:
                lyric_profiles=check_lyric_profiles(environ,value,asset)
            except Exception as exc:problems.append('Lyric phonemizer deployment: '+str(exc))
        except Exception as exc:problems.append('ONNX deployment: '+str(exc))
        return {'ready_for_inference_attempt':not problems,'real_audio_validated':False,'format':'openutau-onnx','problems':problems,
                'lyric_profiles':lyric_profiles,
                'next_step':'Run actual ONNX singing and review pronunciation/audio on the target' if not problems else 'Resolve the listed ONNX assets/policies first'}
    root_value=environ.get('MTA_DIFFSINGER_ROOT','')
    root=Path(root_value) if root_value else None
    if root is None or not root.is_absolute() or not root.is_dir():
        problems.append('MTA_DIFFSINGER_ROOT must name an installed absolute directory')
    else:
        script=root/'scripts'/'infer.py'
        if script.is_symlink() or not script.is_file():
            problems.append('Official DiffSinger scripts/infer.py not installed')
        exp=environ.get('MTA_DIFFSINGER_EXPERIMENT','')
        import re
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',exp):
            problems.append('Invalid/missing experiment name')
        elif not (root/'checkpoints'/exp).is_dir():
            problems.append('Selected experiment is not installed')
    if root and root.is_dir():
        try:
            import yaml
            from app.diffsinger_bridge import safe_file
            config_file=safe_file(str(root/'checkpoints'/environ.get('MTA_DIFFSINGER_EXPERIMENT','')/'config.yaml'),
                                  environ.get('MTA_DIFFSINGER_CONFIG_SHA256',''))
            config=yaml.safe_load(config_file.read_text())
            if not isinstance(config,dict) or config.get('base_config'):raise ValueError('Flattened config required')
            selected=Path(config.get('vocoder_ckpt',''))
            if not selected.is_absolute():selected=root/selected
            if str(selected.resolve())!=str(Path(environ.get('MTA_DIFFSINGER_VOCODER','')).resolve()):
                raise ValueError('Vocoder path does not match experiment config')
        except Exception as exc:problems.append('Experiment config: '+str(exc))
    acoustic_name=Path(environ.get('MTA_NEURAL_SINGER_CHECKPOINT','')).name
    import re
    if not re.fullmatch(r'model_ckpt_steps_\d+\.ckpt',acoustic_name):
        problems.append('Acoustic checkpoint must use exact OpenVPI model_ckpt_steps_<step>.ckpt filename')
    for label,location,digest in (
        ('python','MTA_DIFFSINGER_PYTHON','MTA_DIFFSINGER_PYTHON_SHA256'),
        ('acoustic checkpoint','MTA_NEURAL_SINGER_CHECKPOINT','MTA_NEURAL_SINGER_SHA256'),
        ('vocoder','MTA_DIFFSINGER_VOCODER','MTA_DIFFSINGER_VOCODER_SHA256'),
    ):
        try:
            path=safe_file(environ.get(location,''),environ.get(digest,''))
            if label=='acoustic checkpoint' and root and root.is_dir():
                exp=environ.get('MTA_DIFFSINGER_EXPERIMENT','')
                if not path.resolve().is_relative_to((root/'checkpoints'/exp).resolve()):
                    problems.append('Acoustic checkpoint outside selected experiment')
        except Exception as exc:
            problems.append(label+': '+str(exc))
    return {'ready_for_inference_attempt':not problems,'real_audio_validated':False,'problems':problems,
            'next_step':'Run a real voicebank/vocoder inference and verify audio on the target machine' if not problems else 'Install and authorize the missing assets, then rerun this check'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--json',action='store_true')
    opts=parser.parse_args()
    # Make repo-root imports work when launched as a standalone script.
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    report=check(os.environ)
    if opts.json:print(json.dumps(report,indent=2,ensure_ascii=False))
    else:
        print('READY' if report['ready_for_inference_attempt'] else 'BLOCKED')
        for reason in report['problems']:print('- '+reason)
        print(report['next_step'])
    return 0 if report['ready_for_inference_attempt'] else 2

if __name__=='__main__':sys.exit(main())
