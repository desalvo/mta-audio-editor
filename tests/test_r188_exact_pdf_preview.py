from pathlib import Path

JS = Path('app/static/app.js').read_text(encoding='utf-8')
MAIN = Path('app/main.py').read_text(encoding='utf-8')
REQ = Path('requirements.txt').read_text(encoding='utf-8')


def test_preview_uses_actual_generated_pdf_renderer():
    assert '/lyrics.pdf.preview' in JS
    assert 'lyricsPdfHtmlPreview' not in JS
    assert '_build_project_lyrics_pdf(project, chord_color)' in MAIN
    assert 'fitz.open(pdf_path)' in MAIN
    assert 'pixmap.tobytes("png")' in MAIN


def test_pdf_download_and_preview_share_same_builder():
    route = MAIN[MAIN.index('@app.get("/api/projects/{pid}/lyrics.pdf")'):]
    assert route.count('_build_project_lyrics_pdf(project, chord_color)') >= 2


def test_native_safe_renderer_dependency_is_pinned():
    assert 'PyMuPDF==' in REQ


def test_revision_metadata_consistency():
    rev = int(Path('REVISION').read_text().strip())
    assert f'versionCode = {20000 + rev}' in Path('mobile/android/app/build.gradle.kts').read_text()
    assert f'<string>{20000 + rev}</string>' in Path('mobile/ios/MTAEditorMobile/Info.plist').read_text()


def test_exact_preview_endpoint_rasterizes_real_pdf(tmp_path, monkeypatch):
    from app import main
    from app.models import Chord, LyricLine, Project

    project = Project(
        id='preview-r188', title='Preview', artist='Artist', bpm=120,
        lyrics=[LyricLine(time_ms=0, text='Hello world')],
        chords=[Chord(time_ms=0, chord='C')],
    )
    monkeypatch.setattr(main, '_project_for_actor', lambda request, pid: project)
    response = main.preview_project_lyrics_pdf_exact(project.id, None, '#7B1FA2')
    assert response.status_code == 200
    body = response.body.decode('utf-8')
    assert 'data:image/png;base64,' in body
    assert 'Pagina 1 /' in body
