**Current r210 verification,21October2026:** 4,735 distinct cases verified across the complete regression and final failed-case retry; 98 skipped. Qixuan existing-bank IT/FR software, native UI zoom, audio/MIDI project modes, musical transport/metronome and quantization verified. Twelve real Qixuan CPU cases passed; IT/FR remain disclosed cross-language projections. [Current bilingual report](docs/R210_QIXUAN_MIDI_NATIVE_IT_EN.md). Physical target/listening acceptance and the historical10–16-instrument accuracy gate remain distinct. All earlier status entries below are historical.

**Current r210 verification, 21 October 2026:** 4,680 passed, zero failures/errors, 98 skipped. Fixed tariff navigation and added engine-grouped per-file AI administration. Qixuan IT/FR profiles passed eight actual CPU ONNX cases; these are disclosed cross-language projections. **10–16-instrument accuracy remains unmet, beyond hardware acceptance.** [Current bilingual report](docs/R210_ADMIN_QIXUAN_ACCURACY_IT_EN.md). All earlier status entries below are historical.

**Current r210 verification, 21 October 2026:** 4598 passed, 0 failures/errors, 98 skipped. Fixed combined Deep channel/controller routing, empty-score handling, source-duration note bounds and final cancellation. [Current bilingual report](docs/R210_COMBINED_RESULTS_IT_EN.md) · [Runtime/target acceptance guide](docs/R210_DIFFSINGER_DEEP_ACCEPTANCE_IT_EN.md). Multi-instrument accuracy and Qixuan IT/FR remain open; this is not full three-area certification. Earlier checkpoints below are historical.

**21 October 2026 — current r210 verification:** 4,608 passed, 0 failed, 80 skipped, 6 warnings (524.10 s). Final changed-area checks: 68 passed; the last vocal identity adjustment also passed real Qixuan→YourMT3 PS inference. Real DiffSinger ONNX singing and the metered Deep pipeline/replay now work. The ten–sixteen instrument accuracy gate remains unmet and is not a hardware-only limitation. See [current bilingual report](docs/R210_DIFFSINGER_DEEP_CLOSURE_IT_EN.md) and [acceptance guide](docs/R210_DIFFSINGER_DEEP_ACCEPTANCE_IT_EN.md). Version remains 0.3.0-r210.

**Final general regression / Regressione generale finale: 4.596 passed, 0 failed, 80 skipped, 6 warnings.**

**Current runtime validation, 21 October 2026 — 0.3.0-r210:** real offline CPU inference completed with RVC, strict Seed-VC, Transkun and YourMT3; actual FluidR3/TinySoundFont covered 128 GM programs and 47 drums. Seed import/checkpoint/export compatibility and RVC namespace shadowing were corrected. The ten-program YourMT3 mixture **failed its target** (5 predicted parts); a complete authorized DiffSinger bank and browser/target acceptance are still missing. This is **not** a hardware-only completion claim.

[Current bilingual runtime report](docs/R210_REAL_RUNTIME_HANDOFF_IT_EN.md) · [Target acceptance steps and remaining gates](docs/R210_TARGET_ACCEPTANCE_IT_EN.md) · [Cumulative suggested commit](docs/COMMIT_MESSAGE_R210.txt).

Earlier validation checkpoints below are historical; use the current report for repeated checks.

---

**Current status, 21 October 2026 — 0.3.0-r210:** complete general offline regression: **4,579 passed, 0 failed, 85 skipped, 6 warnings**. Fixed remote lead/backing artifact selection, reconciled legacy harnesses and added offline isolation without weakening authentication or license policy. Complete authorized neural bundles, musical benchmarks and asset/browser/target acceptance remain; the three macroareas are not certified fully complete.

[Final bilingual report](docs/R210_OFFLINE_FINALIZATION_IT_EN.md) · [Cumulative suggested commit](docs/COMMIT_MESSAGE_R210.txt).

---


### r210 single-cycle engineering gate (21 October 2026)
Recovery from an invalid-schema Audio-to-MIDI stage checkpoint now recomputes the real stage rather than aborting; 108 offline cross-area tests passed. Real licensed neural inference, full repository regression, native/browser and GM hardware acceptance remain **unverified**, so the three areas are **not certified complete**. See `docs/DEVELOPMENT_STATUS.md`.

**r210 three-area verification (2026-10-21):** GM atomic WAV export and validated MIDI benchmark instrument target; 101 passed, 0 failed, 5 skipped in an offline subset. The three macroareas are **not yet end-to-end certified**. See `docs/R210_THREE_AREAS_CLOSURE_GATE_20261021_IT_EN.md`.

Additional finalization check: 106 passed, 0 failed, 5 skipped (focused offline tests; not a full regression). The three areas remain conditional on authorized real model inference and target acceptance; see `validation/r210-finalization-current.json`. 


> Offline r210 accelerated hardening: bounded MIDI benchmark augmenting-path work and closed portable GM configuration; 123 focused tests passed, 10 asset/DOM skips. Neural inference, full regression and target acceptance are not certified.


## r210 benchmark provenance follow-up — 21 October 2026

