## 0.2.0-r263

- Zoned metronome BPM labels with per-zone manual/auto edit and atomic partial regeneration; marker boundary ID based persistence.

## 0.2.0-r262
- Fix marker-label double-click on timeline: retain DOM across clicks and avoid initiating a drag on caption.
- Remove inert “Master / Preview” mixer-tab button; preview/master controls remain available in their working locations.

## 0.2.0-r261 — PyTorch/torchvision native-operator compatibility

- Align torchvision with the installed PyTorch release on Windows, macOS ARM64 and macOS Intel.
- Package torchvision native extensions and validate the torchvision::nms operator in GitHub Actions before building native installers.
- Surface an actionable error if an existing runtime has incompatible torch/torchvision libraries.

## 0.2.0-r260 — 2026-10-08

- Removed the redundant standalone “Project” sidebar button. The collapsible Project / File section and all project commands remain available.

## 0.2.0-r259 — model management, sidebar preferences, bilingual UI

- Central model-manager lists Demucs and backing-vocal models, including their filesystem paths and download/delete commands.
- Sidebar sections remember their open/closed state globally across projects.
- Additional IT/EN translations for vocal separation dialogs, download and status messages.
- Background macOS multiprocessing workers request a no-Dock activation policy.

## 0.2.0-r258 — native audio-separator dependency fixes
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

## 0.2.0-r245

- Fix macOS Intel x86_64 CI dependency resolution: librosa 0.11.x with NumPy 1.26.4, while using librosa 1.0.x on other platforms.
- Keep the preceding r243 Chord Lab features unchanged; align Android, iOS, and Windows revision metadata.

## 0.2.0-r243

- Android Gradle toolchain compatibility fix (Gradle 9.6.0).
- Restore wheel-compatible macOS Intel NumPy/Numba/llvmlite dependency pins.

## 0.2.0-r241 — dependency PR reconciliation

- Integrate GitHub Dependabot PRs #10–#15: Android Gradle Plugin 9.4.1; Ruff 0.16.10; PyMuPDF 1.28.2; macOS Intel Numba 0.68.0 / llvmlite 0.50.0 / NumPy 2.5.3; librosa 1.0.x; SoundFile 0.14.x; PyYAML 6.0.3+.
- Update platform toolchain regression checks and Android/iOS/Windows revision metadata.
- Verify deployment builds for macOS Intel, Android, Windows and iOS in GitHub Actions before publishing a production release.

## 0.2.0-r238

- Added a dockable, closable and resizable Piano / Chord Lab beside the Mixer with a scrollable two-octave mini keyboard.
- Added live note audition and common chord presets (major/minor/7/maj7/m7/dim/dim7/aug/sus2/sus4).
- Shift+click builds a live chord on the keyboard, highlights accumulated notes, plays them, and names the recognized chord when Shift is released.
- Piano panel visibility and width are persisted in the project.

## 0.2.0-r237

- Chord extraction defaults to Balanced (sensitivity 45, all advanced stages except beat quantization); legacy Default/Completo is migrated and removed.
- Lyrics/Chords extraction is automatically constrained to an active timeline Range.
- Utility/progress/extraction modals reset transient sizing on every open and keep safe minimum dimensions.
- Timeline Chords support CTRL/CMD multi-selection with batch disable/re-enable/delete; Backspace/Delete removes the selected Chords.
- Context menus display keyboard shortcuts for actions that have one.

## 0.2.0-r236

- Added track-referenced fixed/adaptive metronome generation from the track context menu; rhythmic analysis can use one selected track as the sole timing source.
- Added adaptive metronome shift in milliseconds or beats without recalculating the detected tempo map.
- Added transport display/input mode for absolute time (`mm:ss.mmm`) or musical position (`bar:beat`) using fixed tempo or the adaptive beat map.
- Persisted the metronome reference track, grid origin, shift and transport time mode in project data.
- Preserved the mixer as vertical channel strips with vertical level faders.

## 0.2.0-r235

- Added Adaptive Metronome: every request recalculates the complete beat-by-beat tempo map from the current song and regenerates the click track to follow internal tempo changes.
- Adaptive analysis excludes existing metronome tracks and persists the newly detected local BPM map in the project.

## 0.2.0-r234

- Preserva gli anchor manuali lyrics/chords durante aggiunte, eliminazioni e refresh della traccia Chords.
- Corregge export MP4 Karaoke e unifica la barra di progresso per gli export di progetto.
- Corregge apertura .maeprojz dal Finder su macOS tramite file-open argv emulation.

## 0.2.0-r233
- PDF Lyrics: una riga di lyrics che apre una nuova pagina mantiene sempre la formattazione Lyrics configurata anche quando non ha chords.

## 0.2.0-r232

- Lyrics + Chords + Markers: il timestamp di una nuova linea Lyrics usa ora il formato standard `m:ss.mmm` / `mm:ss.mmm`, con playhead precompilato e validazione coerente con gli altri editor.

## 0.2.0-r231

- Added CTRL/CMD multi-selection for synchronized Lyrics and Chords with one-shot batch deletion.
- Added partial Lyrics/Chords extraction over the current timeline range; only events inside the selected interval are replaced while events outside remain unchanged.
- Partial Chords extraction triggers a single Chords guide-track refresh after completion.

## 0.2.0-r230

- CI: removed unused `io` import from `app/mp3g.py` to satisfy Ruff.

## 0.2.0-r229

- Added project sample rate (44.1/48/96 kHz, default 44.1 kHz), fixed after the first active track is present and editable again only with no tracks.
- Audio imported at 44.1/48/96 kHz is normalized to the project sample rate for timeline use while originals are preserved.
- Added WAV export at 24-bit PCM or 32-bit float with 44.1/48/96 kHz output rates.
- Added MP3+G karaoke export as a ZIP containing same-basename MP3 audio and CDG synchronized graphics for lyrics/chords.
- Updated generated Metronome/Chords/stem tracks to honor the project sample rate.
- Restyled the M-Live/Merish MP3 specification cover to match the other MTA Audio Editor manuals.

## 0.2.0-r228

- Added M-Live / Merish compatible MP3 export using ID3v2.3 synchronized lyrics (SYLT), chords (SYLT chord content type), markers/events and USLT fallback.
- Added bilingual M-Live / Merish MP3 interoperability specification PDFs and validation tests.

## 0.2.0-r227

- Rigenerazione automatica della traccia Chords dopo ogni mutazione audio-rilevante: spostamento, modifica, aggiunta, disabilitazione, riabilitazione, eliminazione, reset ed estrazione.
- Refresh fast/parziale preferito sulla minima regione temporale interessata, con fallback automatico al render completo.
- Avviso di attesa sempre visibile durante il refresh della traccia Chords.
- Se non restano chords attivi, il refresh di una traccia Chords esistente genera correttamente una guida silenziosa invece di lasciare audio obsoleto.

## 0.2.0-r223
- Timeline chord moves now refresh an existing generated Chords audio track, preferring a fast partial-window render and falling back to a full render when needed.
- The UI always displays a wait/progress notice while the Chords track is being refreshed.

## 0.2.0-r222

