"""Verify asynchronous stem commits share project publication serialization."""
import ast
import inspect
import textwrap
from app import main


def test_stem_publication_is_under_project_lock():
    tree=ast.parse(textwrap.dedent(inspect.getsource(main._stem_split_worker)))
    protected=[]
    for node in ast.walk(tree):
        if isinstance(node, ast.With) and any(isinstance(item.context_expr,ast.Call) and isinstance(item.context_expr.func,ast.Name) and item.context_expr.func.id=='project_publication_lock' for item in node.items):
            protected.append(node)
    assert len(protected)>=4  # BPM, stem batch, lyrics, chords
    assert any(any(isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='stems_published' for t in n.targets) for n in ast.walk(block)) for block in protected)


def test_remote_inference_runs_outside_stem_publication_lock():
    source=inspect.getsource(main._stem_split_worker)
    assert source.index('with tempfile.TemporaryDirectory(')<source.index('with project_publication_lock(project_id):\n                project = load_project(project_id)')
