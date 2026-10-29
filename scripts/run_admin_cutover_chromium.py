"""Opt-in Chromium: exact original, drain or complete sensitive-workflow cases, zero skips."""
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
DRAIN_EXPECTED = {f'test_full_settings_original_drain_two_way_cutover_explicit_resume[{width}-{language}]'
                  for width in (390, 1280) for language in ('it', 'en')}
DRAIN_EXPECTED |= {f'{name}[{language}]' for name in (
    'test_lost_drain_response_reload_uses_original_server_identity_without_second_begin',
    'test_committed_crash_holds_service_until_original_forward_recovery',
    'test_unavailable_drain_read_disables_controls_until_explicit_refresh',
    'test_build_mismatch_requires_explicit_original_handoff') for language in ('it', 'en')}
OPERATOR_CASES = {('tests.test_r210_admin_cutover_browser', name) for name in EXPECTED}
OPERATOR_CASES |= {('tests.test_r210_cutover_service_drain_browser', name) for name in DRAIN_EXPECTED}
OPERATOR_CASES |= {('tests.test_r210_sensitive_operator_browser',
    f'test_complete_financial_review_blocks_unsafe_confirmation_and_keeps_all_families_readable[{scenario}-{family}-{width}-{language}]')
    for scenario, family in [('provider', 'provider_history'), ('legacy', 'original_subscription_basis'),
                            ('unknown-schema', 'schema_coverage'), ('worker', 'worker_claims'), ('ledger-unavailable', 'payment_ledger')]
    for width in (390, 1280) for language in ('it', 'en')}
OPERATOR_CASES |= {('tests.test_r210_sensitive_operator_browser',
    f'test_sensitive_review_requires_unchecked_acknowledgement_and_invalidates_after_new_drain[{width}-{language}]')
    for width in (390, 1280) for language in ('it', 'en')}
OPERATOR_CASES |= {('tests.test_r210_sensitive_operator_browser',
    f'test_entire_shipped_sensitive_controls_accessible_without_rule_exclusions[{phase}-{width}-{language}]')
    for phase in ('ready', 'blocked') for width in (390, 1280) for language in ('it', 'en')}
OPERATOR_CASES |= {('tests.test_r210_sensitive_operator_browser',
    f'test_failed_review_read_clears_prior_acknowledgement_until_explicit_retry[{language}]') for language in ('it', 'en')}
OPERATOR_CASES |= {('tests.test_r210_operator_drain_reconcile_browser',
    f'test_actual_financial_reconciliation_closes_original_checkout_under_drain_without_general_clearance[{width}-{language}]')
    for width in (390, 1280) for language in ('it', 'en')}


def validate_report(path, *, service_drain=False, operator_workflow=False):
    if service_drain and operator_workflow:
        raise ValueError('Select exactly one acceptance scope')
    if Path(path).stat().st_size > 2*1024*1024:
        raise ValueError('Unexpectedly large Chromium acceptance report')
    root = ET.parse(path,forbid_dtd=True).getroot()
    if any(list(root.iter(tag)) for tag in ('failure','error','skipped')):
        raise ValueError('Chromium acceptance contains failed or skipped cases')
    cases = list(root.iter('testcase'))
    expected = DRAIN_EXPECTED if service_drain else EXPECTED
    module = 'tests.test_r210_cutover_service_drain_browser' if service_drain else 'tests.test_r210_admin_cutover_browser'
    expected_cases = OPERATOR_CASES if operator_workflow else {(module, name) for name in expected}
    if len(cases) != len(expected_cases) or {(x.get('classname'), x.get('name')) for x in cases} != expected_cases:
        raise ValueError('Expected the exact complete selected cutover/recovery IT/EN desktop/mobile set')
    for case in cases:
        if ((case.get('classname'), case.get('name')) not in expected_cases
                or any(case.find(tag) is not None for tag in ('failure','error','skipped'))):
            raise ValueError('Chromium acceptance requires the exact selected passes and zero failures/errors/skips')
    return {'passed':len(expected_cases),'failed':0,'skipped':0,
            'scope':'actual_complete_sensitive_operator_workflow' if operator_workflow else
                    'actual_service_drain_settings_cutover' if service_drain else 'actual_local_authority_cutover_chromium_api_only',
            'release_candidate':False,'transition_authorized':False}


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('admin-cutover-ci'))
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--service-drain', action='store_true', help='Run only the twelve new integrated service-drain cases')
    scope.add_argument('--operator-workflow', action='store_true', help='Run all59 sensitive operator workflow cases, including financial review and axe')
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
    if args.service_drain or args.operator_workflow:
        for name in ('app/service_admission.py', 'app/service_drain_obligations.py', 'app/static/service_drain_panel.js',
                     'tests/test_r210_cutover_service_drain.py', 'tests/test_r210_cutover_service_drain_browser.py',
                     '.github/workflows/service-drain-cutover-chromium.yml'):
            runtime['source_sha256'][name]=hashlib.sha256((project/name).read_bytes()).hexdigest()
        for name in ('app/regime_operator_preflight.py', 'app/static/admin_accessibility.js'):
            runtime['source_sha256'][name]=hashlib.sha256((project/name).read_bytes()).hexdigest()
    if args.operator_workflow:
        for name in ('tests/test_r210_operator_preflight.py', 'tests/test_r210_sensitive_operator_browser.py',
                     'tests/test_r210_operator_drain_reconcile_browser.py', '.github/workflows/sensitive-operator-chromium.yml'):
            runtime['source_sha256'][name]=hashlib.sha256((project/name).read_bytes()).hexdigest()
    (output/'runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
    report=output/'pytest.xml'
    report.unlink(missing_ok=True)  # A stale passing file can never satisfy this run.
    env={**os.environ,'MTA_TEST_OFFLINE':'1','PYTHONPATH':str(project),'MTA_ALLOW_INSECURE_NO_AUTH':'false'}
    selected = ['tests/test_r210_cutover_service_drain_browser.py'] if args.service_drain else ['tests/test_r210_admin_cutover_browser.py']
    if args.operator_workflow:
        selected = ['tests/test_r210_admin_cutover_browser.py', 'tests/test_r210_cutover_service_drain_browser.py',
                    'tests/test_r210_sensitive_operator_browser.py', 'tests/test_r210_operator_drain_reconcile_browser.py']
    try:
        with (output/'pytest.log').open('w') as log:
            result=subprocess.run([sys.executable,'-m','pytest','--timeout=90','-q','-ra',
                *selected,'--junitxml='+str(report)],
                cwd=project,env=env,stdout=log,stderr=subprocess.STDOUT,check=False,timeout=600)
        if result.returncode:
            raise ValueError('Pytest did not succeed; inspect pytest.log and pytest.xml')
        acceptance=validate_report(report, service_drain=args.service_drain, operator_workflow=args.operator_workflow)
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