- Lyrics/Chords PDF and preview: end-of-line anchored chords now stay close to the end of the lyric text or to the preceding chord instead of being pushed to the far-right page margin.
- PDF style now includes configurable vertical spacing between consecutive marker sections.
- Markers can indent their whole section by a configurable value in millimetres; preview and PDF apply the same geometry.
- New/edit marker forms automatically reuse color, section indentation and related marker options from the latest previous marker with the same name after leaving the name field.

## 0.2.0-r221
- Added keyboard shortcut C to add a chord at the current playhead when Show Chords is enabled, with popular/recent project chord shortcuts.

## 0.2.0-r220
- Chord deletion is now a real hard delete everywhere (timeline, Chords pane, Lyrics+Chords editor and cut/merge paths); deleted chords disappear immediately and are removed from persisted project data.
- Legacy chords carrying the old `deleted=true` soft-delete flag are purged when a project is rendered.
- Fixed timeline chord double-click editing by preserving the marker DOM node after a click without drag.
- Added a vertical waveform positioning guide while dragging a timeline chord, with the exact live timestamp shown beside the guide.
- Added visual chord shortcuts during chord editing, ranked by project usage frequency with most-recent occurrence as tie-breaker.


## 0.2.0-r219
- Registered Portable MTA Audio Editor (`.maeprojz`) as the primary OS document type on Windows and macOS.
- Added `.maeprojz` document/file associations on iOS and Android.
- Kept `.maeproj` registered as a legacy-compatible project type.
- Added regression tests for native/mobile portable project associations.

## 0.2.0-r218

- CI: fixed Ruff F841 in the track-export endpoint so the production workflow can proceed to downstream build jobs.


## 0.2.0-r217
- Portable MTA Audio Editor (`.maeprojz`) is now the default native save/open format; opened portable files stay bound so autosave/manual Save rewrite the portable file instead of only the internal workspace.
- Fixed Chords extraction persistence: refreshed extracted state is rendered before collection/persistence and synchronized to the bound portable project.
- Plugin Inspector now reserves horizontal timeline viewport while open so tracks/playhead/follow never continue underneath it.
- Insert plugin setup opened from Inspector is routed to the top-level utility modal and remains above the Inspector.
- Single-track MP3 export from Plugins/Inspector now asks bitrate, sample rate and editable ID3 metadata before destination selection/rendering.

## 0.2.0-r216
- Added an interactive Chords lane above the first timeline track when Show Chords is enabled.
- Chord markers can be dragged to retime them, edited by double click, and disabled, deleted or re-enabled from their context menu.
- Added “+ Chord at current position” to the timeline context menu.

## 0.2.0-r215
- CI: removed unused `io` import reported by Ruff F401 in the r210 preview/overlay regression tests.
- Tests: revision/build-number validation is now revision-agnostic so future revisions do not fail on a hard-coded r213 assertion.
- Mobile/native packaging metadata aligned to revision 214.

## 0.2.0-r213

- Fixed insert-plugin configuration windows being hidden below the absolute Plugins/Inspector overlay by moving utility dialogs to a higher application modal layer.
- Native single-track WAV/MP3/FLAC export now asks for the destination path before rendering starts; cancelling the save dialog prevents the render job from starting.
- Added atomic native save-to-preselected-path support for rendered audio files.
- Browser track/audio exports use the Save File picker for WAV/MP3/FLAC when supported, with download fallback otherwise.

## 0.2.0-r212

- Zoom timeline reso fluido: durante il trascinamento dello slider viene mostrato immediatamente un preview grossolano scalando la waveform già renderizzata; il redraw completo avviene una sola volta al rilascio.
- Aggiunti pulsanti `−` e `+` per variare gradualmente lo zoom.
- Doppio click sul cursore dello zoom per ripristinare il valore di default (100% / 70 px/s).
- Aggiunto selettore di preset zoom percentuali (25–400%), temporali (1/5/10 s, Fit) e musicali (1/2 beat, 1/2/4/8 misure).
- I preset beat/misure sono calcolati dinamicamente da BPM e time signature del progetto e adattati alla larghezza visibile della timeline.
- Range massimo dello zoom esteso a 1200 px/s per consentire viste musicali ravvicinate.
- Test completi: 705 test passati, coverage 71,23%.

## 0.2.0-r211

- Added direct horizontal clip movement in Select mode.
- Added Shift+drag grouped movement for all clips of selected track(s).
- Added Delete selected range to the timeline context menu.

## 0.2.0-r209

- Chord extraction: new Songbook/Stable, Balanced, Detailed and Raw pipeline presets with explicit sensitivity, minimum chord duration, density ceiling and optional beat quantisation.
- Chord extraction: harmonic refinement, sevenths, sus, dim/aug, slash-bass/inversions and temporal smoothing can be enabled/disabled independently.
- Chord extraction: Stable profile prioritises Madmom Deep Chroma + CRF / CNN+CRF for a more regular major/minor progression, then falls back to Chordino/MTA.
- Native macOS: Chordino discovery now uses only the runtime actually inside the frozen .app; stale CI/Homebrew paths are ignored.
- Native macOS CI: packaged-app smoke test is run with Chordino build/runtime variables removed, preventing false positives from the build workspace.
- Chordino diagnostics now distinguish missing Vamp host, missing plugin and host execution failures.

- r208: CI maintenance: remove unused test imports that blocked Ruff after r207.
## 0.2.0-r207

- Reworked timeline waveforms with a 4096-bin signed min/max envelope instead of the legacy 1024 absolute peaks.
- Waveform cache now preserves upper/lower signal asymmetry and transient detail and is sampled at 8 kHz before envelope extraction.
- Timeline rendering uses a filled high-resolution envelope with zoom-aware aggregation/interpolation and light visual smoothing.
- Legacy waveform caches remain readable and are automatically regenerated because the waveform revision now includes the new cache format.

## 0.2.0-r206

- Simplified automatic chord extraction to a conservative vocabulary (major/minor, 7, maj7, m7, sus2/sus4, dim, aug) with stronger temporal stabilization and fewer slash chords.
- Complex/altered chord symbols remain supported for manual editing and existing projects, but are no longer aggressively proposed by automatic extraction.
- Native macOS Chordino runtime discovery now searches actual PyInstaller app bundle locations (Frameworks/Resources/MacOS/_MEIPASS), builds VAMP_PATH from discovered plugin directories, and exposes runtime diagnostics when the host/plugin cannot load.


## 0.2.0-r205
- Project preview WAV garbage collection: orphaned/stale `.preview/*.wav` files are cleaned during project maintenance.
- Preview files belonging to deleted tracks are removed; only the two most recent previews per existing track are retained.
- Rebuildable `preview-master.mp3` is cleaned as part of project maintenance.
- Preview GC never touches source audio, Clip Library media, or shared-media blobs.

## 0.2.0-r204
- Fixed the Lyrics + Chords + Markers PDF preview in native WebViews by removing the iframe layer and injecting the exact rasterized PDF pages directly into the preview modal.
- Fixed the Plugins/Inspector stacking context so its header and close button stay above the Project Clips bar.
- Kept the Inspector header sticky while only the plugin body scrolls.


