from pathlib import Path


def test_chordpro_export_aligns_chords_and_metadata():
    from app.models import Chord, LyricLine, LyricWord, RightsRecord
    from app.music_text import build_chordpro

    lyrics = [LyricLine(
        time_ms=1000, end_ms=3000, text="Hello world",
        words=[LyricWord(start_ms=1000, end_ms=1500, text="Hello"), LyricWord(start_ms=1800, end_ms=2300, text="world")],
    )]
    chords = [Chord(time_ms=950, chord="C"), Chord(time_ms=1850, chord="G")]
    record = RightsRecord(uid="SIAE:T-1", society="SIAE", title="My Song", original_title="MY SONG", authors=["Author One"], identifiers={"ISWC": "T-1"})
    body = build_chordpro(title="My Song", artist="Singer", key="C", bpm=120, lyrics=lyrics, chords=chords, authors=["Author One"], rights_records=[record])
    assert "{title: My Song}" in body
    assert "{artist: Singer}" in body
    assert "{composer: Author One}" in body
    assert "{key: C}" in body
    assert "{tempo: 120}" in body
    assert "[C] Hello [G] world" in body
    assert "ISWC: T-1" in body


def test_project_rights_metadata_is_persistent_and_mta_attachment_contains_it(tmp_path, monkeypatch):
    import app.codec as codec
    import app.storage as storage
    from app.models import RightsRecord

    monkeypatch.setattr(storage, "ROOT", tmp_path)
    monkeypatch.setattr(codec, "pdir", storage.pdir)
    project = storage.create_project("Song", "MTA8")
    project.original_title = "Original Song"
    project.authors = ["Writer A", "Writer B"]
    project.rights_records = [RightsRecord(uid="SOUNDREEF:42", society="SOUNDREEF", title="Song", original_title="Original Song", authors=["Writer A"], identifiers={"WORK_ID": "42"})]
    project.rights_societies = ["SOUNDREEF"]
    storage.save_project(project)
    loaded = storage.load_project(project.id)
    assert loaded.original_title == "Original Song"
    assert loaded.authors == ["Writer A", "Writer B"]
    assert loaded.rights_records[0].society == "SOUNDREEF"
    assert loaded.rights_societies == ["SOUNDREEF"]
    files = codec._synchronized_text_attachments(loaded)
    sync = next(x for x in files if x.name == "mta-synchronized-text.json")
    text = sync.read_text(encoding="utf-8")
    assert '"rights_records"' in text
    assert '"WORK_ID": "42"' in text
    assert '"rights_societies"' in text and '"SOUNDREEF"' in text


def test_pdf_accepts_rights_footer(tmp_path):
    from app.models import Chord, LyricLine, RightsRecord
    from app.music_text import build_lyrics_pdf

    out = tmp_path / "lyrics-rights.pdf"
    build_lyrics_pdf(
        out,
        title="Song",
        artist="Singer",
        key="D",
        bpm=128,
        lyrics=[LyricLine(time_ms=0, text="First line")],
        chords=[Chord(time_ms=0, chord="D")],
        rights_records=[RightsRecord(uid="SIAE:X", society="SIAE", title="Song", original_title="SONG", authors=["Writer"], performers=["Singer"], identifiers={"ISWC": "T-123"})],
    )
    assert out.read_bytes().startswith(b"%PDF-")
    assert out.stat().st_size > 1000


def test_rights_provider_catalog_defaults_and_portal_fallback(monkeypatch):
    from app.rights_registry import provider_catalog, search_provider

    monkeypatch.delenv("MTA_RIGHTS_SIAE_SEARCH_URL", raising=False)
    monkeypatch.delenv("MTA_RIGHTS_SOUNDREEF_SEARCH_URL", raising=False)
    catalog = provider_catalog()
    assert {x["id"] for x in catalog if x["active_by_default"]} == {"SIAE", "SOUNDREEF"}
    siae = search_provider("SIAE", title="Example")
    assert siae["mode"] == "portal"
    assert siae["results"] == []
    assert siae["portal_url"].startswith("https://")


def test_ui_exposes_chordpro_and_rights_search():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    main = (root / "app/main.py").read_text(encoding="utf-8")
    assert "ChordPro" in js
    assert "Cerca repertorio autori" in js
    assert "SIAE" in js and "SOUNDREEF" in js
    assert "/lyrics.chordpro" in main
    assert "/rights-search" in main
    assert "/rights-records" in main


