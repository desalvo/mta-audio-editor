"""Require explicit source-bound review of all inference/execution entry families.

The census is a review aid, not arbitrary-code reachability analysis or hardware
attestation. All runtime source is pinned, including code outside its patterns.
"""
import ast
import hashlib
import json
from pathlib import Path
import re

if __package__:
    from .check_remote_transport_inventory import call_shape
else:
    from check_remote_transport_inventory import call_shape

ROOTS = ('app', 'native', 'mobile', 'scripts')
EXTENSIONS = frozenset({'.py', '.js', '.ts', '.swift', '.java', '.cpp', '.hpp', '.h', '.m', '.mm'})
CALLS = frozenset({
    'execute_registered_worker', '_execute_registered_worker', 'run_external_worker',
    'run_worker_with_project_audio', 'infer_audio', 'infer_durable_remote',
    'infer_and_register_remote_settlement', 'run_metered_process', 'run_cgroup_process',
    'remote_compute', 'execute_arranger', 'execute_remix', 'extract_lyrics',
    'extract_lyrics_progressive', 'extract_chords', 'extract_chords_progressive',
    'extract_markers', 'transcribe', 'predict', 'predict_and_save', 'from_pretrained',
    'InferenceSession', 'separate', 'infer', 'render_neural',
})
FAMILIES = frozenset({
    'registered_server', 'web_project', 'durable_remote', 'pull_worker',
    'native_local', 'native_remote', 'adapter_child', 'native_mobile',
    'operator_diagnostic', 'non_inference',
})


def sources(root):
    result = {}
    for directory in ROOTS:
        for path in sorted((root / directory).rglob('*')):
            if '__pycache__' in path.parts or path.suffix not in EXTENSIONS or not path.is_file():
                continue
            if path.is_symlink(): raise ValueError('Symbolic runtime source requires review')
            result[path.relative_to(root).as_posix()] = 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
    if not result: raise ValueError('Runtime source unavailable')
    return dict(sorted(result.items()))


def discover(root):
    entries = []
    for name in sources(root):
        path = root / name
        if path.suffix != '.py':
            # Explicit native/WebView model execution boundaries. All other
            # native/browser source bytes are still bound by the complete map.
            pattern = r'\b(?:prediction|predict|separate|separateSync)\s*\(|\bInferenceSession\b'
            for line, text in enumerate(path.read_text().splitlines(), 1):
                if re.search(pattern, text):
                    entries.append({'path': name, 'function': '<native>', 'line': line,
                                    'kind': 'native_inference',
                                    'shape_sha256': hashlib.sha256(text.strip().encode()).hexdigest()})
            continue
        tree = ast.parse(path.read_text())
        def imports(node, aliases):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.Import):
                    for alias in child.names: aliases[alias.asname or alias.name] = alias.name
                elif isinstance(child, ast.ImportFrom):
                    for alias in child.names:
                        aliases[alias.asname or alias.name] = (child.module or '') + '.' + alias.name
                elif not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                    imports(child, aliases)
            return aliases
        def dotted(node, aliases):
            if isinstance(node, ast.Name): return aliases.get(node.id, node.id)
            if isinstance(node, ast.Attribute): return dotted(node.value, aliases) + '.' + node.attr
            return ''
        def visit(node, function='<module>', aliases=None):
            if aliases is None: aliases = imports(tree, {})
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function = node.name
                aliases = imports(node, dict(aliases))
                for decorator in node.decorator_list:
                    if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                            and decorator.func.attr in {'get', 'post', 'put', 'delete', 'patch', 'websocket', 'api_route', 'route'}
                            and decorator.args and isinstance(decorator.args[0], ast.Constant)
                            and isinstance(decorator.args[0].value, str)
                            and decorator.args[0].value.startswith('/')):
                        entries.append({'path': name, 'function': function, 'line': decorator.lineno,
                                        'kind': 'http_entry', 'route': decorator.args[0].value,
                                        'shape_sha256': hashlib.sha256(call_shape(decorator).encode()).hexdigest()})
            if isinstance(node, ast.Call):
                call = dotted(node.func, aliases); leaf = call.rsplit('.', 1)[-1]; kind = None
                if call.startswith('subprocess.') and leaf in {'run', 'Popen', 'call', 'check_call', 'check_output'}:
                    kind = 'process_boundary'
                elif call in {'os.system', 'os.execv', 'os.execve', 'os.execvp', 'os.posix_spawn', 'os.fork'}:
                    kind = 'process_boundary'
                elif leaf in CALLS: kind = 'inference_call'
                if kind:
                    entries.append({'path': name, 'function': function, 'line': node.lineno,
                                    'kind': kind, 'call': call,
                                    'shape_sha256': hashlib.sha256(call_shape(node).encode()).hexdigest()})
            for child in ast.iter_child_nodes(node): visit(child, function, aliases)
        visit(tree)
    return sorted(entries, key=lambda row: (row['path'], row['line'], row['kind']))


def validate(root, review):
    if (review.get('schema') != 'mta-execution-entry-review-1'
            or review.get('source_sha256') != sources(root)
            or review.get('checker_sha256') != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()):
        raise ValueError('Execution entry review missing or stale')
    discovered = discover(root); entries = review.get('entries', [])
    if len(entries) != len(discovered): raise ValueError('Unreviewed or omitted execution entry')
    for actual, item in zip(discovered, entries):
        if any(item.get(key) != value for key, value in actual.items()):
            raise ValueError('Execution boundary changed')
        if item.get('family') not in FAMILIES or len(item.get('boundary', '').strip()) < 30:
            raise ValueError('Execution boundary unclassified')
        proofs = item.get('evidence', [])
        if not proofs or any(not isinstance(p, str) or not (root / p).is_file() for p in proofs):
            raise ValueError('Execution boundary proof unavailable')
    if set(review.get('family_contracts', {})) != FAMILIES:
        raise ValueError('Incomplete execution family review')
    for family, item in review['family_contracts'].items():
        if len(item.get('boundary', '').strip()) < 30 or not item.get('evidence'):
            raise ValueError('Missing ownership/metering family contract: ' + family)
        if any(not (root / p).is_file() for p in item['evidence']):
            raise ValueError('Missing execution family evidence')
    return {'inventory_passed': True, 'runtime_source_files': len(review['source_sha256']),
            'reviewed_boundaries': len(entries), 'families': len(FAMILIES),
            'hardware_model_rights_or_kernel_attestation': False, 'release_candidate': False}


def main():
    root = Path(__file__).resolve().parents[1]
    review = json.loads((root / 'docs/security/AI_EXECUTION_REVIEW_R210.json').read_text())
    print(json.dumps(validate(root, review), sort_keys=True))


if __name__ == '__main__': main()
