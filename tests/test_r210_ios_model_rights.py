"""Real build-input/CLI checks and strict native target refusal;not Apple execution."""
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

import pytest
from scripts import check_ios_model_rights as build
from scripts import run_ios_model_rights_acceptance as native

ROOT=Path(__file__).resolve().parents[1]
NOW=1_800_000_000


@pytest.fixture
def review(tmp_path):
    source=tmp_path/'demucs-default-4.mlmodel';source.write_bytes(b'Own generated test source;not a neural checkpoint')
    license=tmp_path/'LICENSE-fixture.txt';license.write_bytes(b'Own generated fixture license')
    notice=tmp_path/'NOTICE-fixture.txt';notice.write_bytes(b'Own generated fixture notice')
    item={'id':'demucs-4','stemCount':4,'sourceFormat':'mlmodel','sourceSHA256':hashlib.sha256(source.read_bytes()).hexdigest(),
          'licenseFile':license.name,'licenseSHA256':hashlib.sha256(license.read_bytes()).hexdigest(),
          'noticeFile':notice.name,'noticeSHA256':hashlib.sha256(notice.read_bytes()).hexdigest(),
          'authorizationBasis':'written_permission','reviewReference':'https://example.test/own-fixture',
          'reviewer':'Generated test reviewer','reviewedAt':NOW-100,'expiresAt':NOW+100,'localNoncommercialOnly':True}
    return tmp_path,item


def write_registry(folder,models):
    path=folder/'model-rights.json'
    path.write_text(json.dumps({'schema':build.SCHEMA,'models':models}))
    return path


def test_exact_review_license_notice_and_bundled_bytes_form_one_workflow(review):
    folder,item=review;write_registry(folder,[item])
    value=build.load_reviews(folder,now=NOW)
    assert build.verify_source(value['demucs-4',4],folder/'demucs-default-4.mlmodel')==item['sourceSHA256']
    assert build.check_bundled(folder,value)==1
    (folder/'demucs-default-4.mlmodel').write_bytes(b'Other model with the same catalog name')
    with pytest.raises(ValueError,match='bytes'):build.check_bundled(folder,value)


@pytest.mark.parametrize('key,value',[
    ('id','../demucs-4'),('stemCount',True),('stemCount',1),('sourceFormat','foreign'),
    ('sourceSHA256','F'*64),('localNoncommercialOnly',False),('localNoncommercialOnly',1),
    ('authorizationBasis','noncommercial_context'),('authorizationBasis',[]),('reviewer',''),
    ('reviewedAt',True),('reviewedAt',NOW+1),('expiresAt',NOW),('expiresAt',2**64),
    ('reviewReference','http://example.test/rights'),('reviewReference','https://user:fixture@example.test/rights'),
    ('licenseFile','../LICENSE-fixture.txt'),('noticeSHA256','0'*64)])
def test_incomplete_or_incompatible_review_cannot_authorize_download(review,key,value):
    folder,item=review;item[key]=value;write_registry(folder,[item])
    with pytest.raises((ValueError,OSError)):build.load_reviews(folder,now=NOW)


def test_duplicate_selection_unknown_fields_and_duplicate_json_are_refused(review):
    folder,item=review
    for rows in ([item,item],[{**item,'manual_override':True}]):
        write_registry(folder,rows)
        with pytest.raises(ValueError):build.load_reviews(folder,now=NOW)
    (folder/'model-rights.json').write_text('{"schema":"mta-ios-model-rights-1","models":[],"models":[]}')
    with pytest.raises(ValueError,match='Duplicate'):build.load_reviews(folder,now=NOW)


@pytest.mark.parametrize('target',['registry','license','model'])
def test_symlinked_build_input_is_never_rights_evidence(review,target):
    folder,item=review;registry=write_registry(folder,[item])
    path={'registry':registry,'license':folder/item['licenseFile'],'model':folder/'demucs-default-4.mlmodel'}[target]
    original=path.with_name('original-'+path.name);path.rename(original);path.symlink_to(original)
    with pytest.raises(ValueError):
        reviews=build.load_reviews(folder,now=NOW)
        build.check_bundled(folder,reviews)


