"""An omitted route, new executable, alias or changed runtime must need review."""
import copy
import json
from pathlib import Path

import pytest

from scripts.check_ai_execution_inventory import discover, sources, validate

ROOT = Path(__file__).resolve().parents[1]


def test_current_complete_execution_entry_review():
    review = json.loads((ROOT / 'docs/security/AI_EXECUTION_REVIEW_R210.json').read_text())
    result = validate(ROOT, review)
    assert result['inventory_passed'] and result['runtime_source_files'] >= 539
    assert result['families'] == 10


@pytest.mark.parametrize('code', [
    'from subprocess import Popen as launch\nlaunch(command)',
    'import subprocess as child\nchild.run(command)',
    'from onnxruntime import InferenceSession as Load\nLoad(model)',
    'from fastapi import APIRouter\nr=APIRouter()\n@r.post("/new-worker")\ndef invoke():pass',
    'from fastapi import APIRouter\nr=APIRouter()\n@r.api_route("/proxy/{path:path}",methods=["POST"])\ndef invoke():pass',
    'from arbitrary import transcribe as job\njob(source)',
])
def test_new_execution_aliases_and_routes_need_review(tmp_path, code):
    (tmp_path / 'app').mkdir(); (tmp_path / 'app/new.py').write_text(code)
    assert discover(tmp_path)
    with pytest.raises(ValueError): validate(tmp_path, {'schema': 'mta-execution-entry-review-1'})


def test_sibling_local_imports_do_not_rewrite_other_functions(tmp_path):
    (tmp_path / 'app').mkdir()
    (tmp_path / 'app/new.py').write_text('''def first():
 from alpha import infer as work
 work(source)
def second():
 from beta import infer as work
 work(source)
''')
    found = discover(tmp_path)
    assert [(i['function'], i['call']) for i in found] == [('first', 'alpha.infer'), ('second', 'beta.infer')]


@pytest.mark.parametrize('damage', ['omit', 'family', 'proof', 'checker', 'native-source', 'contract'])
def test_review_cannot_omit_or_reclassify_an_entry_without_review(damage):
    review = json.loads((ROOT / 'docs/security/AI_EXECUTION_REVIEW_R210.json').read_text())
    changed = copy.deepcopy(review)
    if damage == 'omit': changed['entries'].pop()
    elif damage == 'family': changed['entries'][0]['family'] = 'everything-approved'
    elif damage == 'proof': changed['entries'][0]['evidence'] = ['tests/nonexistent.py']
    elif damage == 'checker': changed['checker_sha256'] = '0' * 64
    elif damage == 'native-source': changed['source_sha256']['mobile/ios/MTAEditorMobile/LocalStemEngine.swift'] = 'sha256:' + '0' * 64
    else: changed['family_contracts'].pop('native_mobile')
    with pytest.raises(ValueError): validate(ROOT, changed)


def test_native_and_operator_sources_are_part_of_complete_binding(tmp_path):
    for name in ['native/worker.py', 'mobile/worker.swift', 'scripts/worker.py', 'app/static/worker.js']:
        path = tmp_path / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('/* fixture */' if not name.endswith('.py') else '# fixture')
    assert set(sources(tmp_path)) == {'native/worker.py', 'mobile/worker.swift', 'scripts/worker.py', 'app/static/worker.js'}
