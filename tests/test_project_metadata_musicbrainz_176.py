from pathlib import Path


def test_musicbrainz_falls_back_from_combined_artist_to_title(monkeypatch):
    import app.rights_registry as rr

    calls = []

    def fake_read_json(_url, params):
        calls.append(params["query"])
        if " AND artist:" in params["query"]:
            return {"recordings": []}
        return {
            "recordings": [
                {
                    "id": "dwsm-1",
                    "title": "Die With a Smile",
                    "score": 100,
                    "artist-credit": [
                        {"name": "Lady Gaga", "artist": {"name": "Lady Gaga"}},
                        {"name": "Bruno Mars", "artist": {"name": "Bruno Mars"}},
                    ],
                }
            ]
        }

    monkeypatch.setattr(rr, "_read_json", fake_read_json)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    results = rr.search_musicbrainz_metadata(
        title="Die with a smile",
        artist="Lady Gaga & Bruno Mars",
        limit=15,
    )
    assert results
    assert results[0]["title"] == "Die With a Smile"
    assert results[0]["performers"] == ["Lady Gaga", "Bruno Mars"]
    assert len(calls) == 2
    assert " AND artist:" in calls[0]
    assert calls[1] == 'recording:"Die with a smile"'


def test_musicbrainz_general_query_is_last_fallback(monkeypatch):
    import app.rights_registry as rr

    calls = []

    def fake_read_json(_url, params):
        calls.append(params["query"])
        if len(calls) < 2:
            return {"recordings": []}
        return {"recordings": [{"id": "x", "title": "A Song", "score": 80, "artist-credit": []}]}

    monkeypatch.setattr(rr, "_read_json", fake_read_json)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    results = rr.search_musicbrainz_metadata(title="A Song", limit=5)
    assert results[0]["mbid"] == "x"
    assert calls == ['recording:"A Song"', "A Song"]


def test_project_metadata_editor_is_single_modal_without_prompt_chain():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    start = js.index("function editProjectMeta()")
    end = js.index("let metadataSearchCandidates", start)
    block = js[start:end]
    assert "showUtilityModal('Modifica metadata progetto'" in block
    assert "saveProjectMetaEditor" in block
    assert "prompt(" not in block
    assert "projectMetaTitle" in block
    assert "projectMetaAuthors" in block
    assert "projectMetaBpm" in block
    assert "projectMetaTimeSignature" in block
