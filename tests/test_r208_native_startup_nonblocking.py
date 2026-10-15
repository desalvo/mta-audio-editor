"""Regression: optional desktop ACE-Step never delays native HTTP readiness."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ace_autostart_runs_in_daemon_thread():
    text = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert 'name="mta-desktop-ace-autostart"' in text
    assert 'daemon=True' in text[text.index('def _launch_optional_ace_step'):text.index('def _launch_optional_ace_step') + 480]
    assert 'auto_start_server()' in text


def test_application_revision_preserved_but_package_iteration_bumped():
    assert (ROOT / "REVISION").read_text().strip() == "209"
    workflow = (ROOT / ".github/workflows/server-native-runtime-validation.yml").read_text()
    assert 'MTA_RPM_RELEASE="0.$(cat REVISION).1.early.b$(cat BUILD_INFO).r${GITHUB_RUN_ID}.a${GITHUB_RUN_ATTEMPT}"' in workflow
    assert 'MTA_SERVER_VERSION="$(cat VERSION)~early.$(cat REVISION)+pkg1"' in workflow
