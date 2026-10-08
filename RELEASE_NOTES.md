## 0.2.0-r242

- Fix Android AGP 9.4.1 compatibility: GitHub Actions Gradle 9.6.0 (formerly 9.3.1).
- Restore macOS x86_64 Python 3.12 known working NumPy 1.26.4, Numba 0.61.2 and llvmlite 0.44.0 to avoid missing LLVM while preserving other r241 updates.
- Update version metadata and pinned toolchain compatibility tests.

## 0.2.0-r241
- Reconciled dependency PRs #10–#15 and adjusted Android/macOS Intel regression tests.
- Android Gradle Plugin 9.4.1, PyMuPDF 1.28.2, Ruff 0.16.10, Numba 0.68.0, llvmlite 0.50.0, NumPy 2.5.3 (macOS Intel), librosa 1.0.x, SoundFile 0.14.x and PyYAML 6.0.3+.
- Preserves all r240 editor behavior; macOS Intel/native build compatibility must be validated on CI runners before production release.

## 0.2.0-r240
- Timeline Chords: single click selects exclusively, Ctrl/Cmd+click toggles additive selection, clicking outside clears the selection.
- Preserve chord drag and double-click inline editing without replacing captured DOM nodes.


## 0.2.0-r239
- Timeline chord inline editor: close/save X and reliable Enter commit.
- Lyrics/Chords/Markers panel: batch disable, re-enable and delete for multi-selection.
- Open Recent: deduplicated by bound project path and capped at 15 entries.
# MTA Audio Editor 0.2.0-r238

- Piano / Chord Lab dock beside Mixer with live keyboard, chord presets and Shift+click chord recognition.
- Resizable/scrollable panel with persistent visibility and width.

# MTA Audio Editor 0.2.0-r237

This revision fixes chord-extraction defaults and modal sizing, makes selected-range text/music extraction automatic, and adds timeline Chord batch selection/actions with visible shortcuts.