Implemented: Audio-to-MIDI benchmark file reports now record SHA-256 hashes and exact byte lengths of both local MusicResult inputs. This supports reproducibility but does not certify real neural inference or reviewed reference labels. Offline regression: **73 passed, 0 failed, 9 skipped** (requires externally reviewed GM assets/core). The controlled full suite has not been rerun and prior GitHub-request governance blocker is unresolved. No real checkpoint inference, native/browser acceptance or musical listening was performed. No production server changes and no Git operations. **The three macroareas are not signed off; software completion cannot be certified yet.**

## r210 follow-up: local stage recovery safety

The same stage-cache instance now invalidates previous results after runtime/model/policy fingerprint changes. Local checks: 28 passed, 0 failed, 0 skipped; expanded r210 regression interrupted before final counts. Neural checkpoint inference and browser/native testing are not certified. See `docs/DEVELOPMENT_STATUS.md`.

## Three-area cumulative development checkpoint (0.3.0-r210, uncommitted)

## r210 — Managed neural assets, conversion and transcription recovery (uncommitted)

Per-component license/SHA-256 registry, independent DiffSinger singers, full IT/EN/FR text and melismas, expression curves and word/syllable/phrase takes, actual RVC/Seed-VC CLIs, Transkun piano and durable Deep-stage recovery without duplicate billing. Authorized checkpoint inference and musical acceptance remain explicit gates. Real GM runtime audits and exact test outcomes are recorded in [development status](docs/DEVELOPMENT_STATUS.md) and the [IT/EN operator guide](docs/STUDIO_MANAGED_ASSETS_R210_IT_EN.md).

Substantial additions: IT/EN/FR lyrics now reach DiffSinger; optional real eSpeak NG G2P with a hash-pinned bank-specific IPA/inventory profile; multi-phone durations, required score F0, vibrato and expression presets; exact acoustic checkpoint/config/vocoder selection and separate vocoder license admission. Region singing creates aligned alternative takes and retains each singer's generation metadata.

Deep Audio-to-MIDI now performs real Demucs separation followed by per-source YourMT3 and Basic Pitch reconciliation. Separated sources retain identity even with the same GM program; they are not extra independent confidence votes. No fixed 10–16-instrument accuracy is promised. Extra reviewed local SF2 banks can be installed with pinned bank/license hashes and selected in the MIDI editor. The native TinySoundFont backend has produced real PCM for all 128 GM programs and all 47 standard drum notes, with controller and SMF tempo tests.

**The three areas are not yet software-complete.** Voice conversion, managed independent neural banks, further specialist transcribers, silent-stem handling and complete advanced UI/real-client acceptance remain open. Real DiffSinger/YourMT3 inference was not executed here. Existing legacy engines, VST SDK and all original files remain. Version unchanged; no Git or production operations. See [implementation and server setup](docs/THREE_AREA_IMPLEMENTATION_R210_IT_EN.md), [current development status](docs/DEVELOPMENT_STATUS.md), and the included validation reports. New DiffSinger deployments require a flattened pinned config and separately authorized vocoder.

For the MTA web server on Linux, use the standalone [MTA installation wizard](docs/MTA_INSTALLATION.md): `scripts/install_mta.sh` installs the app and exposes a checked web endpoint without requiring a full checkout.

## ACE-Step installation wizard

Optional ROCm kernel timing diagnostics for ACE-Step 0.1.8: [activation, rollback and accounting limits](docs/ACE_TASK_GPU_PROFILER_R210.md).

Live GPU samples and unified AI workers: [activation, coverage and validation limits](docs/LIVE_GPU_AND_AI_WORKERS_R210.md).

Isolated AMD-SMI comparison on Proxmox: [gwads07 side-by-side build and validation](docs/AMD_SMI_SIDECAR_R210.md).

For standalone setup on Debian/RHEL-family Linux (bare metal, VM or LXC), download `scripts/install_ace_step.sh` alone; a full checkout is **not** required. See [ACE-Step Installation](docs/ACE_STEP_INSTALLATION.md) for GPU prerequisites, interactive setup, version selection, firewall, reinstall and uninstall.

### 0.3.0-r154 — Validated bounded batch event IPC (native host disabled)

The event-enabled persistent VST3 worker can now prevalidate entire batches (up to 128 PCM blocks / 65536 frames), including MIDI and parameter offsets, before any IPC is sent. Real ADelay validation covers irregular stereo blocks and automation. This is a control/worker-thread offline API only; native_host_ready remains false.


### 0.3.0-r153 — Experimental VST3 event IPC (native host remains disabled)
Persistent offline VST3 IPC optionally accepts bounded MIDI note-on/off and normalized parameter changes per PCM block, with sample offsets. The legacy PCM stream is unchanged. Events are validated and mapped into Steinberg EventList/ParameterChanges on the isolated worker process. This is not an enabled realtime host.

## r141–r150 — Bounded worker event dispatch (experimental)

Added `native/audio_core/vst3_event_dispatch.hpp`: epoch/sequence gating, bounded MIDI and parameter dispatch, atomic prevalidation, preserved sample offsets, failure counters, lifecycle reset, and deterministic sequence consumption. The worker adapter is not yet wired to Steinberg SDK processing or production playback. `native_host_ready=false`.

r122 experimental native C ABI to real VST3 IPC acceptance is available for tests only. Production playback remains unchanged; `native_host_ready=false`.

Experimental r121 native audio core C ABI available; VST3 realtime host remains disabled (`native_host_ready=false`).

### r70 — Experimental interactive VST3 offline worker

