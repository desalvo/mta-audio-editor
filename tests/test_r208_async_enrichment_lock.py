"""Regression guards for inference/commit ordering in the stem worker."""
import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'app' / 'main.py'


def _worker():
    tree = ast.parse(SOURCE.read_text())
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_stem_split_worker')


def test_whisper_inference_outside_publication_lock():
    worker = _worker()
    calls = [n for n in ast.walk(worker) if isinstance(n, ast.Call)]
    inference = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == 'extract_lyrics']
    assert len(inference) == 1
    remote = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == '_native_remote_infer' and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == 'whisper']
    assert len(remote) == 1
    locks = [n for n in ast.walk(worker) if isinstance(n, ast.With) and any(isinstance(i.context_expr, ast.Call) and isinstance(i.context_expr.func, ast.Name) and i.context_expr.func.id == 'project_publication_lock' for i in n.items)]
    for lock in locks:
        assert not any(inf in ast.walk(lock) for inf in inference + remote)


def test_chords_inference_outside_publication_lock():
    worker = _worker()
    calls = [n for n in ast.walk(worker) if isinstance(n, ast.Call)]
    inference = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == 'extract_chords']
    remote = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == '_native_remote_infer' and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == 'chords-ml']
    assert len(inference) == len(remote) == 1
    for lock in (n for n in ast.walk(worker) if isinstance(n, ast.With) and any(isinstance(i.context_expr, ast.Call) and isinstance(i.context_expr.func, ast.Name) and i.context_expr.func.id == 'project_publication_lock' for i in n.items)):
        assert not any(inf in ast.walk(lock) for inf in inference + remote)


def test_project_reload_and_conflict_check_inside_lyrics_chords_lock():
    worker = _worker()
    locks = [n for n in ast.walk(worker) if isinstance(n, ast.With) and any(isinstance(i.context_expr, ast.Call) and isinstance(i.context_expr.func, ast.Name) and i.context_expr.func.id == 'project_publication_lock' for i in n.items)]
    matching = 0
    for lock in locks:
        attrs = {n.attr for n in ast.walk(lock) if isinstance(n, ast.Attribute)}
        if 'lyrics' in attrs or 'chords' in attrs:
            calls = {n.func.id for n in ast.walk(lock) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
            assert 'load_project' in calls and 'save_project' in calls
            matching += 1
    assert matching >= 2
