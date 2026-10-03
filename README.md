# MTA Audio Editor 0.2.0-94

![MTA Audio Editor](app/static/logo.svg)

![MTA Audio Editor DAW](app/static/docs-assets/daw-overview.png)

**MTA Audio Editor** is a professional Digital Audio Workstation for multitrack editing, mixing, mastering, audio export and native MTA (Multi Track Audio) workflows. Projects can use the unrestricted **Multitrack DAW** format and can be exported to MTA8/MTA16 when required.

Alessandro De Salvo <braket71@gmail.com>  
**Repository:** `desalvo/mta-audio-editor`  
**License:** EUPL-1.2  
**Version:** `0.2.0-94`  
**Build:** generated as `YYYYMMDD-HH:MM:SS`.

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