`native/vst3_probe/stream_worker.py` implements `NativeVST3Worker` (persistent IPC
per plugin) and `render_stream_wav()` (bounded-memory PCM16/24/32 WAV export).
The C++ probe's `--stream-pcm <CID> <channels> <rate>` protocol exchanges
little-endian uint32 frame counts plus interleaved Float32 PCM on stdin/stdout,
1–512 frames at a time; zero frames signals graceful shutdown. This is not a
realtime callback-safe integration. A Python watchdog kills stalled workers,
rejects malformed/nonfinite replies, and leaves preexisting WAV outputs intact
on export errors. Supported sample rates: 44100, 48000, 96000; mono/stereo.
The real ADelay streaming and session acceptance tests run in Linux VST3 SDK CI.
Read `native/vst3_probe/READINESS_GATES.md` before enabling the native host.
**`native_host_ready=false` remains intentional.**

### VST3 experimental offline session — r60

The native probe now processes a bounded list of PCM requests with one plug-in activation, preserving the plug-in's state between requests. The Python `render_native_session()` and `render_native_session_chain()` APIs are experimental and must not run on the realtime audio callback. This is not yet an interactive worker daemon. See `VST3_HOST_SETUP.md`.

# MTA Audio Editor 0.2.0

![MTA Audio Editor](app/static/logo.svg)

![MTA Audio Editor DAW](app/static/docs-assets/daw-overview.png)

**MTA Audio Editor** is a professional Digital Audio Workstation for multitrack editing, mixing, mastering, audio export and native MTA (Multi Track Audio) workflows. Projects can use the unrestricted **Multitrack DAW** format and can be exported to MTA8/MTA16 when required.

Alessandro De Salvo <braket71@gmail.com>  
**Repository:** `desalvo/mta-audio-editor`  
**License:** EUPL-1.2  
**Version:** `0.2.0`  
**Revision:** `153`  
**Build:** generated as `YYYYMMDDhhmmss`.

[Italian README](README_IT.md)

## Documentation downloads

### User and administrator manuals
- [User Manual - English PDF](app/docs/MTA-Audio-Editor-User-Manual-EN.pdf)
- [Manuale Utente - Italiano PDF](app/docs/MTA-Audio-Editor-User-Manual-IT.pdf)
- [Administrator Manual - English PDF](app/docs/MTA-Audio-Editor-Administrator-Manual-EN.pdf)
- [Manuale Amministratore - Italiano PDF](app/docs/MTA-Audio-Editor-Administrator-Manual-IT.pdf)

### Product brochures
- [Product Brochure - English PDF](app/docs/MTA-Audio-Editor-Brochure-EN.pdf)
- [Brochure Prodotto - Italiano PDF](app/docs/MTA-Audio-Editor-Brochure-IT.pdf)

### MTA format specifications
- [Complete MTA Format Specification - English PDF](app/docs/MTA-Audio-Editor-MTA-Format-Specification-EN.pdf)
- [Specifica completa del formato MTA - Italiano PDF](app/docs/MTA-Audio-Editor-MTA-Format-Specification-IT.pdf)
- [MTA Format Specification - English source](docs/MTA_FORMAT_FINAL_SPEC_EN.md)
- [Specifica formato MTA - sorgente italiana](docs/MTA_FORMAT_FINAL_SPEC_IT.md)

## Main features

- unrestricted **Multitrack DAW** projects;
- MTA8 and MTA16 import/export with device-aware Click/Melody mapping;
- multitrack timeline with waveforms, zoom, markers and Follow;
- synchronized playback with pre-buffering and optional rendered master preview;
- non-destructive clip/region editing, cuts, ripple editing and global song cuts;
- track import/replacement and manual/automatic synchronization;
- mixer with volume, pan, mute, solo, realtime meters and master bus;
- per-track and master insert chains with factory/user presets;
- delay, Lexicon-style reverb, room/ambience, EQ, amplify, stereo imaging, maximizer/loudness, mastering, de-noise, crackle cleaning, compressor, limiter and normalization;
- global Auto Mix wizard;
- import/export WAV, MP3 and FLAC plus individual-track export;
- optional Demucs stem separation;
- lyrics, chords, markers, metadata and MTA attachments;
- native desktop packaging plus web, Android and iOS clients;
- Docker and Kubernetes deployments.

## Operating model

The desktop native single-user edition can work without local account management. User accounts, email verification, roles and TOTP are used by the online/server and mobile editions. Mobile clients use the remote server for compute-heavy operations such as FFmpeg rendering, MTA generation and Demucs stem separation.

Mobile apps use the preconfigured service endpoint by default. The default endpoint is not displayed to the user and is not requested during installation or first launch. A custom endpoint can be configured later from application settings; custom values may be displayed and edited.

## Important operational limits

- **MTA8:** maximum 8 physical output slots.
- **MTA16:** maximum 16 physical output slots.
- A Multitrack DAW project can contain more tracks; export to MTA requires merge/mapping into the target slot count.
- Up to **16 insert effects** are supported per track/master chain.
- Default upload limit for server deployments is **1024 MB**, configurable by deployment settings.
- Demucs requires the stem-separation component and significant server CPU/GPU/RAM resources.
- Hardware compatibility of exported MTA files depends on the selected device/firmware profile; live use should be validated on the actual target device.

## Docker quick start

