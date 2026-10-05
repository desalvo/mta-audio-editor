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
