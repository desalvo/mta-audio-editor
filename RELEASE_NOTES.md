## 0.2.0-r259 — model management, sidebar preferences, bilingual UI

- Central model-manager lists Demucs and backing-vocal models, including their filesystem paths and download/delete commands.
- Sidebar sections remember their open/closed state globally across projects.
- Additional IT/EN translations for vocal separation dialogs, download and status messages.
- Background macOS multiprocessing workers request a no-Dock activation policy.

## 0.2.0-r258
- macOS Intel: enforce binary NumPy 1.26.4 / Numba 0.61.2 / llvmlite 0.44.0 wheels, including a constraint on the optional resampy runtime installation.
- Windows: explicitly install and freeze six, required by audio-separator UVR runtime.
- Keep native separator import checks as production gates.

## 0.2.0-r257 — Native stem dependency convergence

- ARM64: install missing audioread explicitly before validating audio-separator.
- Intel macOS: isolate a legacy NumPy 1.x-compatible audio-separator wheel from Demucs 4.1 and NumPy 1.26.
- Windows: bypass broken diffq-fixed sdist via controlled wheel installation and explicit inference dependencies.
- Add Windows-specific requirements and native preflight validation.

## 0.2.0-r256

- CI regression fixes: update legacy context-menu text assertions to the current Add chord / Extract marker labels.
- Make revision metadata regression tests version-independent while preserving Android revision and versionCode consistency checks.

## 0.2.0-r255

- Stabilized Lyrics/Chords/Markers double-click editing without rerendering on single click, preserving scroll and last-row edits.
- PDF Lyrics+Chords reserves a leading column for line-start anchored chords.
- macOS Apple Silicon PyInstaller bundles audio_separator and ONNX Runtime; CI fails when the backing-vocal engine cannot be imported.

## 0.2.0-r254
- Fix visible download button for backing-vocal AI models.
- Surface the backing-vocal separation method while processing.
- Include audio-separator CPU dependency in macOS Intel native builds and explain missing engine.

## 0.2.0-r253
- Metronome source-track refresh with zone-aware recalculation, marker-driven updates, and transport arrow nudging.
- Timeline shortcut M and track/waveform context menu Add marker; simplified Add chord and Extract marker labels.

## 0.2.0-r252
- Double-click timeline marker labels to rename.
- Exact timestamp alignment for marker guide and chord label.
- Playback marker highlighting and synchronized metadata list scrolling.
- Wider inline timestamp editor for lyrics/chords/markers.

## 0.2.0-r251
- Timeline marker captions are placed below the chord-label band to avoid collisions when Show Chords and Show Markers are both enabled.

## 0.2.0-r250
- Timeline markers: drag and reposition, with context menu to add, enable, disable or delete while markers are visible. Markers use a vivid high-contrast magenta line and handle with distinct hover and disabled states.
- Includes r249 update-download progress indicators.

## 0.2.0-r249
- Native desktop and Android installer downloads show live progress, downloaded/total MB and an indeterminate fallback when the server omits Content-Length.
- Desktop installer download is staged atomically, with incomplete transfers rejected.

## 0.2.0-r248
- Piano / Chord Lab falls back to a draggable and resizable in-app detached window when popup permission is unavailable.
- Enlarged Show Lyrics/Chords/Markers icons fill compact 38px toggle buttons, preserving title tooltips and aria-labels.

## 0.2.0-r247
- Compact icon-only New project, Open, Save, Save as, Setup and Export header actions with accessible labels/tooltips.
- Collapsed-by-default View/Vista menu: Lyrics, Chords, Markers, Piano / Chord Lab, Tracks, Plugins, Mixer.
- Removed redundant Lyrics/Meta and Piano header buttons.

## 0.2.0-r246
- Metronome: standard/zones/adaptive modes and persisted sensitivity.
- Context refresh for click and generated chords; markers overlay and icon toggles.
- Atomic staged metronome WAV replacement.
- Zone refresh currently falls back to atomic whole-track render.

## 0.2.0-r245

- Fix macOS Intel x86_64 CI dependency resolution: librosa 0.11.x with NumPy 1.26.4, while using librosa 1.0.x on other platforms.
- Keep the preceding r243 Chord Lab features unchanged; align Android, iOS, and Windows revision metadata.

## 0.2.0-r243

- Real 2-octave piano keyboard layout (C3–B4) with 7 white and 5 black keys per octave, correctly spaced E–F/B–C boundaries and narrower keys.
- Piano / Chord Lab detachable into a movable, resizable native browser window with ↗, synchronized notes and presets. Popup close restores the docked panel.
- Left-edge panel resizer correctly adjusts the left boundary in the mixer grid.
- Most-used chord suggestions rank project-local manually entered recent chords ahead of raw frequency; recency is stored with the project.
- No changes to the audio engine or other existing project features.

## 0.2.0-r243

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