def test_rights_registry_normalisation_and_configured_search(monkeypatch):
    import app.rights_registry as rr

    assert rr._validated_https("https://example.test/api") == "https://example.test/api"
    for bad in ("http://example.test", "file:///tmp/x", "not-a-url"):
        try:
            rr._validated_https(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe URL accepted")
    assert rr._text_list(None) == []
    assert rr._text_list("A; B,C") == ["A", "B", "C"]
    assert rr._text_list(["A", {"name": "B"}, {"full_name": "C"}, {"display_name": "D"}, 3]) == ["A", "B", "C", "D"]
    assert rr._text_list(42) == []
    ids = rr._identifiers({"identifiers": {"iswc": "T-X", "empty": ""}, "ipi": "123", "work_id": 55})
    assert ids == {"ISWC": "T-X", "IPI": "123", "WORK_ID": "55"}
    provider = rr.PROVIDERS["SIAE"]
    rows = rr._normalise_rows(provider, {"data": {"items": [
        {"work_title": "Song", "originalTitle": "SONG", "writers": [{"name": "Writer"}], "artists": "Singer", "editors": ["Publisher"], "iswc": "T-1", "url": "https://example.test/work"},
        {"name": "By Id", "identifiers": {"work_id": "W2"}},
        "skip",
        {},
    ]}})
    assert len(rows) == 2
    assert rows[0].authors == ["Writer"] and rows[0].performers == ["Singer"]
    assert rows[0].identifiers["ISWC"] == "T-1"
    assert rr._normalise_rows(provider, "bad") == []

    monkeypatch.setenv("MTA_RIGHTS_SIAE_SEARCH_URL", "https://example.test/search")
    monkeypatch.setattr(rr, "_read_json", lambda url, params: {"results": [{"title": params["title"], "authors": ["A"], "id": "9"}]})
    result = rr.search_provider("siae", title="Configured", original_title="", artist="Singer", authors=["A"])
    assert result["mode"] == "api"
    assert result["results"][0]["title"] == "Configured"
    assert result["results"][0]["identifiers"]["ID"] == "9"
    try:
        rr.search_provider("unknown", title="X")
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported provider accepted")


def test_rights_api_functions(monkeypatch):
    import app.main as main
    from app.models import Project

    project = Project(id="p", title="Song", artist="Singer", authors=["Writer"])
    saved = []
    monkeypatch.setattr(main, "_project_for_actor", lambda request, pid: project)
    monkeypatch.setattr(main, "save_project", lambda p: saved.append(p.model_copy(deep=True)))
    monkeypatch.setattr(main, "require_user", lambda request: {"id": 1})
    monkeypatch.setattr(main, "rights_provider_catalog", lambda: [{"id": "SIAE"}])
    assert main.api_rights_providers(object())["default_active"] == ["SIAE", "SOUNDREEF"]

    def fake_search(society, **kwargs):
        if society == "BAD":
            raise ValueError("bad provider")
        if society == "BOOM":
            raise RuntimeError("offline")
        return {"provider": society, "mode": "api", "portal_url": "https://example.test", "message": "", "results": [{"uid": society+":1", "society": society, "title": kwargs["title"], "original_title": "", "authors": kwargs["authors"], "performers": [], "publishers": [], "identifiers": {}, "source_url": ""}]}
    monkeypatch.setattr(main, "search_rights_provider", fake_search)
    data = main.api_project_rights_search("p", object(), {"societies": ["siae", "bad", "boom"], "authors": "A; B"})
    assert data["query"]["title"] == "Song"
    assert data["query"]["authors"] == ["A", "B"]
    assert len(data["providers"]) == 3 and len(data["results"]) == 1

    record = {"uid": "SIAE:1", "society": "SIAE", "title": "Song", "original_title": "SONG", "authors": ["Writer"], "performers": [], "publishers": [], "identifiers": {"ISWC": "T-1"}, "source_url": ""}
    out = main.api_project_rights_records("p", object(), {"records": [record], "societies": ["soundreef"]})
    assert out["ok"] and project.rights_records[0].identifiers["ISWC"] == "T-1" and saved
    assert project.rights_societies == ["SOUNDREEF"] and out["rights_societies"] == ["SOUNDREEF"]

    from fastapi import HTTPException
    for body in ({"records": [{}] * 33}, {"records": [{"uid": ""}]}):
        try:
            main.api_project_rights_records("p", object(), body)
        except HTTPException:
            pass
        else:
            raise AssertionError("invalid rights records accepted")

    empty = Project(id="empty", title="")
    monkeypatch.setattr(main, "_project_for_actor", lambda request, pid: empty)
    try:
        main.api_project_rights_search("empty", object(), {"societies": ["SIAE"]})
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("empty search accepted")


def test_multi_provider_rights_export_contains_every_record_and_field(tmp_path):
    from app.models import Chord, LyricLine, RightsRecord
    from app.music_text import build_chordpro, build_lyrics_pdf

    records = [
        RightsRecord(
            uid="SIAE:T-1", society="SIAE", title="Song", original_title="SONG ORIGINAL",
            authors=["Writer A"], performers=["Singer A"], publishers=["Publisher A"],
            identifiers={"ISWC": "T-1", "IPI": "111"}, source_url="https://example.test/siae/T-1",
        ),
        RightsRecord(
            uid="SOUNDREEF:W-2", society="SOUNDREEF", title="Song", original_title="SONG ORIGINAL",
            authors=["Writer A", "Writer B"], performers=["Singer B"], publishers=["Publisher B"],
            identifiers={"WORK_ID": "W-2"}, source_url="https://example.test/soundreef/W-2",
        ),
    ]
    chordpro = build_chordpro(
        title="Song", artist="Singer", key="C", bpm=120,
        lyrics=[LyricLine(time_ms=0, text="Line")], chords=[Chord(time_ms=0, chord="C")],
        rights_records=records,
    )
    for expected in (
        "Provider: SIAE", "UID: SIAE:T-1", "Publisher A", "IPI: 111",
        "Provider: SOUNDREEF", "UID: SOUNDREEF:W-2", "Publisher B", "WORK_ID: W-2",
        "https://example.test/soundreef/W-2",
    ):
        assert expected in chordpro

    out = tmp_path / "multi-provider.pdf"
    build_lyrics_pdf(
        out, title="Song", artist="Singer", key="C", bpm=120,
        lyrics=[LyricLine(time_ms=0, text="Line")], chords=[Chord(time_ms=0, chord="C")],
        rights_records=records,
    )
    assert out.exists() and out.stat().st_size > 1000


def test_project_info_renders_multi_provider_rights_details():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    assert "Dati repertorio / provider diritti" in js
    assert "Lo stesso brano può avere registrazioni in più provider" in js
    assert "Editori:" in js
    assert "Fonte:" in js
