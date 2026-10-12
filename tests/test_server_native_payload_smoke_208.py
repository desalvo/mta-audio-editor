"""Guard the extracted native package offline test against incomplete payloads."""
import importlib.util
from pathlib import Path
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/server_packages/smoke_offline_payload.py'
spec = importlib.util.spec_from_file_location('mta_offline_smoke', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_absent_payload_rejected(tmp_path):
    with pytest.raises(ValueError, match='entrypoints'):
        mod.smoke(tmp_path)


def test_missing_wheels_rejected(tmp_path):
    app = tmp_path / 'usr/lib/mta-audio-editor-server'
    app.mkdir(parents=True)
    (app / 'requirements.txt').write_text('')
    (app / 'app').mkdir()
    (app / 'app/main.py').write_text('')
    with pytest.raises(ValueError, match='offline wheels'):
        mod.smoke(tmp_path)