def test_compiled_source_inventory_binds_filenames_bytes_and_empty_members(review):
    folder,item=review;(folder/'demucs-default-4.mlmodel').unlink()
    compiled=folder/'demucs-4.mlmodelc';compiled.mkdir()
    (compiled/'weights.bin').write_bytes(b'Own generated compiled bytes');(compiled/'empty.bin').write_bytes(b'')
    item['sourceFormat']='mlmodelc';item['sourceSHA256']=build.compiled_digest(compiled)
    write_registry(folder,[item]);reviews=build.load_reviews(folder,now=NOW)
    assert build.check_bundled(folder,reviews)==1
    (compiled/'weights.bin').rename(compiled/'renamed.bin')
    with pytest.raises(ValueError,match='bytes'):build.check_bundled(folder,reviews)


def test_unknown_compiled_member_and_hardlink_are_not_counted_as_a_valid_model(review):
    folder,item=review
    compiled=folder/'generated.mlmodelc';compiled.mkdir()
    (compiled/'weights.bin').hardlink_to(folder/'demucs-default-4.mlmodel')
    with pytest.raises(ValueError,match='Unsafe'):build.compiled_digest(compiled)
    (compiled/'weights.bin').unlink();(compiled/'foreign-link').symlink_to(folder/'demucs-default-4.mlmodel')
    with pytest.raises(ValueError,match='Unsafe'):build.compiled_digest(compiled)


def test_shipped_empty_registry_grants_no_model_and_no_download(capsys):
    folder=ROOT/'mobile/ios/MTAEditorMobile/Models'
    assert build.load_reviews(folder)=={}
    assert build.main(['--model-id','demucs-4','--source-format','mlmodel','--optional-model'])==0
    assert capsys.readouterr().out==''
    assert build.main(['--model-id','demucs-4'])==1


def test_actual_cli_refuses_bundling_unreviewed_bytes_and_preserves_them(tmp_path):
    source=tmp_path/'demucs-default-4.mlmodel';source.write_bytes(b'Own unreviewed bytes')
    write_registry(tmp_path,[])
    result=subprocess.run([sys.executable,str(ROOT/'scripts/check_ios_model_rights.py'),
        '--models-directory',str(tmp_path),'--check-bundled'],capture_output=True,text=True,timeout=10,check=False)
    assert result.returncode==1 and 'lacks an exact rights selection' in result.stderr
    assert source.read_bytes()==b'Own unreviewed bytes'


def test_actual_cli_returns_only_the_verified_fixture_fingerprint(review):
    folder,item=review;now=int(time.time())
    item.update({'reviewedAt':now-100,'expiresAt':now+3600});registry=write_registry(folder,[item])
    before=registry.read_bytes()
    result=subprocess.run([sys.executable,str(ROOT/'scripts/check_ios_model_rights.py'),
        '--models-directory',str(folder),'--model-id','demucs-4','--stem-count','4','--source-format','mlmodel',
        '--source',str(folder/'demucs-default-4.mlmodel')],capture_output=True,text=True,timeout=10,check=False)
    assert result.returncode==0 and result.stdout.strip()==item['sourceSHA256'],result.stderr
    assert registry.read_bytes()==before


def valid_native_report():
    return {'schema':'mta-ios-rights-sdk-tests-1','passed':32,'failed':0,'skipped':0,'actual_keychain_test':True,
            'real_neural_model_inference':False,'checks':[{'name':name,'status':'passed'} for name in sorted(native.EXPECTED_CHECKS)]}


@pytest.mark.parametrize('damage',['skip','failure','missing','duplicate','substituted','false-counter','fake-keychain'])
def test_native_acceptance_gate_rejects_incomplete_or_substituted_proof(damage):
    result=valid_native_report()
    if damage=='skip':result['skipped']=1
    elif damage=='failure':result['checks'][0]['status']='failed'
    elif damage=='missing':result['checks'].pop()
    elif damage=='duplicate':result['checks'][0]=copy.deepcopy(result['checks'][1])
    elif damage=='substituted':result['checks'][0]['name']='unrelated passing check'
    elif damage=='false-counter':result['passed']=True
    else:result['actual_keychain_test']=False
    with pytest.raises(ValueError):native.check_result(result)


