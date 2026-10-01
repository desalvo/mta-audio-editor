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
    assert wizard.version_tuple("0.2.0-18.1") == (0, 2, 0, 18, 1)
    assert wizard.parse_node_selector("kubernetes.io/os=linux,workload=audio") == {
        "kubernetes.io/os": "linux",
        "workload": "audio",
    }


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
    ingress = (output / "ingress.yaml").read_text()
    assert "ingressClassName: haproxy" in ingress
    assert "kubernetes.io/ingress.class: haproxy" in ingress
    assert "haproxy-ingress.github.io/proxy-body-size" in ingress
    assert "mta.example.test" in ingress
    assert config.stat().st_mode & 0o777 == 0o600