```bash
export MTA_ADMIN_PASSWORD='a-long-random-password'
export MTA_ADMIN_EMAIL='admin@example.com'
docker compose up -d --build
```

Open `http://localhost:8080`. There are no default administrative credentials.

## Kubernetes

Kustomize bases and example NGINX/HAProxy overlays are included. A standalone configuration wizard is available in `scripts/k8s-wizard.py`.

## Mobile clients

Native Android and iOS clients are included under `mobile/android` and `mobile/ios`. They connect to the MTA Audio Editor server over HTTPS and delegate heavy audio processing to the server.

## License

EUPL-1.2. See the repository license file for complete terms.

### Configurable stem count
Stem separation exposes **Auto / 2 / 4 / 6 / 8**. Auto is the default. 2 uses vocals/accompaniment, 4 the standard profile, 6 the extended Demucs profile; 8 requires a backend configured with an 8-stem model. The current iPhone and iPad build delegates Demucs to the server, so the same setting is available on both devices without bundling PyTorch in the app.


## On-device Demucs on iPhone/iPad (0.2.0-97)

The iOS/iPadOS client can now run stem separation locally through Core ML. The mobile workflow exposes **Auto / Local / Server** execution. Auto prefers an installed local model and falls back to server-side Demucs when the requested model is unavailable or the local device constraints are exceeded. Core ML models are provisioned as `demucs-2.mlmodel`, `demucs-4.mlmodel`, `demucs-6.mlmodel`, or `demucs-8.mlmodel` from the configured backend and are compiled/cached in the app's Application Support directory for later offline use.

The local runtime decodes the selected audio on-device, converts it to stereo 44.1 kHz Float32 PCM, processes fixed-size overlapping chunks through Core ML using all available compute units (CPU/GPU/Neural Engine where Core ML supports them), overlap-adds the results, writes WAV stems, and uploads the resulting tracks into the current project. The current local safety limit is **12 minutes per source file**; longer material falls back to the server in Auto mode. On iPhone, Auto is intentionally more conservative than on iPad because of memory/thermal constraints.

Server administrators can expose compatible Core ML Demucs models by mounting a directory and setting `MTA_DEMUCS_COREML_MODEL_DIR`. The optional `scripts/export_demucs_coreml.py` utility documents the model contract expected by the app. Model conversion is a release-engineering step and must be validated for each Demucs architecture before publishing a model.

## Native application updates

Native Windows, macOS, Android, iPhone and iPad clients check GitHub for newer builds. The update channel is configurable in the application options:

- **Stable** checks tagged GitHub releases only.
- **Early release** also checks the rolling `early-main` prerelease generated from the latest successful `main` build.

Windows/macOS download and launch the matching installer; Android can download the APK and hand it to the system package installer. iOS/iPadOS cannot silently self-install binaries from GitHub and therefore opens the authorized TestFlight/App Store or managed-distribution flow after confirmation.

### iPhone/iPad local Demucs model lifecycle

The iOS/iPadOS client always attempts to provision a default **4-stem Core ML Demucs** model automatically. A validated model bundled in `Models/demucs-default-4.mlmodel[c]` is preferred; otherwise the app bootstraps it from the configured MTA Audio Editor server. Installed model SHA-256 fingerprints are compared with the authenticated server model inventory and newer server versions replace the cached local model automatically. The installed model remains available offline.

### Automatic mobile Demucs model lifecycle
Docker/Kubernetes refreshes signed-by-hash mobile model payloads from the configured HTTPS manifest every 6 hours by default. iOS/iPadOS and Android check the server periodically. Mobile model downloads are Wi-Fi-only by default and can be enabled on cellular in app preferences. iOS uses Core ML; Android provisions ONNX Runtime Mobile models.


## Model-driven extended stem separation

MTA Audio Editor no longer hard-codes a 2/4/6/8 list. The server and mobile clients discover the stem counts actually published by the model catalogue/manifest: 2, 4, 6, 8, 10, 12, 16, and larger values whenever a compatible model exists. The current safety ceiling is 64 stems per model. Multitrack DAW projects are not constrained by the stem count; MTA8/MTA16 limits are enforced only at export time. Additional server profiles are configured through `MTA_DEMUCS_MODEL_REGISTRY` or `MTA_DEMUCS_MODEL_REGISTRY_FILE`, declaring `model`, `stem_count`, `stem_labels`, and optionally `engine`/`display_name`.


### Demucs model catalogue / Catalogo modelli Demucs
The server periodically synchronizes all configured Demucs/Core ML/ONNX models. Native/mobile clients download requested models on demand, can delete or force-update local copies, and server administrators can blacklist models (which also removes managed server artifacts).

### Synchronized lyrics and chords
A track context menu can extract synchronized lyrics and chords into the project. Chords use the built-in lightweight chroma analyser. Lyrics use bundled OpenAI Whisper in production server/native builds. Whisper model weights are downloaded on demand on first use and cached in the runtime; they are resolved from the upstream Whisper source/cache, not from the MTA Demucs model server. Lyrics can be downloaded as plain text or as PDF; the PDF places synchronized chords above lyric lines and uses project title/artist metadata. MTA exports embed lossless millisecond-timed lyrics/chord attachments in addition to preserved stock attachments.

