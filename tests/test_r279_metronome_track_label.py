from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_track_metronome_mode_label_has_all_three_modes_and_locales():
    source = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
    assert "if(t?.type!=='click')return '';" in source
    assert "current?.metronome_mode||'fixed'" in source
    for value in ('adaptive', 'zones'):
        assert f"mode==='{value}'" in source
    for english, italian in (
        ('Adaptive metronome', 'Metronomo adattivo'),
        ('Zone metronome', 'Metronomo a zone'),
        ('Standard metronome', 'Metronomo standard'),
    ):
        assert f"tr('{english}','{italian}')" in source


def test_metronome_label_only_in_tracks_click_header():
    source = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
    assert "${t.type==='click'?`<div class=\"track-metronome-kind\"" in source
    assert 'track-metronome-kind' in (ROOT / 'app/static/app.css').read_text(encoding='utf-8')
