"""The explicit CI gate cannot turn missing Chromium/coverage into green."""
import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('merchant_chromium_gate',ROOT/'scripts/run_merchant_history_chromium.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)


def report(tmp_path,mutation=None):
    root=ET.Element('testsuite')
    names=sorted(gate.EXPECTED)
    if mutation=='missing':names.pop()
    if mutation=='duplicate':names[-1]=names[0]
    for index,name in enumerate(names):
        row=ET.SubElement(root,'testcase',name=name,classname='tests.test_r210_paypal_merchant_history_browser')
        if mutation in ('skipped','failure','error') and index==0:ET.SubElement(row,mutation)
        if mutation=='wrong_scope':row.set('classname','synthetic_fixture')
    path=tmp_path/'pytest.xml';ET.ElementTree(root).write(path);return path


def test_exact_real_coverage_passes(tmp_path):
    assert gate.validate_report(report(tmp_path))['passed']==4


@pytest.mark.parametrize('mutation',['missing','duplicate','skipped','failure','error','wrong_scope'])
def test_incomplete_or_skipped_coverage_fails(tmp_path,mutation):
    with pytest.raises(ValueError):gate.validate_report(report(tmp_path,mutation))


def test_malformed_or_absent_report_fails(tmp_path):
    path=tmp_path/'bad.xml';path.write_text('<broken')
    with pytest.raises(ET.ParseError):gate.validate_report(path)
    with pytest.raises(FileNotFoundError):gate.validate_report(tmp_path/'absent.xml')


def test_dtd_is_never_accepted(tmp_path):
    from defusedxml.common import DTDForbidden
    path=tmp_path/'entity.xml'
    path.write_text('<!DOCTYPE testsuite><testsuite/>')
    with pytest.raises(DTDForbidden):gate.validate_report(path)
