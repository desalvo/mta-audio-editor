"""Opt-in Chromium acceptance: exactly nine real cutover UI/API cases, zero skips."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

EXPECTED = {f'test_actual_cutover_roundtrip_wallet_periods_keyboard_and_audit[{width}-{language}]'
            for width in (390,1280) for language in ('it','en')}
EXPECTED |= {f'{name}[{language}]' for name in (
    'test_actual_committed_recovery_requires_confirmation_and_preserves_wallet',
    'test_lost_response_reload_retries_only_original_identity_without_second_cutover')
    for language in ('it','en')}
EXPECTED.add('test_unknown_financial_history_cannot_enable_confirmation')


def validate_report(path):
    if Path(path).stat().st_size > 2*1024*1024:
        raise ValueError('Unexpectedly large Chromium acceptance report')
    root = ET.parse(path,forbid_dtd=True).getroot()
    if any(list(root.iter(tag)) for tag in ('failure','error','skipped')):
        raise ValueError('Chromium acceptance contains failed or skipped cases')
    cases = list(root.iter('testcase'))
    if len(cases) != 9 or {x.get('name') for x in cases} != EXPECTED:
        raise ValueError('Expected all nine cutover/recovery IT/EN desktop/mobile cases')
    for case in cases:
        if (case.get('classname') != 'tests.test_r210_admin_cutover_browser'
                or any(case.find(tag) is not None for tag in ('failure','error','skipped'))):
            raise ValueError('Chromium acceptance requires nine real passes and zero failures/errors/skips')
    return {'passed':9,'failed':0,'skipped':0,'scope':'actual_local_authority_cutover_chromium_api_only',
            'release_candidate':False,'transition_authorized':False}


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('admin-cutover-ci'))
    args=parser.parse_args(argv)
    project=Path(__file__).resolve().parents[1]
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    runtime={'python':sys.version,'commit':os.getenv('GITHUB_SHA','local-uncommitted'),
             'playwright':None,'source_sha256':{}}
    try:
        runtime['playwright']=importlib.metadata.version('playwright')
    except importlib.metadata.PackageNotFoundError:
        pass
    for name in ('app/regime_service_lease.py','app/regime_local_readiness.py','app/regime_admin_cutover.py',
                 'app/regime_balance_continuity.py','app/resource_routes.py','app/static/regime_cutover_panel.js',
                 'app/auth.py','app/ai_arranger_runtime.py','app/ai_billing_outbox.py','app/ai_publish_outbox.py',
                 'app/main.py','app/account_lifecycle.py','app/regime_transition_journal.py',
                 'app/templates/admin.html','tests/test_r210_admin_cutover_browser.py',
                 'tests/test_r210_admin_cutover_e2e.py','scripts/run_admin_cutover_chromium.py',
                 '.github/workflows/admin-cutover-chromium.yml'):
        runtime['source_sha256'][name]=hashlib.sha256((project/name).read_bytes()).hexdigest()
    (output/'runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
    report=output/'pytest.xml'
    report.unlink(missing_ok=True)  # A stale passing file can never satisfy this run.
    env={**os.environ,'MTA_TEST_OFFLINE':'1','PYTHONPATH':str(project),'MTA_ALLOW_INSECURE_NO_AUTH':'false'}
    try:
        with (output/'pytest.log').open('w') as log:
            result=subprocess.run([sys.executable,'-m','pytest','--timeout=90','-q','-ra',
                'tests/test_r210_admin_cutover_browser.py','--junitxml='+str(report)],
                cwd=project,env=env,stdout=log,stderr=subprocess.STDOUT,check=False,timeout=600)
        if result.returncode:
            raise ValueError('Pytest did not succeed; inspect pytest.log and pytest.xml')
        acceptance=validate_report(report)
    except (OSError,ValueError,ET.ParseError,DefusedXmlException,subprocess.TimeoutExpired) as exc:
        (output/'acceptance.json').write_text(json.dumps({'accepted':False,'reason':str(exc)},indent=2)+'\n')
        # Keep the complete artifact and expose a bounded failure tail in the
        # job log so diagnosis does not depend on downloading the artifact.
        try:
            with (output/'pytest.log').open('rb') as log:
                log.seek(0,2)
                log.seek(max(0,log.tell()-20_000))
                print(log.read().decode('utf-8',errors='replace'),file=sys.stderr)
        except OSError:
            pass
        print('Chromium acceptance blocked: '+str(exc),file=sys.stderr)
        return 1
    (output/'acceptance.json').write_text(json.dumps({'accepted':True,**acceptance},indent=2)+'\n')
    print(json.dumps(acceptance))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
