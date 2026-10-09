from pathlib import Path


def test_native_build_validates_roformer_pep604_hints():
    workflow = Path('.github/workflows/ci-cd.yml').read_text()
    assert workflow.count('beartype>=0.22.2,<0.23') >= 2
    assert workflow.count('RoFormer Callable | None annotation OK') == 2
    assert 'is_bearable(None, Callable | None)' in workflow


def test_roformer_type_checker_reports_actionable_error():
    source = Path('app/main.py').read_text()
    assert 'separator.load_model(model_filename=info["filename"])' in source
    assert 'RoFormer model cannot be loaded with the installed beartype validator' in source
    assert 'Original error: {exc}' in source