### Rights repertoire lookup / Repertori società d’autori
Project Info can search selected rights societies (SIAE and Soundreef enabled by default), store multiple verified repertoire records for the same song across multiple rights providers, include all of them in MTA project metadata, display every stored record in Project Info, and export all available provider fields in both Lyrics + Chords PDF and ChordPro. Structured lookup uses authorized HTTPS endpoints configured with `MTA_RIGHTS_SIAE_SEARCH_URL` and `MTA_RIGHTS_SOUNDREEF_SEARCH_URL`; otherwise the official repertoire portal plus manual verified-result import is used. Lyrics + Chords can also be exported as ChordPro (`.cho`).

- YouTube audio import: first play the video audio in your browser, then copy and paste a single `youtube.com`/`youtu.be` video URL to add its audio as a project track (authorization/rights confirmation required).


### Lead Vocals / Backing Vocals
**Import & Separate** can run a second pass on the vocal stem. When `MTA_LEAD_BACKING_COMMAND` is configured the server invokes that dedicated AI separator (supported placeholders: `{input}`, `{lead}`, `{backing}`, `{output_dir}`); otherwise it falls back to a local FFmpeg center/side split. The job records which method was used.


### Lead / Backing Vocals AI models (0.2.0-124)
The dedicated vocal split uses `audio-separator==0.47.0` and downloads the selected karaoke model on demand. The default is `UVR_MDXNET_KARA_2.onnx`; Mel-RoFormer Karaoke Aufr33/Viperx and Gabox V2 are selectable for higher-quality/heavier processing. Web/server deployments cache weights under `${MTA_DATA_DIR}/.cache/lead-backing-models` (override with `MTA_LEAD_BACKING_MODEL_DIR`). Native desktop applications use the same mechanism against their local data directory, so model weights stay local. `MTA_LEAD_BACKING_DEFAULT_MODEL` changes the default model. The FFmpeg center/side method is an explicit fallback, not the default.

### Lyrics and Chords model management

Since 0.2.0-126, Lyrics and Chords models are managed on demand like the other AI models. Web deployments cache weights on the server; native desktop applications cache them locally. Lyrics can use the selectable OpenAI Whisper models (`large-v3` by default). Chords always exposes the selected engine before extraction: Madmom Deep Chroma + CRF (default AI), Madmom CNN + CRF, Chordino / NNLS-Chroma, or the built-in MTA Chromagram analyser. The UI also discloses the non-commercial CC BY-NC-SA 4.0 license of the Madmom checkpoint weights.

### Waveform/sample editor
Double-click a timeline waveform or use the track context menu to open the dedicated high-resolution editor. Sample-addressable selections support Cut/Copy/Paste/Remove. In-place processing provides debounced A/B preview for fine Pitch Correction (semitones + cents), pitch-to-scale Auto-Tune (key/scale/strength), Normalizer, Maximizer and a 32-band Graphic EQ with presets. Committing creates a new source for the edited track only, leaving other instances of the original asset untouched.


### Project navigation and Export

- **Export** opens a dedicated on-demand dialog instead of occupying a persistent mixer-side panel.
- The old sidebar **PROJECTS** section has been removed.
- In the web app, **Open project** lists projects already available on the server and **Open local project** imports a project archive from the device.
- In the native desktop app, **Open recent** lists recently opened projects that still exist in the local workspace, while **Open project** uses the native filesystem picker.

### Structured Lyrics editor
“Edit lyrics” now opens a large resizable window with separate Start, End and Text columns; rows can be added/removed and text/timing edited independently.

### Structured Lyrics editor
Lyrics rows can be inserted anywhere with **+ above** / **+ below**, timed segments can be split with **Split**, and rows can be deleted before saving. Suggested timestamps remain fully editable.


### Structured Chords editor
Each Chords row uses the same workflow as Lyrics: **+ above**, **+ below**, **Split**, and **Delete**. Split inserts a new editable chord point at the midpoint of the current time interval.

### Native improvements 0.2.0-149

New projects are immediately loaded into the complete editor workspace. YouTube import now falls back to the operating-system clipboard in native apps and uses a clearer responsive layout.

## Versioning

Public releases use semantic version tags such as `v0.2.0`. `REVISION` identifies the exact source/package revision within that release, while `BUILD_INFO` is the independent 14-digit build identifier.

### Chord extraction profiles (r195)
Chord extraction now offers **Fast**, **Accurate**, and **Maximum accuracy** profiles. Fast favors Chordino/MTA Chromagram; Accurate uses the best installed recognizer (ChordFormer, BTC-HCQT, Madmom, Chordino); Maximum combines multiple recognizers using a weighted ensemble and then applies extended-harmony and bass-chroma refinement. ChordFormer and BTC-HCQT are available on demand from the AI Model Manager.

### Modular workspace and shared media
Since r198 native autosave updates the persistent modular workspace instead of rewriting the complete `.maeproj`. The `.maeproj` remains a portable snapshot refreshed by Save/Save Copy. Identical audio across projects is deduplicated in a SHA-256 content-addressed shared media store; project-local references remain valid and use hardlinks where possible. A global rescan can rebuild the reference index from every `project.json` and garbage-collect only blobs that no project still references.


### Modular native project format
Native `.maeproj` files are lightweight JSON manifests backed by the modular workspace and shared-media store; they are not ZIP archives. Use the portable project archive (`.maeprojz`) when a self-contained file is required for transfer or backup. Legacy ZIP-based `.maeproj` files remain supported for import.

