# Changelog

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
