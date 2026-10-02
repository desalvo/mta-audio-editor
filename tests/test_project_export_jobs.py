from pathlib import Path


def test_project_export_job_download_support_is_present():
    root = Path(__file__).resolve().parents[1]
    main = (root / "app" / "main.py").read_text(encoding="utf-8")
    assert "def _configured_export_worker(" in main
    assert "def start_configured_project_export_job(" in main
    assert '"download_url": f"/api/media-jobs/{job_id}/download"' in main
    assert 'snapshot["kind"] not in {"track-export", "project-export"}' in main
