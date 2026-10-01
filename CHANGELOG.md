# Changelog

## 0.2.0-5

- Fixed GitHub Actions compatibility: Python 3.11-compatible NumPy and current action generations (including Trivy and CodeQL).
- Added conservative native inspection of real M-Live SYL attachments: decoded ID3v2.3 text frames and DELTA/Lyrics3-like wrappers for LYRICS, COLORS, MIDITK and CHORDS.
- Added verified COLORS structural analysis (3-byte binary prefix plus 15-byte records, distinct terminal record) without claiming undocumented field semantics.
- Added corpus-verified read-only LYRICS/CHORDS decoding: shared 256-byte keystream, continuous phase, record delimiter blocks, centisecond timing and XOR-0x30 text/chord recovery; writer support remains intentionally disabled.
- Added MtxInfoData XML parsing, zero-padding detection and NoteOn vector/duration consistency reporting.
- Added a Matroska FileData EBML fallback for attachment extraction when ffmpeg cannot dump attachments from non-canonical MTA containers.
- Analysis schema bumped to reverse-analysis-v2; proprietary payloads remain read-only/preserved rather than rewritten speculatively.

## 0.2.0-4
- Added Delay, Lexicon-style Reverb, Room/Ambience, 32-band Graphic EQ, Amplify, Stereo Imager, Maximizer/Loudness, Mastering Wizard, De-Noise and Crackling Cleaner insert processors.
- Added factory presets and persistent validated user presets for every insert processor.
- Added parameter editor for custom plugin configurations.
- Added reversible global Auto Mix with Balanced, Studio, Live and Gentle profiles.
- Auto Mix snapshots and restores faders, pan, track insert chains and master chain.
- Extended secure processing validation and test coverage.


## 0.2.0-3

Initial production-oriented release.

- DAW-style multitrack timeline with non-destructive clips/regions.
- Per-track and global range deletion with optional ripple editing.
- Track import, replacement, manual offset and automatic alignment.
- MTA8/MTA16 import/export pipeline and preservation of imported attachments.
- Mixer controls, timed lyrics, chords and markers.
- Default-on authentication, request-integrity protection and path/upload hardening.
- Non-root/read-only Docker and Kubernetes deployment.
- Production CI gates, CodeQL, Dependabot, SBOM and provenance.
- Integrated online/PDF user and administrator documentation.
- EUPL-1.2 licensing.

## 0.2.0-3

- New high-fidelity photographic DAW interface based on the approved mockup.
- Direct MP3/WAV single-track import and replace workflow.
- Demucs plugin for MP3 stem separation into independent instrument tracks.
- Per-track and master insert chains with EQ, normalization, compression and limiting presets.
- Master mixing console with pan, faders, mute/solo and rendered preview.
- Stereo WAV 24-bit/44.1 kHz and MP3 320 kbps export in addition to MTA8/MTA16.
- Expanded user/admin documentation and test coverage for audio plugins and stem workflows.


## 0.2.0-3
- Removed the MTA8/MTA16 slot limit from the editing/mixing workspace.
- Added guided MTA output-slot mapping and many-to-one track merge during export.
- Added independent WAV/MP3/FLAC track export.
- Added FLAC stereo master export.
- Added Matroska/SYL reverse-analysis reports and binary diff tooling.
- Added embedded ID3v2.3 inspection and proprietary section discovery for LYRICS/CHORDS/COLORS/MARKER.
- Added tests for over-capacity projects, mapping validation, FLAC and reverse-analysis helpers.
