"""Strict identity/zero-skip acceptance gate, independent of browser availability."""
import xml.etree.ElementTree as ET
from defusedxml import ElementTree as SafeET

import pytest
from scripts.run_transition_progress_chromium import EXPECTED,validate_report


def fixture(tmp_path):
    root=ET.Element('testsuite')
    for module,name in sorted(EXPECTED):ET.SubElement(root,'testcase',classname=module,name=name)
    path=tmp_path/'cases.xml';ET.ElementTree(root).write(path);return path


def test_complete_progress_case_set_is_required(tmp_path):
    result=validate_report(fixture(tmp_path));assert result['passed']==32 and not result['general_cutover_authorized']


@pytest.mark.parametrize('damage',['missing','duplicate','class','skip','failure','error'])
def test_altered_progress_evidence_is_not_accepted(tmp_path,damage):
    path=fixture(tmp_path);tree=SafeET.parse(path);root=tree.getroot()
    if damage=='missing':root.remove(root[0])
    elif damage=='duplicate':root[0].attrib.update(root[1].attrib)
    elif damage=='class':root[0].set('classname','fake')
    else:ET.SubElement(root[0],{'skip':'skipped'}.get(damage,damage))
    tree.write(path)
    with pytest.raises(ValueError):validate_report(path)


def test_missing_pinned_prerequisite_clears_stale_acceptance(tmp_path,monkeypatch):
    import json
    from scripts import run_transition_progress_chromium as runner
    (tmp_path/'acceptance.json').write_text('{"accepted":true}')
    (tmp_path/'pytest.xml').write_text('<testsuite/>')
    monkeypatch.delenv('MTA_TEST_AXE_CORE',raising=False)
    monkeypatch.setattr('sys.argv',['runner','--output',str(tmp_path)])
    assert runner.main()==1
    assert json.loads((tmp_path/'acceptance.json').read_text())['accepted'] is False
    assert not (tmp_path/'pytest.xml').exists()
