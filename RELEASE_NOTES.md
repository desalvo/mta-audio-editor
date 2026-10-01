# MTA Audio Editor 0.2.0-6 - Release Notes

This release combines the extended processing/mixing system with verified, conservative reverse-engineering support for real M-Live MTA samples and fixes the GitHub production pipeline.

## Real MTA inspection
- Decode standard ID3v2.3 text metadata embedded in SYL attachments.
- Parse the observed DELTA and Lyrics3-like wrappers for LYRICS, COLORS, MIDITK and CHORDS.
- Detect the verified COLORS layout: 3-byte binary prefix followed by 15-byte records with a structurally distinct terminal record.
- Expose read-only observed decoders only when their structural invariants validate; undocumented semantics are not rewritten speculatively.
- Parse MtxInfoData XML, including track metadata, zero padding and NoteOn vector/duration consistency.
- Fall back to direct EBML FileData extraction when FFmpeg cannot dump attachments from non-canonical MTA containers.
- Preserve opaque and unknown proprietary bytes for lossless round-trip handling.

## GitHub Actions
- Keep Python 3.11 and pin NumPy to the compatible 2.4.6 release.
- Update checkout/setup-python/upload-artifact, Docker, Gitleaks, Trivy and CodeQL actions to current generations.
- Retain unit/coverage, DSP runtime validation, SAST, dependency audit, secret scanning, filesystem/image scanning, smoke tests, SBOM and provenance gates.

## Audio processing and Auto Mix
- Delay, Lexicon-style Reverb, Room/Ambience, 32-band Graphic EQ, Amplify, Stereo Imager, Maximizer/Loudness, Mastering Wizard, De-Noise and Crackling Cleaner.
- Factory presets, bounded custom parameters and persistent user presets.
- Reversible Auto Mix with Balanced, Studio, Live and Gentle profiles.
- 87 factory/default DSP configurations validated through the real FFmpeg runtime.
