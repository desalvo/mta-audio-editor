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
# 0.2.0 · Revision 154

- Fixed extracted chords being lost by stale hidden timed-text fields before persistence; extracted chords now populate the Chords list immediately.
- Fixed Whisper lyrics extraction on Apple MPS by keeping inference in float32 and transparently retrying on CPU when upstream MPS code attempts an unsupported float64 tensor conversion.
- BPM values are now rounded to whole numbers in the project UI and BPM-estimation endpoints.
- Fixed YouTube import: the Import audio button now sends a proper JSON request and gives launch feedback.
- YouTube Paste buttons have explicit readable styling; standard Ctrl/Cmd copy/cut/paste/select shortcuts are preserved inside text inputs.
- Moved PROJECT / FILE above EDIT / IMPORT / MIX in the vertical sidebar.

# 0.2.0 — revision 153

- Adopted the final release identity convention: public product version `0.2.0`, source/package revision `153`, and the existing 14-digit `BUILD_INFO` as the independent build identifier.
- Stable Git/GitHub release tag is `v0.2.0`; exact downloadable artifacts use `0.2.0-r154` when the revision must be visible.
- Runtime metadata, native installers, Android/iOS packages and Docker builds now keep version, revision and build as separate concepts.
- The Android regression test derives its package identity from `VERSION` + `REVISION`, avoiding hardcoded revision failures.
- Preserved the Windows `.maeproj` Inno Setup quoting fix and all realtime playback improvements from the preceding revisions.

# 0.2.0-152

- Fixed the Native Windows installer Inno Setup compile failure in the `.maeproj` file association.
- The Windows open-command registry value now uses valid Inno Setup embedded quoting, producing the intended command line `"MTA Audio Editor.exe" "%1"` for double-click project opening.
- Preserved the dedicated `.maeproj` format, MIME/UTI associations, native startup project opening, and all 0.2.0-151 realtime playback improvements.
- Aligned Android and iOS package metadata to 0.2.0-152, regenerated Windows version metadata, and refreshed the non-tag container fallback version.

# 0.2.0-151

Questa release ridisegna il transport per ridurre drasticamente la latenza di Play senza sacrificare la sincronizzazione. Il clock del progetto è ora indipendente dai decoder delle singole tracce e usa `AudioContext.currentTime`; i decoder vengono pre-riscaldati in background, l'avvio richiede soltanto un piccolo buffer vicino al cursore e le tracce vengono rese udibili solo dopo il primo lock temporale. Gli insert di traccia possono essere preparati mentre il playback dry è già in corso e vengono sostituiti con un breve crossfade sincronizzato.

# MTA Audio Editor 0.2.0-150

- Project files now use the dedicated `.maeproj` extension instead of `.zip` / `.mta-project.zip`.
- New project saves/exports use MIME type `application/vnd.mta-audio-editor.project`; legacy `.mta-project.zip` and `.zip` project archives remain readable.
- Windows installer registers `.maeproj` with MTA Audio Editor and double-click launches the application with the selected project.
- macOS bundle declares the `.maeproj` document type and exported UTI `com.desalvo.mtaaudioeditor.project`.
- Native desktop startup consumes an associated project path and opens it automatically in the editor.
- Android and iOS declare the same project MIME/UTI for platform file association/document pickers.

## 0.2.0-149

Newly created projects are now activated through the exact same load path as Open project, so the complete editor workspace appears immediately after creation. Native YouTube import can read the real operating-system clipboard when the embedded WebView clipboard API is unavailable, and its dialog has been reorganized into clearer responsive sections.

## 0.2.0-148

The structured Lyrics editor now supports inserting rows above or below any existing segment, splitting a timed segment in place, and deleting rows before committing changes. The Chords editor now provides the same per-row **+ above / + below / Split / Delete** workflow; splitting inserts a new editable chord point at the midpoint of the current harmonic interval. Suggested timestamps remain editable. Word-level timing preservation follows the original lyric row identity rather than its current table position.

## 0.2.0-147