def test_report_schema_validation_is_not_itself_native_acceptance():
    # Validating report structure alone never manufactures accepted:true.
    report=valid_native_report();native.check_result(report)
    assert 'accepted' not in report


def test_missing_apple_sdk_is_blocked_with_zero_fake_passes(tmp_path,monkeypatch):
    monkeypatch.setattr(native.sys,'platform','linux')
    assert native.main(['--output',str(tmp_path)])==2
    result=json.loads((tmp_path/'acceptance.json').read_text())
    assert result['accepted'] is False and result['status']=='blocked' and result['passed']==0 and result['skipped']==0
    assert result['native_sdk_tests_executed'] is False and result['ios_app_compiled'] is False


def test_missing_current_source_invalidates_an_older_accepted_report(tmp_path,monkeypatch):
    (tmp_path/'acceptance.json').write_text('{"accepted":true}')
    def missing(_):raise FileNotFoundError('changed current source')
    monkeypatch.setattr(native,'source_hashes',missing)
    assert native.main(['--output',str(tmp_path)])==1
    result=json.loads((tmp_path/'acceptance.json').read_text())
    assert result['accepted'] is False and result['status']=='failed' and result['source_sha256']=={}
    assert result['native_sdk_tests_executed'] is False


def test_sdk_driver_declares_exact_checked_cases_and_is_in_real_compile_workflow():
    driver=(ROOT/'tests/ios/LocalModelRightsAcceptance.swift').read_text()
    assert set(re.findall(r'try check\("([^"]+)"',driver))==native.EXPECTED_CHECKS
    workflow=(ROOT/'.github/workflows/ios-model-rights.yml').read_text()
    assert 'workflow_dispatch:' in workflow and 'default: false' in workflow
    assert 'run_ios_model_rights_acceptance.py --output ios-rights-ci' in workflow
    assert 'contents: read' in workflow and 'persist-credentials: false' in workflow


def test_native_actual_entry_binds_review_and_receipt_before_compile_load_and_predict():
    policy=(ROOT/'mobile/ios/MTAEditorMobile/LocalModelRights.swift').read_text()
    engine=(ROOT/'mobile/ios/MTAEditorMobile/LocalStemEngine.swift').read_text()
    controller=(ROOT/'mobile/ios/MTAEditorMobile/MobileWebViewController.swift').read_text()
    install=engine[engine.index('private func installReviewedModel'):engine.index('private func ticketFingerprint')]
    assert install.index('rights.beginInstallation')<install.index('MLModel.compileModel')
    inference=engine[engine.index('private func separateSync'):engine.index('private func stemLabels')]
    assert inference.index('rights.authorizeInstalled')<inference.index('MLModel(contentsOf:')
    assert 'try rights.recheck(admission)\n                let prediction = try model.prediction' in inference
    assert 'let prediction = try model.prediction(from: provider)\n                try rights.recheck(admission)' in inference
    download=controller[controller.index('private func downloadAndInstallCoreMLModel'):controller.index('private func showDemucsModelManager')]
    assert download.index('reviewedDownloadFingerprint')<download.index('URLSession.shared.downloadTask')
    assert 'kSecAttrSynchronizable as String: false' in policy and 'kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly' in policy
    assert 'LocalModelRights.swift in Sources' in (ROOT/'mobile/ios/MTAEditorMobile.xcodeproj/project.pbxproj').read_text()


def test_standard_ios_build_no_longer_downloads_a_blanket_approved_default():
    workflow=(ROOT/'.github/workflows/ci-cd.yml').read_text()
    segment=workflow[workflow.index('  mobile-ios:'):workflow.index('      - name: Validate Xcode project',workflow.index('  mobile-ios:'))]
    assert segment.index('--optional-model')<segment.index('if curl')
    assert '--source "$target"' in segment and '--check-bundled' in segment