### Sample rate and karaoke export

Projects support 44.1/48/96 kHz sample rates (44.1 kHz default), with automatic resampling of imported sources to the project rate. Export includes 24/32-bit WAV at 44.1/48/96 kHz, standard MP3, M-Live/Merish MP3 and MP3+G (ZIP containing an MP3+CDG pair).

Multi-singer SAM Audio setup (experimental): see [SINGER_SEPARATION_SETUP.md](docs/SINGER_SEPARATION_SETUP.md).

### VST3 user manuals / Manuali VST3

- [VST3 User Guide (English, PDF)](app/docs/MTA-Audio-Editor-VST3-Manual-EN.pdf)
- [Manuale VST3 (italiano, PDF)](app/docs/MTA-Audio-Editor-VST3-Manual-IT.pdf)
- [VST3 Guide (English, Markdown)](docs/VST3_USER_GUIDE_EN.md)
- [Guida VST3 (italiano, Markdown)](docs/VST3_USER_GUIDE_IT.md)


Revision r127: public experimental VST3 C ABI and strict fixed PCM quantum validation; native_host_ready=false.


### 0.3.0-r130: experimental native parallel dry/wet latency alignment
New native/audio_core/vst3_parallel_mix.hpp aligns dry PCM to plugin-declared latency, supports wet/dry mix and fault-driven latency-aligned dry output; tested in C++20. Experimental isolated primitive, NOT connected to production playback. native_host_ready remains false.


VST3 r152: worker event/audio shape mismatches and excessive stale-event backlogs now fail closed; playback native host remains disabled.


0.3.0-r161: single-block VST3 IPC fault containment; native_host_ready=false.


0.3.0-r162: hardened worker PCM validation; native_host_ready=false.


### r165
Optional supervisor-level VST3 controller and component checkpoint pairing; no realtime callback activation.

- r183: fail-closed AI worker capability probe and experimental native C++ peak/RMS meter; AI inference remains unverified.

Remote ACE-Step on a GPU server / ACE-Step remoto: see [REMOTE_AI_SETUP.md](docs/REMOTE_AI_SETUP.md).

## Native remote ACE-Step / ACE-Step remoto nelle app native

See [Native remote AI setup](docs/NATIVE_REMOTE_AI_SETUP.md) for the first-use Local/Remote choice, persistent preferences, HTTPS bearer authentication and GPU host configuration.

### Secure remote AI access and external VM/LXC reverse proxy

See [REMOTE_AI_REVERSE_PROXY.md](docs/REMOTE_AI_REVERSE_PROXY.md) for per-user tokens, the native app endpoint, and Kubernetes NGINX/HAProxy Ingress or Docker HAProxy deployment examples. Never expose raw ACE-Step directly.

AI billing / Tariffe AI: see [AI_BILLING_SETUP.md](docs/AI_BILLING_SETUP.md) for effective dates, open-ended rates, reports and limitations.

Optional MTA web HTTPS (Linux wizard): see [MTA_WEB_HTTPS.md](docs/MTA_WEB_HTTPS.md).

**Email address changes (r207):** the existing verified address and account
access remain in place until confirmation of the pending new address. The
account API reports pending verification, including when SMTP is not configured.
Configure SMTP and resubmit the email change to request a new confirmation link.


### Durable upload recovery (0.3.0-r208)

See [Durable upload recovery](docs/AI_R208_DURABLE_RECOVERY_CLOSURES_EN.md) for implemented safeguards, validation and outstanding limitations.

ACE-Step r210: [long jobs, internal timeout and cancellation](docs/ACE_LONG_JOBS_AND_CANCELLATION_R210.md).

ACE-Step r210: [cold-start recovery without cancelling an accepted job](docs/ACE_COLD_START_R210.md).

VST3/MIDI r210: [original server plugin editors, tempo maps, sidechains, UMP/MPE/SysEx and external audio capture](docs/VST3_COMPLETION_R210.md).

### r210 chord engine migration
Automatic chord profiles use license-admitted BTC-HCQT, Chordino and MTA Chromagram instead of Madmom NC checkpoints; complex chord labels are retained in Balanced/Detailed modes. See `docs/MADMOM_CHORD_MIGRATION_R210_EN.md` for limitations and verification status.


Restricted AI checkpoint activation policy / Policy di attivazione checkpoint AI: see `docs/LICENSE_ACTIVATION_R210_IT_EN.md` (EN).

Detailed checkpoint licensing update: `docs/AI_CHECKPOINT_RIGHTS_20261020_EN.md`.

### Mega 53 Lead/Backing (experimental, opt-in)
See `docs/MVSEP_MEGA53_LEAD_BACKING_R210_IT_EN.md` for the external checkpoint installation, rights check, and unverified real-audio benchmark status. It is registered but license-blocked until explicitly reviewed.

UVR KARA 2 rights and guarded enablement: `docs/UVR_KARA2_RIGHTS_R210_EN.md`.

**AI model rights registry (r210):** Studio model-license administration now displays curated upstream evidence and outstanding rights gaps for UVR, DrumSep, ChordFormer, Madmom, SAM Audio and selected DiffSinger banks. Evidence does not grant rights or automatically unblock unknown checkpoints. See `docs/MODEL_RIGHTS_DOSSIERS_R210_IT_EN.md`.