The Lyrics/Chords/Markers editor is now a dedicated structured workspace. Lyrics can be edited row-by-row with separate Start, End and Text columns in a large resizable window; Chords and Markers get equivalent Time/Value editing. Rows can be added, removed and reordered automatically by time, with responsive/mobile scrolling.

# 0.2.0-146

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

# 0.2.0-142

- Android CI: installa i package SDK reali `platforms;android-37.0` e `build-tools;37.0.0`, mantenendo compileSdk 37, AGP 9.1.1 e Gradle 9.3.1.
- Corretto il fallimento `Failed to find package platforms;android-37` sui runner GitHub Actions.

## 0.2.0-141

- Fix Android CI preflight after Dependabot updates by moving to the supported API 37 / AGP 9.1.1 / Gradle 9.3.1 toolchain.

## 0.2.0-140

- CI reliability fixes for Ruff and dependency audit.
- Android dependency refresh from Dependabot PR #9: androidx.core 1.19.1 and onnxruntime-android 1.30.0.

## 0.2.0-139

- Clip del progetto collapsed by default on every project open.
- Web admin Settings availability hardened.
- Native WebView viewport recovery prevents the whole app page from becoming stuck scrolled downward.

## 0.2.0-138

- Redesigned About dialog with a large application logo and documentation cover photo background that does not interfere with application information.
- Build identifiers now use the strict 14-digit `YYYYMMDDhhmmss` format.
- Native Settings buttons use explicit WebView-safe text styling.
- Settings is now available to normal web users with editor preferences, AI model management and account access; administrators also get server administration access.

## 0.2.0-137

Export and project navigation were simplified: Export opens only when requested, PROJECTS was removed from the sidebar, native desktop gains Open recent, and the web client cleanly separates server projects from local project imports.

## 0.2.0-136

- Added a dedicated high-resolution waveform/sample editor opened from a track context menu or by double-clicking its timeline waveform.
- Added sample-addressable selection/readout plus cut, copy, paste and remove operations that create an isolated edited source for the selected track.
- Added in-place Pitch Correction (semitones + cents), pitch-to-scale Auto-Tune, Normalizer, Maximizer and 32-band Graphic EQ with factory presets and debounced processed previews.
- The sample editor uses a cached pre-insert track render and an adaptive min/max envelope pyramid so waveform detail follows the current zoom without plotting every audio sample.

## 0.2.0-135

- Native Chords: fixed missing `madmom_infer.features.chords` in frozen builds and improved Chordino availability messaging.
- Waveforms: previews now render from cached project peaks with adaptive decimation instead of re-downloading and decoding every audio file.

## 0.2.0-134

Native AI text-analysis fixes: readable model-download controls, OS-backed TLS validation for model downloads, and a working Madmom chord/chroma runtime.

## 0.2.0-133

- Separation from a track context menu is no longer implicit: all separation parameters must be confirmed first.
- Fixed severe multitrack playback stalls, delayed/ineffective Stop during Render preparation, and timeline/audio drift caused by repeated hard seeks while tracks were buffering.

## 0.2.0-132

- Improved mixer fader/VU layout, added permanent dB scales, double-click unity-gain reset, and realtime peak LEDs for tracks and Master.

## 0.2.0-131

- Fixed the remaining macOS x64 GitHub Actions failure caused by madmom-infer upgrading NumPy beyond the supported Numba range.

## 0.2.0-130

- macOS Intel native builds now use wheel-backed Whisper JIT dependencies, avoiding llvmlite source compilation and missing-LLVM failures.

## 0.2.0-129

- CI coverage regression fixed without lowering the quality gate. AI model manager coverage increased to 99%.

## 0.2.0-128

Lyrics/Chords export controls are now context-aware: Lyrics exports require Lyrics, while Lyrics+Chords exports require both datasets. PDF actions are labelled according to the actual content.

## 0.2.0-127

Lyrics and Chords can now be reset independently so they can be rewritten or extracted again. The Lyrics + Chords PDF can also be previewed inline in the web app before downloading.

## 0.2.0-126

Lyrics and Chords now use the same managed, on-demand model workflow as the other AI features. Web deployments cache models on the server; native desktop editions cache them locally. Chord extraction explicitly identifies the engine/model before it runs.

## 0.2.0-125

