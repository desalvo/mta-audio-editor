"""Pinned, opt-in percussion adapters; catalog entries never authorize execution.

Only the reviewed Mega 53 integration is runnable. Candidate metadata is not a
downloader, a license override or permission to run arbitrary upstream code.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import soundfile as sf


CATALOG_PATH = Path(__file__).with_name('percussion_candidates.json')
ADAPTER_VERSION = 'mta-mega53-percussion-1'
EXECUTABLE_ADAPTERS = frozenset({'mvsep-mega53'})


class AdapterUnavailable(ValueError):
    def __init__(self, state, message):
        self.state = state
        super().__init__(message)


def _json_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata():
    data = json.loads(CATALOG_PATH.read_text())
    if data.get('metadata_schema') != 'mta-percussion-candidates-1':
        raise ValueError('Unsupported percussion candidate metadata')
    return data


def _activation_path():
    from .studio_catalog import root
    return root() / 'percussion-models.json'


def enabled_models():
    defaults = [item['id'] for item in _metadata()['models'] if item['enabled_by_default']]
    path = _activation_path()
    if path.is_symlink() or (path.exists() and path.stat().st_size > 16384):
        raise ValueError('Unsafe percussion activation settings')
    if not path.is_file():
        return defaults
    data = json.loads(path.read_text())
    known = {item['id'] for item in _metadata()['models']}
    if (not isinstance(data, dict) or set(data) != {'schema', 'enabled_models'}
            or data['schema'] != 'mta-percussion-activation-1'
            or not isinstance(data['enabled_models'], list)
            or any(not isinstance(item, str) or item not in known for item in data['enabled_models'])
            or len(set(data['enabled_models'])) != len(data['enabled_models'])):
        raise ValueError('Invalid percussion activation settings')
    return data['enabled_models']


def configure_enabled(model_ids):
    """An admin route must authorize this setter; enabling cannot confer rights."""
    known = {item['id']: item for item in _metadata()['models']}
    if (not isinstance(model_ids, list)
            or any(not isinstance(item, str) or item not in known for item in model_ids)
            or len(model_ids) != len(set(model_ids))):
        raise ValueError('Unknown or duplicate percussion model')
    if any(item not in EXECUTABLE_ADAPTERS or not known[item]['adapter_implemented'] or not known[item]['weights_permission_verified'] for item in model_ids):
        raise AdapterUnavailable('not_authorized', 'Unreviewed candidates cannot be enabled')
    path = _activation_path()
    if path.is_symlink():
        raise ValueError('Unsafe percussion activation settings')
    from .storage import _atomic_json_write
    _atomic_json_write(path, {'schema': 'mta-percussion-activation-1', 'enabled_models': model_ids})
    return {'enabled_models': model_ids}


def model_status(item):
    from . import mega53_runtime
    from .model_license_policy import LicenseDenied, evaluate_model
    if item.get('incompatible_with_fidelity_requirement'):
        return {'state': 'incompatible', 'ready': False, 'reason': item['status_reason']}
    if not item['weights_permission_verified']:
        return {'state': 'not_authorized', 'ready': False, 'reason': item['status_reason']}
    if item['id'] not in EXECUTABLE_ADAPTERS or not item['adapter_implemented']:
        return {'state': 'incompatible', 'ready': False, 'reason': 'No reviewed executable adapter is implemented'}
    if item['id'] not in enabled_models():
        return {'state': 'disabled', 'ready': False, 'reason': 'Disabled by administrator'}
    try:
        evaluate_model(item['id'])
    except LicenseDenied as exc:
        return {'state': 'not_authorized', 'ready': False, 'reason': str(exc)}
    if not mega53_runtime.configured():
        return {'state': 'not_installed', 'ready': False, 'reason': 'No local exact Mega 53 checkpoint/config/runtime configured; remote installation has not been probed'}
    # Status is deliberately not a weight-hashing operation on every UI poll.
    # The explicit prepare/dispatch boundary below verifies all installed bytes.
    return {'state': 'configured_unverified', 'ready': False, 'reason': 'Installation configured; exact verification is required at dispatch'}


def catalog():
    data = _metadata()
    models = [{**item, 'status': model_status(item)} for item in data['models']]
    return {'schema': data['metadata_schema'], 'reviewed_at': data['reviewed_at'],
            'no_automatic_downloads': True, 'models': models}


@dataclass(frozen=True)
class PercussionRequest:
    model_id: str
    model_version: str
    checkpoint_sha256: str
    adapter_version: str
    pipeline_sha256: str
    include_kick: bool
    clap: str
    timpani: str
    source_mode: str
    profile_sha256: str

    def as_dict(self):
        return asdict(self)


def prepare_request(model_id='mvsep-mega53', options=None):
    options = {} if options is None else options
    allowed = {'include_kick', 'clap', 'timpani', 'source_mode'}
    if not isinstance(options, dict) or set(options) - allowed:
        raise ValueError('Unsupported percussion profile options')
    if type(options.get('include_kick', True)) is not bool:
        raise ValueError('include_kick must be boolean')
    if options.get('clap', 'exclude') not in ('include', 'exclude') or options.get('timpani', 'exclude') not in ('include', 'exclude'):
        raise ValueError('Ambiguous percussion categories require include/exclude')
    if options.get('source_mode', 'drums') not in ('drums', 'mix'):
        raise ValueError('Unknown percussion source mode')
    item = next((item for item in _metadata()['models'] if item['id'] == model_id), None)
    if item is None:
        raise AdapterUnavailable('incompatible', 'Unknown percussion adapter')
    if not item['weights_permission_verified']:
        raise AdapterUnavailable('not_authorized', item['status_reason'])
    if model_id not in EXECUTABLE_ADAPTERS or not item['adapter_implemented']:
        raise AdapterUnavailable('incompatible', 'No executable adapter is implemented')
    if model_id not in enabled_models():
        raise AdapterUnavailable('disabled', 'Percussion adapter is disabled')
    if options.get('clap', 'exclude') != 'exclude' or options.get('timpani', 'exclude') != 'exclude':
        raise AdapterUnavailable('incompatible', 'This adapter cannot independently include clap or timpani; no class substitution is permitted')
    values = {'model_id': model_id, 'model_version': item['checkpoint_revision'],
              'checkpoint_sha256': item['checkpoint_sha256'], 'adapter_version': item['adapter_version'],
              'pipeline_sha256': _file_digest(Path(__file__)),
              'include_kick': options.get('include_kick', True), 'clap': options.get('clap', 'exclude'),
              'timpani': options.get('timpani', 'exclude'), 'source_mode': options.get('source_mode', 'drums')}
    return PercussionRequest(**values, profile_sha256=_json_digest(values))


def verify_installation(request):
    """Expensive local verification only on an explicit benchmark/dispatch."""
    from . import mega53_runtime
    from .model_license_policy import evaluate_model
    evaluate_model(request.model_id)
    if not mega53_runtime.configured():
        raise AdapterUnavailable('not_installed', 'Configure MTA_MEGA53_ROOT, MTA_MEGA53_CONFIG and MTA_MEGA53_CHECKPOINT first')
    try:
        checkpoint = mega53_runtime.verify_mega53_checkpoint(os.environ['MTA_MEGA53_CHECKPOINT'])
        config = mega53_runtime._verified_file(os.environ['MTA_MEGA53_CONFIG'], 'config')
        upstream = mega53_runtime._verified_directory(os.environ['MTA_MEGA53_ROOT'])
    except RuntimeError as exc:
        raise AdapterUnavailable('incompatible', str(exc)) from exc
    actual = _file_digest(checkpoint)
    if actual != request.checkpoint_sha256:
        raise AdapterUnavailable('incompatible', 'Checkpoint identity differs from the prepared request')
    return {'checkpoint_sha256': actual, 'config_sha256': _file_digest(config),
            'upstream_entry_sha256': _file_digest(upstream / 'inference.py')}


def verify(model_id='mvsep-mega53', options=None):
    request = prepare_request(model_id, options)
    return {'state': 'ready', 'ready': True, 'request': request.as_dict(),
            'execution_profile': verify_installation(request)}


def _regular(path, label):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Invalid ' + label)
    return path.resolve()


def _combine(components, source, output):
    """Create a declared additive profile, never subtract or normalize silently."""
    info = sf.info(source)
    inputs = []
    for name, path in components.items():
        component = _regular(path, name)
        ci = sf.info(component)
        if (ci.frames, ci.samplerate, ci.channels) != (info.frames, info.samplerate, info.channels):
            raise AdapterUnavailable('invalid_result', 'Percussion components changed duration, sample rate or channel count')
        inputs.append(sf.SoundFile(component))
    try:
        with sf.SoundFile(output, mode='w', samplerate=info.samplerate, channels=info.channels, subtype='FLOAT') as target:
            for _ in range(0, info.frames, 65536):
                blocks = [stream.read(65536, dtype='float64', always_2d=True) for stream in inputs]
                if any(not np.isfinite(block).all() or np.max(np.abs(block), initial=0) > 1 for block in blocks):
                    raise AdapterUnavailable('invalid_result', 'Invalid or clipping percussion component')
                signal = np.sum(blocks, axis=0)
                if not np.isfinite(signal).all():
                    raise AdapterUnavailable('invalid_result', 'Nonfinite percussion output')
                if np.max(np.abs(signal), initial=0) > 1:
                    raise AdapterUnavailable('invalid_result', 'Additive percussion output clips; no automatic normalization was applied')
                target.write(signal)
    finally:
        for stream in inputs:
            stream.close()


def _conform(components, source, output_dir):
    """Restore the input format after fixed-rate inference, retaining raw WAVs.

    Resampling is a declared deterministic format conversion, never a timing
    correction or gain adjustment. Longer/truncated model outputs are rejected.
    """
    from math import gcd
    from scipy.signal import resample_poly
    source_info = sf.info(source)
    conformed, operations = {}, []
    for name, raw in components.items():
        raw = _regular(raw, 'percussion component')
        info = sf.info(raw)
        if (info.frames, info.samplerate, info.channels) == (source_info.frames, source_info.samplerate, source_info.channels):
            conformed[name] = raw
            continue
        expected = source_info.frames * info.samplerate / source_info.samplerate
        if abs(info.frames - expected) > 2:
            raise AdapterUnavailable('invalid_result', 'Percussion model changed audio duration')
        if info.channels != source_info.channels and not (info.channels == 2 and source_info.channels == 1):
            raise AdapterUnavailable('invalid_result', 'Model discarded the original stereo image')
        audio, rate = sf.read(raw, dtype='float64', always_2d=True)
        if not np.isfinite(audio).all() or np.max(np.abs(audio), initial=0) > 1:
            raise AdapterUnavailable('invalid_result', 'Nonfinite or clipping raw percussion component')
        if source_info.channels == 1 and info.channels == 2:
            audio = np.mean(audio, axis=1, keepdims=True)
        if rate != source_info.samplerate:
            factor = gcd(rate, source_info.samplerate)
            audio = resample_poly(audio, source_info.samplerate // factor, rate // factor, axis=0)
        if abs(len(audio) - source_info.frames) > 2:
            raise AdapterUnavailable('invalid_result', 'Unexpected duration after format conversion')
        if len(audio) > source_info.frames:
            audio = audio[:source_info.frames]
        elif len(audio) < source_info.frames:
            audio = np.pad(audio, ((0, source_info.frames - len(audio)), (0, 0)))
        dest = output_dir / ('conformed_' + name + '.wav')
        if dest.is_symlink() or dest.exists():
            raise ValueError('Conformed percussion output already exists')
        sf.write(dest, audio, source_info.samplerate, subtype='FLOAT')
        conformed[name] = dest
        operations.append({'component': name, 'raw_sample_rate': rate,
                           'raw_channels': info.channels, 'output_sample_rate': source_info.samplerate,
                           'output_channels': source_info.channels, 'output_frames': source_info.frames,
                           'resampler': 'scipy.signal.resample_poly', 'gain_applied': False})
    return conformed, operations


def infer(request, source, output_dir, *, original_mix=None, cancel_event=None):
    """Execute under the existing registered server/native ownership contract.

    This is not a new engine entry point: web calls still require the active
    authenticated scheduler owner, registered worker and current model policy.
    """
    if not isinstance(request, PercussionRequest):
        raise ValueError('A prepared percussion request is required')
    options = {key: getattr(request, key) for key in ('include_kick', 'clap', 'timpani', 'source_mode')}
    if request != prepare_request(request.model_id, options):
        raise AdapterUnavailable('incompatible', 'Prepared percussion profile changed')
    if cancel_event is not None and cancel_event.is_set():
        raise RuntimeError('Percussion inference cancelled')
    if request.source_mode == 'mix':
        if original_mix is None:
            raise ValueError('Original mix explicitly requested but unavailable')
        source = original_mix
    source = _regular(source, 'percussion source')
    output_dir = Path(output_dir)
    if output_dir.is_symlink():
        raise ValueError('Unsafe percussion output directory')
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError('A fresh percussion output directory is required')
    from . import main, mega53_runtime
    from .model_license_policy import evaluate_model
    evaluate_model(request.model_id)
    targets = ['percussion', *(['kick'] if request.include_kick else [])]
    worker_job_id = None
    execution_profile = {'checkpoint_sha256': request.checkpoint_sha256, 'profile_sha256': request.profile_sha256}
    if main._ai_external_engine('drumsep'):
        # The server helper independently requires active durable dispatch identity.
        if not main.NATIVE_SINGLE_USER:
            from .ai_server_execution import identity
            identity()
        result, worker_job_id = main._native_remote_infer('drumsep', source, {'model': request.model_id, 'targets': targets})
        expected = {'percussions.wav', *({'kick.wav'} if request.include_kick else set())}
        audio = result.get('audio', {})
        if set(audio) != expected:
            raise AdapterUnavailable('invalid_result', 'Registered worker returned unexpected percussion artifacts')
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, data in audio.items():
            target = output_dir / name
            if target.is_symlink() or target.exists():
                raise ValueError('Percussion output already exists')
            target.write_bytes(data)
    else:
        if not main.NATIVE_SINGLE_USER:
            raise AdapterUnavailable('not_authorized', 'Standalone inference is restricted to the native application')
        execution_profile.update(verify_installation(request))
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = mega53_runtime.infer_drums(source, output_dir, set(targets), cancel_event=cancel_event)
        expected = {'percussions.wav', *({'kick.wav'} if request.include_kick else set())}
        if {Path(path).name for path in paths} != expected:
            raise AdapterUnavailable('invalid_result', 'Native model returned unexpected percussion components')
        if verify_installation(request) != {key: execution_profile[key] for key in ('checkpoint_sha256', 'config_sha256', 'upstream_entry_sha256')}:
            raise AdapterUnavailable('incompatible', 'Percussion assets changed during inference')
    if cancel_event is not None and cancel_event.is_set():
        raise RuntimeError('Percussion inference cancelled')
    components = {'percussion': output_dir / 'percussions.wav'}
    if request.include_kick:
        components['kick'] = output_dir / 'kick.wav'
    raw_components = dict(components)
    output = output_dir / 'percussion_output.wav'
    try:
        components, conversions = _conform(components, source, output_dir)
        _combine(components, source, output)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    evaluate_model(request.model_id)
    return {'model_id': request.model_id, 'model_version': request.model_version,
            'checkpoint_sha256': request.checkpoint_sha256, 'profile_sha256': request.profile_sha256,
            'request': request.as_dict(), 'output': output, 'components': components,
            'raw_components': raw_components, 'format_conversions': conversions,
            'source_mode': request.source_mode, 'worker_job_id': worker_job_id,
            'execution_profile': execution_profile, 'inference_completed': True,
            'manual_validation_status': 'In attesa di validazione umana',
            'warnings': ['Native Mega 53 estimates may overlap; the explicit additive kick profile is experimental and has not been professionally approved.']}
