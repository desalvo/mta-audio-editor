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

Multi-singer SAM Audio setup (experimental): see [SINGER_SEPARATION_SETUP.md](SINGER_SEPARATION_SETUP.md).

### VST3 user manuals / Manuali VST3

- [VST3 User Guide (English, PDF)](app/docs/MTA-Audio-Editor-VST3-Manual-EN.pdf)
- [Manuale VST3 (italiano, PDF)](app/docs/MTA-Audio-Editor-VST3-Manual-IT.pdf)
- [VST3 Guide (English, Markdown)](docs/VST3_USER_GUIDE_EN.md)
- [Guida VST3 (italiano, Markdown)](docs/VST3_USER_GUIDE_IT.md)