### Licensed fallback selection (r210)
If KARA 2 is not admitted, new lead/backing jobs with no explicitly selected engine use Mega 53 when permitted by its own policy. DrumSep offers an explicit `dsp` mode producing broad drums/percussion stems, not individual kit pieces. Restricted original weights remain blocked. Mega 53 still requires an installed runtime and checkpoint.

Mega 53 can also provide separately extracted kick, snare, toms, hi-hat and percussion via the percussion method selector. This is not equivalent to full cymbals separation or guaranteed kit reconstruction; SAM Audio and DSP remain available. Model checkpoint and MSST installation are required.

DrumSep checkpoint-rights deep review and licensed remote Mega 53 drum-parts routing: see `docs/DRUMSEP_RIGHTS_REVIEW_20261020.md`. Original DrumSep weights remain disabled where license evidence is insufficient.

### r210 drums vs percussion AI grouping
Mega 53 can now estimate **drums (kit)** vs **non-kit percussion** from the original mix as two separate stems; this is distinct from its kick/snare/toms extraction and the simpler transient-based DSP fallback. Requires an authorized and installed Mega 53 checkpoint. See `docs/DRUMS_VS_PERCUSSION_R210_IT_EN.md` for limitations and blocked legacy checkpoints.


Studio r210 checkpoint (2026-10-20): stable MIDI note-to-lyric alignment and early singer-part validation; 26 targeted tests passed, one bank-dependent skip. Vocal Studio and full-mix multi-instrument Audio-to-MIDI remain incomplete. See docs/VOCAL_MIDI_COMPLETION_GATE_R210_IT_EN.md.


## Latest r210 Vocal Studio validation
Reject invalid vocal note timing, pitch and velocity before asset loading. 22 targeted tests passed, 5 skipped; neural singing and full multi-instrument transcription remain open.


Vocal Studio: per-singer English lyric input now available in AI Studio; other neural vocal features and 10–16 instrument automatic transcription are still experimental/not certified.


**r210 accelerated Vocal Studio:** per-singer CC0 OddVoices bank selection available in backend (`voice_banks`); GUI control and neural vocals pending. 25 tests passed, 5 skipped. See docs/R210_ACCELERATED_VOCAL_BANKS_IT_EN.md.


Vocal Studio now exposes per-singer installed voicebank selection in the native/web Studio UI, with per-source worker routing.

### Neural Studio integration (r210)
An optional administrator-installed neural singing adapter contract (`neural-external`) is now available, guarded by checkpoint SHA-256, model-rights policy and output validation. It does not bundle or install a neural checkpoint and has not been validated with a real neural inference model. See `docs/NEURAL_SINGER_EXTERNAL_R210_IT_EN.md`.

DiffSinger direct CLI support (r210): see `docs/DIFFSINGER_R210_IT_EN.md`. Requires separately installed, individually licensed acoustic checkpoint, voicebank and vocoder. Not certified by an end-to-end checkpoint test.

**DiffSinger r210 (additional checks):** the bridge now verifies that the acoustic checkpoint belongs to the selected experiment and validates the output length/sample rate. Inference with real licensed voicebanks and vocoders remains to be certified (see `docs/DEVELOPMENT_STATUS.md`).

DiffSinger deployment readiness (r210): run `python scripts/check_diffsinger_ready.py --json` with the operator-installed licensed assets; see `docs/DIFFSINGER_DEPLOYMENT_HANDOFF_R210_IT_EN.md`. This is a preflight check, not a successful neural inference or completed Vocal Studio certification.

**Audio-to-MIDI r210 — conservative reconciliation:** when multiple primary events could match one secondary-model note, none is assigned arbitrarily. The `primary_audit` report counts independent observations supporting primary events; it is not a probability of correctness. Reliable 10–16-instrument transcription from a full stereo mix remains uncertified.

Audio-to-MIDI now includes an offline GM-aware benchmark (`scripts/check_audio_midi_quality.py`); see `docs/AUDIO_TO_MIDI_QUALITY_GATE_R210_IT_EN.md`. Real 10–16 instrument accuracy remains unverified.


MTA r210 combined studio cycle: see `docs/THREE_STUDIOS_HANDOFF_R210_IT_EN.md` for GM offline audit and remaining real-world validation.

### r210 Audio-to-MIDI and GM reliability checkpoint
Instrument-aware benchmarking now uses iterative note matching, emits instrument-specific precision/recall/F1, and bounds benchmark size. GM event scheduling rejects invalid sample rates. The complete neural singing, 10–16-instrument transcription and cross-client GM acceptance goals remain open; see `docs/DEVELOPMENT_STATUS.md`.

### GM MIDI file to WAV (r210)
With `mido`, `soundfile`, a reviewed FluidR3 soundbank and a supported GM runtime installed, run `python scripts/render_gm_midi.py input.mid output.wav`. It supports format-0/1 SMF, track merging, tempo map, program changes, GM drums and CC messages, and exports 24-bit stereo WAV with bounded block rendering. Type-2 SMF and unsupported SysEx are rejected rather than guessed. Actual listening tests on a target workstation remain pending; see `docs/DEVELOPMENT_STATUS.md`.


DiffSinger: added SHA-256-pinned bank-specific syllable lexicons (Italian/French, opt-in English); see docs/DIFFSINGER_REVIEWED_LEXICON_R210_IT_EN.md. The three studios are not yet fully complete.


