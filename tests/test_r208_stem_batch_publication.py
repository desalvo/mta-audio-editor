"""Guard against reintroducing per-stem project publication and unsafe rollback."""
import ast
import inspect
import textwrap
from app import main


def _worker_tree():
    return ast.parse(textwrap.dedent(inspect.getsource(main._stem_split_worker)))


def test_stem_worker_publishes_project_once_after_batch_loop():
    root = _worker_tree()
    fn = root.body[0]
    saves = [node for node in ast.walk(fn) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'save_project']
    # Initial BPM estimation and optional lyrics/chords each save separately;
    # the stem publication itself must not save inside the stem import loop.
    loops = [node for node in ast.walk(fn) if isinstance(node, ast.For) and isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == 'enumerate']
    assert loops
    for loop in loops:
        assert not any(node in ast.walk(loop) for node in saves)
    assignments = [node for node in ast.walk(fn) if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'stems_published' for t in node.targets)]
    assert any(isinstance(node.value, ast.Constant) and node.value.value is True for node in assignments)


def test_stem_worker_does_not_delete_replaced_audio_before_atomic_publish():
    source = inspect.getsource(main._stem_split_worker)
    assert source.index('stems_published = True') < source.index('if obsolete_files:')
    assert 'schedule_project_gc(project_id, {path.name for path in obsolete_files})' in source
    assert 'schedule_project_gc(project_id, abandoned)' in source
