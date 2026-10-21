> Stato aggiornato / Current status: vedere [correttezza dei risultati combinati](R210_COMBINED_RESULTS_IT_EN.md), [runtime reali](R210_DIFFSINGER_DEEP_CLOSURE_IT_EN.md) e [guida ai collaudi](R210_DIFFSINGER_DEEP_ACCEPTANCE_IT_EN.md). Le sezioni di avanzamento qui sotto documentano una fase precedente e non rappresentano il catalogo attuale. Earlier progress sections below are historical, not the current model catalog.

Current workflow update: see [STUDIO_WORKFLOWS_R210_EN.md](STUDIO_WORKFLOWS_R210_EN.md). The sections below describe the earlier foundation checkpoint; project UI, model installation, queue workflows and controller lanes have since been added. The full AI specification remains incomplete.

# AI studios / advanced MIDI checkpoint — 0.3.0-r210

This is an **incomplete development checkpoint**, not the final delivery of AI Vocal Studio or Multi-Track Audio-to-MIDI. The functional specification received on 20 October 2026 remains the acceptance contract. See the Italian companion for the complete implementation matrix and operator configuration example.

## Implemented and locally tested

- `mta-music-1` shared musical result schema: independent parts, notes/controllers, source model, event origin, offsets and retained alternatives. Empty filler tracks are rejected; aggregate event and timeline budgets are validated.
- Authorized, atomic musical import: `GET /api/projects/{pid}/midi/revision` and `POST /api/projects/{pid}/midi/music`. Supply a 32-hex publication ID, expected project revision and typed result. A stale project or conflicting replay is rejected; an identical replay cannot create duplicates. Commit errors preserve already-published media. Sixteen independent parts have been tested for persistence; this is pipeline/editor capacity, not 16-instrument recognition.
- SMF0/1/2 import/export, independent SMF2 tempo maps, SMPTE 24/25/29.97/30 timebases. Notes retain source timing; SMF0/1 use the project grid. Remap conflicting channels before combining independent patterns. UMP remains a separate lossless JSON export.
- MIDI piano roll virtualization, group editing, undo/redo, quantization/swing/humanization, split/join, searchable paginated event list and metadata persistence. Full professional controller/automation editing is still open.
- Identity-scoped lazy DB preferences for editor/sidebar/MIDI device choices, including retry and a durable pending browser queue. Migration of every historical native setting to the DB is not finished.
- Linked MIDI metronome derived from fixed/zoned/adaptive project timing. Unlink it before manually editing its notes. A tempo graph supports a separate dialog or first-track overlay, decimal BPM and keyboard/mouse editing; adaptive timing is read-only.
- Real FluidSynth/FluidR3 GM synthesis, tested offline and inside the server playback worker. Per-track program/bank/gain/polyphony/reverb; MIDI remains editable when the instrument is missing. No third-party library or soundbank is bundled in this source archive.
- Real Basic Pitch 0.4.0 ONNX CPU transcription of an isolated source. Tested through the existing global queue, artifact packaging and CPU ledger. No GPU use is claimed. The synthetic four-note fixture also produces a false extra note; it is not a real-song quality benchmark.

## Still open

Vocal synthesis/conversion and authorized voicebanks; IT/EN/FR phonemization and lyrics alignment; Vocal Studio UI/presets/voice previews; production multitrack transcription and instrument classification; model reconciliation and conflict review; model administration/install/self-test; source-region workflows; checkpoints/cache/recovery for the new pipelines; dedicated ASIO and complete physical audio/MIDI routing; full hardware/platform/GPU acceptance. No mock singer or filler instrument is substituted for those features.

The independent harmony planner currently supports SATB-style MIDI voicings for 2–8 voices, configurable ranges, no crossings, movement penalties and precedence for confirmed project chords. Four/eight-part tests pass. Musical quality, extended styles and synthesis remain unverified; this is not a completed Vocal Studio backend.

## Optional GM runtime

Install a dynamic FluidSynth library and the reviewed FluidR3 GM 3.1 bank separately. Recognized locations are the application data `soundfonts/FluidR3_GM.sf2`, `/usr/share/sounds/sf2/FluidR3_GM.sf2` and `/usr/share/soundfonts/FluidR3_GM.sf2`. Operator-only overrides: `MTA_FLUIDSYNTH_LIBRARY` and `MTA_GM_SOUNDFONT_DIR`.

Bank size: 148,398,306 bytes; SHA-256:
`74594e8f4250680adf590507a306655a299935343583256f3b722c48a1bc1cb0`.

FluidSynth licensing: https://github.com/FluidSynth/fluidsynth/blob/master/LICENSE (LGPL-2.1). FluidR3 bank licensing: https://sources.debian.org/src/fluid-soundfont/3.1-6/debian/copyright (bank MIT; Debian packaging separately GPL-2+). Preserve applicable notices and distribution obligations. Automated cross-platform optional GM installation remains open.

## Basic Pitch pilot

Not automatically installed or production-enabled. Use a separate operator-managed Python 3.12 environment; do not replace the server/ROCm NumPy stack. Tested: Basic Pitch 0.4.0, ONNX Runtime 1.31.0, NumPy 1.26.4, librosa 0.11.0, resampy 0.4.2, pretty-midi 0.2.11.post0, pydantic 2.12.5 and setuptools 80.10.2. The ONNX adapter does not require TensorFlow, despite upstream package metadata; a full production dependency lock/review remains pending.

Register `audio-to-midi` in the existing operator worker registry, pointing to the executable `app/ai_studio_adapter.py` and the isolated Python interpreter, with `gpu_capable:false`. Set `MTA_AI_WORKER_ENABLED=true`. Existing token-authenticated `/api/ai-jobs/execute-audio/audio-to-midi` performs queued execution/accounting; clients cannot select arbitrary executables or model paths.

The model checksum is checked on every worker startup:
`2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec`.

Input: mono/stereo source, up to ten minutes/192 kHz, subject to the existing WAV transport restrictions. Parameters: onset/frame thresholds, minimum note length, name and optional explicitly assigned GM program. Output: `music.json` in the existing artifact manifest. There is no instrument classifier, imported pitch bend or calibrated note confidence. Activation affects velocity only. Progress reports real phases without a fabricated inference percentage. Production UI import and the complete studio workflow are still pending.

Basic Pitch upstream: https://github.com/spotify/basic-pitch, Apache-2.0. The tested model ships in its wheel; no weights are redistributed in this archive. Code, weights, datasets, voicebanks and transitive dependencies must be reviewed separately before production distribution. YourMT3+, MT3, MR-MT3, Transkun, MT3-Infer, DiffSinger, Amphion, RVC and Seed-VC are not enabled merely because their names appear in the specification. Worker process isolation does not automatically resolve copyleft compatibility.

## Resume order

Finish reviewed model installation/capabilities; connect Source/Execution/Results UI to the existing queue and atomic publisher; add and evaluate a licensed multitrack backend; integrate authorized singing/conversion voicebanks and lyrics; finish ASIO/routing/controller editing; execute all specified end-to-end acceptance tests on the actual server and native platforms.
