from pathlib import Path


def test_mta_import_uses_background_job_and_progress_ui():
    root = Path(__file__).resolve().parents[1]
    main = (root / "app/main.py").read_text(encoding="utf-8")
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    assert '@app.post("/api/import-jobs")' in main
    assert 'def _mta_import_worker(' in main
    assert '"kind": "mta-import"' in main
    assert "Upload MTA completato" in main
    assert "Import MTA completato" in main
    assert "uploadWithProgress('/api/import-jobs',fd,'Import MTA')" in js
    assert "pollMediaJob(job.id,'Import MTA'" in js
    assert "showMediaProgress('Import MTA'" in js
