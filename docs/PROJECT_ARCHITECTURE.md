# MTA Audio Editor - project architecture

Version: 0.2.0-7

## Purpose

MTA Audio Editor is a web DAW for non-destructive editing, mixing, analysis and export of multitrack MTA projects. It deliberately separates ordinary audio editing from proprietary MTA reverse-engineering so undocumented metadata cannot silently corrupt imported files.

## Major modules

- `app/main.py`: FastAPI web/API surface, authentication, project routes and documentation endpoints.
- `app/models.py`: project, track, clip, insert, event and MTA slot-mapping data models.
- `app/storage.py`: persistent project filesystem and confinement checks.
- `app/audio_engine.py`: FFmpeg-based clip rendering, synchronization, track/master export and waveform operations.
- `app/plugins.py`: allow-listed DSP registry, factory/user presets and filter generation.
- `app/auto_mix.py`: reversible deterministic Auto Mix rules and snapshots.
- `app/codec.py`: MTA/Matroska import/export adapter and attachment preservation.
- `app/mta_reverse.py`: conservative read-only analysis of Matroska attachments, ID3/SYL, XML, LYRICS, CHORDS, COLORS and MIDITK.
- `app/security.py`: authentication/request-integrity/security-header controls.

## Persistent data

Default root: `/data/projects`.

Each project stores its JSON model, source audio, imported/preserved attachments, generated analysis and exports. User DSP presets are stored in `_custom_presets.json`. Model caches can also live below the data root but may be excluded from backup if they can be recreated.

## Audio editing model

Editing is non-destructive. A Track references an immutable source plus one or more Clips. Deleting/rippling changes clip source/timeline ranges rather than rewriting source media. Rendering applies:

```text
clips -> track inserts -> fader/pan -> slot mapping/summing
      -> [MTA streams]

clips -> track inserts -> fader/pan -> stereo sum
      -> master fader -> master inserts -> WAV/MP3/FLAC
```

Project track count is independent from MTA output capacity. MTA8 exports at most 8 slots and MTA16 at most 16; excess project tracks must be mapped/merged explicitly.

## Plugin safety model

The browser selects only registered plugin types, preset names and schema-validated numeric parameters. It cannot submit arbitrary FFmpeg filter expressions. This keeps FFmpeg command construction on the trusted server side.

## MTA compatibility layers

1. Matroska/MP3 transport - read/write through FFmpeg/FFprobe.
2. Standard metadata - ID3v2.3 and XML parsing.
3. Demonstrated proprietary decoding - LYRICS, CHORDS, COLORS and MIDITK read-only analysis; verified MIDITK is materialized as a Standard MIDI sidecar and exposed by `/api/projects/{pid}/mta-miditk`.
4. Unknown fields - preserved rather than rewritten.

See `docs/MTA_FORMAT_RESEARCH.md` for the byte-level findings and confidence boundaries.

## Security and CI

Production CI checks compilation, documentation generation, real FFmpeg preset validation, Ruff, pytest/coverage, Bandit, pip-audit, Gitleaks, Trivy filesystem/image scans, container smoke tests and CodeQL. The runtime container is non-root and deployment examples apply capability dropping, seccomp/no-new-privileges and read-only filesystem controls where applicable.

## Release policy

`VERSION` is semantic/project version; `BUILD` is generated in Europe/Rome as `YYYYMMDD-HH:MM:SS`. Packages are GitHub-ready ZIPs with generated user/admin PDFs and SHA-256 checksum. Real copyrighted MTA samples are never included in release archives.
