import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('security_review_gate',ROOT/'scripts/check_security_review.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)


def fixture_review(tmp_path):
    (tmp_path/'app').mkdir();(tmp_path/'app/example.py').write_text('value=1\n')
    row={'filename':'app/example.py','test_id':'B105','test_name':'hardcoded_password_string','issue_severity':'LOW',
         'issue_confidence':'MEDIUM','issue_text':'Possible hardcoded password','line_number':1,'line_range':[1],
         'col_offset':0,'end_col_offset':7,'code':'value=1\n'}
    scan={'errors':[],'results':[row],'metrics':{'app/example.py':{},'_totals':{'nosec':0,'skipped_tests':0,'SEVERITY.HIGH':0,'SEVERITY.MEDIUM':0,'SEVERITY.LOW':1}}}
    item={'id':gate.finding_identity(row),'disposition':'false_positive','rationale':'Fixture constant is not an authentication secret.',
          'boundary':'Synthetic application source with no external inputs.','verification':'The exact source and finding are checked in this test.'}
    review={'schema':'mta-security-review-1','source_sha256':gate.source_hashes(tmp_path),'findings':[item]}
    return scan,review


def test_complete_source_bound_review_is_accepted(tmp_path):
    scan,review=fixture_review(tmp_path)
    result=gate.validate(tmp_path,scan,review)
    assert result['scan_review_passed'] and result['reviewed_findings']==1 and not result['release_candidate']


@pytest.mark.parametrize('mutation',['changed_source','new_source','deleted_source','scan_error','missing_file','suppression','high','missing_review','duplicate_review','new_finding','changed_finding','duplicate_scan','wrong_totals','empty_reason','blanket_approval'])
def test_review_cannot_silently_survive_source_or_scan_changes(tmp_path,mutation):
    scan,review=fixture_review(tmp_path)
    if mutation=='changed_source':(tmp_path/'app/example.py').write_text('value=2\n')
    if mutation=='new_source':(tmp_path/'app/extra.py').write_text('extra=1\n')
    if mutation=='deleted_source':(tmp_path/'app/example.py').unlink()
    if mutation=='scan_error':scan['errors']=[{'filename':'app/example.py'}]
    if mutation=='missing_file':scan['metrics'].pop('app/example.py')
    if mutation=='suppression':scan['metrics']['_totals']['nosec']=1
    if mutation=='high':scan['metrics']['_totals']['SEVERITY.HIGH']=1
    if mutation=='missing_review':review['findings']=[]
    if mutation=='duplicate_review':review['findings']*=2
    if mutation=='new_finding':
        row=copy.deepcopy(scan['results'][0]);row['test_id']='B106';scan['results'].append(row);scan['metrics']['_totals']['SEVERITY.LOW']=2
    if mutation=='changed_finding':scan['results'][0]['code']='different code'
    if mutation=='duplicate_scan':scan['results']*=2
    if mutation=='wrong_totals':scan['metrics']['_totals']['SEVERITY.LOW']=4
    if mutation=='empty_reason':review['findings'][0]['rationale']=''
    if mutation=='blanket_approval':review['findings'][0]['disposition']='ignore_all'
    with pytest.raises(gate.ReviewInvalid):gate.validate(tmp_path,scan,review)


def test_current_scan_and_complete_review_ledger_agree():
    review=json.loads((ROOT/'docs/security/APP_SECURITY_REVIEW_R210.json').read_text())
    scan=json.loads((ROOT/review.get('current_scan','docs/validation/r210/security-final-bandit.json')).read_text())
    assert gate.validate(ROOT,scan,review)['scan_review_passed']