Fixes the "Lyrics extraction requires the OpenAI Whisper engine in this runtime" error in production builds. Server and desktop-native packages now include the Whisper engine; only model weights are downloaded on demand.

## 0.2.0-124

Selectable on-demand AI models for Lead Vocals / Backing Vocals separation, with server/native-local model storage.

## 0.2.0-123

- Import & Separate can now split the Demucs vocals stem into Lead Vocals and Backing Vocals.

## 0.2.0-122

- CI fix: Ruff-clean clip metadata probing and YouTube import validation.

## 0.2.0-121

The project clip browser now exposes a collapsed-by-default technical details section for every clip, including type, format, bitrate, HH:MM:SS duration, exact byte size, provenance, current project-relative location, embedded tags and editable notes. Track associations remain ID-based and are unaffected by clip metadata edits.

## 0.2.0-120

The project clip browser now supports safe renaming, audio preview, name search, and 10-item pagination. Track-to-clip relationships use a stable asset ID instead of names.

## 0.2.0-119

- New project Clip Browser for reusable audio assets. Drag a clip onto the timeline to create another track instance at that position, including touch drag support on iPhone/iPad.
- The same clip may be used repeatedly while keeping a single underlying project audio asset.

## 0.2.0-118

- Import Audio from YouTube is now available from the sidebar and editor toolbar. Paste one YouTube video URL, confirm authorization, and the extracted audio becomes a normal project track.

## 0.2.0-117

- CI production-container verification aligned with the pinned msgpack 1.2.3 runtime package.

## 0.2.0-117

- CI production-container verification aligned with the pinned msgpack 1.2.3 runtime package.

## 0.2.0-115

- Added iPhone/iPad and touch-device track contextual menus via a 600 ms long press on track headers and timeline lanes.
- Long-press is cancelled when the finger moves beyond a small threshold so normal scrolling does not accidentally open menus.
- Added a touch-friendly `⋯` menu button on every track as an accessible fallback; it is hidden for fine-pointer desktop users.
- Preserved desktop right-click behavior and reused the same track context-menu actions on all input methods.
- Increased contextual-menu touch targets on coarse-pointer devices and suppressed Safari touch callouts on context-enabled track surfaces.

## 0.2.0-113

- Per-track user-selectable colors, persisted in project files.
- Drag-and-drop track reordering, persisted across save/reopen.
- Lyrics + chords PDF now reports current project key and BPM.
- Project transposition is applied non-destructively to displayed/exported chords and effective key.
- MTA and karaoke exports receive transposed synchronized chords while source analysis data remains intact.
- Project Info now allows editing the project key explicitly.

## 0.2.0-113

- Integrated the safe dependency updates from Dependabot PR #6: FastAPI 0.142.2 and msgpack 1.2.3.
- Kept macOS Intel on torch/torchaudio 2.2.2 because newer official x86_64 macOS wheels are not available for the supported stack.
- Prevented Dependabot from grouping torch/torchaudio platform-specific upgrades with ordinary Python updates.
- Restricted grouped Python and Android dependency updates to minor/patch releases so major toolchain upgrades are reviewed separately.
- Supersedes Dependabot PR #6 and PR #8 without merging their incompatible grouped upgrades.
- Includes the Android BuildConfig and iOS 15/Core ML compiler fixes introduced in 0.2.0-106.

## 0.2.0-105

- Added centralized, periodically synchronized Demucs model catalogue with official Demucs families and manifest-provided mobile/native artifacts.
- Added server model blacklist with managed-storage deletion and web/mobile/native visibility filtering.
- Added server administration UI for model update/blacklist management.
- Added local model management hooks for desktop, iOS/iPadOS, and Android (download/update/delete).
- Native/mobile clients download missing models on demand for splitting.

## 0.2.0-105

- Automatic periodic Demucs mobile-model refresh in Docker/Kubernetes with HTTPS manifest, SHA-256 verification and atomic replacement.
- iPhone/iPad model refresh is periodic and Wi-Fi-only by default, configurable in Options.
- Android receives equivalent periodic ONNX model provisioning, Wi-Fi-only by default.
- Added New project directly inside PROJECT / FILE.

