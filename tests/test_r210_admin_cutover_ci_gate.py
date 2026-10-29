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


@pytest.mark.parametrize('damage', [None, 'missing', 'skip', 'duplicate', 'wrong-family', 'old-report'])
def test_integrated_drain_acceptance_requires_twelve_exact_new_cases(tmp_path, damage):
    from scripts.run_admin_cutover_chromium import DRAIN_EXPECTED
    suite = ET.Element('testsuite')
    for name in sorted(DRAIN_EXPECTED):
        ET.SubElement(suite, 'testcase', classname='tests.test_r210_cutover_service_drain_browser', name=name)
    if damage == 'missing': suite.remove(suite[0])
    elif damage == 'skip': ET.SubElement(suite[0], 'skipped')
    elif damage == 'duplicate': suite[0].set('name', suite[1].get('name'))
    elif damage == 'wrong-family': suite[0].set('classname', 'tests.test_r210_admin_cutover_browser')
    path = tmp_path / 'drain.xml'
    ET.ElementTree(suite).write(path, encoding='utf-8')
    if damage == 'old-report': path = report(tmp_path)
    if damage:
        with pytest.raises(ValueError): validate_report(path, service_drain=True)
    else:
        result = validate_report(path, service_drain=True)
        assert result['passed'] == 12 and result['scope'] == 'actual_service_drain_settings_cutover'
        with pytest.raises(ValueError): validate_report(path)


@pytest.mark.parametrize('damage', [None, 'missing', 'skip', 'duplicate', 'foreign-family', 'old-nine'])
def test_complete_operator_acceptance_requires_all_fifty_nine_cases(tmp_path, damage):
    from scripts.run_admin_cutover_chromium import OPERATOR_CASES
    assert len(OPERATOR_CASES) == 59
    suite = ET.Element('testsuite')
    for module, name in sorted(OPERATOR_CASES):
        ET.SubElement(suite, 'testcase', classname=module, name=name)
    if damage == 'missing': suite.remove(suite[0])
    elif damage == 'skip': ET.SubElement(suite[0], 'skipped')
    elif damage == 'duplicate':
        suite[0].set('name', suite[1].get('name')); suite[0].set('classname', suite[1].get('classname'))
    elif damage == 'foreign-family': suite[0].set('classname', 'tests.unrelated_browser')
    path = tmp_path / 'complete-operator.xml'
    ET.ElementTree(suite).write(path, encoding='utf-8')
    if damage == 'old-nine': path = report(tmp_path)
    if damage:
        with pytest.raises(ValueError): validate_report(path, operator_workflow=True)
    else:
        result = validate_report(path, operator_workflow=True)
        assert result['passed'] == 59 and not result['release_candidate']
        with pytest.raises(ValueError): validate_report(path, service_drain=True, operator_workflow=True)
