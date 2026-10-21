> Historical cycle record / Resoconto del ciclo precedente. Per lo stato attuale, i limiti aggiornati e le attività ora implementate consultare [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md) e [guida asset IT/EN](STUDIO_MANAGED_ASSETS_R210_IT_EN.md).

# Three-area implementation / Implementazione delle tre macroaree — 0.3.0-r210

This is a substantial cumulative software cycle, **not certification that all three areas are complete**. No version/revision increment, Git commit, push, tag, release, production deployment or server changes were performed. All prior source files, legacy AI integrations, SDKs, tests and documentation remain in the package.

## Vocal Studio / Studio vocale

Implemented:

- IT/EN/FR now traverse settings, independent singer lyrics, queue and neural renderer. OddVoices remains English/vocalise only; unsupported backend/language combinations are explicitly rejected.
- Existing reviewed IT/EN/FR lexicons and English native-phone input are preserved. Optional automatic G2P uses the actual external eSpeak NG library/dictionaries, not a handwritten linguistic approximation or fake model. Three language fixtures were executed using espeakng-loader 0.2.4 in this environment.
- A SHA-256-pinned bank profile binds the IPA map and reviewed inventory to the exact acoustic checkpoint. Every emitted phone must be present in that inventory; missing IPA units, multiple vowel nuclei in one MIDI note and mismatched banks fail explicitly. This validates the supplied reviewed inventory, **not automatically the upstream singer's training language or pronunciation quality**. Full-text syllabification/alignment remains manual: one lyric syllable per note; repeated vowels for melismas.
- OpenVPI acoustic scores include the required F0 and timestep, rests, explicit phoneme durations and multi-phone syllables. The vowel receives the sustained duration and consonants bounded duration weights. These are deterministic score decisions, not learned duration prediction.
- Score-derived vibrato (depth/rate/delay), tuning and note gate; neutral/gentle/sustained/straight presets; velocity/dynamics, attack, release and gain through explicit PCM amplitude envelopes. This DSP is documented separately from neural expression. Bank-dependent energy/breathiness/voicing/tension curves, gender and speed are accepted through `settings.expression` only when the bank config supports them. Required missing embedding curves are rejected before inference.
- Exact acoustic checkpoint selection via `--ckpt <step>`; verified vocoder must match the experiment config. Previously hashing one checkpoint while loading an unverified newer one was possible. Configuration SHA-256 and separate vocoder license admission are now required. A free-only singer **or** vocoder makes the combined operation free-only.
- Region inputs inherit the editor's extraction range. Selecting one syllable, word or phrase creates a new time-aligned take with editable MIDI and project revision protection. Existing takes are retained; this is not an automatic destructive splice/word selector.
- Per-source generation metadata now retains every singer instead of overwriting it with the final singer. Neural audio provenance no longer says `oddvoices-cc0`. Settings/lyrics have a 48 KiB serialized per-worker metadata budget; use phrase regions for larger requests.

### Server setup / Configurazione server

Use an isolated deployment interpreter and licensed assets. The cumulative package contains no new voicebank, neural weights or vocoder. Existing OddVoices setup is unchanged.

Required DiffSinger environment:

```
MTA_DIFFSINGER_ROOT=/absolute/path/to/DiffSinger
MTA_DIFFSINGER_EXPERIMENT=singer
MTA_DIFFSINGER_PYTHON=/absolute/path/to/regular-python-binary
MTA_DIFFSINGER_PYTHON_SHA256=<actual interpreter SHA-256>
MTA_NEURAL_SINGER_CHECKPOINT=/absolute/path/to/DiffSinger/checkpoints/singer/model_ckpt_steps_123.ckpt
MTA_NEURAL_SINGER_SHA256=<actual acoustic SHA-256>
MTA_NEURAL_SINGER_POLICY_MODEL=<registered, reviewed singer identity>
MTA_DIFFSINGER_VOCODER=/absolute/path/to/DiffSinger/checkpoints/vocoder/model
MTA_DIFFSINGER_VOCODER_SHA256=<actual vocoder SHA-256>
MTA_DIFFSINGER_CONFIG_SHA256=<SHA-256 of checkpoints/singer/config.yaml>
MTA_DIFFSINGER_VOCODER_POLICY_MODEL=diffsinger-vocoder
```