## 0.2.0-r203
- Clear Lyrics/Chords playback overlays immediately on Stop and project close. Pause keeps the current overlay visible.
- Widen the Lyrics + Chords + Markers timestamp column and force single-line timestamps.
## 0.2.0-r202
- Native `.maeproj` is now a lightweight modular project manifest, not a ZIP archive.
- Portable self-contained project archives use `.maeprojz`; legacy ZIP-based `.maeproj` files remain importable.
- Normal Save updates only the small manifest/workspace; Save Copy creates a portable archive.

## 0.2.0-r201

- Fix macOS arm64 Chordino provisioning: use the Homebrew include root for Vamp SDK headers while linking `libvamp-sdk.a` from the library directory.
- No application behavior changes.

## 0.2.0-r200

- Fix native Chordino provisioning in GitHub Actions on Windows and macOS.
- Windows now cross-compiles NNLS-Chroma x64 reproducibly on Linux and transfers it as a same-run artifact.
- macOS now uses the runner architecture, Homebrew Boost headers, and the actual Homebrew libvamp-sdk.a path.

## 0.2.0-r199

- CI maintenance: fix Ruff/Bandit findings from r198 (HTTPS validation for chord model downloads, logged ensemble failures, remove unused test import).
- No intended application behavior changes.

## 0.2.0-r198

- Project-open storage maintenance now removes unreferenced local audio before editing begins.
- Added content-addressed shared media store across projects with SHA-256 deduplication, hardlink-first local references, safe copy fallback, and reconstructible global reference index.
- Added emergency shared-media rescan/rebuild + garbage collection that scans every project before deleting any shared blob.
- Native autosave now writes only the persistent modular workspace; `.maeproj` is refreshed on explicit Save/Save Copy rather than every autosave.
- Recent native projects reopen their persistent workspace first, preserving crash-recovery state newer than the last portable archive snapshot.

## 0.2.0-r197

- Peak-normalize generated Metronome and Chords guide audio to 0 dBFS and reset their generated-track faders to 0.0 dB.
- Track deletion is now a single logical-delete transaction; the UI updates immediately without a pre-delete full native archive save.
- Added a persistent, crash-safe project garbage-collection journal for unreferenced audio. Cleanup runs asynchronously and resumes/reconciles on restart.
- Generated Metronome/Chords assets are disposable when their tracks are deleted; reusable imported Project Clips remain protected.
- Native project archives exclude pending-GC journal entries and files already logically deleted.


## 0.2.0-r196
- Fixed Lyrics + Chords + Markers editor rendering so word-level/automatic chords remain visible when lyrics are editor-only auto-syllabified; chords can again be selected and reassigned to individual syllables.
- Added staged project-opening progress for workspace, recent native projects, and native project files, covering project loading, metadata/tracks initialization, waveform/UI setup, workspace refresh, and audio prewarm.

## 0.2.0-r195
- Added Fast, Accurate and Maximum-accuracy chord extraction profiles.
- Added on-demand BTC-HCQT and ChordFormer model integrations.
- Added weighted multi-engine ensemble recognition with common extended harmony/bass refinement.
- Added model-manager metadata and progress disclosure for the new chord engines.

## 0.2.0-r194
- Chordino/NNLS-Chroma is now bundled in Docker/Kubernetes and native desktop builds instead of relying on a host installation.
- Linux/Kubernetes builds compile upstream NNLS-Chroma natively and use vamp-simple-host, including amd64/arm64 images.
- macOS native builds compile and bundle Chordino plus a private Vamp host; Windows bundles Sonic Annotator plus an x64 NNLS-Chroma runtime.
- Runtime discovery validates the actual `nnls-chroma:chordino` plugin and exposes host/plugin diagnostics to the UI.
- Native apps configure private PATH/VAMP_PATH automatically, so no system-wide plugin installation is required.
## 0.2.0-r193

- Inspector/plugin panel header is now always visible and reachable.
- Inspector content scrolls inside its own body while Inspector/Stems/Metadata and the close button remain sticky.
- Fixed panel stacking so timeline/mixer layers cannot cover the plugin frame header.

## 0.2.0-r192

- Added multi-stage high-fidelity harmonic analysis after the selected base recognizer.
- Extended chord vocabulary: sevenths, diminished/half-diminished, augmented, sixths, suspensions, added/extended ninths, altered dominant chords.
- Added dedicated bass-chroma analysis for inversions and slash chords (for example C/E and G7/B).
- Added temporal stabilization and base-engine root priors to reduce transient/over-complex labels.
- Chord extraction progress now reports the individual harmonic-analysis stages.

## 0.2.0-r191

- Added a unique generated Chords/Accordi guide track with synchronized digital-piano playback from active project chord events.
- Repeated creation regenerates/reuses the same Chords track and consolidates old duplicates.
- Chords guide participates in the normal mixer, live controls, playback graph and VU metering.

## 0.2.0-r190

- Lyrics + Chords + Markers: clicking an already selected chord now deselects it; double-click still opens structured editing.

## 0.2.0-r189

- Replaced multi-HTMLMediaElement playback with one deterministic WebAudio AudioContext transport.
- Track/master/metronome VU meters now read the actual WebAudio graph.
- Mixer controls are live; rendered track FX are hot-swapped without restarting transport.
- Lyrics editor automatically syllabifies words visually for fine chord anchoring without changing persisted lyric text.
- Disabled lyric lines remain timing boundaries, so they never steal or hide chords from the preceding active line.

## 0.2.0-r188

- PDF Lyrics + Chords + Markers preview now renders the actual generated PDF pages, eliminating divergence from export.
- Native WebViews preview rasterized pages from the same PDF backend instead of a parallel HTML reconstruction.

## 0.2.0-r187

- Playback: removed periodic hard-seek synchronization that caused regular drop-outs in non-Render mode. Re-lock now occurs only at transport actions or after real decoder stalls.
- Render playback: switched from one immutable rendered master to processed per-track stems so volume, pan, mute and solo are live WebAudio controls.
- Insert controls: parameter sliders now schedule live processed-stem replacement while playback continues.
- Preview stems keep volume/pan/mute neutral server-side to avoid double-applying mixer controls.

## 0.2.0-r186

- Lyrics + Chords + Markers: automatic chords before the first sung word are no longer forced onto that word; explicit/manual anchors take precedence.
- Marker editing now includes marker color.
- PDF chords always use the Chords style and never inherit marker/section styling.
- Chords can be anchored to a character position inside a word when syllable timing is unavailable.
- Metronome creation is idempotent: a project can contain only one metronome track, which is regenerated/reused on repeated requests.

## 0.2.0-r185

- CI maintenance: removed unused imports from the compound-meter regression test so Ruff no longer stops the production workflow; revision metadata tests now validate alignment dynamically instead of hard-coding r184.

## 0.2.0-r184

- Lyrics + Chords + Markers: double-click words, chords, and markers to edit them.
- Lyrics text can be edited inline without changing timestamps.
- Chords anchored to deleted words/syllables are reassigned to the previous available token, then the next one, with line-start fallback.


## 0.2.0-r182
- Corrected metronome timing when changing meter from 4/4 to 6/8 (and other /8 signatures): the denominator no longer doubles the audible click rate.
- Manual time-signature BPM recalculation now resolves half/double-tempo ambiguity against the current project BPM, preventing unintended x2/x0.5 jumps.
- Compound meters 6/8, 9/8 and 12/8 retain their grouped accent behavior without changing pulse speed.
- Lyrics + Chords + Markers editor: keep only the combined view, remove duplicate Chords/Markers sections, and provide an explicit persistent vertical scrollbar.

