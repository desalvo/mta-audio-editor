# MTA 0.3.0-r210 — Finalizzazione regressione offline / Offline regression finalization

This report supersedes the general-regression and legacy-failure status in the previous Work runtime report. No version change, Git mutation or production action.

## Modifiche effettive / Implemented changes

- Fixed remote lead/backing artifact selection: `backing_vocals.wav` could match the generic `vocal` predicate and be published as both tracks when listed first. Select distinct artifact indices, prioritize backing/instrumental and lead labels, and support identical silent bytes without treating the second artifact as missing. Four dedicated regressions.
- Added opt-in `MTA_TEST_OFFLINE=1` test isolation: disable optional Demucs auto-update and UVR checkpoint repair before application imports, force HF/Transformers offline, prohibit external Python DNS/connect/connect_ex while allowing loopback. Production defaults and OS network restrictions remain unchanged. No approval or retry of the rejected external GitHub request.
- Reconciled legacy test harnesses with the current architecture: explicitly local desktop extraction for local separator/lyrics tests; current Mega53 default; real interpreter path rather than a venv symlink; authenticated admin before testing server-native alias boundaries. No production authentication checks were removed or relaxed.
- ChordFormer archive extraction tests now use the existing generated-fixture rights helper, scoped to a temporary policy file. Downloads remain mocked; no third-party model license approval or real inference is implied. Independent policy regression passed.
- Real Unix-socket transport tests check platform capability synchronously and skip if AF_UNIX creation/binding is denied. Do not weaken OS restrictions. Nine additional mock-transport tests exercise malformed payload rejection, diagnostic-only billing status and host identity/token redaction even without Unix IPC. These are protocol unit tests, not real transport acceptance or neural inference.
- Restored executable permissions from the original ZIP metadata in the working tree. The archive already carried 0755 on shell installers and the unified worker; Python ZIP extraction had placed them as 0644. No upstream mode change is invented.

## Regressione / Regression

- **Final complete offline run:** 4579 passed, 0 failed, 85 skipped, 6 warnings in 500.25 seconds; exit code 0. `validation/r210-offline-final-verified.log` and `.xml`; machine-readable summary and every skip reason: `validation/r210-offline-final-summary.json`.
- **First complete pass:** 4546 passed, 30 failed, 75 skipped, 16 warnings. All 30 outcomes were analyzed; corrected harnesses/modes were verified, and the 10 forbidden Unix IPC cases are explicitly skipped by capability, with separate protocol validation. First-pass evidence: `validation/r210-offline-final-general.*`. The final whole-suite run is authoritative; counts are not additive.
- **Warnings:** one Starlette/httpx deprecation, three existing duplicate OpenAPI operation-ID warnings, and two intentionally malformed ZIP tests which create duplicate entries. Not suppressed.
- **Skip inventory:** 33 external VST/SDK cases, 13 reviewed real GM-bank cases, 5 neural/voicebank/model cases, 10 forbidden Unix IPC cases, 21 browser/Playwright cases (including two collection skips), 1 Happy DOM case, 1 real audio-device case and 1 Win32 API case. Browser/DOM dependencies are software environment gaps, not user hardware-only tasks. No skipped case is counted as passed.

Historical first-pass logs are kept as evidence, not added to final totals. Local focused 76 passed/10 Unix-transport skips, 9 protocol tests, 9 license-policy tests and 8 remote/local vocal-selection tests overlap the final general suite and must not be added.

Run the safe regression from the checkout with its pinned development dependencies and CMake/compiler available:

```bash
MTA_TEST_OFFLINE=1 python -m pytest -q --timeout=120 --junitxml=validation/r210-offline-final-verified.xml
```

The offline Python guard is test isolation, not an OS sandbox for arbitrary native programs. Existing OS network controls remain in force. Optional browser/DOM, real model/voicebank/SoundFont/VST and Unix transport integrations report their actual missing capabilities instead of success.

## Asset, inferenze e limiti / Assets, inference and limits

Previous evidence retained: asset archive 991830047 bytes and SHA-256 `7e2803bb0e8bd1b92815eb8ca1a147ed2c59c66889e4f04b878f4dbb6590fe15`; all segment hashes, all asset hashes and nested ZIP CRCs passed. Actual Transkun CPU inference loaded strict real pretrained weights and returned valid MIDI with zero notes on a synthetic chord. This proves runtime execution, not musical accuracy. No fixture substituted for model execution.

The remaining requirements are not only hardware acceptance:

| Area | Required before full end-to-end sign-off |
| --- | --- |
| DiffSinger | Authorized matching acoustic voicebank, flattened experiment config, phoneme/language profile and vocoder; isolated NumPy <2/librosa <0.10 environment; real pronunciation/expression inference |
| RVC | Authorized acoustic conversion checkpoint and voice rights; exact supplied runtime layout for HuBERT/RMVPE; pinned retrieval index when enabled; real voice conversion |
| Seed-VC | Matching 44.1 kHz F0 singing DiT checkpoint, Whisper-base, matching BigVGAN and complete local auxiliary cache; isolated upstream dependencies; real singing conversion |
| Multi-track Audio-to-MIDI | Reviewed general multitrack model(s) and independently annotated 10–16-instrument recordings; Transkun is piano-only |
| General MIDI | Reviewed full SoundFont and real bank/controller/SMF playback; native VST assets where applicable |
| Target environments | Real Unix IPC, Windows/macOS/ROCm/GPU, audio device/browser/native integration and musical listening |

Missing bundle contents must be resolved separately from target hardware. No automated registry authorization, downloaded replacements, fabricated license receipts or claim of fully completed neural workflows. See `R210_WORK_NEURAL_RUNTIME_VALIDATION_IT_EN.md` for exact supplied source revisions and dependency conflicts.

## Messaggio di commit / Suggested commit

`docs/COMMIT_MESSAGE_R210.txt` contains one cumulative line. Basis: last explicit user commit confirmation on 19 October 2026 before the subsequent metronome/UI/manual and studio cycles; no exact Git SHA was available. ZIP SHA values are not Git commit IDs. The message incorporates subsequent MIDI/AI Studio, licensed voices, billing/regime, routing/recovery, GM, installers/imports, runtime validation and this offline finalization. No commit was executed.

AI legacy, SDK VST, sources, tests and existing documentation remain preserved.