English DiffSinger reviewed lexicons now accept pinned `en` dictionaries when `use_reviewed_lexicon=true`; legacy English bank-native phonemes remain valid.

### Audio-to-MIDI benchmark r210 (2026-10-20)
Instrument note matching now uses a pitch/onset index while preserving one-to-one maximum-cardinality semantics. Non-finite matching tolerances are rejected. Focused regression: 61 passed, 1 skipped (real voicebank unavailable). Real 10–16 instrument transcription, neural vocal synthesis and GM audio rendering still require real-asset validation; some software features also remain unfinished. See `docs/DEVELOPMENT_STATUS.md`.

### 0.3.0-r210 follow-up (21 October 2026)

Improved offline MIDI benchmark input limits and tolerance validation, StageCache directory safety, and GM portable synthesizer closed-handle errors. Offline verification: 70 passed, 7 skipped, 0 failed; hardware/core GM controller tests skipped in this environment. Neural asset inference, full regression, browser/native acceptance and musical benchmarks remain outstanding. No Git operations or production changes.

### r210 MIDI benchmark bounded matching (21 October 2026)
Dense matching graphs above 1,000,000 candidate note pairs now fail explicitly instead of risking unbounded CPU/memory use. Local targeted validation: 72 passed, 0 failed, 12 skipped. Neural/hardware acceptance and full offline regression are still open.

### r210 finalization readiness (21 October 2026)
The three Studio/Vocal, multitrack transcription and GM workstreams are implemented in substantial part but **not yet certified complete**. The offline MIDI benchmark now uses bounded, inode-validated input opening, rejecting non-regular paths and symlink redirection. Local focused verification: 121 passed / 0 failed / 9 skipped in two disjoint batches. Real licensed model inference, project-wide regression, cross-client playback and musical quality acceptance remain open; see `docs/DEVELOPMENT_STATUS.md`. No deployment or Git operation was performed.

### r210 accelerated finalization checkpoint (2026-10-21)
Offline benchmark input consistency now detects concurrent file changes. Nine focused cross-area test modules: 96 passed, 0 failed, 5 skipped (missing phonemizer or reviewed GM assets). General regression and real neural/native/audio acceptance remain open; no three-area completion claim.

### r210 final verification note (21 October 2026)
Offline Studio/MIDI/GM regression: 143 passed, 0 failed, 15 skipped. This is not full project regression or neural/hardware certification; see `docs/DEVELOPMENT_STATUS.md` and `validation/r210-final-handoff.json`.

## 2026-10-21 — Single-cycle three-area development review (r210)

- **Software fixed:** isolated GM/MIDI worker (`app/midi_render.py`) now stages WAV output in the destination directory, atomically publishes on success, and removes staged files after failure. Previous renders remain intact if playback processing fails. Two new tests cover successful PCM export and a mid-render fault.
- **Cross-area offline verification:** 112 passed, 0 failed, 7 skipped across thirteen focused modules covering multilingual DiffSinger contracts, managed assets, multitrack reconstruction, checkpoint recovery, score benchmarking, GM MIDI rendering and worker atomicity. Skips: approved GM/compiled core assets (2), PyAV (2), optional VSTi (2), real YourMT3 model (1). No unapproved network activity or fake neural inference. This is **not** the full repository regression.
- **Software not fully certified:** DiffSinger/RVC/Seed-VC/Transkun genuine licensed inference, 10–16 instrument quality/independent performer separation, browser/native GM playback, and complete safe project-wide regression remain unverified. No claim of full macroarea completion or operator-only handoff.
- Version **0.3.0-r210** unchanged; no Git operations or production changes.


**r210 checkpoint validation (21 October 2026):** Freshly computed Audio-to-MIDI scores must pass the shared music schema before their recovery checkpoint is committed or a worker is acknowledged. Selected offline checks: 113 passed, 0 failed, 2 skipped. Real neural models, full regression and target-device acceptance are not certified.


### Cross-area offline verification (r210, 21 October 2026)
See `docs/R210_SINGLE_CYCLE_PCM_CLOSURE_IT_EN.md`: Vocal Studio post-resampling PCM guard, 86 passed / 0 failed / 4 skipped; full neural inference and acceptance remain unverified.

### r210 ten-pass offline verification
The latest cumulative r210 engineering pass validates worker render durations and output PCM before publication, and enforces normalized PCM bounds after vocal conversion. Cross-area offline tests: **214 passed, 0 failed, 14 skipped** (not a complete project-wide regression). External licensed neural checkpoints, reviewed GM assets and native/browser listening tests remain prerequisites before final certification. See `docs/DEVELOPMENT_STATUS.md`.


Offline Vocal Studio PCM verification and completion blockers: `docs/R210_20_PASS_CLOSURE_IT_EN.md`.


### 0.3.0-r210 — Work runtime validation (2026-10-21)

Work runtime validation: real Transkun CPU inference completed (synthetic input, zero notes; not a musical benchmark); Seed-VC singing config guard and offline asset audit added. General regression interrupted by automatic approval review of unexpected GitHub egress, without bypass. The three macroareas are not certified complete; remaining work is not limited to hardware acceptance.

[Detailed bilingual report](docs/R210_WORK_NEURAL_RUNTIME_VALIDATION_IT_EN.md).
