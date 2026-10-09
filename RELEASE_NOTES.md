## 0.2.0-r274 — Optional FLAC project storage + MTA compatibility

- Global opt-in setting for FLAC project storage in web/native Settings; defaults to WAV.
- Persist storage mode per project, and ask explicitly before migrating a WAV project when opening it.
- Convert integer PCM WAV assets to fast FLAC level 1 with decoding verification; retain 32-bit/float files without silent quantization.
- Keep previews and export PCM in ephemeral locations outside the portable project; portable archives carry referenced FLAC assets.
- MTA export continues to render all sources to a common time-aligned PCM timeline, then writes MP3 audio slots; no raw FLAC streams in MTA.
- End-to-end FLAC conversion → `.maeprojz` archive → `.mta` export tests and regression coverage.

## 0.2.0-r272 — DrumSep hybrid ONNX inference

- Combine frequency-domain ISTFT with time-domain predictions; align centred Hann STFT and overlap-add windows.
- DrumSep kit-only mix is reconstructed from kick, snare, toms and cymbals rather than copying Demucs drums.
- Non-kit percussions remain a separate SAM Audio model selection; no misleading DrumSep claim.
- Real-model inference and subjective separation quality require native testing.

## 0.2.0-r271 — DrumSep ONNX integration

- Optional ONNX model download with SHA-256 and atomic installation; selectable Kick/Snare/Toms/Cymbals.
- Demucs to DrumSep selective extraction; SAM Audio remains for non-kit percussion.

## 0.2.0-r270 — optional SAM Audio percussion separation

- Select SAM Audio Small/Base/Large or DSP; the selection is remembered across projects.
- Selectively extract kick, snare, toms, cymbals or non-kit percussion through Demucs and optional SAM Audio.
- SAM Audio uses an isolated Python worker; user-authorized gated checkpoints are not bundled.
- Only requested outputs are imported.

## 0.2.0-r269 — selective stem extraction and percussion split

- Add selective re-extraction of lead vocals, percussions, drum body and Other on an existing track.
- Add optional drums/percussions second-pass spectral separation; imports only requested stems.
- Preserve existing stem workflow and add explicit validation of selection.

## 0.2.0-r268 — transport scrubber and MusicBrainz hover
- Add a viewport-independent seek slider in the transport with whole-project progress during playback; frame zoom and project navigation as distinct controls.
- Position MusicBrainz candidate details near the hovered row within viewport bounds rather than underneath the scrolling results list.

## 0.2.0-r267 — RoFormer beartype validator compatibility
- Override legacy beartype 0.18.x with a PEP 604-compatible validator in native packaging, and add a smoke check for Callable | None.
- Make RoFormer failure actionable with an explicit dependency diagnostic.
- Preserve installed model files and existing separation/outputs.

## 0.2.0-r266 — AI backing vocal output path fix
- Resolve audio-separator relative WAV filenames inside the per-job output directory, rather than the process working directory.
- Validate both generated stems before moving them; add regression coverage for UVR MDX-NET karaoke output naming.

## 0.2.0-r265 — editor/PDF marker/lyric associations
- Align all marker placements with lyric START times, preserve multiple markers between lines, and persist explicit manual lyric anchors in the Marker schema.
- Apply the same auto/manual associations when rendering Lyrics+Chords PDF.

## 0.2.0-r264 (2026-10-09)

- Lyrics editor: marker sections grouped by lyric start timestamp; drag a marker chip onto a lyric line to persist a manual association, restore Auto via context menu.
- Preserve manual lyric-line association when its timestamp changes.

## 0.2.0-r263

- Zoned metronome BPM labels with per-zone manual/auto edit and atomic partial regeneration; marker boundary ID based persistence.

## 0.2.0-r262
- Fix marker-label double-click on timeline: retain DOM across clicks and avoid initiating a drag on caption.
- Remove inert “Master / Preview” mixer-tab button; preview/master controls remain available in their working locations.

## 0.2.0-r261

- Fixed native backing-vocals AI splitting failures caused by missing or mismatched torchvision::nms C++ operators. Added dependency pins, package collection and build-time smoke checks.

## 0.2.0-r260

- Removed the standalone Project sidebar shortcut; retained Project / File and existing project commands.

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

