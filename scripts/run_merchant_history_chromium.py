"""Opt-in Chromium acceptance: exactly four real UI/API cases, zero skips."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

EXPECTED = {f'test_actual_admin_history_confirmation_readback_and_reload[{width}-{language}]'
            for width in (390,1280) for language in ('it','en')}


def validate_report(path):
    if Path(path).stat().st_size > 2*1024*1024:
        raise ValueError('Unexpectedly large Chromium acceptance report')
    root = ET.parse(path,forbid_dtd=True).getroot()
    if any(list(root.iter(tag)) for tag in ('failure','error','skipped')):
        raise ValueError('Chromium acceptance contains failed or skipped cases')
    cases = list(root.iter('testcase'))
    if len(cases) != 4 or {x.get('name') for x in cases} != EXPECTED:
        raise ValueError('Expected all four IT/EN desktop/mobile acceptance cases')
    for case in cases:
        if (case.get('classname') != 'tests.test_r210_paypal_merchant_history_browser'
                or any(case.find(tag) is not None for tag in ('failure','error','skipped'))):
            raise ValueError('Chromium acceptance requires four real passes and zero failures/errors/skips')
    return {'passed':4,'failed':0,'skipped':0,'scope':'actual_merchant_history_chromium_api_only',
            'release_candidate':False,'transition_authorized':False}


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('merchant-history-ci'))
    args=parser.parse_args(argv)
    project=Path(__file__).resolve().parents[1]
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    runtime={'python':sys.version,'commit':os.getenv('GITHUB_SHA','local-uncommitted'),
             'playwright':None,'source_sha256':{}}
    try:
        runtime['playwright']=importlib.metadata.version('playwright')
    except importlib.metadata.PackageNotFoundError:
        pass
    for name in ('app/paypal_merchant_history.py','app/resource_routes.py','app/static/regime_admin_panel.js',
                 'tests/test_r210_paypal_merchant_history_browser.py','scripts/run_merchant_history_chromium.py',
                 '.github/workflows/merchant-history-chromium.yml'):
        runtime['source_sha256'][name]=hashlib.sha256((project/name).read_bytes()).hexdigest()
    (output/'runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
    report=output/'pytest.xml'
    report.unlink(missing_ok=True)  # A stale passing file can never satisfy this run.
    env={**os.environ,'MTA_TEST_OFFLINE':'1','PYTHONPATH':str(project)}
    try:
        with (output/'pytest.log').open('w') as log:
            result=subprocess.run([sys.executable,'-m','pytest','--timeout=90','-q','-ra',
                'tests/test_r210_paypal_merchant_history_browser.py','--junitxml='+str(report)],
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
