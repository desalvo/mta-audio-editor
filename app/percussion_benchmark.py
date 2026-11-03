"""Persistent reproducible AI evaluation; imported claims never grant approval."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import time
import uuid
import zipfile

import numpy as np
import soundfile as sf

from . import auth
from .ai_project_lock import project_publication_lock

SCHEMA = 'mta-ai-benchmark-1'
SCORES = ('isolation', 'contamination', 'naturalness', 'transients', 'completeness', 'overall')
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_FILES = 2048
_ID = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$')
CRITERIA = {
    'version': 'engineering-integrity-v1',
    'frozen_before_evaluation': True,
    'technical': 'Readable finite PCM; preserved frames, rate and channel count; no introduced clipping. Alignment, drift and discontinuity diagnostics require case review.',
    'quality': 'No universal professional quality threshold. Compare exact-reference metrics by category, input baseline and paired cases; human approval is mandatory.',
    'human': 'Six 1–5 ratings; contamination 5 means negligible bleed. Explicit professional approval binds exact pipeline, checkpoint, options, input and output hashes.',
    'minimum_release_cases': {'synthetic': 12, 'negative': 6, 'real': 6},
}


def root():
    path = auth.data_root() / 'ai-benchmarks'
    if path.is_symlink():
        raise ValueError('Unsafe benchmark root')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def identifier(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError('Invalid benchmark identifier')
    return value


def digest(path):
    hasher = hashlib.sha256()
    if path.is_symlink() or not path.is_file():
        raise ValueError('Benchmark artifact must be a regular file')
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def pipeline_hash():
    base = Path(__file__).parent
    names = ('percussion_benchmark.py', 'percussion_adapters.py', 'percussion_candidates.json', 'percussion_metrics.py', 'percussion_corpus.py')
    return json_hash({name: digest(base / name) for name in names})


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError('Unsafe benchmark state')
    fd, temp = tempfile.mkstemp(prefix='.benchmark-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)



def folder(cid):
    base = root()
    path = base / 'campaigns' / identifier(cid)
    if any(p.is_symlink() for p in (base, base / 'campaigns', path)):
        raise ValueError('Unsafe campaign directory')
    return path



def _validate_campaign(value):
    if not isinstance(value, dict) or value.get('schema') != SCHEMA:
        raise ValueError('Invalid campaign schema')
    identifier(value.get('id'))
    config = value.get('config')
    if not isinstance(config, dict) or value.get('config_sha256') != json_hash(config):
        raise ValueError('Frozen campaign configuration mismatch')
    models, cases = config.get('model_ids'), config.get('cases')
    if (not isinstance(models, list) or not models or len(models) > 16
            or any(not isinstance(model, str) for model in models) or len(models) != len(set(models))
            or not isinstance(cases, list) or not 1 <= len(cases) <= 256 or len(cases) * len(models) > 1024):
        raise ValueError('Invalid campaign model/case inventory')
    known_cases = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get('case_key'), str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,239}', case['case_key']):
            raise ValueError('Invalid campaign case identity')
        identifier(case.get('id')); identifier(case.get('dataset_id'))
        if case['case_key'] in known_cases or type(case.get('prepared')) is not bool:
            raise ValueError('Invalid or duplicate campaign case')
        known_cases.add(case['case_key'])
    if (value.get('kind') not in ('experimental', 'release') or not isinstance(value.get('title'), str)
            or not 1 <= len(value['title']) <= 200 or type(value.get('actor_user_id')) is not int
            or value['actor_user_id'] <= 0 or not isinstance(config.get('options'), dict)
            or not isinstance(config.get('criteria'), dict) or config['criteria'].get('minimum_release_cases') != CRITERIA['minimum_release_cases']):
        raise ValueError('Invalid campaign authority, title or frozen criteria')
    for key in ('results', 'ratings'):
        if not isinstance(value.get(key), list) or len(value[key]) > 4096:
            raise ValueError('Invalid campaign result/rating inventory')
    pairs = set()
    for row in value['results']:
        if not isinstance(row, dict) or row.get('case_id') not in known_cases or row.get('model_id') not in models:
            raise ValueError('Result is outside the frozen case/model inventory')
        pair = (row['case_id'], row['model_id'])
        if pair in pairs or row.get('candidate_id') != _candidate_id(value, *pair):
            raise ValueError('Invalid or duplicate candidate result')
        pairs.add(pair)
    return value

def _read(cid):
    path = folder(cid) / 'campaign.json'
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Campaign not found or invalid')
    from .percussion_dataset_import import _json
    value = _json(path.read_bytes())
    if value.get('id') != cid:
        raise ValueError('Invalid campaign schema')
    return _validate_campaign(value)


@contextmanager
def locked(cid):
    with project_publication_lock('benchmark:' + identifier(cid)):
        yield


def prepare_synthetic():
    from .percussion_corpus import generate
    with locked('corpus'):
        return generate(root() / 'datasets' / 'mta-synthetic-v1', seed=42)


def dataset_manifest(dataset_id):
    path = root() / 'datasets' / identifier(dataset_id) / 'manifest.json'
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Dataset is not prepared')
    from .percussion_dataset_import import _json
    value = _json(path.read_bytes())
    if value.get('id', value.get('dataset_id')) != dataset_id or not isinstance(value.get('cases'), list):
        raise ValueError('Invalid dataset manifest')
    return value


def catalog():
    from .percussion_adapters import catalog as model_catalog
    candidates = model_catalog()
    if isinstance(candidates, dict):
        candidates = candidates.get('models', candidates.get('candidates', []))
    from .percussion_adapters import enabled_models
    enabled = set(enabled_models())
    candidates = [{**item, 'enabled': item['id'] in enabled,
                   'version': item.get('checkpoint_revision'), 'license': {'status': item.get('weights_license', 'not verified')}, 'status': item['status'].get('state', 'adapter_unavailable'),
                   'ready': item['status'].get('ready', False), 'reason': item['status'].get('reason', '')}
                  if isinstance(item.get('status'), dict) else item for item in candidates]
    datasets = []
    base = root() / 'datasets'
    if base.exists():
        for path in sorted(base.iterdir()):
            if not path.is_dir() or path.is_symlink():
                continue
            try:
                manifest = dataset_manifest(path.name)
                cases = manifest['cases']
                datasets.append({'id': path.name, 'name': manifest.get('name', path.name), 'cases': len(cases),
                                 'prepared': True, 'prepared_cases': sum(bool(c.get('prepared')) for c in cases),
                                 'groups': sorted({c.get('group', 'unknown') for c in cases})})
            except (OSError, ValueError):
                continue
    if not any(x['id'] == 'mta-synthetic-v1' for x in datasets):
        datasets.append({'id': 'mta-synthetic-v1', 'name': 'MTA original synthetic corpus v1',
                         'cases': 24, 'prepared': False, 'prepared_cases': 0,
                         'groups': ['synthetic', 'negative', 'real']})
    return {'models': candidates, 'datasets': datasets, 'criteria': CRITERIA,
            'permissions': {'approve': True}, 'pipeline_sha256': pipeline_hash()}


def create(body, actor):
    if not isinstance(body, dict) or set(body) - {'title', 'kind', 'model_ids', 'dataset_ids', 'options', 'seed'}:
        raise ValueError('Invalid campaign fields')
    model_ids, datasets = body.get('model_ids'), body.get('dataset_ids')
    if (not isinstance(model_ids, list) or not 1 <= len(model_ids) <= 16
            or any(not isinstance(x, str) for x in model_ids) or len(set(model_ids)) != len(model_ids)
            or not isinstance(datasets, list) or not 1 <= len(datasets) <= 8
            or any(not isinstance(x, str) for x in datasets) or len(set(datasets)) != len(datasets)):
        raise ValueError('Select models and datasets')
    if type(actor) is not int or actor <= 0:
        raise ValueError('Authenticated benchmark administrator required')
    candidates = {v['id']: v for v in catalog()['models']}
    if any(x not in candidates for x in model_ids):
        raise ValueError('Unknown benchmark model')
    title = body.get('title', 'Percussion validation')
    kind = body.get('kind', 'experimental')
    seed = body.get('seed', 42)
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200 or kind not in ('experimental', 'release'):
        raise ValueError('Invalid campaign title or kind')
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError('Invalid campaign seed')
    options = body.get('options', {})
    if (not isinstance(options, dict) or set(options) - {'include_kick', 'clap', 'timpani', 'source_mode'}
            or type(options.get('include_kick', True)) is not bool
            or options.get('clap', 'excluded') not in ('percussion', 'excluded')
            or options.get('timpani', 'excluded') not in ('percussion', 'excluded')
            or options.get('source_mode', 'both') not in ('drums', 'mix', 'both')):
        raise ValueError('Invalid percussion category policy')
    options = {'include_kick': True, 'clap': 'excluded', 'timpani': 'excluded', 'source_mode': 'both', **options}
    cases = []
    for dataset in datasets:
        from .percussion_corpus import load
        manifest = load(root() / 'datasets' / identifier(dataset))
        for case in manifest['cases']:
            modes = ('drums', 'mix') if options['source_mode'] == 'both' else (options['source_mode'],)
            for mode in modes:
                key = dataset + '--' + identifier(case['id']) + '--' + mode
                item = {**case, 'dataset_id': dataset, 'case_key': key, 'source_mode': mode}
                if mode == 'mix' and not case.get('input_mix'):
                    item.update(prepared=False, unavailable_reason='Original mix was not supplied for this case')
                cases.append(item)
    if not cases or len(cases) > 256 or len(cases) * len(model_ids) > 1024:
        raise ValueError('Invalid number of benchmark cases')
    cid = uuid.uuid4().hex
    config = {'model_ids': model_ids, 'dataset_ids': datasets, 'options': options, 'seed': seed,
              'models': [candidates[x] for x in model_ids], 'cases': cases,
              'pipeline_sha256': pipeline_hash(), 'criteria': CRITERIA}
    value = {'schema': SCHEMA, 'id': cid, 'title': title.strip(), 'kind': kind, 'actor_user_id': actor,
             'created_at': time.time(), 'status': 'created', 'config': config,
             'config_sha256': json_hash(config), 'results': [], 'ratings': [], 'attempt': 0,
             'human_validation': 'In attesa di validazione umana'}
    _write(folder(cid) / 'campaign.json', value)
    return public(value)


def _counts(value):
    result = {}
    for row in value['results']:
        state = row['status']
        if state == 'validated_automatically' and not _verified_result(value['id'], row, value=value):
            state = 'invalid_result'
        result[state] = result.get(state, 0) + 1
    result.update(total=len(value['config']['cases']) * len(value['config']['model_ids']),
                  completed=result.get('validated_automatically', 0),
                  failed=result.get('inference_failed', 0), invalid=result.get('invalid_result', 0),
                  unavailable=sum(v for k, v in result.items() if k in ('not_installed', 'not_authorized', 'adapter_unavailable', 'dataset_unavailable', 'incompatible', 'disabled', 'configured_unverified')))
    return result



def summary(value):
    groups = {}
    for row in value['results']:
        # Separate models and categories. This is descriptive, not a paired significance test.
        group = ' / '.join(str(row.get(key) or 'unknown') for key in ('model_id', 'group', 'category'))
        state = groups.setdefault(group, {'model_id': row.get('model_id'), 'cases': 0, 'technically_valid': 0, 'si_sdr_db': []})
        state['cases'] += 1
        state['technically_valid'] += _verified_result(value['id'], row, value=value)
        metric = ((row.get('metrics') or {}).get('quality', {}) or {}).get('si_sdr_db')
        if row.get('provenance') == 'local_execution' and isinstance(metric, (int, float)) and np.isfinite(metric):
            state['si_sdr_db'].append(metric)
    for state in groups.values():
        values = state.pop('si_sdr_db')
        state['mean_si_sdr_db'] = float(np.mean(values)) if values else None
        state['n_metric'] = len(values)
        if len(values) >= 3:
            rng = np.random.default_rng(value['config']['seed'])
            means = np.mean(rng.choice(values, (1000, len(values))), axis=1)
            state['bootstrap_95_percent_interval'] = [float(x) for x in np.quantile(means, [.025, .975])]
        else:
            state['bootstrap_95_percent_interval'] = None
    approved = approval(value)['approved']
    return {'counts': _counts(value), 'categories': groups, 'professional_approval': approved,
            'human_validation': 'Approvato manualmente' if approved else 'In attesa di validazione umana'}


def public(value):
    results = []
    rated = {(v['case_id'], v['candidate_id']) for v in value['ratings']}
    for row in value['results']:
        item = {k: v for k, v in row.items() if k not in ('model_id', 'checkpoint_sha256', 'model_version', 'request', 'output', 'components', 'input_path', 'reference_path', 'files', 'raw_components', 'execution_profile', 'source_bindings', 'worker_job_id')}
        revealed = (row['case_id'], row['candidate_id']) in rated
        item['identity_revealed'] = revealed
        if row.get('status') == 'validated_automatically' and not _verified_result(value['id'], row, value=value):
            item.update(status='invalid_result', evidence_current=False)
        if revealed:
            item.update({k: row.get(k) for k in ('model_id', 'model_version', 'checkpoint_sha256')})
        if item.get('metrics'):
            item['metrics'] = {**item['metrics'], **item['metrics'].get('quality', {}),
                               **item['metrics'].get('technical', {})}
        results.append(item)
    case_rows = [{'id': c['case_key'], 'title': c.get('title', c['id']), 'category': c.get('category', ''),
                  'group': c.get('group', ''), 'duration_seconds': c.get('duration_seconds', 0),
                  'prepared': bool(c.get('prepared')), 'source_mode': c.get('source_mode')} for c in value['config']['cases']]
    campaign = {k: v for k, v in value.items() if k not in ('config', 'results', 'ratings')}
    campaign['counts'] = _counts(value)
    campaign['human_validation'] = approval(value)['state']
    return {'campaign': campaign, 'cases': case_rows, 'results': results,
            'ratings': value['ratings'], 'summary': {'counts': _counts(value), 'human_validation': approval(value)['state']}, 'approval': approval(value)}


def get(cid):
    return public(_read(cid))


def campaigns():
    path = root() / 'campaigns'
    values = []
    for item in sorted(path.iterdir(), reverse=True) if path.exists() else []:
        try:
            values.append(public(_read(item.name))['campaign'])
        except (OSError, ValueError):
            continue
    return {'campaigns': sorted(values, key=lambda c: c['created_at'], reverse=True)}



def _dataset_file(case, relative):
    base = root() / 'datasets' / identifier(case['dataset_id'])
    path = _safe_file(base, relative)
    expected = case.get('sha256', {}).get(relative) if isinstance(case.get('sha256'), dict) else None
    if not isinstance(expected, str) or not re.fullmatch('[a-f0-9]{64}', expected) or digest(path) != expected:
        raise ValueError('Corpus artifact lacks its exact original SHA-256 or changed')
    return path


def _safe_file(base, relative):
    from .percussion_dataset_import import _name
    relative = _name(relative)
    base = Path(base)
    path = base.joinpath(*PurePosixPath(relative).parts)
    if any(p.is_symlink() for p in [path, *path.parents] if p == base or base in p.parents):
        raise ValueError('Symbolic benchmark artifact')
    if not path.is_file() or path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError('Benchmark artifact unavailable or oversized')
    return path



def _reference(case, options):
    mode = case.get('source_mode', options['source_mode'])
    refs = case.get('mix_references' if mode == 'mix' else 'references', {})
    relative = refs.get('include_kick' if options['include_kick'] else 'exclude_kick') if isinstance(refs, dict) else None
    if relative:
        return _dataset_file(case, relative)
    if mode == 'mix' and case.get('input_mix') != case.get('input_drums'):
        return None  # Different source, no explicit exact reference: no guessed truth.
    relative = case.get('reference') or case.get('target_reference')
    return _dataset_file(case, relative) if relative else None


def _case_options(value, case):
    options = dict(value['config']['options'])
    options['source_mode'] = case.get('source_mode', options['source_mode'])
    if options['source_mode'] not in ('drums', 'mix'):
        raise ValueError('A benchmark case requires an explicit source variant')
    return options


def _source_bindings(case, options):
    mode = case.get('source_mode', options['source_mode'])
    names = {'input': case['input_mix' if mode == 'mix' else 'input_drums']}
    reference = _reference(case, options)
    if reference is not None:
        base = root() / 'datasets' / identifier(case['dataset_id'])
        names['reference'] = reference.relative_to(base).as_posix()
    names.update({'source:' + key: value for key, value in case.get('sources', {}).items()})
    return {key: {'dataset_id': case['dataset_id'], 'relative': name, 'sha256': digest(_dataset_file(case, name))}
            for key, name in names.items()}


def _row_binding(value, row):
    binding = {key: row.get(key) for key in ('model_id', 'model_version', 'checkpoint_sha256', 'profile_sha256',
               'input_sha256', 'reference_sha256', 'source_bindings', 'files', 'execution_profile', 'format_conversions')}
    binding.update(config_sha256=value['config_sha256'], pipeline_sha256=value['config']['pipeline_sha256'])
    return binding


def _approval_binding(value):
    return json_hash({'config': value['config_sha256'], 'results': value['results'], 'ratings': value['ratings']})


def _candidate_order(value, case_id):
    models = list(value['config']['model_ids'])
    seed = hashlib.sha256((str(value['config']['seed']) + ':' + case_id).encode()).digest()
    np.random.default_rng(int.from_bytes(seed[:8])).shuffle(models)
    return {model: 'Candidate ' + chr(65 + n) for n, model in enumerate(models)}


def _candidate_id(value, case_id, model):
    return hashlib.sha256((value['id'] + ':' + case_id + ':' + model).encode()).hexdigest()[:24]



def _verified_result(cid, row, *, value=None):
    if (row.get('status') != 'validated_automatically' or row.get('inference_completed') is not True
            or row.get('provenance') != 'local_execution' or not row.get('metrics', {}).get('technical_pass')):
        return False
    try:
        value = _read(cid) if value is None else value
        if value['config_sha256'] != json_hash(value['config']) or value['config']['pipeline_sha256'] != pipeline_hash():
            return False
        case = next(c for c in value['config']['cases'] if c['case_key'] == row['case_id'])
        if row['model_id'] not in value['config']['model_ids'] or row['candidate_id'] != _candidate_id(value, row['case_id'], row['model_id']):
            return False
        files = row.get('files')
        if (not isinstance(files, dict) or not files or row.get('output') not in files
                or any(not isinstance(sha, str) or not re.fullmatch('[a-f0-9]{64}', sha) for sha in files.values())):
            return False
        if not all(digest(_safe_file(folder(cid), name)) == sha for name, sha in files.items()):
            return False
        actual = _source_bindings(case, _case_options(value, case))
        if actual != row.get('source_bindings') or actual['input']['sha256'] != row.get('input_sha256'):
            return False
        reference = actual.get('reference', {}).get('sha256')
        if reference != row.get('reference_sha256'):
            return False
        from .percussion_adapters import prepare_request
        options = _case_options(value, case)
        request = prepare_request(row['model_id'], {**options,
            'clap': 'include' if options['clap'] == 'percussion' else 'exclude',
            'timpani': 'include' if options['timpani'] == 'percussion' else 'exclude'})
        return request.as_dict() == row.get('request') and request.profile_sha256 == row.get('profile_sha256')
    except (ValueError, OSError, KeyError, TypeError, StopIteration):
        return False



def approval(value):
    reasons = []
    if value['kind'] != 'release':
        reasons.append('Only a release campaign can receive professional approval')
    if value['config']['pipeline_sha256'] != pipeline_hash() or value['config_sha256'] != json_hash(value['config']):
        reasons.append('The pipeline or frozen configuration has changed')
    unique = {(c['dataset_id'], c['id']): c for c in value['config']['cases']}
    for group, minimum in value['config']['criteria']['minimum_release_cases'].items():
        if sum(c.get('prepared') and c.get('group') == group for c in unique.values()) < minimum:
            reasons.append('Release corpus coverage is incomplete: ' + group)
    real_cases = [c for c in unique.values() if c.get('prepared') and c.get('group') == 'real']
    real_families = {c.get('family_id') for c in real_cases if isinstance(c.get('family_id'), str) and c['family_id'].strip()}
    real_recordings = {c.get('sha256', {}).get(c.get('input_drums')) for c in real_cases}
    if (len(real_families) < 6 or len(real_recordings - {None}) < 6
            or any(not isinstance(c.get('family_id'), str) or not c['family_id'].strip()
                   or not isinstance(c.get('rights'), dict) or c['rights'].get('basis') not in ('user_owned', 'licensed') for c in real_cases)):
        reasons.append('Six distinct real recording families with explicit provenance and distinct audio hashes are required')
    if any(not c.get('prepared') for c in value['config']['cases']):
        reasons.append('The complete corpus, including real recordings, is not prepared')
    expected = {(c['case_key'], model) for c in value['config']['cases'] for model in value['config']['model_ids']}
    actual = [(r.get('case_id'), r.get('model_id')) for r in value['results']]
    if len(actual) != len(set(actual)) or set(actual) != expected or any(not _verified_result(value['id'], r, value=value) for r in value['results']):
        reasons.append('The complete benchmark has not produced valid reproducible local output')
    for result in value['results']:
        binding = _row_binding(value, result)
        if not any(r.get('candidate_id') == result['candidate_id'] and r.get('actor_user_id') == value['actor_user_id']
                   and r.get('decision') == 'professional' and r.get('explicit_approval') is True
                   and r.get('binding') == binding and r.get('imported') is not True for r in value['ratings']):
            reasons.append('The campaign owner has not explicitly approved every exact listening comparison')
            break
    manual = value.get('manual_approval')
    active = bool(manual and not reasons and manual.get('actor_user_id') == value['actor_user_id']
                  and manual.get('binding_sha256') == _approval_binding(value))
    return {'can_approve': not reasons, 'blocked_reasons': reasons,
            'configuration_sha256': value['config_sha256'], 'approved': active,
            'state': 'approved_manually' if active else 'In attesa di validazione umana'}


def approve(cid, body, actor):
    if (not isinstance(body, dict) or set(body) - {'confirm', 'configuration_sha256', 'comment'}
            or body.get('confirm') is not True or not isinstance(body.get('comment', ''), str)
            or len(body.get('comment', '')) > 4000):
        raise ValueError('Explicit professional approval is required')
    with locked(cid):
        value = _read(cid)
        state = approval(value)
        if actor != value['actor_user_id'] or body.get('configuration_sha256') != value['config_sha256']:
            raise ValueError('Only the original evaluator can approve this exact frozen campaign')
        if not state['can_approve']:
            raise ValueError('; '.join(state['blocked_reasons']))
        binding = _approval_binding(value)
        value['manual_approval'] = {'actor_user_id': actor, 'created_at': time.time(), 'comment': body.get('comment', ''),
                                    'binding_sha256': binding}
        value['human_validation'] = 'Approvato manualmente'
        _write(folder(cid) / 'campaign.json', value)
    reports(cid)
    return get(cid)


def _store_run(value, invalidated=None):
    with locked(value['id']):
        latest = _read(value['id'])
        value['ratings'] = [r for r in latest['ratings'] if r['candidate_id'] != invalidated]
        value.pop('manual_approval', None)
        _write(folder(value['id']) / 'campaign.json', value)


def run(cid, actor, progress=None, cancel_event=None, retry_failed=False):
    from . import percussion_adapters as adapters
    from .percussion_metrics import analyze
    value = _read(cid)
    if value['config']['pipeline_sha256'] != pipeline_hash() or value['config_sha256'] != json_hash(value['config']):
        raise ValueError('Pipeline or frozen campaign configuration changed; create a new campaign')
    models = {v['id']: v for v in catalog()['models']}
    started = time.time()
    total = len(value['config']['cases']) * len(value['config']['model_ids'])
    with locked(cid):
        value = _read(cid)
        value['status'] = 'running'
        value['attempt'] += 1
        _write(folder(cid) / 'campaign.json', value)
    for case in value['config']['cases']:
        labels = _candidate_order(value, case['case_key'])
        for model_id in value['config']['model_ids']:
            if cancel_event is not None and cancel_event.is_set():
                value['status'] = 'cancelled'
                _store_run(value)
                reports(cid)
                return get(cid)
            candidate = _candidate_id(value, case['case_key'], model_id)
            previous = next((r for r in value['results'] if r['candidate_id'] == candidate), None)
            if previous and _verified_result(cid, previous, value=value):
                continue
            if previous and not retry_failed and previous['status'] not in ('not_installed', 'not_authorized', 'adapter_unavailable', 'dataset_unavailable', 'imported_unverified', 'invalid_result', 'validated_automatically'):
                continue
            row = {'case_id': case['case_key'], 'candidate_id': candidate, 'label': labels[model_id],
                   'model_id': model_id, 'group': case.get('group'), 'category': case.get('category'), 'source_mode': case.get('source_mode'),
                   'status': 'pending', 'warnings': [], 'started_at': time.time(), 'metrics': None}
            model = models[model_id]
            status = model.get('status', 'adapter_unavailable')
            if not case.get('prepared'):
                row.update(status='dataset_unavailable', error=case.get('unavailable_reason', 'Real recordings and rights are not provided'))
            elif status not in ('ready', 'available', 'installed', 'authorized', 'configured_unverified'):
                row.update(status=status, error=model.get('reason', 'Model unavailable; inference was not executed'))
            else:
                try:
                    options = _case_options(value, case)
                    adapter_options = {**options, 'clap': 'include' if options['clap'] == 'percussion' else 'exclude',
                                       'timpani': 'include' if options['timpani'] == 'percussion' else 'exclude'}
                    request = adapters.prepare_request(model_id, adapter_options)
                    frozen_model = next(m for m in value['config']['models'] if m['id'] == model_id)
                    if any(getattr(request, key) != frozen_model[field] for key, field in [('model_version', 'checkpoint_revision'), ('checkpoint_sha256', 'checkpoint_sha256'), ('adapter_version', 'adapter_version')]):
                        raise ValueError('Frozen model version or checkpoint changed')
                    adapters.verify_installation(request)
                    source_key = 'input_mix' if options['source_mode'] == 'mix' else 'input_drums'
                    source = _dataset_file(case, case[source_key])
                    target_dir = folder(cid) / 'audio' / candidate / ('attempt-' + str(value['attempt']))
                    target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
                    before = time.perf_counter()
                    result = adapters.infer(request, source, target_dir,
                                            original_mix=source if options['source_mode'] == 'mix' else None,
                                            cancel_event=cancel_event)
                    elapsed = time.perf_counter() - before
                    output = Path(result['output'])
                    output.relative_to(folder(cid))
                    reference = _reference(case, options)
                    source_bindings = _source_bindings(case, options)
                    desired = {'percussion', 'percussions', 'accessory_percussion', 'target'} | ({'kick'} if options['include_kick'] else set())
                    sources = {k: _dataset_file(case, v) for k, v in case.get('sources', {}).items() if k not in desired}
                    metrics = analyze(output, source, reference, sources=sources)
                    info = sf.info(str(source))
                    files = {output.relative_to(folder(cid)).as_posix(): digest(output)}
                    if result.get('inference_completed') is not True:
                        raise ValueError('Adapter did not establish an actual completed inference')
                    for part in [*result.get('components', {}).values(), *result.get('raw_components', {}).values()]:
                        part = Path(part)
                        files[part.relative_to(folder(cid)).as_posix()] = digest(part)
                    row.update(status='validated_automatically' if metrics['technical_pass'] else 'invalid_result',
                               model_version=result.get('model_version'), checkpoint_sha256=result.get('checkpoint_sha256'),
                               profile_sha256=result.get('profile_sha256'), request=request.as_dict(),
                               output=output.relative_to(folder(cid)).as_posix(), files=files,
                               input_sha256=digest(source), reference_sha256=digest(reference) if reference else None,
                               source_bindings=source_bindings, provenance='local_execution', inference_completed=True,
                               execution_profile=result.get('execution_profile', {}), format_conversions=result.get('format_conversions', []),
                               worker_job_id=result.get('worker_job_id'),
                               duration_seconds=info.duration, elapsed_seconds=elapsed,
                               real_time_factor=elapsed / info.duration if info.duration else None,
                               metrics=metrics, warnings=result.get('warnings', []),
                               resources={'cpu_seconds': None, 'gpu_seconds': None, 'peak_ram_bytes': None,
                                          'peak_vram_bytes': None, 'source': 'Unavailable counters are not estimated; registered worker retains authoritative metering.'})
                except Exception as exc:
                    state = getattr(exc, 'state', 'inference_failed')
                    row.update(status=state, error=str(exc)[:700])
            row['finished_at'] = time.time()
            value['results'] = [r for r in value['results'] if r['candidate_id'] != candidate] + [row]
            invalidated = candidate if previous and previous.get('files') != row.get('files') else None
            _store_run(value, invalidated)
            if progress:
                _write(Path(progress), {'progress': int(100 * len(value['results']) / total), 'message': row['status']})
    value.update(status='completed', completed_at=time.time(), elapsed_seconds=time.time() - started)
    value['human_validation'] = 'In attesa di validazione umana'
    _store_run(value)
    reports(cid)
    return get(cid)


def start(cid, actor, retry_failed=False):
    from . import ai_arranger_runtime as queue
    if type(retry_failed) is not bool:
        raise ValueError('Invalid retry flag')
    with locked(cid):
        value = _read(cid)
        if value.get('queue_job_id'):
            prior = queue.get(value['queue_job_id'])
            if prior and prior['state'] in ('queued', 'running'):
                return get(cid)
        statuses = [v.get('status') for v in catalog()['models'] if v['id'] in value['config']['model_ids']]
        if not any(s in ('ready', 'available', 'installed', 'authorized', 'configured_unverified') for s in statuses):
            return run(cid, actor, retry_failed=retry_failed)
        job_id = uuid.uuid4().hex
        value.update(queue_job_id=job_id, status='queued')
        _write(folder(cid) / 'campaign.json', value)
        payload = {'schema_version': 1, 'campaign_id': cid, 'actor_user_id': actor, 'retry_failed': retry_failed}
        try:
            queue.start('benchmark-' + cid, 'percussion-benchmark', _restorer('', payload, job_id),
                        job_id=job_id, cancellable=True, payload=payload)
        except Exception:
            value.update(status='admission_failed', queue_job_id=None)
            _write(folder(cid) / 'campaign.json', value)
            raise
    return get(cid)


def _restorer(pid, payload, job_id):
    cid = identifier(payload['campaign_id'])
    actor = payload['actor_user_id']

    def execute(progress, stop):
        with auth.db() as con:
            row = con.execute('SELECT role,active FROM users WHERE id=?', (actor,)).fetchone()
        if row is None or row['role'] != 'admin' or not row['active']:
            raise ValueError('Benchmark administrator is no longer active')
        run(cid, actor, progress, stop, payload.get('retry_failed', False))
    return execute


def _audio_copy(cid, case, role):
    if role == 'reference':
        return _reference(case, _read(cid)['config']['options'])
    mode = case.get('source_mode', _read(cid)['config']['options']['source_mode'])
    return _dataset_file(case, case['input_mix' if mode == 'mix' else 'input_drums'])


def blind(cid, case_id):
    value = _read(cid)
    case = next((v for v in value['config']['cases'] if v['case_key'] == case_id), None)
    if case is None:
        raise ValueError('Unknown benchmark case')
    candidates = []
    for row in sorted(value['results'], key=lambda r: r['label']):
        if row['case_id'] != case_id or not _verified_result(cid, row, value=value):
            continue
        path = _safe_file(folder(cid), row['output'])
        data, _ = sf.read(path, dtype='float32', always_2d=True)
        stride = max(1, len(data) // 240)
        peaks = [float(np.max(np.abs(data[n:n + stride]))) for n in range(0, len(data), stride)]
        url = f'/api/admin/ai-benchmarks/campaigns/{cid}/audio/{row["candidate_id"]}'
        rated = any(r['candidate_id'] == row['candidate_id'] for r in value['ratings'])
        candidates.append({'candidate_id': row['candidate_id'], 'label': row['label'], 'audio_url': url,
                           'matched_audio_url': url + '?matched=true', 'peaks': peaks, 'rated': rated})
    base = f'/api/admin/ai-benchmarks/campaigns/{cid}/cases/{case_id}'
    info = next(v for v in public(value)['cases'] if v['id'] == case_id)
    info['excerpt'] = {'start': 0, 'end': min(20, info['duration_seconds'] or 12)}
    return {'case': info, 'candidates': candidates, 'reference_url': base + '/reference',
            'input_url': base + '/input', 'blind': True}


def audio(cid, candidate, matched=False):
    value = _read(cid)
    row = next((r for r in value['results'] if r['candidate_id'] == candidate), None)
    if row is None or not _verified_result(cid, row, value=value):
        raise ValueError('Verified candidate audio unavailable')
    path = _safe_file(folder(cid), row['output'])
    if not matched:
        return path.read_bytes()
    data, rate = sf.read(path, dtype='float64', always_2d=True)
    target_rms = .1
    rms = float(np.sqrt(np.mean(data * data)))
    gain = target_rms / rms if rms > 1e-12 else 1.0
    peak = float(np.max(np.abs(data)))
    gain = min(gain, .98 / peak) if peak > 0 else 1.0
    out = io.BytesIO()
    sf.write(out, data * gain, rate, format='WAV', subtype='PCM_24')
    return out.getvalue()


def case_audio(cid, case_id, role):
    if role not in ('reference', 'input'):
        raise ValueError('Invalid case audio role')
    value = _read(cid)
    case = next((v for v in value['config']['cases'] if v['case_key'] == case_id), None)
    if case is None or not case.get('prepared'):
        raise ValueError('Case audio unavailable')
    path = _audio_copy(cid, case, role)
    if path is None:
        raise ValueError('Exact reference unavailable')
    return path.read_bytes()


def rate(cid, body, actor):
    if type(actor) is not int or actor <= 0:
        raise ValueError('Authenticated evaluator required')
    allowed = {'case_id', 'candidate_id', 'scores', 'decision', 'comment', 'explicit_approval'}
    if not isinstance(body, dict) or set(body) - allowed:
        raise ValueError('Invalid rating fields')
    scores = body.get('scores')
    if not isinstance(scores, dict) or set(scores) != set(SCORES) or any(type(v) is not int or not 1 <= v <= 5 for v in scores.values()):
        raise ValueError('All six scores must be integers from 1 through 5')
    if body.get('decision') not in ('professional', 'limited', 'rejected'):
        raise ValueError('Choose a final listening decision')
    comment = body.get('comment', '')
    approved = body.get('explicit_approval', False)
    if not isinstance(comment, str) or len(comment) > 4000 or type(approved) is not bool:
        raise ValueError('Invalid rating comment or approval')
    if approved and body['decision'] != 'professional':
        raise ValueError('Professional approval requires the corresponding explicit decision')
    with locked(cid):
        value = _read(cid)
        row = next((r for r in value['results'] if r['candidate_id'] == body.get('candidate_id') and r['case_id'] == body.get('case_id')), None)
        if row is None or not _verified_result(cid, row, value=value):
            raise ValueError('Cannot rate missing, invalid or changed audio')
        binding = _row_binding(value, row)
        rating = {**body, 'actor_user_id': actor, 'created_at': time.time(), 'binding': binding,
                  'explicit_approval': approved}
        value['ratings'] = [r for r in value['ratings'] if not (r['candidate_id'] == body['candidate_id'] and r['actor_user_id'] == actor)] + [rating]
        value.pop('manual_approval', None)
        value['human_validation'] = 'In attesa di validazione umana'
        _write(folder(cid) / 'campaign.json', value)
    reports(cid)
    return {'rating': rating, 'identity': {'name': row['model_id'], 'version': row.get('model_version'),
                                         'checkpoint_sha256': row.get('checkpoint_sha256')}, 'binding': binding}


def reports(cid):
    value = _read(cid)
    result = {'schema': SCHEMA, 'campaign': value, 'summary': summary(value),
              'generated_at': datetime.now(timezone.utc).isoformat(),
              'warning': 'Human professional approval is never inferred from automatic metrics.'}
    _write(folder(cid) / 'percussion_benchmark_results.json', result)
    lines = ['# MTA Percussion Benchmark & Validation', '', value['title'], '',
             '**' + ('Approvato manualmente' if approval(value)['approved'] else 'In attesa di validazione umana') + '**', '',
             'Campaign kind: ' + value['kind'], 'Frozen configuration: `' + value['config_sha256'] + '`', '',
             '| Case | Candidate | State | Real inference |', '|---|---|---|---|']
    for row in value['results']:
        lines.append(f'| {row["case_id"]} | {row["label"]} | {row["status"]} | {"yes" if row.get("inference_completed") and row.get("provenance") == "local_execution" else "no"} |')
    lines += ['', 'Synthetic and real cases remain separate. Missing checkpoints, rights or recordings are unavailable, never passed.',
              'Detailed metrics, exact identities, source checksums and limitations: percussion_benchmark_results.json.']
    (folder(cid) / 'PERCUSSION_BENCHMARK_REPORT.md').write_text('\n'.join(lines) + '\n')
    valid = [r for r in value['results'] if _verified_result(cid, r)]
    representatives = []
    seen = set()
    for row in valid:
        if row['category'] not in seen:
            representatives.append(row)
            seen.add(row['category'])
    representatives = representatives[:8]
    manual = ['# Guided manual validation', '', '**In attesa di validazione umana**', '',
              'Start with this representative batch (at most eight cases). Compare the original DRUMS, exact reference where available, and blind candidates at the same position.',
              'Score isolation, contamination (5 = clean), naturalness, transients, completeness and overall quality from 1 to 5. Choose professional / limited / rejected; add concrete comments.',
              'Check missing conga/shaker attacks, snare/tom/cymbal bleed, false events, stereo shifts and tails. Use original gain to check dynamics after level-matched A/B.']
    if not representatives:
        manual += ['', 'No model produced verified listening audio. Install and authorize a real candidate, run this campaign, then generate the first listening batch. Do not evaluate synthetic references as if they were model outputs.']
    for row in representatives:
        manual += ['', f'- {row["case_id"]}: {row["label"]}; `{row["output"]}`; first 10–20 s, then complete source.']
    manual += ['', 'ChatGPT reviews the actual report and your scores, chooses follow-ups for the observed defects, and requests explicit approval only after the complete release corpus has been evaluated.']
    (folder(cid) / 'PERCUSSION_MANUAL_VALIDATION.md').write_text('\n'.join(manual) + '\n')
    return result



def export(cid):
    reports(cid)
    value = _read(cid)
    directory = folder(cid)
    registered = {'campaign.json': directory / 'campaign.json',
                  'PERCUSSION_BENCHMARK_REPORT.md': directory / 'PERCUSSION_BENCHMARK_REPORT.md',
                  'PERCUSSION_MANUAL_VALIDATION.md': directory / 'PERCUSSION_MANUAL_VALIDATION.md',
                  'percussion_benchmark_results.json': directory / 'percussion_benchmark_results.json'}
    for row in value['results']:
        for name, sha in row.get('files', {}).items():
            path = _safe_file(directory, name)
            if digest(path) != sha:
                raise ValueError('Changed result cannot be exported as verified evidence')
            registered[name] = path
    bundles = {}
    for case in value['config']['cases']:
        if not case.get('prepared'):
            continue
        for relative, sha in case.get('sha256', {}).items():
            path = _dataset_file(case, relative)
            name = 'source_audio/' + identifier(case['dataset_id']) + '/' + relative
            registered[name] = path
            bundles[case['dataset_id'] + ':' + relative] = {'path': name, 'sha256': sha}
    value['bundled_sources'] = bundles
    state = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode()
    if len(registered) > MAX_FILES or sum(p.stat().st_size for p in registered.values()) + len(state) > MAX_ARCHIVE_BYTES:
        raise ValueError('Campaign exceeds export limits')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, path in registered.items():
            archive.writestr(name, state if name == 'campaign.json' else path.read_bytes())
    if output.tell() > MAX_ARCHIVE_BYTES:
        raise ValueError('Compressed campaign exceeds export limit')
    return output.getvalue()



def restore(data, actor):
    if type(actor) is not int or actor <= 0:
        raise ValueError('Authenticated campaign restore administrator required')
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_ARCHIVE_BYTES:
        raise ValueError('Campaign archive exceeds size limit or is empty')
    from .percussion_dataset_import import _json, _name
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, RuntimeError, EOFError) as exc:
        raise ValueError('Unsafe campaign ZIP archive') from exc
    with archive:
        entries = archive.infolist()
        if not 1 <= len(entries) <= MAX_FILES or sum(e.file_size for e in entries) > MAX_ARCHIVE_BYTES:
            raise ValueError('Unsafe or oversized campaign archive')
        names, normalized = set(), {}
        for entry in entries:
            try:
                name = _name(entry.filename)
            except ValueError as exc:
                raise ValueError('Unsafe campaign archive entry: ' + str(exc)) from exc
            mode = stat.S_IFMT(entry.external_attr >> 16)
            if (entry.orig_filename != entry.filename or name.casefold() in names or entry.is_dir()
                    or mode not in (0, stat.S_IFREG) or entry.flag_bits & 1
                    or entry.file_size < 0 or entry.compress_size < 0):
                raise ValueError('Unsafe campaign archive link, alias, encryption or special file')
            top_level = {'campaign.json', 'percussion_benchmark_results.json',
                         'PERCUSSION_BENCHMARK_REPORT.md', 'PERCUSSION_MANUAL_VALIDATION.md'}
            if name not in top_level and not ((name.startswith('audio/') or name.startswith('source_audio/')) and name.endswith('.wav')):
                raise ValueError('Unsafe campaign artifact extension or location')
            if any(name.casefold().startswith(old + '/') or old.startswith(name.casefold() + '/') for old in names):
                raise ValueError('Unsafe campaign archive path collision')
            names.add(name.casefold()); normalized[name] = entry
        if 'campaign.json' not in normalized or normalized['campaign.json'].file_size > 8 * 1024 * 1024:
            raise ValueError('Unsafe campaign state missing or oversized')
        try:
            value = _json(archive.read(normalized['campaign.json']))
        except (zipfile.BadZipFile, RuntimeError, EOFError) as exc:
            raise ValueError('Unsafe campaign archive content') from exc
        cid = identifier(value.get('id') if isinstance(value, dict) else None)
        destination = folder(cid)  # Reject an unsafe parent before inspecting imported claims.
        _validate_campaign(value)
        with locked(cid):
            if destination.exists():
                raise ValueError('Campaign already exists; restore never overwrites evaluations')
            stage = Path(tempfile.mkdtemp(prefix='.campaign-', dir=root()))
            try:
                for name, entry in normalized.items():
                    target = stage / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry) as source, target.open('xb') as output:
                        written = 0
                        while chunk := source.read(1024 * 1024):
                            written += len(chunk)
                            if written > entry.file_size or written > MAX_ARCHIVE_BYTES:
                                raise ValueError('Unsafe expanded campaign archive size')
                            output.write(chunk)
                    if written != entry.file_size:
                        raise ValueError('Campaign ZIP size mismatch')
                registered = {'campaign.json', 'percussion_benchmark_results.json',
                              'PERCUSSION_BENCHMARK_REPORT.md', 'PERCUSSION_MANUAL_VALIDATION.md'}
                for row in value['results']:
                    files = row.get('files', {})
                    if not isinstance(files, dict):
                        raise ValueError('Invalid imported result inventory')
                    for name, sha in files.items():
                        if not name.startswith('audio/') or not isinstance(sha, str) or not re.fullmatch('[a-f0-9]{64}', sha):
                            raise ValueError('Unsafe imported result binding')
                        if digest(_safe_file(stage, name)) != sha:
                            raise ValueError('Restored audio hash mismatch')
                        registered.add(name)
                    row['historical_status'] = row.get('status')
                    row.update(status='imported_unverified', provenance='untrusted_import', inference_completed=False)
                bundles = value.get('bundled_sources', {})
                if not isinstance(bundles, dict) or len(bundles) > MAX_FILES:
                    raise ValueError('Invalid imported source inventory')
                expected = {c['dataset_id'] + ':' + name: sha for c in value['config']['cases'] for name, sha in c.get('sha256', {}).items()}
                for key, item in bundles.items():
                    if (key not in expected or not isinstance(item, dict) or item.get('sha256') != expected[key]
                            or not isinstance(item.get('path'), str) or not item['path'].startswith('source_audio/')
                            or digest(_safe_file(stage, item['path'])) != expected[key]):
                        raise ValueError('Restored corpus hash mismatch')
                    registered.add(item['path'])
                if set(normalized) - registered:
                    raise ValueError('Unsafe unregistered campaign artifact')
                value['imported_ratings'] = value.pop('ratings', [])
                value['ratings'] = []
                if value.get('manual_approval'):
                    value['imported_approval'] = value.pop('manual_approval')
                value.pop('queue_job_id', None)
                value.update(actor_user_id=actor, status='imported', human_validation='In attesa di validazione umana',
                             restoration={'actor_user_id': actor, 'at': time.time(),
                                          'archive_sha256': hashlib.sha256(data).hexdigest(), 'claims_verified': False})
                _write(stage / 'campaign.json', value)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.parent.is_symlink() or destination.exists():
                    raise ValueError('Unsafe campaign directory changed before publication')
                destination.mkdir(mode=0o700)  # Exclusive reservation; never replace another campaign.
                try:
                    for child in list(stage.iterdir()):
                        child.rename(destination / child.name)
                except BaseException:
                    shutil.rmtree(destination)
                    raise
            finally:
                if stage.exists():
                    shutil.rmtree(stage)
    reports(cid)  # Discard imported report authority; generate a current unverified report.
    return get(cid)

