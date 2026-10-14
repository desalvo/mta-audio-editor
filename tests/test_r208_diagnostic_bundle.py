import logging
import zipfile
import pytest
from app import diagnostic_bundle as diag


def test_disabled_and_redacted_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(diag, "BASE", tmp_path)
    monkeypatch.delenv("MTA_DIAGNOSTICS_ENABLED", raising=False)
    assert diag.enabled() is False
    with pytest.raises(PermissionError):
        diag.create({})
    assert diag.configure(True)
    diag.SafeEvents().emit(logging.LogRecord("mta.test", logging.ERROR, __file__, 7, "password=TOPSECRET", (), None))
    archive = diag.create({"token": "TOPSECRET", "message": "password=TOPSECRET"})
    assert diag.resolve(archive.name) == archive
    with zipfile.ZipFile(archive) as f:
        assert {"diagnostics.json", "events.jsonl"}.issubset(f.namelist())
        assert "TOPSECRET" not in f.read("diagnostics.json").decode()
        assert "TOPSECRET" not in f.read("events.jsonl").decode()
    with pytest.raises(FileNotFoundError):
        diag.resolve("../mta.env")
    assert not diag.configure(False)
    with pytest.raises(PermissionError):
        diag.create({})


def test_diagnostic_expiry(tmp_path, monkeypatch):
    monkeypatch.setattr(diag, "BASE", tmp_path)
    diag.configure(True)
    archive = diag.create({"status": "ready"})
    import os
    os.utime(archive, (1, 1))
    diag.clean()
    assert not archive.exists()
