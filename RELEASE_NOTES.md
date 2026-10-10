# MTA Audio Editor 0.3.0-r25

- Native VST3 offline diagnostic: 16 sequential blocks with deterministic non-silent input and measured output energy/peak.
- Steinberg ADelay reference plugin end-to-end acceptance test, integrated in Linux SDK CI job.
- Input buses correctly marked non-silent, output buffers cleared between blocks, bounded untrusted diagnostics.
- No realtime integration: further compatibility and performance gates remain open.

## 0.3.0-r25

Isolated VST3 probe: 16-block 440 Hz deterministic signal processing; per-block buffer clearing, bounded output energy and non-finite diagnostics. This remains experimental; no realtime integration or validated MIDI/automation/latency compensation.

## 0.3.0-r24

- Added SDK-built isolated VST3 single-block offline smoke-test, explicitly opt-in.
- Bounded silent audio bus buffers, cleanup and finite-output diagnostics.
- No audio-engine integration or realtime plugin support.

## 0.3.0-r23
- Fixed real-SDK VST3 probe linking using official MIT SDK IID implementation units; build validated locally on Linux x86_64.
- SDK-enabled plugin processing, GUI and bus activation remain experimental and disabled in the playback engine.

## 0.3.0-r23
- Fixed real-SDK VST3 probe linking using official MIT SDK IID implementation units; build validated locally on Linux x86_64.
- SDK-enabled plugin processing, GUI and bus activation remain experimental and disabled in the playback engine.

## 0.3.0-r22 — External VST3 SDK checkout validation

- Reject incomplete Steinberg VST3 SDK GitHub ZIPs before native compilation.
- Require recursive SDK checkout for opt-in native VST3 compilation.
- Preserve the isolated diagnostic host; audio playback remains unchanged.

## 0.3.0-r21 (2026-10-10)

- Add explicit isolated VST3 `--configure` diagnostic: test processor setup at 48 kHz / 512 samples using a supported 32/64-bit format, without activation or processing.
- Return validated processing setup metadata to the Python probe; keep `native_host_ready=false` and production playback unchanged.
- Add tests for CLI safety, opt-in configuration, and mobile version consistency.
- The SDK-specific code path still requires compile/runtime validation against the Steinberg VST3 SDK and real plugins.

## 0.3.0-r20 (2026-10-10)

- Add isolated VST3 processor tail-length diagnostics (getTailSamples) after successful lifecycle initialization, bounded in C++ and validated in Python.
- Compile the standalone VST3 factory probe without SDK in both Linux DEB/RPM CI matrix targets, including ARM64.
- Keep realtime native VST3 hosting disabled pending official SDK and plugin interoperability tests.

## 0.3.0-r19 (2026-10-10)

- Fix Linux ARM64 packaging: install libopus-dev and pkg-config, and verify the Opus pkg-config entry before installing sphn/Demucs. This prevents audiopus_sys from building the incompatible bundled Opus source with modern CMake.
- Preserve native VST3 diagnostics in experimental isolated mode; no playback activation.

## 0.3.0-r18 (2026-10-10)

- Fix Android and iOS revision metadata mismatch causing six pytest failures in GitHub Actions.
- Add tests for VST3 discovery, path restrictions, and optional runtime; preserve the 70% coverage gate.
- Keep native VST3 probe experimental and isolated from playback.

## 0.3.0-r17 (2026-10-10)

- Harden VST3 factory class-name and category parsing by bounding reads of Steinberg fixed-size arrays.
- Reject out-of-range plugin bus channel counts before emitting diagnostics.
- Add regression guard for C++ metadata bounds; native host remains experimental and offline.
- Synchronize release identifiers and mobile build metadata.
- SDK-enabled compilation and GitHub Actions run logs were unavailable for validation.

## 0.3.0-r16 — VST3 diagnostic hardening

- Validate the requested 32-hex CID in the C++ probe before loading plugin binaries, including in no-SDK builds.
- Reject non-object JSON and diagnostic output exceeding 2 MB in the Python adapter.
- Add targeted tests and retain the isolated, non-realtime host diagnostics from r15.
- SDK-backed C++ compilation and interoperability with third-party plugins remain unverified; playback is unchanged.

## 0.3.0-r15 — VST3 processor capability diagnostics and CI build gate

- Isolated lifecycle mode now probes supported 32-bit/64-bit sample formats and reported plugin latency. Values are sanitized in the Python adapter; no audio processing is enabled.
- GitHub Actions quality job now builds the standalone C++20 VST3 probe without Steinberg SDK as a regression gate.
- Added tests for capability decoding, invalid latency data and playback isolation.
- SDK-backed compilation and real plugin interoperability remain unverified. No claims of resolving remote Actions failures without corresponding logs.

