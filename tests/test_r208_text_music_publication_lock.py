"""Regression checks for asynchronous text/music project publication boundaries."""
import ast
from pathlib import Path


def _worker():
    tree = ast.parse((Path(__file__).parents[1] / 'app' / 'main.py').read_text())
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_text_music_worker')


def _within(node, parent):
    return any(x is node for x in ast.walk(parent))


def test_all_three_publications_are_locked():
    worker = _worker()
    locks = [n for n in ast.walk(worker) if isinstance(n, ast.With) and
             any(isinstance(i.context_expr, ast.Call) and isinstance(i.context_expr.func, ast.Name)
                 and i.context_expr.func.id == 'project_publication_lock' for i in n.items)]
    assert len(locks) == 3
    saves = [n for n in ast.walk(worker) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'save_project']
    assert len(saves) == 3
    assert all(any(_within(save, lock) for lock in locks) for save in saves)


def test_inference_is_outside_all_publication_locks():
    worker = _worker()
    locks = [n for n in ast.walk(worker) if isinstance(n, ast.With) and
             any(isinstance(i.context_expr, ast.Call) and isinstance(i.context_expr.func, ast.Name)
                 and i.context_expr.func.id == 'project_publication_lock' for i in n.items)]
    inference = {'extract_lyrics', 'extract_lyrics_progressive', 'extract_chords',
                 'extract_chords_progressive', 'extract_markers', '_native_remote_infer'}
    calls = [n for n in ast.walk(worker) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in inference]
    assert calls
    assert all(not any(_within(call, lock) for lock in locks) for call in calls)


def test_annotation_conflicts_checked_inside_lock_before_write():
    locks = [n for n in ast.walk(_worker()) if isinstance(n, ast.With) and
             any(isinstance(i.context_expr, ast.Call) and isinstance(i.context_expr.func, ast.Name)
                 and i.context_expr.func.id == 'project_publication_lock' for i in n.items)]
    for name in ('lyrics', 'chords'):
        target = next(n for n in locks if any(isinstance(x, ast.Attribute) and x.attr == name for x in ast.walk(n)))
        assert isinstance(target.body[0], ast.Assign)  # reload project
        assert isinstance(target.body[1], ast.If)  # check concurrent change
        assert any(isinstance(x, ast.Raise) for x in ast.walk(target.body[1]))
        assert any(isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id == 'save_project' for x in ast.walk(target))
