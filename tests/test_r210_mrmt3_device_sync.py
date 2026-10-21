"""Regression: MR-MT3 adapters must use the same device as their weights."""
import ast
from pathlib import Path


def test_adapter_device_synchronized_after_weights_move():
    source = (Path(__file__).resolve().parents[1] / "scripts" / "run_mrmt3_resumable.py").read_text()
    tree = ast.parse(source)
    stmts = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
             and any(isinstance(t, ast.Attribute) and t.attr == "device_str"
                     for t in node.targets)]
    assert len(stmts) >= 1
    assert any(isinstance(stmt.value, ast.Name) and stmt.value.id == "device" for stmt in stmts)
