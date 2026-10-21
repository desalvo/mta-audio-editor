> Historical runtime report. General regression and legacy-failure status superseded by [offline finalization](R210_OFFLINE_FINALIZATION_IT_EN.md); asset and inference limits remain applicable.

# MTA 0.3.0-r210 — Work neural runtime validation / Verifica runtime neurali

21 October / ottobre 2026. No deployment; no Git mutations. Source base: MTA-0.3.0-r210-closure-validation-cumulative.zip (2639 entries, full CRC passed).

## Risultati verificati / Verified results

- Environment: real Python execution, file IO and subprocesses passed. Python 3.12.14, Linux x86_64, CPU; CUDA unavailable. Exact installed dependencies: `validation/r210-work-environment.txt`.
- Three original segments verified against manifest; reconstructed ZIP 991830047 bytes, SHA-256 `7e2803bb0e8bd1b92815eb8ca1a147ed2c59c66889e4f04b878f4dbb6590fe15`; all 15 ZIP members read with CRC verification. All 13 asset hashes and nested archive CRCs verified again by `scripts/check_neural_validation_assets.py`.
- Transkun: real CPU inference through the MTA runner with supplied `pretrained/2.0.pt` and `2.0.conf`, exact source revision c5cb8370e17b4a1650b5971ba87ee4b0d208e5b6. PyTorch 2.14.1+cpu, torchaudio 2.11.0+cpu; strict state loading succeeded. Offline audit hook enabled. Two-second synthetic decaying sine chord; valid type-1 MIDI, zero detected notes. Actual model execution, **not** recorded-piano accuracy or multi-instrument validation. No stub model substituted. Evidence: `validation/r210-transkun-real-final.log` and `r210-transkun-real-summary.json`.
- C++ core compiled from preserved sources using g++ C++20; audio DSP self-test and GM ABI 1 passed. CMake initially absent; subsequently provisioned for the native regression. No SoundFont supplied or license approval fabricated.

## Correzioni / Changes

1. Seed-VC singing conversion validates the configured architecture before launching inference: 44100 Hz and F0 conditioning in both DiT and length regulator. The supplied speech config/checkpoint is 22050 Hz, Whisper-small, F0 disabled. Passing `--f0-condition True` does not convert speech weights into singing weights. MTA now rejects this mismatch explicitly. Install bridge requirements with `requirements-studio-conversion.txt` in the MTA worker; keep upstream neural environments separate.
2. Transkun runner disables upstream training gradient checkpointing during inference. Avoids unnecessary autograd checkpoint paths and their changing PyTorch defaults; strict weight verification and offline isolation remain intact. Actual inference repeated after the change.
3. Added an offline SHA/CRC asset audit command. It does not deserialize checkpoints, download files, change registry admission or approve model rights. Dedicated tamper and path-escape regression tests.

## Runtime e checkpoint / Runtime and checkpoint findings

| Runtime | Supplied contents | Remaining blocker |
| --- | --- | --- |
| DiffSinger | Apache-2.0 source at 76b75dec8a5233afa47ef0e1377d25a080af3289 | No acoustic voicebank, flattened experiment config, phoneme profile/dictionary or vocoder checkpoint. Upstream requires NumPy <2 and librosa <0.10: do not install into MTA's NumPy 2.5 environment. |
| RVC | MIT source at 81eed5e8f68b6bed1789f682fe78cdd324495afc; Transformers HuBERT folder and RMVPE | No trained voice conversion checkpoint or voice authorization. Upstream CLI arguments match MTA. Place HuBERT under runtime assets/hubert_base and RMVPE under assets/rmvpe as required by this source revision; separately pin/review them. Optional retrieval index required when index_rate >0. |
| Seed-VC | GPL-3.0 source at 51383efd921027683c89e5348211d93ff12ac2a8; speech DiT, CAMPPlus, speech and singing configs | Missing matching F0 singing DiT, Whisper-base encoder, 44 kHz BigVGAN and complete offline auxiliary cache. Speech model cannot validate singing. Source requires torch 2.4.0, torchaudio 2.4.0, numpy 1.26.4, scipy 1.13.1, transformers 4.46.3: isolated runtime needed. Source explicitly sets HF_HUB_CACHE to ./checkpoints/hf_cache; HF_HOME alone is insufficient to relocate it. |
| Transkun | MIT source, wheel, pretrained piano weights/config | CPU execution verified; recorded-piano quality, long tracks and target OS/device integration still unverified. Piano specialist, not evidence for 10–16 independent instrument transcription. |

Each source, checkpoint, auxiliary model, voicebank, reference voice, dictionary and vocoder retains its independent license requirements. Model-card labels in the asset manifest are provenance, not blanket permission. No commercial eligibility was changed, no managed registry receipts were fabricated, no model weights are redistributed in the source package.

## Test / Tests

- Focused compatibility/contracts: 18 passed (overlaps cross-area suite).
- Cross-area: 123 passed, 1 skipped (missing approved CC0 voicebank). XML/log: `validation/r210-work-crossarea.*`.
- Native/further MIDI final: 114 passed, 7 skipped; includes real CMake builds, C++ DSP/timeline and installed espeak-ng. XML/log: `validation/r210-work-native-final.*`. The two final suites are disjoint: 237 passed, 0 failed, 8 skipped. Earlier overlapping runs are not added.
- Ruff on modified Python files passed; dependency consistency (`pip check`) passed before native additions. Exact frozen environment retained.
- Full collection: 4646 tests collected, plus two browser-module skips. General execution was interrupted at approximately 62% by automatic approval review after unexpected GitHub egress. Its incomplete log contains 2866 pass markers, 26 failure markers and 56 skip markers; these are **provisional progress markers, not a completed regression summary**. No general JUnit certification exists; no retry of the blocked path, authorization or restriction bypass performed.
- Independent local analysis of two legacy modules: 4 passed, 4 failed. Failures: two pre-global-job direct separation tests lack authenticated job identity; one expects obsolete UVR default while current catalog selects Mega53; one supplies a symlinked virtualenv Python where the Mega53 asset validator requires a regular interpreter. Kept intact and reported rather than weakening authentication, changing model defaults or relaxing asset validation to obtain green tests. `validation/r210-legacy-failures.log`.

## Stato e limiti / Status and limits

Le tre macroaree NON sono dichiarate completamente sviluppate o certificate. Sono stati risolti problemi concreti di compatibilità ed eseguita una vera inferenza Transkun; non è corretto affermare che restino soltanto prove sul tuo hardware. Mancano ancora asset autorizzati completi, regressione generale conclusa e correzioni eventualmente emerse da tali verifiche. Servono anche benchmark annotati 10–16 strumenti e accettazione GM con banca reale.

The three macroareas are NOT declared fully complete or certified. Actual Transkun execution and local regression are verified; full model bundles, complete regression and any resulting engineering work remain open. Target-hardware-only work includes native Windows/macOS/ROCm/GPU and browser/device playback and musical listening acceptance; missing assets and incomplete regression are separate blockers.

AI legacy, VST SDK, sources, tests and existing documentation are preserved. Version remains 0.3.0-r210. No commit/push/tag/release or real server changes.