## 0.3.0-r14 — Isolated VST3 diagnostic host context

- Added a stack-scoped minimal `IHostApplication` implementation with host name, interface negotiation and reference counting in the subprocess only.
- `--lifecycle` now passes that diagnostic context to `IComponent::initialize()`. Unsupported host-created objects explicitly return `kNotImplemented`.
- Added `host_context_provided` to diagnostic JSON/Python results. `native_host_ready` remains `false`.
- No playback, rendering, VST audio processing, plugin editor or automation changes.
- SDK-backed compilation and real-plugin interoperability are **not yet validated**. Some plug-ins can legitimately decline initialization.
- Preserved the r13 VST3 support manual cover titles and PDFs.

## 0.3.0-r13
- Correct VST3 manual cover titles in both PDFs and display current revision.
- Add isolated, opt-in VST3 IAudioProcessor/IEditController interface discovery; no realtime host activation.
- Preserve existing playback and exports.

## 0.3.0-r12
- Add isolated VST3 bus information diagnostics after successful component initialization; no realtime processing.
- Update VST3 support manual titles and license-only sections in Italian and English; regenerate PDFs retaining cover artwork.

## 0.3.0-r11

- Added opt-in isolated VST3 IComponent lifecycle diagnostic (--lifecycle CID): initialize with null host context, terminate only after successful initialization, always release.
- Kept the previous create-only mode and production playback untouched.
- Some plugins reject a null host context; this diagnostic is not a realtime-host certification.

## 0.3.0-r10

- Optional VST3 SDK-backed audio-component instance creation diagnostic by exact CID; release immediately, no playback activation.
- Validate instance creation request and report results independently of factory enumeration.
- Keep all realtime VST3 processing, GUI, MIDI and automation experimental and disabled.

## 0.3.0-r9

- Added bilingual VST3 manuals (Markdown and PDF) with the exact existing user manual cover page.
- Hardened untrusted native VST3 class metadata against duplicate CIDs and control characters.
- Kept existing playback/rendering unchanged.

## 0.3.0-r6

- Compliance: archive scanner for source/release ZIP and TAR; rejects unreviewed bundled VST3/AU/AAX and traversal paths.
- Packaging behavior unchanged; native audio host remains experimental.

## 0.3.0-r2

- Added transactional native C++20 mono-to-stereo constant-power pan mixer with input validation.
- Preserved Python audio backend and existing VST3 offline path; new mixer primitive is opt-in only.
- Updated Android, iOS, and Windows revision metadata.

## 0.2.0-r302

- Added opt-in compiled PCM accumulation primitive for future native real-time mixer; no changes to current playback engine.
- Tests cover buffer validation and equivalent portable fallback.

## 0.2.0-r301

- Per-category vector icons for insert setup panels, including VST3.
- Optional C++ PCM gain routine; existing Python processing remains default.

## 0.2.0-r300

- Experimental Linux x86_64/arm64 Debian/RPM workflows.
- Optional portable compiled C++ PCM metering library with Python fallback.
- Native Settings VST3 plugin discovery/status and rescan.
- Existing audio engine and APIs unchanged to minimize regressions.
- Complete native VST3 hosting, MIDI, realtime audio, plugin GUIs and compiled web backend NOT YET implemented.

## 0.2.0-r299

- Mixer Insert shows a strong green indicator for active FX, amber when all inserts are bypassed, and updates without global rerender.
- VST3 insert additions and parameter changes refresh the rendered playback path when audio is playing.
- Clarified rendered VST3 playback versus native real-time host limitations.

## 0.2.0-r297

- Experimental desktop VST3 track insert discovery and isolated offline processing via optional pedalboard host.
- VST3 plugin selection in mixer insert interface, path persistence, explicit unsupported master/live restrictions and setup guide.

## 0.2.0-r296

- mixer: double click on a channel name now allows renaming the track directly from the mixer.
- insert FX setup: refreshed visual design with artistic/photo background, integrated app mark and plugin-type specific mood.

## 0.2.0-r294 — Native Settings Save freeze fix

- Avoid synchronous full-page localization during Settings Save.
- Avoid importing the server module inside the native-settings IPC handler.
- Prevent concurrent saves and report bridge errors/timeouts.
- Keep playback updates deferred and unnecessary work out of Save.

## 0.2.0-r293 — Fast Settings dialog and save

- Localize only updated DOM subtrees rather than translating the entire track-heavy page for each mutation.
- Show Settings immediately while native configuration is loading.
- Avoid relocalizing the entire interface on save unless the language actually changed.
- Skip expensive playback metadata sync on Settings save while idle.