The experiment `config.yaml` must be flattened (no unresolved `base_config` inheritance) and its `vocoder_ckpt` must resolve to the verified vocoder. Review/authorize the individual vocoder through Studio model license policy; it defaults to disabled. Selecting another policy ID is only legitimate for the actual licensed vocoder, never as a billing bypass. Models requiring variance curves must receive those curves through the expression API; the compact UI currently exposes the basic score controls.

Read-only preflight:

```
python scripts/check_diffsinger_ready.py --json
```

Install `requirements-studio-diffsinger.txt` into the MTA singing worker for pinned YAML config validation. For G2P, install `requirements-studio-phonemizer.txt` into the MTA singing worker interpreter. eSpeak NG is an optional external GPL component with separate source/notice obligations when redistributed. No eSpeak binary or dictionary is included in this ZIP. Alternatively configure administrator-controlled absolute `MTA_ESPEAK_LIBRARY` and `MTA_ESPEAK_DATA` paths. The library is loaded only by singing workers.

Set `MTA_DIFFSINGER_PHONEMES` and `MTA_DIFFSINGER_PHONEMES_SHA256`. Supply a reviewed JSON profile with:

- `schema`: `mta-bank-phonemes-1`.
- `language`: `it`, `en` or `fr`.
- `bank_sha256`: exact acoustic checkpoint SHA-256.
- `inventory`: the actual bank's reviewed unique phoneme tokens, including `SP`.
- `vowels`: vowel tokens from that inventory.
- `ipa_map`: IPA unit → list of native bank tokens. Mapping uses longest matching units, preserves nasalization/length and removes stress markers only. No silent guessed substitutions.
- Optional `bank_language`: the bank's exact OpenVPI language key for multilingual models.

Profiles are bank-specific assets. No example inventory is represented as compatible with a real singer. The current environment variables select one reviewed profile/experiment per worker deployment; independent neural-bank selection per singer still requires a managed multi-bank registry. The existing independent OddVoices bank selections remain available.

Choose DiffSinger, the lyric language and Automatic eSpeak in the UI; or use `pronunciation: "lexicon"` with the legacy pinned lexicon variables. A word not covered by a legacy dictionary remains an error. Real-bank pronunciation review remains required in all three languages.

**Still incomplete:** RVC/Seed-VC timbre conversion; managed neural voicebank/vocoder installation and independent neural-bank selection per singer; full text-to-note alignment; learned variance prediction; complete advanced-curve editing UI. Seed-VC's GPL code and separate DiT/Whisper/BigVGAN assets require a version/checkpoint-specific rights and runtime selection before implementing a reproducible deployment. These are actual remaining software/integration tasks, not merely listening tests.

## Audio-to-MIDI / Trascrizione multitraccia

- Fast and Accurate retain their previous semantics. Deep (`maximum`) is now a distinct functional pipeline: registered/metered Demucs `htdemucs` four-source separation; YourMT3 for bass/drums/other/vocals; YourMT3 + Basic Pitch reconciliation separately for the three pitched sources. Basic Pitch is never reinterpreted as a drum model.
- The same model on multiple stems is **not** counted as independent-model confidence. Source identity survives in part IDs/names, including repeated GM programs. Same-program players within one separated source remain unresolved.
- Demucs, YourMT3 and Basic Pitch admission are all checked before starting. Any free-only component imposes the stricter free-only policy on automatic and manual server import. Each real worker retains its existing metering and native/remote routing; no unmetered inference path was added.
- Cancellation and a single total deadline cover separation and all source/model passes. Remote acknowledgements happen after completed musical output is durably saved. Empty, malformed or failed model output fails explicitly; there is no filler MIDI. Silent/no-note stem handling and recovery within a partially completed separated source still need improvement; completed original source results retain existing retry recovery.
- Four exact, bounded, validated Demucs WAV artifacts are required. No arbitrary artifact path or executable can be supplied by a client.
- Install/enable the existing Demucs `htdemucs`, YourMT3 and Basic Pitch runtimes on the server. Native remote mode also needs a Demucs route (in addition to the transcription route). No automatic migration of remote tokens/settings is performed.

**Not guaranteed:** 10–16 independent performers, inferred velocity for YourMT3 (its existing explicit value 96 remains), automatic duplicate removal across leaking stems, or full-mix accuracy. The pipeline returns only parts really emitted by models and can produce fewer than ten parts. Basic Pitch can estimate velocity for isolated pitched sources; that is not a full-mix dynamics guarantee. Use the existing reproducible ground-truth benchmark and inspect its per-instrument metrics.

