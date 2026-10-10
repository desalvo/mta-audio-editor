"""Regression guard for the GitHub Actions Ruff F401 failures in r32/r33."""
import ast
from pathlib import Path


def test_unused_import_regressions():
    root = Path(__file__).parents[1]
    chain = ast.parse((root / "native/vst3_probe/native_chain.py").read_text())
    test_file = ast.parse((root / "tests/test_r32_native_chain.py").read_text())
    assert all(not (isinstance(n, ast.Import) and any(a.name == "json" for a in n.names)) for n in chain.body)
    assert all(not (isinstance(n, ast.ImportFrom) and any(a.name == "NativeChainError" for a in n.names)) for n in test_file.body)
