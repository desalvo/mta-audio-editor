from pathlib import Path

JS = Path('app/static/app.js').read_text()


def test_word_level_chords_remain_visible_with_auto_syllables():
    assert "wordLevel=(byAnchor.get(`${li}:word:${wi}:x`)||[]).map(chip).join('')" in JS
    assert "chips=(si===0?wordLevel:'')+syllableChips" in JS
    assert "editorAutoSyllableParts" in JS


def test_project_open_progress_covers_real_open_stages():
    assert "function showProjectOpenProgress" in JS
    assert "project-open-progress" in JS
    assert "Caricamento progetto…" in JS
    assert "Inizializzazione tracce e metadata…" in JS
    assert "Caricamento waveform e interfaccia…" in JS
    assert "Preparazione motore audio…" in JS
    assert "Progetto pronto" in JS


def test_all_project_open_paths_use_progress():
    assert "async function openP(id)" in JS
    assert "async function openRecentNativeProject(id)" in JS
    assert "Selezione e lettura file progetto…" in JS
    assert JS.count("finishProjectOpenProgress()") >= 6