### Specialist model assessment / Valutazione specialisti

| Candidate | Assessment and decision in this package |
|---|---|
| Existing YourMT3 noPS multi-decoder | Preserved pinned runtime/tensor checkpoint; actual installed backend used by the pipeline. No claim that a different YourMT3+ checkpoint was installed. |
| Google MT3 | Distinct T5X/JAX runtime and checkpoint; not installed/validated here. No relabeling of YourMT3 as Google MT3. |
| MR-MT3 / MT3-Infer | Separate implementations/checkpoint provenance and license validation required; not executable backends in this package. |
| Transkun | Upstream identifies it as a piano transcription system with MIT code. Useful for an isolated piano source, not a 16-instrument classifier. No exact checkpoint/runtime installed or integration claimed. |
| Basic Pitch | Retained real ONNX isolated-pitched-source backend; not used for percussion or automatic source identity. |

**Still incomplete:** specialist inference adapters/checkpoint registration beyond the two existing transcribers, independent same-source players, learned YourMT3 dynamics, robust silent-stem continuation, and validated stereo benchmarks. No specialist contract-only stub is presented as implemented inference.

## General MIDI / Generatore GM

- Native C++ core built successfully in this environment; actual reviewed FluidR3 3.1 bank installed in a temporary local test area and validated by its pinned hash. Neither that bank nor the compiled test library is added to the source ZIP.
- Actual TinySoundFont PCM audit now covers all 128 melodic programs and all 47 standard percussion notes 35–81 on channel 10. The audit tries pitches C4/C3/C2/C5 because SF2 presets may have limited key ranges; contrabass legitimately lacks the initial C4 sample in this bank. This checks audible finite PCM, not timbral fidelity.
- Corrected portable Bank Select state: MSB/LSB represent a persistent 14-bit bank across successive controller changes and Reset All Controllers. No changes to the vendored TinySoundFont source.
- Actual PCM tests cover volume, expression, velocity, sustain/release, pan, pitch bend, overlapping notes, All Sound Off, and type-0/type-1 SMF-to-WAV rendering with tempo changes. FluidSynth-specific behavior remains unexecuted here because its shared library is not installed. Portable aftertouch remains explicitly unsupported.
- Additional reviewed local SF2 banks can be installed using the administrator CLI below. File and license notice hashes are checked; no download, path selected by an HTTP client, or overwrite of existing banks. Supported license declarations are MIT, CC0, BSD and CC-BY-4.0; the operator must have the actual corresponding rights. This is not a license grant or automatic provenance determination.
- Authorized installed banks appear in the shared web/native MIDI instrument selector; bank ID persists in projects. Switching banks requires reloading the instrument. Each backend uses the exact selected bytes. Custom banks are not reported as verified 128-program GM banks until independently audited.

```
python scripts/install_gm_soundfont.py /local/reviewed.sf2 --id sf2-my-bank \
  --name 'Reviewed bank' --sha256 ACTUAL_SHA256 --license MIT \
  --license-file /local/LICENSE.txt --evidence-url https://publisher.example/license \
  --rights-reviewed
python scripts/check_gm_soundfont.py --bank-id sf2-my-bank --output gm-audit.json
python scripts/render_gm_midi.py song.mid song.wav
```

Existing synchronized editor playback, mixer/export, project persistence, FluidSynth, TinySoundFont and default FluidR3 support remain. Final web/native/device playback, FluidSynth parity, real-project reopening and musical listening still require target-system acceptance. The three macroareas therefore **cannot yet be marked software-complete**.

## Primary technical references / Fonti tecniche primarie

- OpenVPI acoustic input fields and checkpoint CLI: https://github.com/openvpi/DiffSinger/blob/main/inference/ds_acoustic.py and https://github.com/openvpi/DiffSinger/blob/main/scripts/infer.py
- OpenVPI exact checkpoint loading: https://github.com/openvpi/DiffSinger/blob/main/utils/__init__.py
- eSpeak NG: https://github.com/espeak-ng/espeak-ng ; optional loader https://pypi.org/project/espeakng-loader/0.2.4/
- Demucs: https://github.com/facebookresearch/demucs
- Transkun: https://github.com/Yujia-Yan/Transkun
- Seed-VC (not integrated): https://github.com/Plachtaa/seed-vc
- Google MT3: https://github.com/magenta/mt3

Technical source inspection is not a substitute for independent asset license review. See the machine-readable validation reports included with this cycle for actual executed checks and their limits.