## 0.2.0-105

- Fixed native macOS project destination dialogs: pywebview now uses a valid ZIP filter while preserving the .mta-project.zip extension.
- Prevented accidental utility-modal dismissal when selecting/editing the project name.
- Reworked non-Render playback buffering to use short adaptive pre-roll rather than canplaythrough for every track.
- Reworked multi-track drift correction to use smooth playback-rate nudging and only rare hard seeks.
- Mixer volume, pan, mute and solo are applied immediately in WebAudio and no longer depend on buffering.

## 0.2.0-97

- Added native on-device stem separation for iPhone/iPad using Core ML-compatible Demucs models.
- Added Auto / Local / Server mobile execution modes with automatic server fallback.
- Added authenticated model provisioning and on-device model compilation/cache.
- Added chunked 44.1 kHz stereo inference with overlap-add and WAV stem import into the project.
- Added conservative device-aware Auto stem recommendations and a 12-minute local safety limit.
- Added `scripts/export_demucs_coreml.py` documenting/exporting the expected Core ML model contract.

## 0.2.0-96

- Added configurable stem count: Auto, 2, 4, 6, or 8.
- Added 2-stem Demucs mode (vocals/accompaniment), standard 4-stem mode, and 6-stem extended mode.
- 8-stem mode is exposed only through a compatible backend model configured with `MTA_DEMUCS_8_MODEL`; no synthetic/duplicate stems are generated.
- Persisted the preferred stem count in the application and reused it for full-song and single-track separation.
- Documented identical iPhone/iPad controls; the current mobile build delegates heavy Demucs processing to the server.

## 0.2.0-95

- Fixed GitHub Actions documentation regression test to validate the current bilingual cover assets.
- Added meaningful audio-engine regression tests for media duration, project duration, clip initialization, track shifting and metronome WAV generation.
- Restored CI coverage above the 70% production gate without lowering the configured threshold.
- Updated the production-image fallback version to 0.2.0-95.

## 0.2.0-93

- README.md is now the primary English README; README_IT.md contains the Italian version.
- Added direct README links to user/admin manuals, IT/EN brochures and complete IT/EN MTA format specification PDFs.
- Expanded both product brochures to two pages with operating modes, limits, server/mobile behavior, MTA limits and resource considerations.
- Added full detailed MTA format specification PDFs in Italian and English.

## 0.2.0-92

- Updated documentation cover pages to use the approved mockup-style artwork for IT/EN user and administrator manuals.
- Regenerated the documentation package with refreshed cover assets and updated version/build information.

## 0.2.0-81

- Added unrestricted **Multitrack DAW** project format alongside MTA8/MTA16.
- DAW projects can export WAV/MP3/FLAC directly and choose MTA8 or MTA16 only when an MTA output is requested.
- Selecting a track no longer causes waveform validation/recalculation; persisted waveforms are validated once per project and recomputed only when missing or explicitly invalidated.
- Plugin numeric parameter boxes commit on Enter or focus loss; knobs commit on release/change.
- Removed redundant static volume bars from mixer channels and enlarged the faders.
- Regenerated real-UI documentation screenshots and corrected screenshot text artifacts.
- Reworked PDF covers with an artistic professional DAW photograph behind the existing application data plate and a large application title/logo.

## 0.2.0-81

- Completely expanded the integrated **User Manual** in Italian and English with end-to-end workflows, screenshots, diagrams, examples, troubleshooting, glossary, MTA profiles, synchronized playback and live mixer behavior.
- Expanded the **Administrator Manual** in Italian and English with architecture, deployment, security, storage/backup, audio pipeline, desktop/mobile clients, MTA format, observability, upgrades and CI/CD.
- Rebuilt all four documentation PDFs with a photographic full-page cover, application logo, version/build/creator/license/repository plate and supported-platform badges.
- Added PDF pagination safeguards and verified the generated manuals for orphan headings.
- Consolidated the bilingual MTA format specification with container, media transport, MP3/SimpleBlock, Cluster/Cues/SeekHead, Xing/Info, CRC, SYL/LYRICS/CHORDS/COLORS/MIDITK, MtxInfoData, NoteOn, PreCntUSec, Click/Melody profiles, reader/writer algorithms and validation invariants.
- Updated format documentation to present the MTA specification as corpus-validated technical documentation without describing it as reverse engineering.
- Mobile Android and iOS/iPadOS clients now use the built-in service automatically on first launch, never prompt for a server URL during installation/first run, and never display the built-in default address. A custom URL can be set later in Server settings and may be displayed/edited because it is user-configured.
- Added documentation regression coverage for bilingual manuals, hidden default mobile URL and format-document wording.

