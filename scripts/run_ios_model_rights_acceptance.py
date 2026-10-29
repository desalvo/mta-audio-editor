"""Opt-in Apple SDK acceptance of the shipped rights guard and unsigned iOS build.

No neural weights,signing credentials,publication or server/provider actions.
Missing Apple prerequisites produce blocked/accepted:false,never a passing skip.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import shutil
import subprocess
import sys

SOURCES=('mobile/ios/MTAEditorMobile/LocalModelRights.swift',
         'mobile/ios/MTAEditorMobile/LocalStemEngine.swift',
         'mobile/ios/MTAEditorMobile/MobileWebViewController.swift',
         'mobile/ios/MTAEditorMobile/AppDelegate.swift',
         'mobile/ios/MTAEditorMobile/NativeUpdateManager.swift',
         'mobile/ios/MTAEditorMobile.xcodeproj/project.pbxproj',
         'mobile/ios/MTAEditorMobile/Models/model-rights.json',
         'tests/ios/LocalModelRightsAcceptance.swift',
         'scripts/check_ios_model_rights.py',
         'scripts/run_ios_model_rights_acceptance.py',
         '.github/workflows/ci-cd.yml',
         '.github/workflows/ios-model-rights.yml')
EXPECTED_CHECKS=frozenset('''empty registry denies
unknown checkpoint denies
path selector denies
wrong stem count denies
unknown source format denies
expired permission denies
future review denies
commercial grant denies
NC label is not authorization
credentialed reference denies
missing license denies
changed notice denies
actual source bytes required
server fingerprint is not authority
source link denies
compiled root link denies
compiled member link denies
compiled bytes tampering denies
compiled extra member denies
missing secure receipt denies
disk receipt cannot grant rights
foreign receipt identity denies
loaded review revocation denies
loaded review replacement denies
loaded grant expiry denies
valid offline receipt survives object restart
compiled member rename denies
receipt failure restores original installation
publish failure is rolled back
missing source denies
real isolated keychain roundtrip
reviewed compiled source inventory accepted'''.splitlines())


def source_hashes(root):
    paths={root/name for name in SOURCES}
    paths.update(p for p in (root/'mobile/ios/MTAEditorMobile/Models').rglob('*') if p.is_file())
    result={}
    for path in sorted(paths):
        if path.is_symlink():raise ValueError('Symbolic native source or review evidence')
        with path.open('rb') as stream:result[path.relative_to(root).as_posix()]=hashlib.file_digest(stream,'sha256').hexdigest()
    return result


def check_result(result):
    if (not isinstance(result,dict) or result.get('schema')!='mta-ios-rights-sdk-tests-1'
            or type(result.get('passed')) is not int or result['passed']!=32
            or type(result.get('failed')) is not int or result['failed']!=0
            or type(result.get('skipped')) is not int or result['skipped']!=0
            or result.get('actual_keychain_test') is not True or result.get('real_neural_model_inference') is not False
            or not isinstance(result.get('checks'),list) or len(result['checks'])!=32):
        raise ValueError('Incomplete native rights acceptance;32 actual checks with zero skips are required')
    names=[]
    for case in result['checks']:
        if (not isinstance(case,dict) or set(case)!={'name','status'} or not isinstance(case['name'],str)
                or not case['name'] or case['status']!='passed'):
            raise ValueError('Invalid or failed native rights check')
        names.append(case['name'])
    if len(set(names))!=32 or set(names)!=EXPECTED_CHECKS:raise ValueError('Missing,duplicate or substituted native rights checks')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('ios-rights-ci'))
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1];output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    report={'schema':'mta-ios-rights-acceptance-1','accepted':False,'status':'blocked','source_sha256':{},
            'passed':0,'skipped':0,'native_sdk_tests_executed':False,'ios_app_compiled':False,
            'real_neural_model_inference':False,'installed_OS_acceptance':False,'full_F4_accepted':False,
            'release_candidate':False,'platform':platform.platform()}
    path=output/'acceptance.json'
    def save():path.write_text(json.dumps(report,indent=2)+'\n')
    # Invalidate an earlier outcome even if a current input is missing.
    save()
    try:
        hashes=source_hashes(root);report['source_sha256']=hashes
    except (OSError,ValueError) as exc:
        report.update({'status':'failed','reason':str(exc)});save();return 1
    if sys.platform!='darwin' or not shutil.which('xcrun') or not shutil.which('xcodebuild'):
        report['reason']='Apple Swift/CryptoKit/Security SDK and Xcode iOS SDK required;run the opt-in workflow on macOS.'
        save();print(report['reason'],file=sys.stderr);return 2
    def run(name,command,timeout=600):
        with (output/(name+'.log')).open('w') as log:
            result=subprocess.run(command,cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=timeout,check=False)
        if result.returncode:raise RuntimeError(name+' failed;inspect the retained log')
    try:
        run('review-inputs',[sys.executable,str(root/'scripts/check_ios_model_rights.py'),'--check-bundled'])
        xcrun=shutil.which('xcrun');xcode=shutil.which('xcodebuild')
        run('swift-version',[xcrun,'swiftc','--version'])
        run('xcode-version',[xcode,'-version'])
        executable=output/'rights-sdk-tests'
        run('compile-policy',[xcrun,'swiftc','-swift-version','5','-parse-as-library',
            str(root/SOURCES[0]),str(root/'tests/ios/LocalModelRightsAcceptance.swift'),'-o',str(executable)])
        run('native-policy-tests',[str(executable),str(output/'native-checks.json')])
        sdk=json.loads((output/'native-checks.json').read_text());check_result(sdk)
        report['native_sdk_tests_executed']=True;report['passed']=32
        run('ios-build',[xcode,'-project',str(root/'mobile/ios/MTAEditorMobile.xcodeproj'),'-scheme','MTAEditorMobile',
            '-configuration','Release','-sdk','iphoneos','-destination','generic/platform=iOS',
            '-derivedDataPath',str(output/'build'),'CODE_SIGNING_ALLOWED=NO','CODE_SIGNING_REQUIRED=NO','build'],timeout=900)
        if hashes!=source_hashes(root):raise ValueError('Native source changed during acceptance')
        report.update({'accepted':True,'status':'passed','ios_app_compiled':True,
                       'scope':'32 real Swift/CryptoKit/Security checks including an isolated Keychain service,and unsigned compilation of the actual iOS app. No neural/physical-OS or full-F4 acceptance.'})
        save();return 0
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
        report.update({'accepted':False,'status':'failed','reason':str(exc)})
        save();print(str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
