"""Regression gates for the observed HAProxy/Arranger outage and unique RPM builds."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_haproxy_legacy_backend_example_is_selectorless_and_has_no_real_ip():
    source = (ROOT / 'deploy/remote-ai/kubernetes/mta-haproxy-external-native-example.yaml').read_text()
    assert 'kind: Service' in source
    assert 'type: ClusterIP' in source
    assert 'kind: Endpoints' in source
    assert 'BACKEND_PRIVATE_IP' in source
    assert '192.168.1.144' not in source
    assert 'externalName:' not in source
    assert 'kind: EndpointSlice' not in source
    assert 'kubernetes.io/ingress.class: "haproxy"' in source
    assert 'ingressClassName: haproxy' in source
    assert '# secretName: mta-tls' in source
    assert '# kind: Secret' in source


def test_arranger_retries_transient_status_with_elapsed_clock():
    js = (ROOT / 'app/static/app.js').read_text()
    section = js[js.index('let aiArrangerWatchTimer=null;'):js.index('async function generateAndAddAiRemix()')]
    assert 'Connection interrupted; retrying AI job status automatically:' in section
    assert 'setTimeout(poll,delay)' in section
    assert 'setInterval(aiArrangerRenderElapsed,1000)' in section
    assert 'Math.min(15000,' in section
    assert 'aiArrangerWatchEpoch' in section
    assert "job.gpu_seconds==null?'N/A'" in section


def test_verified_cpu_gpu_usage_reaches_queue_state():
    source = (ROOT / 'app/ai_metering_bridge.py').read_text()
    assert "normalized.get('cpu_seconds')" in source
    assert "normalized.get('gpu_seconds')" in source
    assert 'gpu_seconds=COALESCE(?,gpu_seconds)' in source
    assert "if any(k.startswith('gpu_') for k in normalized) and source != 'gpu-agent'" in source


def test_early_rpm_naming_and_cleanup_are_run_unique_and_safe():
    build = (ROOT / '.github/workflows/server-native-runtime-validation.yml').read_text()
    publish = (ROOT / '.github/workflows/server-pages-publish.yml').read_text()
    assert build.count('.b$(cat BUILD_INFO).r${GITHUB_RUN_ID}.a${GITHUB_RUN_ATTEMPT}') == 2
    assert '.b${expected_build}.r${RUN_ID}.a${source_attempt}' in publish
    assert '--limit 20' in publish
    assert 'Remove unreferenced RPM Release assets after Pages verification' in publish
    assert 'Public Pages metadata is stale' in publish
    assert publish.index('Verify public GitHub Pages RPM indexes') < publish.index('Remove unreferenced RPM Release assets')
