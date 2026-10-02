from pathlib import Path


def test_stem_progress_keeps_active_project_and_cannot_be_replaced():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")

    assert "activeStemProjectId" in js
    assert "resta nel progetto corrente fino al completamento" in js
    assert "barra di progresso rimane visibile fino al completamento" in js
    assert "showUtilityModal(title,html,stemProgress=false)" in js
    assert "showStemProgress(job)" in js
    assert "showUtilityModal('Separazione strumenti'" in js
    assert "`,true);" in js

    # The active project is restored if anything has changed current while polling.
    assert "if(!current||current.id!==job.project_id)" in js
    assert "current=await api(`/api/projects/${job.project_id}`)" in js

    # Completion refreshes project contents and redraws 100% progress before unlock.
    completed = js.index("if(job.status==='completed')")
    unlock = js.index("activeStemJob=null;", completed)
    redraw = js.index("showStemProgress(job);", completed)
    assert redraw < unlock
    assert "activeStemProjectId=null" in js[completed:unlock + 200]


def test_project_navigation_and_delete_are_blocked_during_active_stem_job():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")

    assert "if(activeStemJob&&activeStemProjectId&&id!==activeStemProjectId)" in js
    assert "if(activeStemJob&&activeStemProjectId===id)" in js
    assert "Attendi il completamento della separazione prima di creare un altro progetto" in js
