# MTA Audio Editor 0.2.0-2

Build: generated automatically in `YYYYMMDD-HH:MM:SS` format.

This release turns the interface into the production DAW mockup and extends the audio engine with MP3/WAV import, plugin-based stem separation, per-track/master insert processing, a master mixing/preview console and WAV/MP3 master export.

## New audio workflows

- Import an MP3/WAV as a single independent track.
- Replace a track and keep, manually set or automatically recalculate synchronization.
- Split an MP3 through the Demucs plugin and merge the resulting stems into the current MTA project or a new MTA8/MTA16 project.
- Apply multiple ordered inserts per track: EQ, Normalizer, Compressor and Limiter.
- Apply a separate master insert chain to preview, WAV and MP3 exports.
- Export MTA8/MTA16 multitrack, WAV 24-bit/44.1 kHz or MP3 320 kbps.

## Production notes

Demucs model weights are cached in the persistent data volume on first use. Air-gapped deployments should preload the model cache. Plugin parameters are server-side allow-listed; no arbitrary FFmpeg expression is accepted from the browser.
