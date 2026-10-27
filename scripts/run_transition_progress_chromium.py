"""Source-bound E5 acceptance: general lifecycle controls plus original cutover UI."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.run_admin_cutover_chromium import EXPECTED as ORIGINAL  # noqa: E402

AXE_SHA256='880970c081707360e64f34cea25ff91892f5bc95675b0776925b9709dd8a68bb'
MODULE='tests.test_r210_transition_progress_browser'
EXPECTED={('tests.test_r210_admin_cutover_browser',name) for name in ORIGINAL}
EXPECTED|={(MODULE,f'test_reserved_cancel_keyboard_confirmation_actor_audit[{w}-{lang}]') for w in (390,1280) for lang in ('it','en')}
EXPECTED|={(MODULE,f'test_unverified_and_legacy_commits_show_reason_without_unsafe_controls[{kind}-{lang}]') for kind in ('mirror','legacy','conflict','disabled') for lang in ('it','en')}
EXPECTED|={(MODULE,f'test_failed_progress_read_clears_actions_and_refresh_recovers[{lang}]') for lang in ('it','en')}
EXPECTED.add((MODULE,'test_progress_poll_follows_independent_cancellation_without_mutating'))
EXPECTED|={(MODULE,f'test_full_shipped_settings_progress_accessibility[{phase}-{w}-{lang}]') for phase in ('idle','committed') for w in (390,1280) for lang in ('it','en')}


def validate_report(path):
    if path.stat().st_size>3*1024*1024:raise ValueError('Oversized progress acceptance report')
    root=ET.parse(path,forbid_dtd=True).getroot();cases=list(root.iter('testcase'))
    if len(cases)!=len(EXPECTED) or {(c.get('classname'),c.get('name')) for c in cases}!=EXPECTED:
        raise ValueError('Missing,duplicate or unexpected lifecycle acceptance cases')
    if any(list(root.iter(tag)) for tag in ('failure','error','skipped')):
        raise ValueError('Progress acceptance requires zero failures/errors/skips')
    return {'accepted':True,'criterion':'E5','passed':len(EXPECTED),'failed':0,'skipped':0,
            'scope':'transition_progress_audit_and_forward_recovery_controls',
            'general_cutover_authorized':False,'release_candidate':False}


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=Path('transition-progress-ci'));args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    report=out/'pytest.xml';report.unlink(missing_ok=True)
    (out/'acceptance.json').unlink(missing_ok=True)
    (out/'runtime.json').unlink(missing_ok=True)
    try:
        axe=Path(os.environ.get('MTA_TEST_AXE_CORE',''))
        if not axe.is_file() or hashlib.sha256(axe.read_bytes()).hexdigest()!=AXE_SHA256:
            raise ValueError('Exact pinned axe-core4.10.3 required')
        names=['app/regime_transition_status.py','app/regime_admin_cutover.py','app/regime_local_readiness.py',
               'app/resource_routes.py','app/static/regime_cutover_panel.js','app/templates/admin.html',
               'app/regime_service_lease.py','app/regime_balance_continuity.py','app/regime_transition_journal.py',
               'app/auth.py','app/main.py','tests/test_r210_transition_progress.py',
               'tests/test_r210_transition_progress_browser.py','tests/test_r210_admin_cutover_browser.py',
               'scripts/run_transition_progress_chromium.py']
        runtime={'commit':os.getenv('GITHUB_SHA','local-uncommitted'),'python':sys.version,'axe_sha256':AXE_SHA256,
                 'source_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names}}
        (out/'runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
        with (out/'pytest.log').open('w') as log:
            run=subprocess.run([sys.executable,'-m','pytest','--timeout=90','-q',
                'tests/test_r210_admin_cutover_browser.py','tests/test_r210_transition_progress_browser.py',
                '--junitxml='+str(report)],cwd=root,env={**os.environ,'MTA_TEST_OFFLINE':'1','MTA_ALLOW_INSECURE_NO_AUTH':'false'},stdout=log,stderr=subprocess.STDOUT,timeout=600,check=False)
        if run.returncode:raise ValueError('Chromium run failed;inspect pytest.log')
        acceptance=validate_report(report)
    except (OSError,ValueError,ET.ParseError,DefusedXmlException,subprocess.SubprocessError) as exc:
        (out/'acceptance.json').write_text(json.dumps({'accepted':False,'reason':str(exc)},indent=2)+'\n')
        print(str(exc),file=sys.stderr);return 1
    (out/'acceptance.json').write_text(json.dumps(acceptance,indent=2)+'\n');print(json.dumps(acceptance));return 0


if __name__=='__main__':raise SystemExit(main())