## 0.2.0-77

- Added transport **Torna all'inizio** control.
- Dynamic playback now buffers every track before starting, starts all tracks together and continuously corrects decoder drift against a shared transport clock.
- Added visible buffering/synchronization status before Play.
- Render playback now keeps a dedicated master transport clock, restoring Follow during Render and across seamless rendered-master refreshes.
- Added persistent MTA device profiles: Merish5/Xynthia2, B.Beat/DIVO family, Merish5+ PLUS MTA16 and Generic.
- MTA8 export physically pads missing streams with silence when needed so Click/Melody stay at the documented stream positions.
- Merish5/Xynthia2 profile uses Melody 7 / Click 8; B.Beat/DIVO family uses Click 7 / Melody 8.
- MTA16 does not invent a universal Click/Melody position; the Merish5+ PLUS profile requires explicit mapping when Click/Melody are present.
- Imported MTA8 files infer the device profile when the Click/Melody order is unambiguous.

## 0.2.0-76

- Volume, pan, mute/solo and FX chain state now update while Play remains active.
- Track FX changes hot-swap the affected rendered preview at the current cursor; Render mode automatically refreshes the master.
- Master fader is applied relative to the rendered baseline, avoiding double gain.
- Fixed VU meters with Render enabled: analyser paths keep the actual audio level and only the monitor destination is muted.
- MTA import no longer guesses Click/Melody solely from slots 7/8; explicit metadata and track names take precedence.
- Documented M-Live device-profile difference for Click/Melody ordering.

## 0.2.0-75

- Native MTA import now asks where to save the project before the import starts; cancelling the save dialog cancels the import.
- Native project file bindings are persisted across application restarts and are displayed in **Info progetto**.
- Added **Info progetto** under Project / File with name, project ID, home/workspace, location, type, duration, track count, artist, BPM, key and autosave state.
- Mute/solo now update the active WebAudio graph immediately during playback. All tracks stay instantiated and audibility is controlled by gain, so unmute/unsolo no longer requires Stop/Play.
- Rendered-master preview automatically refreshes after live mute/solo changes and refreshes on Resume when changed while paused.
- Includes the 0.2.0-74 macOS WKWebView/pywebview CSP fix (`unsafe-eval` only in native single-user mode).

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

- Workspace dedicato per utente con proprietà dei progetti e visibilità dei soli progetti propri/condivisi.
- Condivisione progetto verso altri utenti attivi e confermati; i collaboratori possono modificare, mentre gestione condivisioni ed eliminazione restano al proprietario/admin.
- Gestione file progetto con elenco, download, upload di file originali aggiuntivi e cancellazione sicura dei file non referenziati.
- Conservazione automatica degli upload originali in `originals/`, inclusi audio importati, sostituzioni, sorgenti MTA e input MP3 dello stem splitter.
- Export/import completo di un progetto tramite archivio `.mta-project.zip`, con riassegnazione al nuovo proprietario e reset delle condivisioni all'import.
- Dump amministrativo completo di tutti i progetti di tutti gli utenti, organizzato per proprietario e comprensivo dei file originari.
- Limite upload predefinito portato a 150 MB; wizard Kubernetes configurabile con `--max-upload-mb` e annotazioni Ingress NGINX/HAProxy coerenti.
- Overlay Kubernetes e Docker Compose aggiornati al nuovo limite.
- Migrazione automatica dei progetti legacy senza proprietario verso il primo amministratore persistente che apre il workspace.

# MTA Audio Editor 0.2.0-68

## Multi-user authentication and administration

