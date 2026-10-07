from pathlib import Path

from app.chordino_runtime import _discover_bundled_runtime, configure_chordino_environment
from app.music_text import _chord_templates, _simplify_chord_label


def test_automatic_chord_vocabulary_is_conservative():
    labels = {name for name, _ in _chord_templates()}
    assert 'C' in labels and 'Cm' in labels and 'C7' in labels and 'Cmaj7' in labels and 'Cm7' in labels
    assert 'Csus2' in labels and 'Csus4' in labels and 'Cdim' in labels and 'Caug' in labels
    for unwanted in ('C9', 'Cmaj9', 'Cm9', 'C7b9', 'C7#9', 'C7b5', 'C7#5', 'CmMaj7', 'Cm7b5', 'Cdim7', 'Cadd9'):
        assert unwanted not in labels


def test_complex_recognizer_labels_are_simplified_but_manual_vocabulary_can_remain_supported():
    assert _simplify_chord_label('C9') == 'C7'
    assert _simplify_chord_label('Cmaj9') == 'Cmaj7'
    assert _simplify_chord_label('Cm9') == 'Cm7'
    assert _simplify_chord_label('C7b9') == 'C7'
    assert _simplify_chord_label('Cm7b5') == 'Cdim'
    assert _simplify_chord_label('Cadd9') == 'C'
    assert _simplify_chord_label('C7sus4') == 'Csus4'


def test_native_macos_bundle_discovery_handles_frameworks_and_resources(tmp_path, monkeypatch):
    contents = tmp_path / 'MTA Audio Editor.app' / 'Contents'
    frameworks = contents / 'Frameworks'
    resources = contents / 'Resources'
    host_dir = frameworks / 'bin'
    vamp_dir = frameworks / 'vamp'
    host_dir.mkdir(parents=True)
    vamp_dir.mkdir(parents=True)
    resources.mkdir(parents=True)
    host = host_dir / 'vamp-simple-host'
    host.write_text('host')
    plugin = vamp_dir / 'nnls-chroma.dylib'
    plugin.write_text('plugin')
    monkeypatch.delenv('MTA_CHORDINO_HOST', raising=False)
    monkeypatch.delenv('MTA_VAMP_PATH', raising=False)
    found_host, vamp_dirs = _discover_bundled_runtime(frameworks)
    assert found_host == host.resolve()
    assert vamp_dir.resolve() in vamp_dirs
    configure_chordino_environment(bundle_root=frameworks)
    import os
    assert os.environ['MTA_CHORDINO_HOST'] == str(host.resolve())
    assert str(vamp_dir.resolve()) in os.environ['VAMP_PATH']