## 0.2.0-r180
- Lyrics + Chords + Markers editor: persistent Save action in top toolbar and footer.
- Prevent accidental loss of unsaved editor changes on close.
- Make all editor action labels readable in native WebViews.
- Make the complete editor body vertically scrollable while keeping controls accessible.

## 0.2.0-r179
- Fixed Render playback echo by preventing parallel rendered-master and per-track audio paths.
- Stabilized non-render playback and track VU metering.
- Metronome and BPM/time-signature analysis now honor compound meters such as 6/8.
- Lyrics + Chords PDF preview/native button readability fixed; added configurable lyric line spacing.
- Added automatic marker extraction from the track context menu.
- MusicBrainz matches now expose richer hover details, scrolling and pagination (10/page).
- Lyrics + Chords graphical editor button readability improved and individual chords can be enabled/disabled independently.
- Delete tracks / Delete selected range moved into the Select/Split/Range/Ripple toolbar row.

## 0.2.0-r177
- Fixed unreadable Lyrics + Chords editor controls.
- Timeline selection/range overlays are now drawn only on selected tracks; the toolbar shows the selected-track count.
- Moved Delete tracks / Delete selected range into the compact upper editor toolbar.
- Added native OS-language detection with Auto/Italiano/English override and bilingual native UI translation.
# Changelog

## 0.2.0 — revision 175

- Main transport now exposes the project time signature directly next to BPM; changing it recalculates BPM using the selected meter.
- Plugins/Inspector frame can be closed with an explicit × button and reopened from the Plugins sidebar entry without losing plugin state; visibility is persisted in the project.
- Carries forward adaptive/persisted mixer height, per-track vertical resizing, previous/current/next lyrics/chords display options, and time-signature-aware BPM estimation/PDF metadata.
- Project export excludes muted tracks using the live project state, offers optional peak normalization for WAV/MP3/FLAC, includes an explicit Stop Preview control, keeps export-button labels readable, and uses a single atomic overwrite path in native mode.
- Native sidebar keeps Save project, hides redundant Save project locally, and preserves Save project as.
- Updated desktop/mobile build metadata to revision 175 and retains the GitHub Actions Ruff/coverage fixes.

## 0.2.0 — revision 173

- Project exports now omit tracks explicitly marked Mute; MTA slot planning and mapping ignore muted tracks as well.
- Added per-track vertical height resizing in the Tracks/timeline view, persisted in the project with a 78 px minimum/default.
- Native desktop sidebar now hides the redundant “Save project locally” action and exposes “Save project” for an explicit manual save of the current project.

## 0.2.0 — revision 153

- Standardized release identity into three independent fields: product version `0.2.0`, revision `153`, and 14-digit `BUILD_INFO`.
- Stable release tag convention is now `v0.2.0`; exact artifacts use `0.2.0-r153`.
- Propagated the convention across runtime metadata, CI/CD, Docker, Kubernetes, Windows/macOS installers and Android/iOS packages.
- Preserved the `.maeproj` association fix and realtime playback work from the preceding revision chain.

## 0.2.0-151

- Reworked realtime transport around an `AudioContext` master clock instead of using one track as the timing authority.
- Added background decoder/source prewarming when a project opens so Play normally starts without a visible buffering phase.
- Reduced startup buffering to the minimum decodable window near the cursor; deep buffering continues in the background.
- Tracks start muted, hard-lock to the transport clock, then fade in over 8 ms to avoid audible inter-track start skew.
- Sync monitoring now runs every 120 ms with tighter micro drift correction and hard relock only for meaningful drift or decoder recovery.
- Non-render playback starts from dry/direct sources immediately; enabled track FX are prepared in the background and hot-swapped with a short clock-locked crossfade.
- Master volume no longer forces a rendered preview; it stays a realtime Web Audio gain control. Rendered-master mode remains available through the explicit Render Preview toggle.
- Mute, Solo, Pan and Volume remain downstream realtime controls and therefore do not wait for server render or buffering.

## 0.2.0-150

- Project files now use the dedicated `.maeproj` extension instead of `.zip` / `.mta-project.zip`.
- New project saves/exports use MIME type `application/vnd.mta-audio-editor.project`; legacy `.mta-project.zip` and `.zip` project archives remain readable.
- Windows installer registers `.maeproj` with MTA Audio Editor and double-click launches the application with the selected project.
- macOS bundle declares the `.maeproj` document type and exported UTI `com.desalvo.mtaaudioeditor.project`.
- Native desktop startup consumes an associated project path and opens it automatically in the editor.
- Android and iOS declare the same project MIME/UTI for platform file association/document pickers.

## 0.2.0-149

- Restore New project activation: after creation the app now reopens the canonical project through the same `openP()` path used by Open project, immediately restoring Tracks, Mixer, timeline and toolbars.
- Native YouTube import adds operating-system clipboard fallback (macOS `pbpaste`, Windows native clipboard API, Linux Wayland/X11 fallback) plus explicit Paste buttons for URL and track-name fields.
- Redesign YouTube import into clear Source, Positioning and Rights sections with responsive layout for narrow native windows.

## 0.2.0-148

- Lyrics editor: insert new rows anywhere with **+ above** / **+ below** controls.
- Lyrics editor: add a dedicated **Split** action that divides a segment timing at its midpoint and creates an editable row below.
- Lyrics editor: delete any row before saving, with confirmation for non-empty rows.
- Chords editor now mirrors the Lyrics row workflow with **+ above**, **+ below**, **Split** and **Delete** on every chord row; Split creates an editable chord point at the temporal midpoint.
- Preserve word-level timing against the original lyric row even when rows are inserted or removed.

## 0.2.0-147

- Lyrics editor redesigned as a large structured, resizable editor instead of a one-line prompt.
- Lyrics rows expose Start, End and Text as separate editable fields; Chords and Markers use the same structured Time/Value workflow.
- Timed editors support `mm:ss.mmm` or seconds, add/remove rows, automatic sorting by start time and mobile-safe scrolling.
- Editing a Lyrics row invalidates stale per-word karaoke timing only for the changed row.

## 0.2.0-146

- Fix GitHub Actions Ruff S110 failures in native AI accelerator probing by logging non-fatal CUDA/MPS probe errors instead of silently passing.

## 0.2.0-145
- Lyrics/Chords extraction chooser stays open until a real background job exists and the progress dialog can show a concrete preparation/download/analysis state.
- Extraction progress now uses real audio time in 5-second chunks, with indeterminate progress while a model is being loaded/downloaded and monotonic percentages during analysis/sync/save.
- Native Open recent is persisted by the native bridge in `native-settings.json`, so recent projects survive WebView/app restarts.
- Lyrics/Chords extracted by background jobs are immediately persisted, reloaded into the UI, and synchronized to any bound native project archive so they survive the next launch.
- Added regression tests for timed-text JSON round-trip and native recent-project persistence.

