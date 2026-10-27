"""A browser acceptance artifact must prove all exact cases, not collection/skips."""
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from scripts.run_admin_cutover_chromium import EXPECTED, validate_report


def report(tmp_path, change=None):
    suite = ET.Element('testsuite')
    for name in sorted(EXPECTED):
        ET.SubElement(suite, 'testcase', classname='tests.test_r210_admin_cutover_browser', name=name)
    if change:
        change(suite)
    path = tmp_path / 'browser.xml'
    ET.ElementTree(suite).write(path, encoding='utf-8')
    return path


def test_complete_exact_browser_report_is_required(tmp_path):
    result = validate_report(report(tmp_path))
    assert result['passed'] == 9 and result['skipped'] == 0 and result['release_candidate'] is False


@pytest.mark.parametrize('tag', ['failure', 'error', 'skipped'])
def test_any_failure_error_or_prerequisite_skip_refuses_acceptance(tmp_path, tag):
    with pytest.raises(ValueError):
        validate_report(report(tmp_path, lambda suite: ET.SubElement(suite[0], tag)))


@pytest.mark.parametrize('change', [
    lambda suite: suite.remove(suite[0]),
    lambda suite: suite[0].set('classname', 'unrelated.passing.tests'),
    lambda suite: suite[0].set('name', suite[1].get('name')),
])
def test_missing_foreign_or_duplicate_case_cannot_replace_real_acceptance(tmp_path, change):
    with pytest.raises(ValueError):
        validate_report(report(tmp_path, change))


def test_dtd_is_rejected_before_parsing(tmp_path):
    from defusedxml.common import DefusedXmlException
    path = Path(tmp_path) / 'entity.xml'
    path.write_text('<!DOCTYPE x [<!ENTITY a "unexpected">]><testsuite>&a;</testsuite>')
    with pytest.raises(DefusedXmlException):
        validate_report(path)
