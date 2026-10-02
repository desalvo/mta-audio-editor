import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIZARD = ROOT / "scripts" / "k8s-wizard.py"


def load_wizard():
    spec = importlib.util.spec_from_file_location("mta_k8s_wizard", WIZARD)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_version_and_node_selector_helpers():
    wizard = load_wizard()
    assert wizard.version_tuple("0.2.0-63.1") == (0, 2, 0, 63, 1)
    assert wizard.parse_node_selector("kubernetes.io/os=linux,workload=audio") == {
        "kubernetes.io/os": "linux",
        "workload": "audio",
    }
    assert wizard.parse_bool("yes") is True
    assert wizard.parse_bool("no") is False


def test_wizard_generates_custom_kustomize_manifests(tmp_path):
    output = tmp_path / "generated"
    config = tmp_path / "config.json"
    subprocess.run(
        [
            sys.executable,
            str(WIZARD),
            "--no-self-update",
            "--non-interactive",
            "--admin-username",
            "operator",
            "--admin-password",
            "unit-test-password",
            "--admin-email",
            "operator@example.test",
            "--storage-class",
            "fast-storage",
            "--namespace",
            "audio-tools",
            "--node-selector",
            "workload=audio,kubernetes.io/os=linux",
            "--ingress",
            "haproxy",
            "--ingress-host",
            "mta.example.test",
            "--tls-termination",
            "--tls-secret",
            "mta-example-tls",
            "--max-upload-mb",
            "175",
            "--image-pull-policy",
            "Always",
            "--output-dir",
            str(output),
            "--config",
            str(config),
        ],
        check=True,
    )
    assert (output / "namespace.yaml").exists()
    assert (output / "pvc.yaml").exists()
    assert (output / "deployment.yaml").exists()
    assert (output / "kustomization.yaml").exists()
    assert "storageClassName: \"fast-storage\"" in (output / "pvc.yaml").read_text()
    deployment = (output / "deployment.yaml").read_text()
    assert "namespace: audio-tools" in deployment
    assert "workload: \"audio\"" in deployment
    assert 'value: "175"' in deployment
    assert "imagePullPolicy: Always" in deployment
    assert "fsGroup: 10001" in deployment
    assert "fsGroupChangePolicy: OnRootMismatch" in deployment
    assert "startupProbe:" in deployment
    assert "optional: true" in deployment
    ingress = (output / "ingress.yaml").read_text()
    assert "ingressClassName: haproxy" in ingress
    assert "kubernetes.io/ingress.class: haproxy" in ingress
    assert 'haproxy-ingress.github.io/proxy-body-size: "175m"' in ingress
    assert 'haproxy-ingress.github.io/ssl-redirect: "true"' in ingress
    assert "tls:" in ingress
    assert "- mta.example.test" in ingress
    assert "secretName: mta-example-tls" in ingress
    assert "mta.example.test" in ingress
    assert config.stat().st_mode & 0o777 == 0o600


def test_haproxy_tls_without_specific_secret(tmp_path):
    wizard = load_wizard()
    output = tmp_path / "generated-default-tls"
    values = {
        "admin_username": "operator",
        "admin_password": "unit-test-password",
        "admin_email": "operator@example.test",
        "storage_class": "",
        "namespace": "audio-tools",
        "node_selector": "",
        "ingress": "haproxy",
        "ingress_host": "mta-default.example.test",
        "tls_termination": True,
        "tls_secret": "",
        "image": "desalvo/mta-audio-editor:0.2.0-63",
    }
    wizard.write_manifests(output, values)
    ingress = (output / "ingress.yaml").read_text()
    assert 'haproxy-ingress.github.io/ssl-redirect: "true"' in ingress
    assert 'haproxy-ingress.github.io/proxy-body-size: "150m"' in ingress
    assert "\n  tls:\n" in ingress
    assert "- mta-default.example.test" in ingress
    assert "secretName:" not in ingress


def test_haproxy_without_tls_has_no_tls_section_or_ssl_redirect(tmp_path):
    wizard = load_wizard()
    output = tmp_path / "generated-no-tls"
    values = {
        "admin_username": "operator",
        "admin_password": "unit-test-password",
        "admin_email": "operator@example.test",
        "storage_class": "",
        "namespace": "audio-tools",
        "node_selector": "",
        "ingress": "haproxy",
        "ingress_host": "mta-http.example.test",
        "tls_termination": False,
        "tls_secret": "",
        "image": "desalvo/mta-audio-editor:0.2.0-63",
    }
    wizard.write_manifests(output, values)
    ingress = (output / "ingress.yaml").read_text()
    assert "haproxy-ingress.github.io/ssl-redirect" not in ingress
    assert "\n  tls:\n" not in ingress