## 0.2.0-144
- Lyrics extraction now defaults to OpenAI Whisper **base** (still user-selectable).
- Lyrics/Chords/Markers panel is responsive, wraps controls safely on narrow windows, and can expand into a dedicated full-size working window and return to the docked view.
- PDF preview no longer relies on an embedded PDF viewer in native WebViews; it renders a faithful printable HTML preview while keeping real PDF download/export unchanged.
- Native/web transport startup is faster for simple unprocessed tracks by playing the original project audio directly; dynamic prebuffer requirements were reduced and playback no longer waits for a full autosave before starting.
- Spacebar play/stop handling is captured more robustly across native WebViews.
- Mute/Solo changes now queue a second rendered-master refresh when a previous refresh is still running, so the latest mixer state is never dropped.
- Track context menu adds **Recalculate BPM from this track**, updating project/base BPM from the selected track.

## 0.2.0-143

- Native AI Models: pulsanti Lyrics/Chords con testo sempre leggibile nelle WebView native.
- Waveform timeline più densa: rendering per pixel visibile con interpolazione tra i picchi persistiti, mantenendo il rendering leggero.
- Lyrics e Chords: estrazione progressiva con output parziale live, progressbar e comando Annulla estrazione.
- Download modelli Lyrics/Chords tramite job con progressbar (indeterminata quando il backend non espone i byte totali).
- Accelerazione AI automatica: CUDA o Apple Metal/MPS quando disponibili, fallback CPU; Madmom prova il backend Torch accelerato prima del fallback NumPy.
- Madmom Deep Chroma/CNN: input convertito automaticamente in WAV PCM RIFF 44.1 kHz prima dell'analisi, eliminando gli errori sui contenitori MP3/M4A/AAC.
- Android metadata aggiornati a versionCode 20143 / versionName 0.2.0-143.

## 0.2.0-142

- Android CI: installa i package SDK reali `platforms;android-37.0` e `build-tools;37.0.0`, mantenendo compileSdk 37, AGP 9.1.1 e Gradle 9.3.1.
- Corretto il fallimento `Failed to find package platforms;android-37` sui runner GitHub Actions.

## 0.2.0-141

- Android toolchain aligned with androidx.core 1.19.1: compileSdk 37, AGP 9.1.1, Gradle 9.3.1, explicit API 37/build-tools install in CI.

## 0.2.0-140

- Fixed GitHub Actions Ruff regressions in sample-editor/native TLS code.
- Fixed chord dependency auditing for the commit-pinned non-PyPI madmom-infer package while retaining strict auditing of all resolved PyPI dependencies.
- Integrated Dependabot Android updates: androidx.core 1.19.1 and ONNX Runtime Android 1.30.0.

## 0.2.0-139

- Project Clip browser now starts collapsed and resets to collapsed whenever a project is created, opened or imported.
- Web Settings are robustly available to administrators and reload the session if needed before routing.
- Native desktop viewport is pinned to the application frame so accidental document scrolling cannot strand the UI below the top.

## 0.2.0-138

- Redesigned About dialog with a large application logo and documentation cover photo background that does not interfere with application information.
- Build identifiers now use the strict 14-digit `YYYYMMDDhhmmss` format.
- Native Settings buttons use explicit WebView-safe text styling.
- Settings is now available to normal web users with editor preferences, AI model management and account access; administrators also get server administration access.

## 0.2.0-137

- Export is now an on-demand dedicated dialog and is no longer kept as a persistent panel beside the mixer.
- Removed the vertical PROJECTS section from the sidebar.
- Added native-only Open recent under PROJECT / FILE, limited to projects that still exist in the native workspace.
- Web Open project now lists projects already active on the server; Open local project imports a project archive from the user's device.
- Native Open project keeps the filesystem-native project picker.

## 0.2.0-136

- Added a dedicated high-resolution waveform/sample editor opened from a track context menu or by double-clicking its timeline waveform.
- Added sample-addressable selection/readout plus cut, copy, paste and remove operations that create an isolated edited source for the selected track.
- Added in-place Pitch Correction (semitones + cents), pitch-to-scale Auto-Tune, Normalizer, Maximizer and 32-band Graphic EQ with factory presets and debounced processed previews.
- The sample editor uses a cached pre-insert track render and an adaptive min/max envelope pyramid so waveform detail follows the current zoom without plotting every audio sample.

## 0.2.0-135

- Fix native Madmom chord recognition bundling by explicitly freezing its lazily imported chord/chroma/CRF modules and checking real submodule availability.
- Clarify Chordino/NNLS-Chroma status: it uses no AI model and requires an installed Sonic Annotator + Chordino engine.
- Replace slow waveform full-audio fetch/decode rendering with zoom-aware drawing from persisted waveform peaks only.

## 0.2.0-134

- Fixed native Lyrics/Chords model download buttons and native TLS trust-store handling.
- Native TLS now uses the OS trust store via truststore, with verification kept enabled.
- Fixed Chords AI runtime by pinning madmom-infer to an upstream commit that actually contains chroma/chord modules; PyPI 0.2.0 predates them.
- Model download endpoints now return useful diagnostics instead of a generic HTTP 500.

## 0.2.0-133

- Track context menu: “Separa” now always opens a parameter wizard before starting, with explicit Demucs model, stem count and optional Lead/Backing model selection.
- Track stem jobs now pass the selected stem_count to the Demucs plugin instead of only storing it in the job metadata.
- Dynamic multitrack playback: removed aggressive 50 ms hard-seek correction that could starve buffering tracks after 1–2 seconds; buffering recovery is now conservative and drift correction is smooth.
- Dynamic multitrack playback: require a real buffered-ahead window before synchronized start and use a healthier active media clock when the previous clock stalls/ends.
- Transport Stop now invalidates pending playback/render startups immediately and aborts media loading where possible, preventing delayed restart after Stop.
- Improved timeline/audio synchronization during start, seek, resume and recovery from buffering.

## 0.2.0-132

- Mixer: separate fader, dB scale and realtime VU columns so meters never overlap the volume control.
- Mixer: always-visible graduated dB scale beside every track and Master fader.
- Mixer: double-clicking the volume fader resets the level to 0 dB for tracks and Master.
- Mixer: add realtime-only red PEAK LEDs, latched at 0 dBFS until meter reset/stop.

## 0.2.0-131

- Fix macOS Intel native dependency resolution: keep NumPy 1.26.4 while installing the chord engine so it remains compatible with Numba 0.61.2 / llvmlite 0.44.0 used by Whisper.

## 0.2.0-130

- Fixed macOS x64 native CI packaging for Whisper by pinning numba 0.61.2 and llvmlite 0.44.0 only on Darwin/x86_64, ensuring CPython 3.12 prebuilt wheels are used instead of an LLVM source build.

## 0.2.0-129

- Fixed GitHub Actions coverage gate after AI model manager growth by adding focused coverage for Lyrics/Chords model download, catalog, availability, cache and deletion paths.
- Kept the production coverage threshold at 70%; full suite now reaches 70.13%.

## 0.2.0-128

- Hide all Lyrics export controls until Lyrics exist.
- Show Lyrics+Chords TXT/ChordPro exports only when both Lyrics and Chords exist.
- PDF preview/download labels now reflect whether the document contains Lyrics only or Lyrics + Chords.
- Added defensive export guards for missing Lyrics/Chords.

## 0.2.0-127

- Added independent Lyrics and Chords reset actions with confirmation. Resetting clears both synchronized content and the corresponding engine/model provenance, without affecting the other analysis type or project rights metadata.
- Added inline in-app preview for the Lyrics + Chords PDF, using the exact same renderer as the downloadable export.
- Added responsive PDF preview styling for desktop and mobile web clients.