This release replaces the browser-facing single-admin login flow with application-managed users and a responsive photographic login faithful to the approved visual concept. Users can self-register, must confirm a mandatory email address, and remain inactive until approved by an administrator. Administrators can manage users and roles, while safeguards prevent accidental removal of the final active administrator.

Users can optionally enable TOTP from their profile. MTA Audio Editor generates the TOTP secret and QR code internally. Administrators can configure SMTP, STARTTLS or SMTPS with optional credentials, test connectivity, and use the mail service for address verification and activation notifications. All active administrators with confirmed email addresses are notified when an account is activated.

Authentication state is persisted on the application data volume, browser sessions use HttpOnly/SameSite cookies, and password/email changes invalidate or re-gate access as appropriate. Docker Compose and the Kubernetes manifest wizard now include the bootstrap administrator email.

The release also retains the current Python 3.14 / Debian Trixie container baseline, CPU-only PyTorch multiarch strategy, GitHub Actions security gates, Kubernetes HAProxy TLS behavior, and accumulated MTA reverse-engineering work.

# MTA Audio Editor 0.2.0-13

## Python 3.14 and Kubernetes/Kustomize release

This release supersedes the two previously open Dependabot proposals by adopting the Python 3.14 container baseline and the compatible dependency set instead of suppressing those updates.

- Production and CI baseline: `python:3.14-slim-bookworm`.
- NumPy updated to 2.5.3.
- Demucs remains 4.1.0 and the production image validates the Python 3.14 stem stack.
- The Docker and Python dependency PR intents are therefore incorporated into mainline package contents.
- Gitleaks pull-request scanning keeps full Git history.


## GitHub Actions reliability fix

The follow-up Quality run also exposed three Ruff 0.16.9 findings in the Kubernetes wizard. The unused import was removed; the two security rules are suppressed only at the exact intentional operations (`urlopen` against the hard-coded HTTPS GitHub raw URL and `os.execv` for shell-free self-restart), with inline rationale.

The Python 3.14 baseline remains enabled. The Quality job exposed an intermittent resolver failure for `pydantic==2.13.5`, which requires `pydantic-core==2.46.5`. The Security job in the same workflow could resolve it while the Quality job could not. This release pins `pydantic==2.12.5`, whose `pydantic-core==2.41.5` dependency has established CPython 3.14 wheels, and prevents Dependabot from immediately reopening the unstable 2.13/2.14 upgrade.

## Kubernetes

Kubernetes resources are now split under `k8s/base` into Namespace, PVC, Deployment and Service, with an example Secret kept outside the default Kustomization. NGINX and HAProxy Ingress examples are supplied as independent Kustomize overlays.

A new `scripts/k8s-wizard.py` is downloadable directly from the GitHub raw URL and uses only the Python standard library. It asks for initial administrator username/password, PVC StorageClass, namespace and nodeSelector, remembers the last values in a mode-0600 configuration file, can optionally generate NGINX/HAProxy Ingress, and creates a local Kustomization. On startup it checks GitHub for a strictly newer wizard version; after an atomic self-update it automatically restarts itself.

The generated `secret.yaml` contains local credentials and must not be committed. Use `--no-save-password` when password persistence is not wanted.

### 0.2.0-68

The standalone Kubernetes wizard now emits the legacy-compatible HAProxy ingress annotation `kubernetes.io/ingress.class: haproxy` every time HAProxy ingress is selected, while retaining the Kubernetes v1 `ingressClassName` field. Reverse-engineering documentation also includes the latest Cluster transport evidence.

## 0.2.0-73
macOS ARM native-dialog reliability fix: project creation and Import & Separate now wait for the native pywebview bridge readiness event, tolerate delayed WebKit bridge injection, and keep modal interactions from closing the dialog unexpectedly.

## 0.2.0-113
- Import & Separate correctly reflects the current project type.
- Native desktop model acquisition for splitting uses upstream Demucs directly.
- Existing identical project files are reused for stem separation instead of rejected.

## 0.2.0-r181

The combined Lyrics + Chords + Markers editor now uses contextual actions for whole lyric lines, individual chords and markers. Marker insertion supports required start and optional end times, and lyric timestamps can be edited directly.