## 0.2.0-r292
- Select/Split/Range/Ripple and track selection no longer rerender the entire project.

## 0.2.0-r292 — Insert setup button legibility

- Explicit readable colors and native WebView text-fill for Save preset & apply, Apply custom and Cancel in insert setup dialogs.

## 0.2.0-r290
- Keep the sticky Chords lane fully transparent: only chord labels appear over the first track, without the dark band. Chord drag/edit and marker behavior are unchanged.

## 0.2.0-r289
- BPM context menu: Manual BPM sets the musical tempo without changing audio playback speed; Reset BPM restores the original detected tempo and original speed.
- Tap Tempo sets manual BPM. Direct input continues to change playback speed.
- Original detected BPM is persisted independently from the musical reference tempo.

## 0.2.0-r288
- Tap Tempo icon next to BPM; manual BPM/time signature edits regenerate active metronome tracks.
- New/updated metronome tracks no longer have BPM in their name.

## 0.2.0-r287 — Track delay and metronome interval

- Inline delay under track volume (milliseconds or beats based on transport mode), applied to playback/timeline/render/export via existing persisted track delay.
- Generated metronome and chords tracks preserve their non-destructive track delay across refreshes.
- Metronome start and stop (milliseconds) are persistent; empty stop means project end. Generated metronome WAV is silent outside the requested range, with unmodified timeline timestamps.

## 0.2.0-r287 — Track delay controls

- Inline delay under track volume (milliseconds or beats based on transport mode), applied to playback/timeline/render/export via existing persisted track delay.
- Generated metronome and chords tracks preserve their non-destructive track delay across refreshes.

## 0.2.0-r286 — YouTube guidance and initial track alignment
- Explain browser playback before YouTube URL import (Italian/English).
- Reset initial Tracks/timeline vertical scroll on first track insertion and disable scroll anchoring.

## 0.2.0-r285 — timeline chord and marker visibility
- Keep chord labels and marker editing handles visible during vertical track scrolling without changing their timestamp positions or event handlers.

## 0.2.0-r284 — branding and project title layout
- Top-left native application mark links to the GitHub project.
- Project title follows the playback controls on the line below.
- Enlarged sidebar branding while retaining responsive layout.

## 0.2.0-r283
- Stabilize the asynchronous garbage-collection regression test on GitHub Actions without changing production cleanup behavior.

## 0.2.0-r282
- Compact transport header, sidebar branding, mixer-channel Insert controls.

## 0.2.0-r281

Reduced UI latency with projects containing many audio tracks and stems. Switching the embedded Lyrics/Chords/Markers tab and revealing Plugins no longer triggers a complete timeline render.

## 0.2.0-r280 — Timed row split and reconcile
- Preserve start/end boundaries when splitting Lyrics, Chords or Markers rows.
- Add contextual Reconcile timestamp on start/end fields and optional end timestamps for Chords and Markers.

## 0.2.0-r279 — Metronome type indicator in Tracks

- Display Standard / Adaptive / Zone metronome beneath the volume controls of each metronome track.
- The label follows the project metronome mode and active IT/EN interface language.

## 0.2.0-r278 — Native UI localization fixes

- Reapply active locale to dynamically inserted contextual menu items and dialog titles.
- Expand EN/IT translations for metadata search, stem separation, model management, and editing actions.
- Keep language preference Auto / Italiano / English.

## 0.2.0-r277
- MusicBrainz results: per-row information button and compact layout; pagination button legibility.
- GitHub Actions macOS Chordino: execute installer script through bash.

## 0.2.0-r276 — Singer separation and GitHub CI coverage fix

- Add an experimental SAM Audio multi-singer mode (2–8 singers) to new-song and existing-track stem workflows.
- Each singer receives a solo positive time-span reference; all other singers' reference spans become negative anchors, as supported by SAM Audio.
- Extract all singers or only one selected singer. Song-relative references are validated, and generated tracks begin at timeline offset zero.
- Keep separate singer names, selected model, and last selected singer target; retain existing WAV/FLAC project storage, MTA export and percussive separation workflows.
- Fix the CI `scipy` ModuleNotFoundError: install both SciPy and SoundFile in base/runtime requirements, including the test image.
- Add test coverage for real DSP/ONNX framing, the SAM CLI temporal anchors, singer reference validation and selective track replacement, keeping the 70% coverage gate unchanged.
- No model weights or Hugging Face credentials are bundled. SAM inference with licensed checkpoints and overlapping singers still needs testing in the native runtime.

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


### 0.2.0-r295
- Fix sidebar and Settings freezes with no project open, caused by repeated localization attribute mutations.