## 0.2.0-126

- Added unified on-demand model management for Lyrics (OpenAI Whisper) and Chords, with server storage in web deployments and local storage in native desktop applications.
- Added selectable Whisper models (tiny/base/small/medium/large-v2/large-v3/turbo), with large-v3 as default.
- Added explicit chord engines: Madmom Deep Chroma + CRF (default AI), Madmom CNN + CRF, Chordino / NNLS-Chroma and built-in MTA Chromagram.
- Chord extraction UI now always discloses the exact engine/model and checkpoint licensing before extraction.
- Added download/delete APIs and model-manager UI for Lyrics/Chords models; model choices also apply to Import & Separate workflows.
- Persist the last Lyrics and Chords engine/model used in project metadata.

## 0.2.0-125

- Fix lyrics extraction in production: OpenAI Whisper is now installed in Docker/server and native builds instead of being only an optional requirements file.
- Bundle the Whisper Python package in PyInstaller desktop applications; model weights remain on-demand and cached.
- CI audits the lyrics dependency set and production Docker smoke validation imports Whisper.
- Clarify in the UI that the selected Whisper model is downloaded on first use.

## 0.2.0-124

- Lead/backing vocal separation now uses selectable AI karaoke models by default via audio-separator 0.47.0.
- Default model: UVR-MDX-NET Karaoke 2; optional Mel-RoFormer Karaoke models are selectable.
- Models are downloaded on demand to server cache, or locally in native desktop mode.
- Center/side DSP is retained only as an explicit fallback.

## 0.2.0-123

- Added optional second-pass Lead Vocals / Backing Vocals separation after Demucs.
- Supports a configurable dedicated AI separator through MTA_LEAD_BACKING_COMMAND, with a deterministic FFmpeg center/side fallback.
- Added web workflow option and job metadata reporting the vocal split method.

## 0.2.0-122

- Fixed GitHub Actions Ruff failures in clip metadata probing and YouTube import job validation.
- Clip metadata probe failures are now logged instead of silently ignored.

## 0.2.0-121

- Project Clip Browser: added a collapsible per-clip details panel, collapsed by default.
- Persist technical clip information: semantic type, codec/container format, bitrate when available, duration, byte size, provenance, project-relative location and embedded metadata.
- Added editable per-clip notes stored in the project without changing track-to-clip `source_clip_id` associations.
- YouTube imports record the source URL as provenance; local file imports record the original filename.
- Existing project clips are backfilled conservatively via ffprobe and stored to avoid repeated probing.

## 0.2.0-120

- Project clip browser: rename reusable clips without changing existing track names or breaking associations.
- Track-to-library association is now explicit via stable `source_clip_id`, with automatic migration of existing projects.
- Added per-clip audio preview controls in the project clip browser.
- Added case-insensitive clip-name search and pagination with at most 10 clips per page.

## 0.2.0-119

- Added a reusable project Clip Browser containing audio assets independently from their timeline instances.
- A library clip can be inserted on the timeline any number of times without duplicating the source audio file.
- Dragging a clip to the timeline creates a new track at the horizontal drop time; touch devices get a dedicated pointer-drag handle, with a + button fallback that inserts at the current play cursor.
- Existing projects automatically backfill the clip library from current tracks.
- Deleting timeline tracks no longer deletes audio assets retained by the project clip library.

## 0.2.0-118

- Added server-side YouTube audio import for a single `youtube.com`/`youtu.be` video, using yt-dlp stable 2026.08.19.
- YouTube imports are audio-only, asynchronous, size-limited, restricted to validated HTTPS YouTube video URLs and reject playlist-only URLs.
- Added explicit user confirmation that the content may lawfully be downloaded/imported.
- Imported audio follows the normal track pipeline: ffprobe validation, duplicate detection, project original preservation, waveform generation, optional auto-sync and first-track BPM estimation.

## 0.2.0-117

- Fixed the Container production gate after the msgpack 1.2.3 dependency update: the CI runtime verification now expects msgpack 1.2.3, matching the Dockerfile and installed image.
- Quality/Ruff/unit-test behavior from 0.2.0-116 is unchanged.

## 0.2.0-117

- Fixed the Container production gate after the msgpack 1.2.3 dependency update: the CI runtime verification now expects msgpack 1.2.3, matching the Dockerfile and installed image.
- Quality/Ruff/unit-test behavior from 0.2.0-116 is unchanged.

## 0.2.0-116

- Fixed CI Ruff F821 in `app/codec.py` by importing `RightsRecord` for synchronized MTA metadata restoration.
- Preserved the 0.2.0-115 mobile context-menu behavior and multi-provider rights metadata features unchanged.

## 0.2.0-115

- Added iPhone/iPad and touch-device track contextual menus via a 600 ms long press on track headers and timeline lanes.
- Long-press is cancelled when the finger moves beyond a small threshold so normal scrolling does not accidentally open menus.
- Added a touch-friendly `⋯` menu button on every track as an accessible fallback; it is hidden for fine-pointer desktop users.
- Preserved desktop right-click behavior and reused the same track context-menu actions on all input methods.
- Increased contextual-menu touch targets on coarse-pointer devices and suppressed Safari touch callouts on context-enabled track surfaces.

## 0.2.0-114

- Rights metadata is explicitly multi-provider: one project can persist simultaneous repertoire records from SIAE, Soundreef and other configured providers without collapsing them into a single match.
- Project Info now shows every stored repertoire record and its provider, title/original title, authors, performers, publishers, identifiers and source.
- Lyrics + Chords PDF and ChordPro exports now include all stored fields for every selected provider record, not only a subset.
- Clarified in the repertoire UI that provider selections are search preferences while stored records are cumulative project metadata.

## 0.2.0-113
- Track colors and drag/drop ordering.
- Key/BPM metadata in lyrics/chords PDFs and transposition-aware chord export.

## 0.2.0-97

- Added native on-device stem separation for iPhone/iPad using Core ML-compatible Demucs models.
- Added Auto / Local / Server mobile execution modes with automatic server fallback.
- Added authenticated model provisioning and on-device model compilation/cache.
- Added chunked 44.1 kHz stereo inference with overlap-add and WAV stem import into the project.
- Added conservative device-aware Auto stem recommendations and a 12-minute local safety limit.
- Added `scripts/export_demucs_coreml.py` documenting/exporting the expected Core ML model contract.

## 0.2.0-81

- Added persistent editable per-track MTA slot assignment in the Track Inspector.
- Export suggestions now honor explicit track slots and confirmed mappings update the track slot preference.
- Factory FX presets now expose schema-valid parameter values to the client; changing preset immediately refreshes visible controls.
- Added synchronized rotary knob + numeric controls for continuous plugin parameters, while the 32-band EQ keeps dedicated faders.
- Expanded the IT/EN user manuals: MTA = Multi Track Audio, MTA8/MTA16 creation, project/single-track exports, online/mobile authentication/TOTP scope, track slot workflow and FX controls.
- README now links directly to all IT/EN PDF manuals and includes an English section.
- Replaced documentation UI screenshots derived from the historical mockup with captures rendered from the current application template/JS/CSS and a deterministic demo project.
- Updated MTA format documentation and data/API/architecture references.
- Regenerated all IT/EN PDF manuals and checked section-heading orphan candidates.

## 0.2.0-73

- CI: remove the stale unused `revision` assignment in the waveform import fallback so Ruff F841 passes without suppressing the rule.

## 0.2.0-73

- CI: suppress Ruff/Bandit S310 on both `urllib.request.Request` construction and `urlopen`, only after strict HTTPS/provider-host validation in `_validate_oauth_endpoint`.
- Keeps the OAuth endpoint allowlist, HTTPS-only policy, no embedded credentials, and port 443-only validation introduced in 0.2.0-69.


## 0.2.0-73
- Waveform cache resa esplicitamente persistente e validata all'apertura: i picchi salvati nel progetto vengono mostrati subito e la revision server-side rigenera automaticamente solo waveform mancanti o obsolete, salvando il risultato nel progetto.
- La revisione waveform generata durante import/metronomo usa ora la stessa firma track-aware (sorgente + insert) usata per la validazione successiva.
- Il Play/Preview resta indipendente dalla disponibilità o dal calcolo delle waveform.
- Rimosso il pulsante Record dalla transport, non essendo associato ad alcuna funzione di registrazione.
- Aggiunti Mute all / Unmute all, Solo all / Unsolo all e Bypass all FX / Enable all FX per tutti gli insert di traccia e master. Il cambio globale degli FX invalida e rigenera le waveform delle tracce interessate.

## 0.2.0-73

- Security/CI fix for social OAuth HTTP calls: endpoints are now restricted to HTTPS and to the explicit Google, GitHub and Facebook provider hosts before any network request.
- Ruff S310 is suppressed only on the validated `urlopen` call, with regression coverage for rejected schemes, credentials, ports and untrusted hosts.

## 0.2.0-68

- Added optional OAuth 2.0 login/registration with Google, Facebook and GitHub; all providers are disabled by default.
- Social registrations trust only a provider-supplied verified email, skip local email verification, and remain inactive until administrator approval.
- Added signed, short-lived OAuth state bound to an HttpOnly browser cookie and persistent provider/subject identity mapping.
- Existing local accounts are never auto-linked solely by matching email.
- New registrations notify administrators when SMTP is configured; administrator approval sends the activation email to the user.
- Added Docker/Kubernetes defaults and `docs/SOCIAL_LOGIN.md` with provider callback and enablement instructions.

## 0.2.0-68

- Auto-save enabled by default, configurable in desktop Settings; manual Save remains available.
- Session Undo/Redo with standard shortcuts.
- Timeline Cut/Copy/Paste/Remove for selected ranges/tracks.
- Fixed selected-track checkbox lookup.

## 0.2.0-68

- Fixed desktop-native save-location chooser by waiting for the pywebview JS bridge instead of silently returning while the bridge is still initializing.
- Import & Separate now requires and opens a native save destination chooser when the destination is a new project.
- Renamed Native settings to Settings and made native detection/session/bridge readiness consistent.
- Grouped Import MTA, Import Audio, Import & Separate, Tracks, Plugins and Mixer into a dedicated collapsed-by-default EDIT / IMPORT / MIX sidebar section.
- Tracks, Plugins and Mixer now perform explicit navigation/focus actions and report when a project/track is required.

## 0.2.0-68

- Portato a 1024 MB (1 GiB) il limite predefinito di import/upload per server, Docker e Kubernetes.
- `MTA_MAX_UPLOAD_MB` resta configurabile in Docker; il wizard Kubernetes configura coerentemente applicazione e Ingress NGINX/HAProxy fino a 10240 MB.
- Le app desktop native hanno ora **Native settings** con limite import/upload configurabile 1–10240 MB, persistente e applicato immediatamente senza riavvio.
- Il limite continua a essere verificato sia sul `Content-Length` sia durante la copia streaming del file, evitando di caricare l’intero upload in RAM.

## 0.2.0-68

- Corretto il secondo errore Android rilevato nel run GitHub Actions 37057175276: il progetto usa dipendenze AndroidX ma non abilitava `android.useAndroidX`.
- Aggiunto `mobile/android/gradle.properties` con AndroidX abilitato e Jetifier disabilitato, dato che le dipendenze del progetto sono già AndroidX.
- Aggiunto test regressivo per impedire la rimozione accidentale della configurazione AndroidX.

## 0.2.0-68

- Il menu contestuale di una traccia include anche `Rimuovi`, per eliminare la traccia selezionata dal progetto.

- Aggiunti input numerici sincronizzati con gli slider del volume per tracce, Inspector, Mixer e Master; valori ammessi da -60 a +12 dB con autosave.


- `Import Audio` ora avvia automaticamente l'import immediatamente dopo la scelta del file, senza richiedere un secondo click.
- `Delete tracks` ora elimina realmente le tracce selezionate dal progetto; non richiede più una selezione temporale.
- `Delete song segment` mantiene invece il comportamento di cancellazione intervallo/ripple sulla timeline.

- Added full multi-user authentication with a responsive photographic login based on the approved mockup.
- Added self-registration with mandatory email confirmation and administrator approval before activation.
- Added `admin`/`user` roles, admin-only user management, activation/deactivation, role changes and deletion safeguards that preserve at least one active administrator.
- Added optional RFC 6238 TOTP with in-app secret generation and QR-code enrollment.
- Added user profile management, email-change reverification/reapproval, password change and email password reset.
- Added SMTP/STARTTLS/SMTPS configuration with optional credentials, connection test, confirmation mail and activation notifications to all active administrators with confirmed email addresses.
- Added persistent SQLite authentication/session data on the application volume and HttpOnly/SameSite application sessions while keeping HTTP Basic only for operational compatibility.
- Updated Docker Compose and Kubernetes bootstrap configuration to include the administrator email.
- Preserved the previous Python 3.14/Trixie, CPU-only PyTorch, CI security, Kubernetes TLS and MTA reverse-engineering work.

# Changelog

## 0.2.0-13

- Fixed Ruff 0.16.9 CI failures in the standalone Kubernetes wizard: removed an unused import and documented narrow S310/S606 suppressions for the hard-coded HTTPS self-update URL and intentional shell-free self-restart.
- Kept the Python 3.14 production/CI baseline while making dependency resolution deterministic on GitHub-hosted runners.
- Pinned Pydantic to 2.12.5 (pydantic-core 2.41.5), a stable Python 3.14-compatible pair, after the 2.13.5/core 2.46.5 combination intermittently failed to resolve in the Quality job.
- Added a Dependabot guard against Pydantic 2.13.x/2.14.x until the CPython 3.14 production gate is deterministic.
- Moved the production and CI baseline from Python 3.11 to Python 3.14, absorbing the previous Docker Dependabot PR.
- Updated NumPy to 2.5.3 and aligned the dependency policy with the Python 3.14 baseline, absorbing the remaining grouped Python dependency PR intent.
- Split Kubernetes assets into Namespace, PVC, Deployment and Service resources and added Kustomize base/overlays.
- Added NGINX Ingress and HAProxy Ingress examples.
- Added a standalone standard-library Kubernetes manifest wizard with self-update, automatic restart after update, persistent last-used values, nodeSelector support, StorageClass selection and local Kustomization output.
- Added wizard generation tests and security notes for locally persisted/generated credentials.


## 0.2.0-10

- Resolved the two open Dependabot proposals without changing the 0.2.x Python 3.11 support baseline.
- Incorporated compatible dependency updates from PR #4: Demucs 4.1.0, pytest 9.1.1, pytest-cov 7.1.0, Ruff 0.16.9, Bandit 1.9.4, pip-audit 2.10.1 and WeasyPrint 70.0.
- Kept NumPy at 2.4.6 because NumPy 2.5.x requires Python >=3.12.
- Kept the production base image on python:3.11-slim-bookworm instead of PR #1's Python 3.14 proposal.
- Added Dependabot ignore policy for Python 3.12+ Docker bases and NumPy 2.5+ while the 0.2.x compatibility policy remains Python 3.11.
- Fixed Gitleaks pull-request scans by checking out full Git history in the security job.
- Updated the Docker stem-plugin smoke import for Demucs 4.1, which no longer requires torchaudio for inference.
- Retained setuptools 84.0.0 / wheel 0.48.0 runtime hardening for the previous Trivy findings.

## 0.2.0-9

- Fixed the current Trivy production-image gate by upgrading runtime packaging tooling to `setuptools==84.0.0` and `wheel==0.48.0`.
- `setuptools 84.0.0` vendors `jaraco.context 6.1.0` and `wheel 0.46.3`, eliminating CVE-2026-23949 and CVE-2026-24049 reported against the base image's `setuptools 79.0.1`.
- Added a Docker build-time import smoke test for core runtime modules and optional Torch/Torchaudio stem-separation modules.
- Retained all 0.2.0-8 MTA reverse-engineering, security, documentation and CI improvements.

## 0.2.0-8

- Consolidated the GitHub Actions fixes for Python 3.11 and current action tags, including Trivy `v0.36.0`, CodeQL v4 and NumPy 2.4.6.
- Hardened XML parsing with `defusedxml` and replaced silent exception swallowing with explicit logged fallbacks.
- Upgraded proprietary MTA analysis with a corpus-verified 256-byte shared keystream recovered from COLORS.
- Decoded COLORS normal records as four decimal centisecond digits plus three decimal progressive highlight-position digits and minute carry; special sentinel values remain read-only/undocumented.
- Added corpus-verified LYRICS/CHORDS decoding with monotonic minute/centisecond timing and XOR-0x30 text/chord recovery.
- Added MIDITK decoding to byte-exact Standard MIDI plus MIDI header, PPQ, track-length, tempo and Marker meta-event analysis.
- Added `docs/MTA_FORMAT_RESEARCH.md` and `docs/PROJECT_ARCHITECTURE.md` and updated online/PDF manuals with current compatibility boundaries.
- Retained conservative write policy: unknown fields and proprietary writer semantics are preserved, not synthesized, until hardware round-trip validation is complete.

## 0.2.0-6

- Fixed current GitHub Actions references and Python 3.11 compatibility.
- Added `defusedxml` for untrusted XML parsing and explicit exception logging/fallbacks.
- Corrected Python 3.11-incompatible test syntax reported by Ruff.

## 0.2.0-5

- Added verified structural parsing for stock M-Live SYL/XML attachments.
- Added read-only LYRICS/CHORDS decoding and initial COLORS keystream/timing analysis.
- Added MtxInfoData parsing and conservative EBML FileData attachment fallback.

## 0.2.0-4

- Added Delay, Lexicon-style Reverb, Room/Ambience, 32-band Graphic EQ, Amplify, Stereo Imager, Maximizer/Loudness, Mastering Wizard, De-Noise and Crackling Cleaner.
- Added factory presets and persistent validated user presets for every insert processor.
- Added parameter editor and reversible Auto Mix with Balanced/Studio/Live/Gentle profiles.

## 0.2.0-3

- Removed the MTA8/MTA16 slot limit from the editing/mixing workspace.
- Added explicit MTA output-slot mapping and many-to-one track merge during export.
- Added independent WAV/MP3/FLAC track export and FLAC master export.
- Added the first Matroska/SYL reverse-analysis reports and binary diff tooling.

## 0.2.0-2

- Added the photographic DAW interface, mixer and master preview.
- Added direct MP3/WAV track import/replacement and Demucs stem separation.
- Added per-track/master insert chains and WAV/MP3 master export.

## 0.2.0-1

- Added production CI/CD, CodeQL, Dependabot, SBOM/provenance and security gates.
- Added default-on authentication, request-integrity checks, upload/path hardening and non-root container deployment.
- Added integrated user/admin online and PDF documentation.

## 0.2.0

- Added non-destructive clip editing, arbitrary range deletion, ripple editing, track import/replace/sync, history/timeline events and initial MTA import/export preservation model.

## 0.1.0

- Initial FastAPI/FFmpeg MTA8/MTA16 web editor prototype.

## 0.2.0-68

- Kubernetes wizard: HAProxy ingress now always emits `kubernetes.io/ingress.class: haproxy` in addition to `spec.ingressClassName: haproxy`.
- Reverse-engineering notes: confirmed the 181392 ns Matroska timecode scale, 40 MP3 frames per Cue interval, exact 320 kbit/s frame/SimpleBlock sizing, and frame-major per-track interleaving evidence.

## 0.2.0-73
- Fixed macOS ARM native project dialogs so interacting with/selecting the default project name cannot be interpreted as a backdrop action.
- Native filesystem actions now wait for the pywebview `pywebviewready` event and tolerate slower WebKit bridge injection (up to 15 seconds), fixing transient “Bridge nativo non ancora disponibile” errors.
- New Project and Import & Separate modal actions now use explicit non-submit buttons and protected modal event propagation.

## 0.2.0-113
- Fixed Import & Separate current-project type detection in the UI.
- Native desktop Demucs splitting now uses the upstream Demucs model resolver/cache directly instead of the MTA model server.
- Re-importing an already stored source now reuses the existing project file and starts separation even when the source is not on the timeline.

## 0.2.0-r181

- Lyrics + Chords + Markers editor: moved per-event Modify/Enable-Disable/Merge/Delete/Restore actions to context menus for lyric lines, individual chords, and markers.
- Added context-menu marker creation with required start time and optional end time.
- Lyric line timestamps are directly clickable/editable with m:ss.mmm / mm:ss.mmm validation.
- Updating lyric times preserves manual chord anchors.

## 0.2.0-r183
- PDF Lyrics + Chords + Markers preview rebuilt as native-WebView-safe HTML preview.
- Fixed chord styling when a PDF page begins with a chord row.
- Granular chord anchors: line start/end, word/syllable, and chord-to-chord sequences.
- Editor preserves scroll position after operations; added cut/copy/paste and undo/redo.
- Moved Dividi qui to the word context menu and compacted editor rows/timestamps.
- Added saving-in-progress overlay and close protection while persistence completes.

- Edit Lyrics / Edit Chords / Edit Markers now open scrolled to the event nearest the current timeline/playhead position, without moving the transport.

## 0.2.0-r245
- Chords: refresh starts after project PUT, without waiting for native synchronization.
- Fast WAV patch updates only affected samples and waveform envelope bins.
- Serialized generated-Chords refresh requests to prevent overlapping operations.
