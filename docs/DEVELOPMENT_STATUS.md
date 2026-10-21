## 2026-10-21 — CI lint repair and multitrack accuracy development (in progress)

- **Starting state:** uploaded CI logs show 15 Ruff findings, 4 unused imports and 11 test-only S108/S311 findings; quality job failed. All 10–16 instrument accuracy gates remain open; model weights and representative ground truth are not available in the ZIP.
- **Completed:** removed four unused imports; added narrow test-line Ruff comments for fixed mocked /tmp paths and predictable non-cryptographic seeded random generator. No production code or global lint configuration weakened.
- **Verified:** 47 targeted pytest cases passed, Python compile of six modified test modules passed. CI static Ruff rerun blocked by unavailable executable / network resolution. Full CI rerun is still pending.
- **Pending:** full CI and independent end-to-end neural quality runs; avoid asserting 10–16-instrument accuracy from archived negative results.
- **Blocked:** no authorized 10–16 instrument model checkpoints and representative paired ground-truth mix/MIDI provided; past MR-MT3 F1=0 gate remains unsatisfied.

## 2026-10-21 — Post-commit diagnostic cycle / Ciclo diagnostico Audio-to-MIDI

- **Completed/Completato:** verified source ZIP size/SHA and CRC for 3,080 entries; inspected state documents and code; added explicit non-scoring instrument/onset error diagnostics and regression test; README IT/EN and cycle report updated.
- **Verified/Verificato:** 32/32 focused pytest passed (includes 19 benchmark cases); Python compile passed; replay of archived real MR-MT3 output still fails unchanged 10-instrument quality gate (F1=0, exit 2). Diagnostic data: 13 pitch/onset overlaps across programs, 1 program/pitch/onset overlap; neither is a strict note match.
- **Pending/Pendente:** real new neural inference and software/model optimization toward accurate 10–16 instrument separation; full-suite all-green regression; Qixuan IT/FR artistic listening.
- **Blocked/Bloccato:** no model checkpoint present in source ZIP for fresh inference; separate Qixuan IT/FR bundle not locally present. No target hardware claims. Historical failures and lint findings remain disclosed, not silently resolved.
- **Policy:** version 0.3.0-r210, no Git operations, deployment or loosened accuracy gates. See `docs/R210_POSTCOMMIT_MIDI_DIAGNOSTICS_IT_EN.md`.

## 2026-10-21 — Qixuan IT/FR and native/MIDI workflow verified

- Complete general regression: **4717 passed, 18 failed, 0 errors, 98 skipped, 6 warnings**, 1935.07s. All 18 failed cases passed the final retry; **4735 distinct cases verified**. No single all-green full invocation is claimed. Late source changes have focused verification; detailed skips and overlapping focused counts in `validation/r210-qixuan-midi-native-summary.json`.
- Qixuan existing-bank software complete: parent→pinned runtime G2P, contextual French liaison, effective readiness,12 actual CPU ONNX cases and78 G2P words. IT/FR are disclosed cross-language projections, not native acoustic training; listening remains. New complete bank preserves 37 original members, distinct ID, disabled pending genuine operator review.
- Native desktop/mobile UI zoom, audio/MIDI project modes and safe reversible conversion, metronome origin including pre-roll, four-field transport, unified MIDI/tempo synchronization, audible SMF export and visible musical quantization implemented. Fixed double scaling of metronome tempo, stale conversion state and ambiguous toolbar icons.
- Native core Release build, Ruff for changed/new sources, compile and JS syntax passed; whole-archive Ruff retains 51 findings in byte-identical baseline files. Physical Windows/macOS/Linux GUI, mobile builds/devices, audio/MIDI/VST and Qixuan listening remain target acceptance.
- Historical 10–16-instrument transcription accuracy still open; no new transcription inference or quality closure claimed this cycle. Version 0.3.0-r210 unchanged; no Git/production actions. Current report: `R210_QIXUAN_MIDI_NATIVE_IT_EN.md`. Earlier entries below are historical.

## 2026-10-21 — Administration and Qixuan IT/FR verified; accuracy target still open

- Final general regression: **4680 passed, 0 failed/errors, 98 skipped, 6 warnings**, 540.37 s, exit 0. Focused counts overlap and are not added. Exact skip reasons in `validation/r210-admin-language-final-summary.json`.
- Fixed protected tariff navigation; retained the useful central tariff link. Added engine-grouped individual model-file source download, exact SHA restore, export and selective deletion with locks, cache safety and unchanged license admission.
- Qixuan: pinned EN/IT/FR profiles, real-prefix phone editing, default vocalise, receipts/UI and complete upgraded bank. **IT/FR are disclosed cross-language projections, not native trained acoustic languages.** 78 real G2P words, 8 actual CPU ONNX cases and 2 actual Studio parent-G2P checks passed. Original 37 bank/vocoder members unchanged; asset disabled pending genuine review. User-approved dependencies installed; pip check clean.
- Optional strictly verified MR-MT3 baseline integrated; original baseline and memory checkpoints both ran real CPU inference but failed the unchanged ten-program mix (F1=0). **10–16-instrument quality remains unresolved software/model work, not just user hardware acceptance.** No fixtures counted as inference or thresholds relaxed.
- Current report: `R210_ADMIN_QIXUAN_ACCURACY_IT_EN.md`; detailed administration and Qixuan guides linked there. Version remains 0.3.0-r210; legacy AI/SDK retained; no Git or production operations. Earlier entries below are historical.

## 2026-10-21 — Combined-result correctness verified / Risultati combinati verificati

- **General regression: 4598 passed, 0 failures/errors, 98 skipped**, 546.63 s. Log/XML and exact skip reasons in `validation/r210-combined-*`. More prerequisites are absent after scratch reset than in the previous environment; skips are not passes.
- r210 area: 1369 passed / 138 skipped / 0 failed. Focused: 53 passed. Counts overlap and must not be added. Ruff and compilation passed; native C++ Release core built successfully.
- Fixed: explicit empty-score parsing, region offset/warnings preservation, nonempty primary fallback, combined Deep MIDI channel/controller routing, Basic Pitch/YourMT3 source-duration bounds and cache invalidation, final worker cancellation, and voice-vs-playback-proxy benchmark identity.
- Stored actual Deep output replayed through routing and SMF 0/1: 55 notes preserved within 1 ms, original alternatives unchanged, accuracy unchanged. No new neural inference this cycle; prior real-inference evidence retained as historical.
- **Still open:** 10–16 instrument accuracy, Qixuan IT/FR bank/profile review, target OS/browser/device/VST/GPU acceptance. Not a hardware-only completion claim. See `R210_COMBINED_RESULTS_IT_EN.md`.
- Version 0.3.0-r210 unchanged; all previous archive paths retained, legacy AI/SDK untouched. No Git or production changes. Suggested cumulative commit is compact, one line (157 characters); exact last-user-commit SHA unavailable in this source-only archive.

## 2026-10-21 — Combined-result correctness in progress

- Restored SHA/CRC-verified last cumulative after scratch reset; prior real-inference evidence retained, environments are not retained.
- Reproduced empty-score offset loss and rejection of valid no-notes JSON by benchmark; fixing three-model primary fallback, Deep channel collisions and cancellation after final worker.
- No claim of new neural inference, no 10–16 accuracy closure. Version 0.3.0-r210 unchanged.

**21 October 2026 — current r210 verification:** 4,608 passed, 0 failed, 80 skipped, 6 warnings (524.10 s). Final changed-area checks: 68 passed; the last vocal identity adjustment also passed real Qixuan→YourMT3 PS inference. Real DiffSinger ONNX singing and the metered Deep pipeline/replay now work. The ten–sixteen instrument accuracy gate remains unmet and is not a hardware-only limitation. See [current bilingual report](R210_DIFFSINGER_DEEP_CLOSURE_IT_EN.md) and [acceptance guide](R210_DIFFSINGER_DEEP_ACCEPTANCE_IT_EN.md). Version remains 0.3.0-r210.

## 2026-10-21 — Deep runtime closure in progress

- Starting archive: `MTA-0.3.0-r210-real-runtime-handoff-cumulative.zip`; version unchanged. No Git/production actions.
- Objective: actual complete separated/transcribed/reconciled Deep execution, additional real runtime gates and concrete DiffSinger asset search.
- Basic Pitch isolated ONNX installation and actual self-test passed; Demucs 4.1.0 installed with the existing pinned CPU torch/NumPy stack. Official HTDemucs weights are being checksum-verified before offline use.
- No new completion claim yet. Previous ten-program benchmark failure and missing DiffSinger bank remain explicit gates.

## 2026-10-21 — Real CPU runtime handoff / Passaggio con runtime reali

- **Final general regression:** 4596 passed, 0 failed/errors, 80 skipped, 6 warnings; exit 0, 543.30 s. XML/log and detailed skip reasons included. 22 focused checkpoint/runner tests and 23 real GM tests overlap the general count.
- **Actual execution:** RVC, strict Seed-VC F0 44k, Transkun 2.0 and YourMT3 noPS ran offline on CPU. Piano notes 60/64/67 detected by Transkun and YourMT3. FluidR3/TinySoundFont produced valid real PCM for 128 programs and 47 drums. HappyDOM flows executed. All three environments passed pip check.
- **Fixed:** RVC namespace import shadowing; complete strict active Seed checkpoint validation with narrowly checked deterministic/legacy compatibility; linear Seed export headroom based on actual 48 kHz resampling overshoot. The final real Seed output passed the production PCM guard after resampling. This cannot undo the upstream BigVGAN output clamp or certify timbre.
- **Test prerequisites:** 11 cases exposed missing Chromium after Playwright installation. Explicit binary capability checks now skip only when absent and do not suppress launch/runtime failures for an installed executable. Original failed run retained; browser acceptance not claimed.
- **NOT complete / Non concluso:** ten-program actual YourMT3 benchmark returned 5 parts/7 notes, only 1 exact instrument/pitch/timing match, F1 0.117647: target not met. Authorized complete native DiffSinger bank/vocoder/profile missing. Deep/representative recorded-music quality, browser/Unix transport, FluidSynth, target VST/OS/device/GPU tests remain. **Not all remaining gates are hardware-only.**
- Version 0.3.0-r210 unchanged; no Git/production actions. All previous archive paths and SDK/legacy entries retained. No model weights or runtime environments redistributed. Licenses, attribution, hash receipts and technical audio included.
- Current report: `docs/R210_REAL_RUNTIME_HANDOFF_IT_EN.md`; actionable target steps: `docs/R210_TARGET_ACCEPTANCE_IT_EN.md`; cumulative one-line suggested commit: `docs/COMMIT_MESSAGE_R210.txt` (last confirmed user commit 19 October; exact SHA unavailable).

## 2026-10-21 — Remaining software acceptance in progress

- Goal: close browser/DOM and real GM gaps, identify complete authorized neural bundles and remaining software incompatibilities.
- Starting verified regression: 4579 passed, 0 failed, 85 skipped, 6 warnings. Version remains 0.3.0-r210; no Git or production operations.
- In progress; no hardware-only handoff claim yet.

## 2026-10-21 — Final offline regression / Regressione offline conclusa

- **Fixed:** remote lead/backing selection could duplicate backing audio as lead when backing_vocals was listed first. Distinct artifact indices also handle identical silent output bytes. Four new regression tests.
- **Testing changes:** opt-in offline test isolation disables optional Demucs updater/UVR repair and denies external Python DNS/connections. Legacy local-execution and admin tests explicitly select their intended authenticated/local route; generated checkpoint fixtures use temporary rights policy; original ZIP executable modes restored. Production authentication/licensing and OS restrictions unchanged.
- **Complete final general regression:** **4579 passed, 0 failed, 85 skipped, 6 warnings**, exit 0, 500.25 seconds. `validation/r210-offline-final-verified.xml`, `.log`, and `r210-offline-final-summary.json`. Earlier first pass (4546 passed/30 failed/75 skipped) retained for analysis; do not sum runs. Ruff passed on changed Python sources/tests.
- **Skipped:** missing reviewed GM/model/voicebank/VST assets, browser/DOM dependencies, Unix IPC forbidden by environment, actual Win32/audio-device acceptance. Nine separate offline protocol unit cases preserve malformed-payload and diagnostic privacy/billing checks; they do not replace real IPC acceptance.
- **Current status:** general offline regression and reproduced defects closed for this source state. AI Vocal Studio, multi-track transcription and GM are NOT fully end-to-end certified: complete authorized bundles, representative 10–16 instrument benchmark, real GM bank, browser/target/IPC acceptance remain. Do not say only hardware tests are left. Prior real Transkun CPU inference remains valid runtime evidence, not quality evidence.
- **Commit message:** cumulative from last user commit confirmation on 19 October 2026, exact SHA unavailable, one line in `docs/COMMIT_MESSAGE_R210.txt`. Includes preceding MIDI/studio/GM, licensing/billing, metronome/UI/manual, routing/recovery, installers/imports and these validations. No commit, push, tag, release or production action.
- **Version:** 0.3.0-r210 unchanged. All previous cumulative archive paths preserved. Details: `docs/R210_OFFLINE_FINALIZATION_IT_EN.md`.

## 2026-10-21 — Work real runtime validation / Verifica reale runtime

- **Implemented:** Seed-VC singing architecture preflight (44.1 kHz/F0), Transkun inference bypass of training gradient checkpointing, offline asset SHA/CRC audit CLI and regressions. Source inventory preserved; no files missing from original 2639 entries.
- **Verified:** environment execution and IO; reconstructed assets 991830047 bytes, expected SHA-256 and full CRC; all 13 internal hashes/nested archive CRC; actual Transkun CPU inference with strict pretrained weight loading and offline network audit, valid MIDI with zero detected notes on synthetic chord (not musical accuracy); C++20 native DSP self-test and GM ABI.
- **Final local disjoint regression:** cross-area **123 passed, 1 skipped**; native/MIDI/phonemizer **114 passed, 7 skipped**. Total **237 passed, 0 failed, 8 skipped** across those suites. Focused 18-test run overlaps and is not added. Ruff, compilation and pip check passed.
- **Not green generally:** general suite interrupted around 62% by automatic approval review after unexpected GitHub egress; incomplete progress only (2866 pass/26 fail/56 skip markers), no full-suite certification. Separate legacy failure analysis: **4 passed, 4 failed**; details retained rather than relaxing authentication/asset guards or changing current model defaults. No retry/bypass of rejected egress.
- **Open software/runtime gates:** complete safe general regression, legacy test reconciliation, licensed complete DiffSinger/RVC/Seed-VC bundles, actual full-path singing/conversion, 10–16 instrument benchmark and real GM bank acceptance. These are not all hardware-only tasks. No claim that all software is complete.
- **Hardware-only acceptance:** target Windows/macOS/ROCm/GPU, browser/native audio devices and musical listening. No production intervention or Git operations; version 0.3.0-r210 unchanged.
- **Evidence:** `docs/R210_WORK_NEURAL_RUNTIME_VALIDATION_IT_EN.md`, `validation/r210-work-summary.json`, XML/logs and exact environment. Next: provide missing reviewed assets, reconcile authenticated legacy test harnesses and isolate the exact test responsible for GitHub egress before any general regression retry.

## 21 October 2026 — Additional closure attempt / Tentativo di chiusura aggiuntivo

- **Implemented / Implementato:** strict PCM shape and floating-point dtype validation for post-resampling vocal conversion; malformed empty-channel arrays, string and complex buffers now raise an explicit ValueError before any WAV replacement. New regression test covering all rejected buffers.
- **Tested / Testato:** isolated offline cross-area regression: **104 passed, 0 failed, 4 skipped, 0 interrupted**, covering Vocal Studio, managed assets, benchmark, MIDI recovery and GM file/event/worker. Test log: `validation/r210-20pass-crossarea.log`. Python compilation passed. Earlier cross-area results are overlapping, not additive.
- **Not completed / Non completato:** whole-repository regression; authorized real DiffSinger/RVC/Seed-VC/Transkun inference; runtime/library compatibility on target operating systems; independently labeled 10–16 instrument datasets; GM acoustic and native/browser hardware acceptance. Without these, completion of all three macroareas remains *unverified*, and additional software changes may be required. No fictitious inference was performed.
- **Governance:** version **0.3.0-r210** unchanged; original 2,635 archive entries preserved; no Git operations, production server edits, remote downloads or bypass of network restrictions. Separate license review required for code/checkpoints/voicebanks/vocoders/auxiliary models/SoundFonts.

## 21 ottobre 2026 — Guardia PCM post-resampling / Post-resampling PCM guard

- **Implementato:** Vocal Studio verifica output convertito dopo resampling, audio dry e mix effettivo, rifiutando dati vuoti, NaN/infiniti e picchi fuori gamma prima della sostituzione del file originale. Sei test dedicati.
- **Testato:** 86 passed, 0 failed, 4 skipped, 0 interrupted (suite offline trasversale, non regressione generale). `validation/r210-single-cycle-closure-tests.log`.
- **Non chiuso:** inferenze checkpoint realmente autorizzati, compatibilità upstream e regressione completa, benchmark strumentali, accettazione GM e native/browser. Non dichiarare tre macroaree integralmente complete.
- Nessuna modifica server reale/Git; versione 0.3.0-r210 invariata. Dettagli: `docs/R210_SINGLE_CYCLE_PCM_CLOSURE_IT_EN.md`.

## 21 ottobre 2026 — Convalida dei risultati calcolati / Computed-result checkpoint validation

- **Implementato:** la cache Audio-to-MIDI verifica anche l'output musicale appena calcolato con lo schema `MusicResult`/`EmptyTranscription` prima di persisterlo o inviare l'acknowledgement; output malformati non vengono certificati da un checkpoint. Test di regressione dedicato.
- **Verificato:** selezione offline trasversale su 11 moduli: **113 passed, 0 failed, 2 skipped, 0 interrupted**. Gli skip richiedono SoundFont/core GM esterni revisionati. Log: `validation/r210-computed-result-validation-tests.log`. Suite dedicata sovrapposta: 42 passed; non sommare.
- **Non certificato:** regressione generale, inferenze reali DiffSinger/RVC/Seed-VC/Transkun, benchmark multi-strumento su audio reale e accettazione hardware/browser/native. La convalida dei contratti non equivale alla compatibilità dei checkpoint. Tre macroaree **non dichiarate completamente chiuse**.
- Versione invariata 0.3.0-r210, nessuna operazione Git o server reale, nessun bypass di restrizioni di rete.

## 21 ottobre 2026 — Ciclo unico di chiusura software / Single-cycle closure attempt

- **Corretto e testato:** il recupero degli stadi Audio-to-MIDI riconosce checkpoint ZIP integro ma risultato MusicResult invalido per schema e degrada a ricalcolo reale; gestisce anche errori di decompressione/troncamento. Non attribuisce usage zero a un risultato non valido. Test dedicato con cache riparata e secondo recupero verificato.
- **Regressione offline di 11 moduli:** 108 passed, 0 failed, 0 skipped; 39 passed nel primo gruppo sovrapposto (non sommare). Un invio iniziale errato dei test ha restituito `file not found` e nessun test eseguito; corretto il nome della suite e rilanciata. Log `validation/r210-onecycle-offline.log`.
- **Non chiuso:** nessuna inferenza con checkpoint reali e autorizzati DiffSinger, RVC, Seed-VC o Transkun; nessun benchmark audio multi-strumento validato, nessuna accettazione GM browser/native/hardware, e regressione dell'intero repository non eseguita. Restano potenziali incompatibilità software che possono emergere solo con tali asset. Non attestare chiusura delle tre macroaree.
- **Conservazione e policy:** invariata 0.3.0-r210; nessun commit/push/tag/release o accesso a server reale; non sono stati aggirati precedenti blocchi di rete. Ogni famiglia di licenze va certificata autonomamente.

## 21 ottobre 2026 — Three-area closure engineering pass / Ciclo di chiusura verificabile

- **Implementato:** pubblicazione atomica del WAV GM con preservazione del file originale in caso di errore e pulizia dei temporanei; validazione `--min-instruments` del benchmark tra 1 e 128. Tre nuovi test di regressione.
- **Testato:** 101 passed, 0 failed, 5 skipped, 0 interrupted nella suite locale offline; 22 passed nei test GM renderer / benchmark. Vedi `validation/r210-closure-focused.log` e `docs/R210_THREE_AREAS_CLOSURE_GATE_20261021_IT_EN.md`.
- **Non certificato:** regressione generale; runtime e inferenze neurali con asset autorizzati; benchmark multi-strumento reale; browser/native e ascolto GM. Non dichiarare completate le tre macroaree finché tali gate non sono soddisfatti. Nessun server o Git modificato.

## Verifica finale locale aggiuntiva — 21 ottobre 2026 / Additional offline verification

- Eseguiti 10 moduli di regressione mirata autonomi: **106 passed, 0 failed, 5 skipped, 0 interrupted**. XML e log: `validation/r210-finalization-local.xml`, `validation/r210-finalization-local.log`.
- Gli skip sono 3 per `espeakng_loader` non installato e 2 per runtime/core SoundFont GM autorizzati non presenti.
- La verifica è indipendente, **non** è una regressione generale e non certifica inferenze AI reali o ascolto GM. Non sommare il risultato ai conteggi storici (suite sovrapposte).
- **Decisione di handoff: non certificato.** Le attività software restano condizionate da compatibilità dei modelli/dipendenze e da eventuali difetti rilevati nella regressione generale. `validation/r210-finalization-current.json` elenca i gate.
- Confermati i vincoli: versione invariata, nessun Git o server reale modificato, nessun bypass del blocco GitHub, nessuna fixture qualificata come inferenza reale.

## Final verification handoff — 21 October 2026 / Verifica finale (non certificazione completa)

- **Versione invariata:** 0.3.0-r210; nessun commit, push, tag, release o intervento su server reali.
- **Regressione offline mirata ampia:** 143 passed, 0 failed, 15 skipped (`validation/r210-final-gate-broad.xml`). Suite sovrapposta: 96 passed, 0 failed, 2 skipped; **non sommare i conteggi**.
- **Bloccato/non verificato:** regressione generale (precedente blocco rete/GitHub non aggirato), inferenze con checkpoint DiffSinger/RVC/Seed-VC/Transkun autorizzati, esatte dipendenze upstream, audio reale benchmark 10–16 strumenti, interfacce browser/native, GM hardware e ascolto.
- **Stato:** tutte e tre le macroaree con percorsi software sviluppati, ma **non firmate end-to-end**. Le verifiche mancanti possono ancora generare correzioni software, pertanto non si dichiara che rimangano soltanto collaudi utente.
- **Consegna:** `validation/r210-final-handoff.json` documenta esiti e gate. Asset, licenze per codice/checkpoint/vocoder/voicebank/ausiliari/soundfont e compatibilità richiedono verifica indipendente.

## Ciclo accelerato offline — 21 ottobre 2026 (0.3.0-r210, uncommitted)

- **Implementato:** il motore GM TinySoundFont impedisce la riconfigurazione dopo la chiusura dell'handle; il benchmark Audio-to-MIDI limita anche le scansioni dei cammini aumentanti (2.000.000) oltre al limite di coppie candidate, rifiutando con errore esplicito carichi computazionali eccessivi. Nuovi test per entrambi i casi.
- **Testato:** regressione mirata su Vocal Studio, Audio-to-MIDI e General MIDI: **123 passed, 0 failed, 10 skipped**. Skip: asset FluidR3/core compilato e Happy DOM esterni. Nessuna inferenza neurale fittizia presentata come vera.
- **Ancora aperto:** regressione generale sicura (precedente richiesta GitHub bloccata da policy), compatibilità delle dipendenze neurali e inferenze con checkpoint/voicebank autorizzati, prova browser/native, ascolto GM e benchmark trascrizione 10–16 strumenti. **Non è ancora dimostrabile che tutto lo sviluppo residuo sia concluso.** Nessun intervento su server, nessuna operazione Git.

## Ciclo di protezione benchmark — 21 ottobre 2026 (r210, non committato)

- **Implementato:** limite verificabile di 1.000.000 archi nel grafo di matching per strumento del benchmark MIDI; evita l’espansione quadratica su migliaia di note con onset/offset sovrapposti e produce un errore esplicito, senza trasformare benchmark incompleti in accuratezza. Aggiunta regressione dedicata.
- **Verificato:** 72 passed, 0 failed, 12 skipped nella suite mirata MIDI, Vocal Studio e GM (assenza `espeakng_loader`, core audio compilato e banca FluidR3 revisionata). Python compileall sulle modifiche superato. Integrità archivio di partenza ZIP e SHA-256 verificata.
- **Non verificato:** regressione generale offline (precedente blocco GitHub da analizzare senza bypass), inferenze reali con checkpoint DiffSinger/RVC/Seed-VC/Transkun, collaudi browser/native e benchmark reali su 10–16 strumenti. Nessun server reale modificato, nessuna operazione Git. **Non è ancora dimostrabile che lo sviluppo delle tre macroaree sia completato e che restino solo collaudi utente.**


## r210 benchmark provenance follow-up — 21 October 2026

Implemented: Audio-to-MIDI benchmark file reports now record SHA-256 hashes and exact byte lengths of both local MusicResult inputs. This supports reproducibility but does not certify real neural inference or reviewed reference labels. Offline regression: **73 passed, 0 failed, 9 skipped** (requires externally reviewed GM assets/core). The controlled full suite has not been rerun and prior GitHub-request governance blocker is unresolved. No real checkpoint inference, native/browser acceptance or musical listening was performed. No production server changes and no Git operations. **The three macroareas are not signed off; software completion cannot be certified yet.**

## Additional software hardening — 21 October 2026 (uncommitted, r210)

- **Implemented:** bounded aggregate Audio-to-MIDI benchmark event collection (200,000 note maximum per score), reject boolean matching tolerances, verify StageCache directory again after creation, and fail cleanly on GM portable reset/event/render after closing its native handle. Added a regression for boolean tolerances.
- **Verified here:** 70 passed, 0 failed, 7 skipped in an offline mixed suite (managed Vocal Studio assets/contracts, MIDI benchmark, GM audit/events/render/controllers, lifecycle); narrower 37 passed, 0 failed, 0 skipped. All skips in the mixed suite require a built core and an externally reviewed FluidR3 GM soundbank. Python compileall passed. These do not establish neural inference or a GM real-audio audit in this environment.
- **Incomplete or blocked:** real authorized DiffSinger, Seed-VC, RVC and Transkun checkpoint inference; full-suite reproducible regression and investigation of the prior indirect GitHub request; browser/native acceptance; hardware GM audition and representative 10–16-instrument reference benchmarks. The three macroareas are **not** independently ready for final sign-off.
- **Server actions for operator:** no real server touched; install matching server/client only after review, obtain independent legal evidence for code/checkpoints/voicebanks/vocoders/auxiliary models/SoundFonts, run native and browser acceptance and audited GPU/CPU inference, run controlled full regression without bypassing network governance.

## Follow-up recovery hardening — 21 October 2026 (uncommitted)

- **Implemented:** invalidate an already-created stage cache's recovery key at each stage boundary, rather than keeping a stale model/runtime/policy fingerprint across repeated calls on the same object. This prevents reusing old Fast/Accurate/Deep inference artifacts after an in-process runtime change.
- **Verified locally:** 28/28 independent managed-asset and Studio completion-contract tests passed, including a new regression covering runtime mutation on the same cache object. Python compileall on changed files passed. These tests use contract fixtures, not real neural inference or browser acceptance.
- **Interrupted:** a larger `tests/test_r210_*.py` run exceeded its execution deadline after partial output (~10% progress); no final JUnit totals were produced, and the partial progress is *not* a pass count. No internet/third-party model download was authorized or used to resolve it. The earlier full-suite GitHub review blocker remains unresolved and was not bypassed.
- **Outstanding:** actual DiffSinger/Seed-VC/RVC/Transkun checkpoint inference; compatibility of those runtimes/weights; realistic 10–16 instrument benchmark and source separation; target server, native and browser acceptance; full regression and musical listening on production hardware. GM's prior real FluidSynth/TinySoundFont audits remain historical verification, not rerun in this follow-up.
- **Server:** no production changes performed. Before deployment, install matching r210 server/client code together, review every asset's code/checkpoint/voice/vocoder/auxiliary/SoundFont licensing independently, install only authorized disabled-by-default model bundles, configure pinned interpreters and hashes, run real inference/GM/browser/native tests, and complete an offline-controlled full regression.

# Stato corrente — 0.3.0-r210, 21 ottobre 2026

**Ciclo sostanziale consegnato; versione e revisione invariate. Nessun commit, push, tag, release o intervento sui server reali.** Sorgenti, funzionalità, AI legacy, SDK VST, test e documentazione precedenti sono conservati integralmente nel cumulativo.

## Attività implementate e testate

| Macroarea | Sviluppo implementato | Prove eseguite | Prove ancora necessarie |
|---|---|---|---|
| AI Vocal Studio | Registro asset/vocoder con ZIP atomici, inventario SHA-256 e diritti per componente; DiffSinger con voce/profilo IT/EN/FR indipendenti per cantante; testo completo e melismi espliciti; curve F0/dinamica/varianza; selettori parole/frasi/sillabe con ID note e fonemi editabili verificati; conversione reale tramite CLI RVC/Seed-VC; persistenza e interfaccia condivisa web/native | G2P e score/curve, fixture di contratto CLI e PCM, gestione asset/diritti/hash, persistenza, cinque flussi DOM, trasporto remoto autenticato | Inferenze con checkpoint autorizzati, tutte le dipendenze upstream e ogni banca/profilo; pronuncia e collaudo musicale; browser/native su piattaforme effettive |
| AI Multi-Track Audio-to-MIDI | Basic Pitch/YourMT3 preservati; nuovo adattatore API Transkun piano; selezione Veloce, riconciliazione Accurata e separazione Demucs Approfondita; risultati senza note; identità sorgente e programmi GM ripetuti; checkpoint degli stadi con hash di audio/piano/runtime/policy in tutte e tre le modalità e recupero senza doppio conteggio | Orchestrazione e riconciliazione, MIDI reale da fixture, velocity/sustain, risultati vuoti senza tracce fittizie, coda/import/reopen, retry anche dopo cambio runtime, benchmark/matching indicizzato | Checkpoint Transkun e inferenze aggregate reali; benchmark musicali etichettati 10–16 strumenti, classificazione e separazione di esecutori identici; GPU/server |
| Generatore General MIDI | Tutti i percorsi GM precedenti; fix note-off idempotente per campioni terminati/voice stealing FluidSynth; drenaggio cache/rampa breve delle vecchie voci dopo reset; soundfont autorizzati, controller, polifonia, SMF 0/1, WAV/mixer e progetti | Audit reale **128/128 programmi e 47/47 percussioni su entrambi FluidSynth e TinySoundFont**; 25 test GM reali: controller, sustain, velocity, pan, pitch, polifonia/reset, SMF/tempo, rendering e sessione PCM | Ascolto e accettazione su hardware target, mixer/browser/native; audit indipendente di ogni soundfont personalizzato |

Gli adattatori RVC/Seed-VC/Transkun chiamano i motori effettivi e non hanno un fallback di inferenza simulata. Qui sono verificati contratti, validazione e percorsi applicativi; **non è stata eseguita un'inferenza neurale di questi checkpoint assenti**. La compatibilità dei fonemi è controllata rispetto all'inventario revisionato e vincolato all'hash della banca: non è una certificazione automatica del training linguistico o della pronuncia reale.

L'allineamento testo/score è deterministico tramite eSpeak e nuclei vocalici del profilo, con conteggi espliciti per melismi. Non è forced alignment acustico né previsione appresa della durata/espressività. La dinamica PCM rimane dichiarata DSP. La rigenerazione produce nuove take non distruttive; le note sorgente eliminate o fuori dalle clip sono rifiutate.

La pipeline ammette molte parti e programmi GM ripetuti, ma **non garantisce l'accuratezza su 10–16 strumenti né la distinzione di esecutori con lo stesso timbro dentro una singola sorgente**. Nessuna traccia viene inventata per raggiungere un numero. Google MT3, MR-MT3 e MT3-Infer restano alternative valutate/documentate, non backend installati o verificati. La variante YourMT3 esistente non viene rinominata YourMT3+.

## Test e ambiente

- Estrazione, modifica, esecuzione Python/Node, pytest, compilazione del core e rendering PCM reale sono possibili nell'ambiente. Gli asset e le librerie di prova sono esterni al package; nessun peso o soundfont viene redistribuito senza autorizzazione.
- **Suite mirata finale: 149 superati, 0 falliti, 1 saltato.** L'unico skip richiede la voicebank OddVoices esterna autorizzata e il core; non è presentato come inferenza superata.
- **Suite GM reale: 25 superati, 0 falliti, 0 saltati.** Include entrambi i motori; gli audit separati di tutte le famiglie/programmi e percussioni sono salvati in JSON. I conteggi delle suite non vanno sommati come test unici: alcuni contratti sono comuni.
- Happy DOM 21.0.4 (MIT) con Node 24.19.0: **5 flussi applicativi passati**, compresi testi/curve/conversione, voci indipendenti, parole, sillabe e selezione Transkun. È un DOM effettivo, non un browser né una prova di inferenza. Canvas nel test è sostituito da un contesto di prova; verifica visuale/browser non dichiarata.
- Compileall Python, sintassi JavaScript e Ruff dei file modificati: passati.
- **Suite generale attuale interrotta, senza conteggi finali/JUnit.** La revisione automatica ha rifiutato una richiesta indiretta a github.com della suite, poiché dati/credenziali trasmessi non erano determinati. Il processo è terminato senza resoconto finale; il log parziale contiene fallimenti e `fatal library error, lookup self`. Non è stato aggirato il blocco né ripetuta la suite generale; sono stati eseguiti soltanto i test locali indipendenti. Non è possibile dichiarare la regressione generale verde.
- Lo storico del precedente ciclo resta **4401 superati, 29 falliti, 133 saltati**, con gli stessi 29 fallimenti riprodotti sull'archivio originario. Non sono i risultati della suite generale di questo ciclo e non è verificato che rappresentino tutti i fallimenti attuali. Vedere `validation/r210-baseline-failures.json` e i log conservati.
- Chromium/browser E2E non disponibile: il precedente tentativo di installazione restituiva un archivio troncato. Le app native e le piattaforme del server richiedono accettazione reale.

Resoconti: `validation/r210-completion-summary.json`, `r210-completion-targeted.xml`, `r210-completion-gm-real.xml`, `r210-completion-fluidsynth-audit.json`, `r210-completion-tinysoundfont-audit.json`, `r210-completion-lint.log`, `r210-completion-full.log`.

## Blocchi, attività aperte e interventi sul server

1. Preparare runtime/checkpoint/vocoder/cache ausiliarie/riferimenti vocali **effettivamente autorizzati** per DiffSinger, Seed-VC, RVC e Transkun. Ogni componente richiede avvisi, prova dei diritti, file/hash e policy indipendenti. Installare i bundle disabilitati, verificare gli interpreti dedicati tramite SHA-256 e abilitarli solo dopo la revisione. Sono istruzioni, non interventi già effettuati sul server.
2. Aggiornare insieme server e client per i payload score/opzioni voluminosi: `mta-studio-request-1`, massimo 8 MiB complessivi e 240 KiB di opzioni tipizzate. Gli header legacy restano piccoli e compatibili. Il catalogo remoto è autenticato e non ricade silenziosamente sui modelli locali.
3. Eseguire inferenze reali e accettazione IT/EN/FR per ogni banca, RVC/Seed-VC con voce autorizzata, Transkun su piano e mix, confrontando originali, take, export e riapertura. Possibili incompatibilità di dipendenze/upstream emergenti richiederanno correzioni verificabili; non possono essere dichiarate assenti tramite fixture.
4. Ripetere benchmark riproducibili con riferimenti musicali reali per 10–16 strumenti e ascoltare mixer/GM su hardware target; non dedurre accuratezza dal numero di tracce o da output sintetici di test.
5. Completare la regressione generale in un ambiente controllato dove i test che richiedono download/rete e socket locali siano eseguibili in modo autorizzato; riesaminare i fallimenti storici senza indebolire autenticazione, licenze o metering. Restano aperte la nuova regressione completa e l'accettazione browser/native.

**Non si certificano tutte e tre le macroaree come integralmente concluse e verificate.** I percorsi software sopra sono implementati e coperti dai test descritti; restano i blocchi di asset/inferenza reale, accettazione piattaforme e regressione generale. Guida completa: [STUDIO_MANAGED_ASSETS_R210_IT_EN.md](STUDIO_MANAGED_ASSETS_R210_IT_EN.md). I resoconti storici seguenti sono conservati e non sostituiscono questo stato corrente.

---

# Historical previous cycle — expressive-separated-gm / Ciclo precedente

## Current status / Stato corrente

| Macroarea | Implemented and verified in this cycle | Still open in software | Real assets/hardware gates |
|---|---|---|---|
| AI Vocal Studio | IT/EN/FR settings/lyrics routing; real optional eSpeak G2P; pinned reviewed IPA/inventory tied to bank; multi-phone DS/F0; presets/vibrato/gate/DSP dynamics; exact checkpoint and config/vocoder matching; vocoder license admission; region takes and multi-singer metadata | RVC/Seed-VC; managed independent neural banks and vocoders; full text alignment; learned variance prediction; advanced curve UI | Authorized acoustic/vocoder inference, bank pronunciation IT/EN/FR, neural quality and native/ROCm |
| AI Multi-Track Audio-to-MIDI | Distinct Deep mode with registered Demucs separation and per-source YourMT3/Basic Pitch; cancellation/deadline; strict component admission; source identity and bounded artifact validation | Further specialist adapters; silent/no-note stem continuation; same-source independent players; dynamics beyond existing model capabilities; partial separated-source retry improvements | Actual full-mix multi-instrument references and installed runtimes; 10–16-instrument accuracy, GPU/native acceptance |
| General MIDI | Core compiled; reviewed bank actually rendered all 128 programs and 47 drums; real controller/SMF tests; 14-bit Bank Select; extra authorized SF2 installer/catalog/editor/persistence | Complete cross-client acceptance and issues it may expose; custom-bank musical coverage remains unverified until separately audited | FluidSynth parity, target-device/mixer listening and real-project acceptance |

**None of the three macroareas is marked fully complete.** This cycle closes substantial application paths; it does not replace model-specific integration with contract-only placeholders. Existing source, SDKs, tests and manuals remain intact. Version/revision remain 0.3.0-r210; no Git commit, push, tag, release or server changes.

## Validation / Validazione

- Extraction, modification, Python/Node execution, pytest and C++ compilation succeeded. Initial missing test/runtime dependencies were installed only in this temporary environment. This environment uses Python 3.12; a production lockfile installation and target platform matrix remain separate.
- Final focused regression: **145 passed, 0 failed, 10 skipped**, including real eSpeak IT/EN/FR fixtures and existing queue/publication/reopen tests. Nine GM asset-dependent skips were exercised successfully in the separate real GM suite; the remaining skip requires installed OddVoices assets. An executable JavaScript submission contract checks all three neural lyric languages without requiring OddVoices banks.
- Separate real GM suite: **17 passed, 0 failed, 0 skipped**. Native TinySoundFont + reviewed FluidR3, no mocked audio engine. GM audit: **128/128 programs and 47/47 standard drums**. This is audio software validation, not musical listening certification; no bank or compiled binary is bundled here.
- Full-project regression: **4401 passed, 29 failed, 133 skipped**. All 29 failures were reproduced on the original archive in this environment (identical failing test IDs). Final focused tests were rerun after the last preset-persistence, neural UI routing and singer-specific metadata fixes; the broad run precedes those last isolated fixes and does not include the subsequently added JS submission and singer-publication contracts. Full totals and baseline comparison are recorded in `validation/r210-cycle-summary.json` and JUnit XML. Known pre-existing harness/policy assumptions and prohibited AF_UNIX sockets prevent a green full-project claim. Every failure must remain visible; do not bypass authentication or rights policy to satisfy old tests.
- Browser installation was attempted, but the Chromium provider returned an invalid/truncated archive. Actual browser/native UI E2E is unverified; JavaScript syntax checks pass. Full SDK browser tests and external VSTi/voicebanks/YourMT3 checkpoints require their independent assets.
- All original archive entries will be verified present when packaging; unchanged SDK/legacy content is preserved byte-for-byte. Python compileall, changed-file lint and ZIP CRC/checksum checks are recorded with delivery.

## Next / Prossimi passi

1. Resolve remaining software integrations listed above; obtain exact authorized neural assets/checkpoint choices before model-specific deployment work. Do not label these tasks as mere listening checks.
2. Configure the separately authorized DiffSinger vocoder, flattened config hash, exact checkpoint filename and optional bank G2P profile; run the updated read-only preflight.
3. Enable existing Demucs/YourMT3/Basic Pitch workers and native routes to exercise Deep mode on representative mixtures; benchmark actual inferred notes against ground truth and review stem leakage/duplicates.
4. Run target FluidSynth/native/web playback, export, project reopen and musical auditions. No production changes are automated by this package.

Detailed changes, configuration, licensing boundaries and specialist assessment: `docs/THREE_AREA_IMPLEMENTATION_R210_IT_EN.md`. Earlier entries below are historical checkpoints, not overrides of this current status.

---

## Checkpoint r210 — English reviewed lexicon and three-area status (20 ottobre 2026)

- **Implemented / Implementato:** DiffSinger `en` reviewed lexicon route verified end-to-end at score conversion using a voicebank-specific SHA-256-pinned mapping; `en` retains legacy bank-native phonemes when disabled, `it`/`fr` require reviewed lexicons. Explicit invalid opt-in fails closed. No fabricated G2P or model weights.
- **Tested / Testato:** See this cycle's pytest results; no real acoustic inference performed.
- **Remaining software / Sviluppo non completo:** general G2P for IT/EN/FR, neural expression and voice conversion, specialist multi-instrument inference and full application end-to-end validation. GM renderer implemented but real-bank audition outstanding. Thus all three macroareas cannot truthfully be marked fully complete.
- **Real-world gates / Collaudi:** authorized voicebank+vocoder on user server, stereo-to-10/16-instrument reference benchmark and GM full soundbank instrument/controller audition. Version unchanged 0.3.0-r210; no Git operations.

## Checkpoint r210 — DiffSinger lexicon IT/FR (20 ottobre 2026)

- **Implementato:** lessico sillaba→singolo fonema nativo della voicebank per DiffSinger (`it` e `fr`, `en` opt-in), verificato con SHA-256; errori di copertura o lingua bloccano la sintesi.
- **Testato:** 58 superati, 2 saltati (asset GM reali assenti) nella regressione mirata DiffSinger, quality gate Audio-to-MIDI e GM.
- **Non completato:** fonemizzazione linguistica automatica generale IT/EN/FR, conversione timbrica, espressività neurale avanzata, prova di inferenza DiffSinger, accuratezza 10–16 strumenti, rendering GM reale su hardware. Le tre macroaree non possono essere dichiarate chiuse.
- **Prossimo passo:** installare asset autorizzati e collaudare; completare le funzionalità applicative residue prima di dichiarare sviluppo chiuso.

# Ciclo combinato Vocal Studio / Audio-to-MIDI / GM — 20 ottobre 2026

**Implementato:** validazione comune dei pacchetti e della temporizzazione MIDI per FluidSynth e TinySoundFont, ordine stabile per eventi simultanei, limite a 20.000 eventi per blocco; audit GM opzionale per 128 programmi e percussioni con SoundFont realmente installato. Nessuna modifica a SDK VST, checkpoint o licenze.

**Testato:** regressione mirata 59 passed, 7 skipped prima dell’aggiunta dell’audit; ultimo risultato aggiornato nei log del ciclo. **Bloccato:** collaudi DiffSinger con asset autorizzati, qualità reale 10–16 strumenti, ascolto/benchmark GM con banco verificato. **Non ancora implementato completamente:** fonemizzazione multilingue, conversione vocale ed espressività avanzata, ensemble specializzati reali quando necessari, chiusura end-to-end con progetti veri. Non dichiarare le macroaree chiuse. Versione 0.3.0-r210, nessun Git commit/push/tag/release.

---

# Audio-to-MIDI reproducible quality gate — 20 October 2026 / Benchmark verificabile

**Implemented:** Offline `mta-music-1` benchmark with GM-aware maximum-cardinality note matching, per-instrument TP/FP/FN, precision/recall/F1, source JSON validation and explicit non-certification; `scripts/check_audio_midi_quality.py` for real model results. Bounded YourMT3 decoded notes, replaced quadratic per-event note-id allocation with linear counter; no model or licensed artifact modified. **Tests:** See current cycle report; synthetic 16-instrument fixture validates metrics only. **Blocked on user test environment:** reviewed multitrack reference MIDI and stereo mixes, actual YourMT3 runtime/checkpoint, CPU/ROCm and editor end-to-end trials. **Status:** overall Audio-to-MIDI 10–16 instrument reliability not yet proven; no assertion of neural quality from a simulated fixture. 0.3.0-r210, no Git actions.

---

# Reconciliation safety cycle — 20 October 2026 / Ciclo riconciliazione

**Implemented / Implementato:** With 3–4 Audio-to-MIDI hypotheses, reconciliation compares every independent model only against the original primary model notes. Events contributed by a secondary model cannot be promoted to primary agreement by subsequent secondary predictions. Secondary-only notes remain unreviewed, and all original hypotheses remain available. Report policy string updated accordingly. No model weights were installed; no new neural backend was claimed.

**Tested / Testato:** 23 targeted tests passed (music reconciliation, bounded Vocal Studio, multi-singer lyrics and voicebank routing). General regression, real 10–16 instrument audio benchmark, GPU ROCm, neural vocal synthesis and native end-to-end remain unverified or incomplete.

**Status:** Both overall macroareas remain open; the above is a verified Audio-to-MIDI data-integrity improvement, not end-to-end completion. Version 0.3.0-r210 unchanged. No Git commit/push/tag/release.

---

# Two bounded engineering closures — 20 October 2026 / Due chiusure circoscritte

**Vocal Studio:** implemented and tested aggregate 40,000-note job admission limit before loading voicebanks. **Audio-to-MIDI:** implemented and tested conservatively preserving unison notes from distinct performers even where their GM program is identical. **Tests:** 21 passed, 1 skipped (real voicebank unavailable). See `docs/R210_TWO_MACROAREAS_GATE_20261020.md`. **Not complete:** full Vocal Studio neural synthesis/IT-FR/voice conversion and 10–16-instrument end-to-end full mix transcription, GPU/native/music benchmarks and full regression. Version r210 unchanged; no Git actions.

# Ciclo Vocal Studio — voicebank individuali end-to-end UI → worker (20 ottobre 2026)

**Implementato:** selezione bilingue di voicebank CC0 installate per ogni cantante nella schermata di sintesi; mapping per ID delle tracce selezionate; validazione dell'elenco sul server; controllo delle installazioni e assegnazione di un'unica voicebank alla singola sorgente inviata al worker. Retrocompatibilità con `voicebank` condivisa. Nessuna variazione a licensing, billing o numero di revisione.

**Testato:** 41 passed, 1 skipped nei test Vocal Studio e Studio workflow; `node --check` riuscito. Il test saltato richiede voicebank e backend compilato reali. Test di UI/routing statici, non browser end-to-end. **Aperto:** synth neurale, fonemizzazione IT/FR, conversione timbrica, accuratezza 10–16 strumenti, benchmark e ROCm/native. Le macroaree non sono ancora completate.

---

# Ciclo accelerato Vocal Studio — voicebank indipendenti, 20 ottobre 2026

**Implementato:** il backend OddVoices accetta `voice_banks` (una banca CC0 per cantante), mantenendo `voicebank` come predefinita legacy. Ogni cantante usa il proprio renderer, chiuso sempre dopo l’uso. Validazione preventiva del numero di voicebank, elenco chiuso a `air`, `cicada`, `quake`, e manifest di output con SHA-256 per ciascuna banca. Nessun backend neurale fittizio aggiunto.

**Test:** 25 passed, 5 skipped nel gruppo Vocal Studio + MIDI. I 5 skipped richiedono voicebank/compilato, PyAV e VSTi non presenti. Nessun collaudo vocale reale in questo ciclo. **Pendente:** collegamento UI per la scelta individuale delle banche, backend neurali autorizzati, fonemizzazione IT/FR, voice conversion, trascrizione 10–16 strumenti e benchmark hardware. Le macroaree non sono ancora completate.

**Versione:** 0.3.0-r210; nessun commit/push/tag/release.

---

# Ciclo unico richiesto: Vocal Studio / Audio-to-MIDI — 20 ottobre 2026

**Versione obbligatoria: 0.3.0-r210; nessun commit, push, tag o release.**

**Implementato in questo ciclo:** UI bilingue con sequenze di sillabe indipendenti per ogni cantante/traccia MIDI; trasmissione `singer_lyrics` per ID traccia; validazione server dell’insieme esatto di ID e della corrispondenza una sillaba/nota; inoltro delle sillabe giuste per ciascuna sorgente in fase di rendering; retrocompatibilità con il campo condiviso `syllables`. Nessuna scorciatoia nella licenza dei modelli.

**Testato:** 35 test superati, 5 saltati (voicebank, PyAV, VSTi assenti), più 3 test specifici superati; Python compileall e `node --check` riusciti. La validazione complessiva su hardware reale non è stata eseguita.

**Non completato / non certificato:** Vocal Studio neurale con voicebank autorizzate, fonemizzazione IT/FR, RVC/Seed-VC, editing espressivo/rigenerazione; trascrizione a 10–16 strumenti affidabile da mix stereo, ensemble MT3/MR-MT3/Transkun, modalità Maximum, benchmarking musicale, CI integrale, GPU ROCm e interfacce native reali. Il motore YourMT3/Basic Pitch già presente è mantenuto, ma non è stata introdotta una nuova trascrizione in questo ciclo. Le due macroaree NON sono chiuse end-to-end. Non spacciare test di contratto per inferenza musicale reale.

---

# Ciclo validazione Vocal Studio — 20 ottobre 2026

**Implementato:** controllo preventivo su durata massima di ogni nota, inizio non negativo, pitch e velocity MIDI, numeri non finiti e limite al numero di note prima del caricamento degli asset; nessuna modifica alle licenze o alle capacità dichiarate dei modelli. **Testato:** 22 passed, 5 skipped in test Vocal Studio e MIDI (voicebank, PyAV e VSTi non disponibili). **Ancora aperto:** backend neurali vocali con pesi autorizzati, fonemizzazione IT/FR, timbro vocale, 10–16 strumenti indipendenti da mix completo, prove reali native e ROCm. Questa macroarea **non è chiusa**. Versione 0.3.0-r210 invariata; nessun commit, push, tag o release.

# Checkpoint Vocal Studio / Audio-to-MIDI — 20 ottobre 2026 (ulteriore ciclo)

**Implementato e testato:** allineamento stabile nota-sillaba per parti MIDI non ordinate, controllo preventivo di parti vuote/sovrapposte/oltre 10 minuti. 26 passed, 1 skipped (voicebank reale assente). Audio-to-MIDI: regressione riconciliazione inclusa, nessun nuovo modello. Vedi `docs/VOCAL_MIDI_COMPLETION_GATE_R210_IT_EN.md`. **Entrambe le macroaree restano aperte** fino a sintesi neurale, multi-instrument reale, benchmark e prove native/ROCm.

# Checkpoint parziale Vocal Studio / Audio-to-MIDI — 20 ottobre 2026

Versione invariata **0.3.0-r210**. Implementati `voice_syllables` indipendenti per ogni cantante OddVoices, validazione del numero di sillabe per parte prima del caricamento della voicebank, retrocompatibilità `syllables`. Test mirati Vocal Studio + riconciliazione MIDI + workflow Studio: **24 passed, 1 skipped** (voicebank reale non installata). Documento `docs/STUDIO_VOCAL_MULTI_SINGER_LYRICS_R210_IT_EN.md`. **Non chiuse** le due macroaree: mancano sintesi neurale e voicebank/language coverage, UI completa per gli input individuali, ensemble multi-motore completo, qualità trascrizione 10–16 strumenti su mix reale, benchmark e prove native/ROCm. Nessun commit/push/tag/release.

## Ciclo 20 ottobre 2026 — alternativa DrumSep tramite Mega 53

Versione 0.3.0-r210 invariata, nessun commit/push/tag/release. Mega 53, già integrato per voci lead/backing, è ora selezionabile per parti della batteria tramite lo stesso checkpoint autorizzato: kick, snare, toms, hi-hat e percussioni. I target cymbals (cymbals completi) e drums_without_percussions vengono rifiutati esplicitamente, perché le uscite Mega 53 non ne garantiscono l'equivalenza. Nessuna modifica ai diritti degli originali DrumSep, ChordFormer o Madmom. Test mirati: 10/10 passati. Suite estesa: 16 passati, 2 falliti in vecchi test DrumSep per mancanza di contesto job AI autenticato (non attribuiti automaticamente al nuovo percorso). Inferenza reale checkpoint non eseguita; inferenza checkpoint reale, benchmark musicale/ROCm e regressione generale ancora da verificare. L'esecuzione richiede configurazione MSST e pesi hash-verified, non inclusi nello ZIP.

---

# Ciclo sblocco funzionale tramite motori e pesi alternativi — 20 ottobre 2026

**Implementato e verificato localmente:** selezione automatica di `mvsep-mega53` (checkpoint con dichiarazione MIT dell'autore) per i job lead/backing senza modello esplicito, quando la prima preferenza UVR KARA 2 non supera la verifica della policy. L'override esplicito di UVR non viene sostituito silenziosamente, e il modello Mega 53 rispetta sempre la propria policy. Per DrumSep è stata resa eseguibile nel worker remoto la modalità esplicita `dsp`, priva di pesi neurali: genera realmente WAV `drums_without_percussions` e `percussions`; **non** separa kick/snare/toms individualmente. Restano disponibili BTC-HCQT, Chordino e raffinamento MTA per gli accordi e SAM Audio secondo la sua licenza per multi-cantante. Gli esatti pesi Madmom NC, ChordFormer, DrumSep ONNX e DiffSinger non autorizzati **non sono stati sbloccati**; nessuna falsa licenza né sostituzione di checkpoint con pesi di identità diversa sotto lo stesso nome. I checkpoint Mega 53 non sono inclusi né scaricati qui.

**Test del ciclo:** unit test su fallback automatizzato, override espliciti bloccati, bypass impossibile del fallback disabilitato, DSP remoto con generazione di file WAV reali e manifest; da collaudare su hardware reale, con checkpoint Mega 53 installato, e da completare regressione generale, billing end-to-end e benchmark qualitativi. Versione 0.3.0-r210 invariata; nessun commit/push/tag/release.

# Ciclo preferenze UVR KARA 2 / Mega 53 — 20 ottobre 2026

**Implementato:** UVR KARA 2 preferenza principale per lead/backing quando amministrativamente autorizzato; Mega 53 opzione secondaria esplicita, con licenza MIT dei pesi confermata dall’autore (issue ZFTurbo #245) e controllo integrità del checkpoint originale v1.0.21. Nessun sblocco di UVR non autorizzato. Modalità multi-cantante SAM Audio separata e preservata: Mega 53 distingue lead e cori collettivi, non identifica automaticamente singoli cantanti.

**Test:** test mirati di catalogo, policy, checksum ed adattatore con esecuzione simulata. **Aperti:** installazione del checkpoint originale, test reale su AMD ROCm, confronto audio KARA 2/Mega 53 e collaudo multi-cantante; SAM Audio segue i propri termini.

**Licenze:** UVR README invita a MIT/attribuzione, ma issue #2185 rimane senza conferma definitiva sui pesi KARA 2. L'override richiede doppio consenso e un'autorizzazione reale. L'autore di Mega 53 ha dichiarato MIT per pesi e distribuzione commerciale, senza garanzie sui dati di training; il checkpoint deve corrispondere all'hash dichiarato. Versione 0.3.0-r210 conservata, nessun commit/push/tag/release.

# Ciclo UVR KARA 2 — 20 ottobre 2026

**Implementato:** identità license-policy indipendente `uvr-kara-2`; checkpoint KARA 2 vincolato a SHA-256 ufficialmente distribuito, guard al download e prima dell’inferenza locale, attivazione condizionata a doppio consenso amministrativo e fonte di licenza/permissi verificati. **Stato:** non riabilitato automaticamente; attivabile dopo attestazione reale del gestore. Gli altri modelli UVR rimangono bloccati secondo propria policy. **Testato:** 11 test mirati superati su policy, file fake, symlink e doppia conferma. **Bloccato:** conferma dell’avente diritto che MIT copra questo esatto ONNX e i diritti di hosting/redistribuzione; inferenza reale e benchmark non eseguiti. Approfondimento in `docs/UVR_KARA2_RIGHTS_R210_IT.md` / `_EN.md`. Nessun cambio versione, commit, push, tag o release.

# Ciclo modalità commerciale e checkpoint — 20 ottobre 2026

**Implementato:** controllo amministrativo bilingue per il già presente switch `commercial-service`, due conferme, motivazione e chiamata API; chiarita la portata reale dello switch che protegge l'ammissione `cost_recovery` ma **non spegne** abbonamenti e fatturazione globali. Pubblicate analisi IT/EN `AI_CHECKPOINT_RIGHTS_20261020_*`. **Testato:** ammissione conservativa e doppia conferma con pytest, parsing JS. **Bloccato:** licenza dei 5 pesi ChordFormer, ONNX UVR KARA 2 e identità dell'ONNX DrumSep MTA; rimangono `disabled` in default. Nessuna distribuzione non autorizzata o abilitazione automatica. Nessuna verifica end-to-end dei flussi commerciali su produzione o hardware. Versione 0.3.0-r210 invariata, nessun commit/push/tag/release.

# Aggiornamento r210 — doppia attestazione per attivazione modelli (20 ottobre 2026)

**Implementato:** selettore di base autorizzativa e due conferme UI; verifica server-side richiesta per l’attivazione di Madmom, ChordFormer, UVR, DrumSep e modelli aggiuntivi; storicizzazione e policy esistente preservate. Nessuna riabilitazione di default dei checkpoint non chiariti. **Testato:** test mirati licenze, guard download, worker billing simulati e nuovi test di doppia conferma. **Bloccato:** provenienza/autorizzazioni specifiche di checkpoint e test end-to-end reali. La doppia conferma e la responsabilità non equivalgono a licenza.

# Ciclo verifica licenze/checkpoint e fail-closed — 20 ottobre 2026

**Versione 0.3.0-r210 conservata, nessun commit/push/tag/release.** Il cumulativo utente è stato aperto ed estratto correttamente nell'ambiente corrente. Tutti i file precedenti sono conservati. Le affermazioni seguenti si riferiscono solo alle modifiche e ai test effettivamente realizzati in questo ciclo.

| Area | Stato | Risultato / blocco |
|---|---|---|
| Default modello e billing | Preservato, test mirati | La policy preesistente fornisce modalità `disabled`, `free_only`, `cost_recovery`, ledger non fatturabile per free-only e statistiche CPU/GPU; test mirati superati. Non si sostiene la copertura end-to-end completa di web, native, API/token, report e fatturazione. |
| Madmom / madmom-infer | Bloccato (pesi NC) | Codice separato dai pesi CC BY-NC-SA 4.0: gratuità e rimborso hardware non conferiscono automaticamente diritto a usare quei pesi in un servizio ospitato. Nessun peso riabilitato di default. |
| ChordFormer | Bloccato (cinque checkpoint s0–s4) | Fork MTA `shojha24/ChordFormer-Artificial-Dataset-Benchmarking` discende da `mwaseemrandhawa/ChordFormer`. Non è stata stabilita l'autorizzazione per ognuno dei cinque `.sdict`. Nuovo guard prima dell'acquisizione. |
| UVR / lead-backing | Bloccato per checkpoint configurato | La dichiarazione upstream UVR attribuisce MIT ai propri modelli con credito, ma provenienza/checksum e applicabilità al preciso `UVR_MDXNET_KARA_2.onnx` scaricato da MTA non sono conclusi. Download protetto; fallback DSP preservato. |
| DrumSep | Bloccato per checkpoint configurato | `inagoy/drumsep` è MIT per il repository, ma l'ONNX proveniente dal mirror `gridshiftstudio/drumsep-onnx` non è stato ricondotto con prove sufficienti ai pesi originali; guard download, locale e remoto implementato. |
| Attestazioni amministrative | Implementate e testate localmente | L'override preesistente richiede URL HTTPS, motivazione e assunzione esplicita responsabilità. Aggiunto `license-policy-history.json` con attestazioni precedenti e attore; test di cambio/revoca passati. Non sostituisce firma digitale o verifica indipendente dell'autorizzazione. |
| Modelli futuri | Fail closed, test locale | Le identità non registrate sono disabilitate. Serve revisione specifica codice, pesi, condizioni d'uso e deployment. |
| Web/native/API/token e sicurezza | Parzialmente testato, accettazione incompleta | Test autorizzazioni/billing/coda/Studio eseguiti localmente; nessun sistema di produzione, token reale, abbonamento reale o fatturazione live collaudato. L'isolamento e il metering esistenti non sono stati indeboliti intenzionalmente. |

**Test del ciclo:** 77 test passati nel primo gruppo mirato; **112 test passati** nel gruppo esteso (licenze, download, subscriptions, global queue, Studio workflows, SAM/backing/ROCm, stem codec e dialog). La fixture di trasporto UVR è stata adeguata a simulare un checkpoint autorizzato, senza allentare il controllo reale. Compilazione sintattica Python superata. Nessuna regressione integrale, end-to-end commerciale reale o certificazione hardware. Ruff non è installato in questo ambiente.

**Bloccanti di rilascio:** raccogliere licenza/permesso esplicito e provenienza verificabile, hash esatto e condizioni di servizio per ogni checkpoint ambiguo; collaudare tutti i percorsi web/native/API con token, quote, abbonamenti, report e fatture su un ambiente isolato e poi con autorizzazione in produzione. Non abilitare un modello semplicemente perché il costo è zero.

---

# Ciclo canto, riconciliazione, GM e collaudo hardware — 20 ottobre 2026

Versione **0.3.0-r210** invariata. Baseline: `MTA-0.3.0-r210-native-vst3-youtube-windows-cumulative.zip`, SHA-256 `8f8fb86752e0eb225dec4ea99e0b6e68f43bc97bf93a831ef631505e13344b56`. Utente conferma che il commit NON è stato eseguito: tutte le modifiche e la linea commit restano cumulative. Nessun commit/push/tag/release o accesso alla produzione.

**La specifica integrale dei due moduli AI non è ancora completata.** Questo ciclo chiude percorsi reali CPU e prepara il collaudo hardware; non dichiara implementati canto neurale, conversione timbrica o trascrizione massima con tutti i modelli candidati. Le sezioni successive sono storico; questa tabella descrive lo stato aggiornato.

| Area | Stato | Risultato verificabile / limite |
|---|---|---|
| Canto da MIDI con OddVoices | Implementata e verificata su CPU Linux | Tre voci CC0 scaricate, hash verificati, compilate e provate con audio reale; inglese americano/vocalizzi, non sintesi neurale. Note a pitch differenti verificate nel segnale; otto parti indipendenti renderizzate. |
| Coda, progetto e output vocali | Implementata e verificata end-to-end | Job reale, CPU accounting, audio + MIDI salvati atomicamente, offset regione, riapertura, ZIP risultati, importazione idempotente, mix udibile del progetto e rimozione banco senza cancellare i risultati. Guide MIDI con uscita Nessuna per evitare blocchi e note su hardware non richieste. |
| Voicebank e GM installer | Implementata; verificata ricetta reale e UI | Download esplicito con consenso e hash; avanzamento byte/segmenti, test PCM prima attivazione, annullamento, pulizia, disinstallazione. FluidR3 GM MIT, TinySoundFont MIT C++ fallback; 128 programmi e note batteria producono PCM, gain live e rendering server isolato verificati. Banchi grandi esclusi dallo ZIP sorgenti. |
| Riconciliazione YourMT3 + Basic Pitch | Implementata e verificata CPU | Due modelli reali sulla stessa registrazione di pianoforte di 2,1 s: tre eventi concordanti, nessuna duplicazione, due ipotesi originali conservate, salvataggio/riapertura e alternativa importata idempotentemente. Non è un benchmark di accuratezza su mix complessi. |
| Retry e alternative | Implementata e verificata | Checkpoint per modello/sorgente e conferma remota dopo persistenza; confronto uno-a-uno, conflitti conservati, originali importabili nel piano roll; nessuna falsa probabilità. |
| Licenze e billing | Implementata; verificata ammissione e ledger | App native/locali gratuite; rimborso solo CPU/GPU/disco server senza lucro. NC/servizio gratuito non derogati automaticamente. Default bloccanti per pesi non verificati; override esplicito operatore con fonte, motivazione e responsabilità. Job free-only conservano accounting senza billing/crediti/quote a pagamento; snapshot della decisione. |
| UI e documentazione | Implementata; verificata IT/EN | Chromium server/native, installazione e policy; quattro manuali HTML/PDF aggiornati con schermate reali, pagine finali ispezionate e nessun blocco fuori pagina. Termini IT/EN chiariscono il solo rimborso hardware server. |
| ASIO/ROCm | Preparazione implementata; collaudo reale bloccato dall’assenza hardware | Script inventario + test fisici espliciti con JSON/checksum. Assenza ROCm rifiutata senza fallback CPU spacciato per GPU. Nessuna certificazione di Windows ASIO, Proxmox/LXC, Radeon 8060S o billing GPU dell’istanza reale. |
| DiffSinger/Amphion/SVS, RVC/Seed-VC | Non completate / bloccate da integrazione, diritti e prove | Nessuna voicebank neurale produttiva dichiarata attiva. Italiano/francese, conversione, melismi legati ed espressione avanzata restano aperti. |
| Trascrizione Massima accuratezza | Non implementata | Mancano ensemble con stem e modelli specialistici, confronto renderizzato e benchmark reali a 5–10+ strumenti; MT3/MR-MT3/Transkun/MT3-Infer non attivati. |
| Routing hardware completo | In sviluppo; non verificato su hardware | Routing master stereo multicanale già presente; bus hardware indipendenti per traccia, loopback/reconnessione, MIDI hardware e collaudi cross-platform restano aperti. |

Rapporti reali: `validation/r210-accurate-real-models.json`, `r210-vocal-real-voices.json`, `r210-eight-voices-real.json`, `r210-gm-programs-real.json`, `r210-music-hardware-inventory.json`, `r210-rocm-absent-rejected.json`. Policy/licenze e istruzioni IT/EN: `docs/MUSIC_ASSETS_AND_LICENSES_R210.md` e `_EN.md`. Qixuan, Nishiren, SPORE, Madmom e checkpoint non verificati sono descritti singolarmente; SAM Audio non è classificato erroneamente come NC e BTC-HCQT dichiara MIT per codice e pesi.

Regressione generale finale: **4340 passati, 43 saltati, 10 esclusi**, nessun errore, 20m24s. Sono escluse le dieci prove socket Unix dell’agente host non eseguibili in questo sandbox, senza modificare i test/skip della CI. Verifiche aggiuntive: 22 passate per audio reale/GM/UI/integrità; 16 per ammissione e Studio; 1 retry per modello; 1 pipeline reale YourMT3 + Basic Pitch; 67 controlli adapter/ledger; 19 integrità/UI (esecuzioni distinte, non sommate). Ruff, Bandit alle soglie CI, pip check, license gate e sintassi JavaScript passati. C++ compilato su Linux; manuali PDF rigenerati e ispezionati. Dettagli in `validation/r210-music-assets-summary.json` e log associati. Nessun commit/push/tag/release, accesso alla produzione o incremento di versione. Prossimo checkpoint: prove sul server aggiornato e sulle native reali, poi backend neurali autorizzati, massima accuratezza e bus hardware mancanti.

# Ciclo correzioni native Windows — 20 ottobre 2026

Baseline allegata: `MTA-0.3.0-r210-device-routing-yourmt3-cumulative.zip`, SHA-256 `860abe53d2297a2459740163d559d0b449bac6cb95bca0e5dfe8df32f9a69c7c`, 2.380 elementi, CRC verificato. Versione 0.3.0-r210 invariata. Nessun commit successivo confermato: la consegna/linea di commit rimangono cumulative.

| Funzione | Stato | Verifica / limite |
|---|---|---|
| VST3 opzionali nelle native | Implementata; verificata API e Chromium IT/EN | Endpoint locali per catalogo/licenze/installazione/polling/disinstallazione; ruoli server, CSRF e consenso mantenuti; alias nativi indisponibili sul server. Compilazione del plugin simulata nel test del job manager, non certificata su Windows/macOS. |
| Errori non JSON | Implementata; verificata IT/EN | Errore leggibile con HTTP status; nessuna eccezione JSON non gestita. Cache frontend invalidata nelle pagine editor e admin. |
| YouTube e journal su Windows | Implementata; verificata con restrizioni Windows simulate su Linux | WAV reale importato, progetto riletto e rollback verificato. File fsync, sostituzioni atomiche e identità conservati; POSIX continua a propagare gli errori di sync delle directory. Download YouTube live e kernel Windows non verificati. |
| Workspace AppData | Comportamento previsto | Dati di lavoro in AppData, archivio `.maeprojz` nel percorso scelto; nessuna migrazione necessaria per questo errore. |

Verifiche: **76 test mirati passati, 1 saltato** (API Win32 reali); **21 passati** con ambiente nativo. Regressione generale: **4325 passati, 41 saltati, 10 esclusi**: i dieci casi socket Unix dell'agente host non sono eseguibili in questo sandbox; nessuna modifica alle esclusioni/skip della CI. Ruff scope CI, Bandit soglie CI, license gate, pip check e sintassi JS passati. Le nuove regressioni API/media sono aggiunte ai job CI nativi Windows e macOS, non eseguiti qui su quei sistemi.

Rapporti: `validation/r210-native-vst3-media-*`. Note operative IT/EN: `docs/NATIVE_VST3_MEDIA_R210.md` e `_EN.md`. Nessun file del cumulativo di partenza rimosso. Nessun commit/push/tag/release o intervento in produzione. Prossima verifica: installare la build aggiornata su Windows, installare un plugin opzionale e importare un contenuto YouTube autorizzato, salvare e riaprire.

Le macroaree Studio/hardware ancora aperte del checkpoint seguente restano aperte. Questo fix non certifica il server né completa i moduli vocali/modello/hardware mancanti.

# MTA Audio Editor — stato dello sviluppo

## Checkpoint dispositivi, workflow remoti e YourMT3 — 20 ottobre 2026

Versione **0.3.0-r210**, REVISION **210** e BUILD_INFO **20261015171900** invariati. Ripresa dal cumulativo `studio-queue-controller-workflows`, SHA-256 `fa53a22da50332d18b47927922554d250ec6d9409530dcbbe9fa45b227d7cad1`, 2.332 elementi. Nessun nuovo commit confermato dall’utente: questo ciclo include anche tutti i precedenti sviluppi MIDI/Studio non ancora committati. Nessun commit, push, tag, release o intervento sulla produzione.

**La richiesta di completamento integrale NON è ancora soddisfatta.** La tabella seguente descrive lo stato attuale; le sezioni successive sono storico. Un backend funzionante e provato su CPU non certifica ROCm, hardware ASIO o qualità su mix arbitrari.

| Macroarea | Stato | Evidenza / limiti |
|---|---|---|
| Output PortAudio e matrici C++ | Implementata; verificata su callback compilati e ALSA virtuale | Callback senza Python/GIL, master stereo → fino a 64 uscite, fino a 64 ingressi → stereo; selezione API/dispositivo, buffer/latency, preferenze DB. Nessuna sostituzione silenziosa di dispositivi mancanti. |
| Registrazione duplex | Implementata; callback compilato verificato | Uno stream per ingresso/uscita; controllo overflow, teardown dopo chiusura del callback, registrazione non avviata dopo preparazione interrotta. Dispositivi fisici/driver Windows/macOS non verificati. |
| ASIO distribuito e bus per-traccia | In sviluppo, incompleta | Selettore PortAudio/ASIO e backend presenti. DLL ASIO del wheel esclusa dalla distribuzione automatica finché mancano bundle di sorgenti corrispondenti e avvisi verificati. Matrici attuali collegano master e registratore stereo, non bus indipendenti per traccia. |
| Studio nativo → server | Implementato; verificato con token, API e worker reale tramite trasporto HTTP di test | Armonie JSON limitate/validate, journal idempotente, recupero dopo crash prima dell’ack, un solo addebito server, metriche mostrate senza ledger locale duplicato. Cancellazione remota; nessun fallback locale implicito. |
| Amministrazione modelli nelle native | Implementata e verificata API/browser | Percorsi locali dedicati: i precedenti `/api/admin/*` erano bloccati dal middleware nativo. API locali non esposte nel server web. Inclusi sorgenti Python/ricette per gli interpreti separati del bundle; il binario app congelato non viene usato come Python. Fallback uv gestito per Python 3.12, attivato solo dall’installazione esplicita. Layout estratto con worker esterno reale verificato; installer congelato Windows/macOS non verificato. |
| YourMT3 noPS | Implementato; inferenza CPU e progetto/coda verificati | Pubblicazione originale autore fissata, 100 sorgenti con hash, checkpoint originale verificato e conversione weights-only → 655 tensori safetensors. Tre note di pianoforte con pitch/tempi/program corretti; circa 17 s CPU; traccia MIDI salvata e riletta. Nessuna prova di accuratezza su dieci strumenti reali o ROCm/CUDA. |
| Installer YourMT3 | Implementato; ricetta Linux CPU con cache verificata | Ambiente separato Python 3.11/3.12, consenso esplicito, self-test prima dell’attivazione, cache offline integralmente verificata, pulizia del runtime fallito. Download sorgenti nella prima prova pulita rifiutato dalla rete di questo ambiente; cleanup verificato. Seconda installazione pulita da cache verificata riuscita; runtime 1.810.689.063 byte, pip check passato. Job avviato dal browser usando il nuovo runtime completato e importato. UI installazione/disinstallazione/default e ricetta Windows/macOS non implementate. |
| Dati musicali YourMT3 | Implementati, percorso reale verificato | Programmi GM/percussioni, note predicted/unreviewed, velocity generata 96 esplicitamente dichiarata, nessuna confidenza inventata. Parti melodiche su canali distinti fino a 15; canale 10 per percussioni. Oltre 15 parti melodiche serve rimappatura per hardware/SMF. Stesso programma/esecutori aggregati. |
| GM FluidSynth/FluidR3 | Backend precedente preservato; installer multipiattaforma non iniziato | Banco/libreria autorizzati ancora separati. Rendering reale usato per il campione YourMT3; nessun banco presentato come voce AI cantata. |
| Sintesi/correzione/conversione vocale | Non iniziata / bloccata per i voicebank da distribuire | Planner armonico MIDI funzionante, non cantante. Restano adapter SVS/VC reali, voicebank/lingue autorizzati IT/EN/FR, lyrics/fonemi/melismi, espressione, preset, anteprime e rigenerazione voce/regione. Seed-VC rimane candidato da valutare con tutte le dipendenze/pesi. |
| Trascrizione accurata/multimodello | Non iniziata | Restano STEM specializzati, confronto modelli, riconciliazione/alternative/confidenza calibrata e benchmark comparabili su mix reali 5–10+ strumenti. |
| Certificazione server/native | Non completata | Nessun test di produzione Rocky/LXC/ROCm né driver/dispositivi Windows/macOS fisici. Non dichiarare certificato il server. |

### Verifiche di questo ciclo

- 21 test mirati iniziali passati, inclusi stream PortAudio ALSA virtuale, Studio e job remoti.
- Otto test nativi finali con compilazione/callback reali e PortAudio virtuale passati; successiva correzione della latenza duplex solo nella rappresentazione dello stato.
- Prima regressione estesa: 4.309 passati, 41 saltati, 10 esclusi per socket Unix non disponibili, un fallimento nella fixture di preparazione silenziosa. Corretto il controllo preferenze I/O dopo il guard nativo; successivi 17 test transport/I/O passati, uno stream opt-in saltato in quel comando. I controlli di accesso produttivi restano attivi.
- Due test remoti reali del protocollo/ledger passati; 19 Studio/checkpoint/API passati e un test modello opt-in non eseguito in quel comando. Cinque test successivi su checkpoint/cache offline/normalizzazione errori passati.
- Inferenza reale YourMT3 CPU: test pytest musicale passato; worker registrato reale passato; coda → importazione → rilettura progetto passata. Queste prove non sono esecuzioni simulate del modello.
- Browser Chromium: finestra YourMT3 senza soglie Basic Pitch improprie, amministrazione modelli nativa, matrice I/O e salvataggio backend predefinito; zero errori JavaScript.
- C++ core compilato ABI 1; Ruff scope CI, Bandit soglie CI, pip check e license gate passati. Sintassi JS modificati passata. Manuali online/PDF IT/EN aggiornati; quattro pagine interessate renderizzate e controllate.
- Seconda regressione completa: **4.311 passati, 41 saltati, 10 esclusi, un fallimento** nel solo controllo del prefisso cache frontend. Ripristinato il prefisso `0.3.0-r210`, mantenendo il suffisso di invalidazione; 18 controlli identità release/Studio successivi passati. Non è stata eseguita una terza regressione completa dopo questa correzione di metadati. Ulteriori 22 test Studio/packaging/checkpoint/remote e 11 test staging server/identità release passati dopo i fix del bundle. Staging con compilazione reale C++; download wheel omesso nella fixture. Ricette/runtime Studio incluse nei payload RPM/DEB, Docker e bundle nativi. Nessuna build completa RPM/DEB/Windows/macOS eseguita qui.

### Prossimi passi e ripresa

1. Completare gestione grafica/lifecycle YourMT3 e distribuzione GM su ciascuna piattaforma, con build/test reali.
2. Integrare un modello vocale e voicebank autorizzati, fonemizzazione/lyrics ed espressione; svolgere i test musicali richiesti per canto/SATB/otto parti/regione.
3. Realizzare modalità di trascrizione accurata/multimodello, riconciliazione e revisione; misurare mix reali con dieci o più parti senza filler.
4. Completare bus audio hardware per-traccia e distribuzione ASIO con sorgenti corrispondenti; testare routing audio/MIDI e driver reali.
5. Completare l’accettazione su Rocky/LXC/ROCm e native Windows/macOS; verificare licenze transitive/binarie prima della distribuzione di ciascun runtime.

Dettagli e licenze: `docs/YOURMT3_RUNTIME_R210.md`, `_EN.md`, `docs/STUDIO_WORKFLOWS_R210.md`, `_EN.md`. Rapporti di questo ciclo: `validation/r210-device-*` e `validation/r210-yourmt3-*`.

## Storico dei checkpoint precedenti

## Integrazioni Studio e corsie MIDI — 20 ottobre 2026

Versione **0.3.0-r210**, REVISION e BUILD_INFO invariati. Ripresa dal cumulativo midi-studio-foundation, SHA-256 `ce0d0e48e15f10f65a62f94e133bc34f357f1ab64181b04c7a467502ddb64a91`, **2.306 elementi precedenti tutti conservati**. L’utente NON ha ancora committato il checkpoint precedente: package e suggerimento di commit comprendono entrambi i cicli. Nessun commit/push/tag/release o modifica alla produzione.

**Le specifiche integrali AI Vocal Studio / Multi-Track Audio-to-MIDI non sono completate.** L’interfaccia espone soltanto le capacità realmente collegate; il canto non è sostituito da tracce dimostrative e non vengono aggiunti strumenti fittizi. L’assenza di modelli autorizzati e delle prove hardware non viene occultata.

| Macroarea | Stato attuale | Evidenza / limite |
|---|---|---|
| Workflow Studio di progetto | Implementato e verificato localmente | Coda globale esistente, worker reali, permessi, cancellazione, retry/checkpoint sorgenti, timeout, risultato revisionato e pubblicazione atomica/idempotente. Progetto modificato durante inference: risultato conservato per revisione. |
| Audio-to-MIDI su sorgenti indipendenti | Verificato CPU locale | Due sorgenti audio → due MIDI salvati; offset regione, clip, delay e gain; ledger CPU corrispondente alla lista coda. Fino a 32 sorgenti; nessun riconoscimento degli strumenti dal mix. |
| Armonie vocali MIDI | Verificate localmente | 2–8 voci SATB-style; worker reale; partitura strutturata oltre 256 KiB; quattro parti da MIDI trascritto, persistenti alla riapertura. Nessuna sintesi vocale. |
| UI Studio | Implementata e verificata Chromium | Schede sorgente/arrangiamento/esecuzione/risultati, CPU/GPU, diagnostica ZIP, import esplicito, riapertura ultimo job, chiusura senza cancellazione. Cantanti/espressione espongono l’assenza del backend. |
| Catalogo Basic Pitch | Implementato, inferenza CPU verificata | Installazione esplicita Python 3.11/3.12 separata, checksum e vero self-test prima dell’attivazione; test ripetibile, enable/disable/uninstall con protezione runtime attivi. Runtime locale misurato 610.857.789 byte; dimensione dipendente dalla piattaforma. |
| Privacy ONNX | Implementata e verificata localmente | Primo test bloccato dal controllo automatico per telemetria Microsoft; alternativa più sicura documentata ufficialmente: opt-out PRIMA dell’inizializzazione e API disattivazione. Inferenze successive riuscite. Nessuna elusione dei controlli. |
| Pulizia / conservazione | Implementata, testata | Risultati/checkpoint privati scadono dopo sette giorni configurabili; job attivi e media pubblicati conservati. Sorgenti WAV temporanee rimosse fra passaggi; eliminazione account include cache Studio. |
| Corsie controller MIDI | Implementate e verificate nel browser | CC, bend 14 bit, pressione e programmi, selezione multipla, drag/frecce/snap, campi numerici, cancellazione, undo/redo, zoom/scroll condivisi; eventi persistenti in riapertura. Non equivale a un ambiente professionale MIDI integralmente certificato. |
| SMF2/SMPTE, GM, griglia/grafico tempo | Preservati dal checkpoint precedente | Nessuna rimozione; regressioni automatiche/browser e compilazione C++ locali. Installer GM multipiattaforma ancora aperto. |
| Sintesi/conversione vocale, IT/EN/FR, lyrics/fonemi | Non implementata / diritti da verificare | Nessun voicebank autorizzato integrato; candidati non abilitati senza modello, ricetta e licenze separate verificati. |
| Trascrizione multi-strumento da mix / riconciliazione | Non implementata | Basic Pitch non sostituisce YourMT3/MT3; niente modalità Accurate/Massima simulate. Capacità editor ≥16 parti già testata, non capacità predittiva. |
| ASIO dedicato e matrice audio/MIDI fisica completa | In sviluppo, incompleta | Non modificata/certificata da questo ciclo; serve backend dedicato e collaudo sui dispositivi reali. |
| Nuovi workflow progetto nativo → server remoto | In sviluppo, incompleto | Protocollo token worker esistente riusabile; import/persistenza intero workflow locale-remoto ancora da completare. |
| Certificazione server ROCm e native | Non completata | Nessun accesso né test di inferenza sul server dell’utente, nessun hardware Windows/macOS/ASIO in questa verifica. |

### Verifiche di questo ciclo

- 46 test mirati finali passati (Studio/pubblicazione/crediti); 2 test reali ONNX CPU passati separatamente, incluso audio → MIDI → armonie, riapertura e ledger. Altri 19 controlli protocollo/billing precedenti passati; ultime 13 regressioni worker/pubblicazione ripetute e passate dopo la pulizia WAV intermedia.
- Chromium reale autenticato: editing note/gruppi/undo/redo, canvas esteso, controller CC/bend/tastiera/delete, persistenza, preferenze lazy, grafico tempo, overlay, finestre Studio e modelli; **zero errori JavaScript**.
- Compilazione C++ `mta_audio_core` ABI 1 passata; sintassi di tutti i 40 JS passata; Ruff nello scope CI e script nuovi, Bandit alle soglie CI, `pip check`, license gate passati.
- Prima regressione estesa: 4.240 passati, 93 saltati, 12 fallimenti. Dieci richiedono socket Unix bloccati dal runtime; uno richiedeva CMake nel PATH; uno ha rilevato una sezione GM impropriamente dopo l’appendice licenze, corretta anche nello script idempotente dei manuali. Ripetizione finale: **4.299 passati, 39 saltati, 10 esclusi per socket Unix non disponibili, nessun fallimento** (526,01 s). Nessuna modifica ai controlli CI o ai test socket; i 46 mirati finali e le 2 inferenze reali sono stati ripetuti dopo gli ultimi aggiustamenti.
- Sei manuali PDF/online IT/EN aggiornati, immagini della fixture reale senza dati personali, pagine modificate renderizzate e controllate. Rapporti nel namespace `validation/r210-studio-workflows-*`.

### Prossima ripresa

1. Integrare un backend vocale reale con voicebank IT/EN/FR autorizzati, fonemizzazione/lyrics e rendering delle parti; completare preset, ascolto e rigenerazione voce/regione.
2. Verificare diritti dei checkpoint e dipendenze dei modelli multistrumento, integrare inferenza, riconciliazione/alternative e test musicali comparabili senza confidenza inventata.
3. Completare ASIO dedicato, routing fisico multicanale, installer GM/interpreti nativi e workflow locali con server AI remoto.
4. Eseguire tutta l’accettazione su Rocky/LXC/ROCm e dispositivi nativi reali; nessuna certificazione preventiva.

Dettagli operativi e registro licenze: `docs/STUDIO_WORKFLOWS_R210.md` e `_EN.md`. Le sezioni seguenti conservano lo storico del checkpoint precedente.

## Checkpoint in sviluppo — MIDI, GM e fondamenta AI Studio (20 ottobre 2026)

Versione **0.3.0-r210**, BUILD_INFO invariato. Ultimo commit dell’utente confermato sul cumulativo `transport-priority-zone-buttons`; baseline SHA-256 `ad2258e805405b70b83b8fa6b5222ff0aacc6a8b3233f066f3c4a7b281587e1a`, 2.272 elementi. Nessun commit/push/tag/release e nessun intervento sul server di produzione.

**AI Vocal Studio e AI Multi-Track Audio-to-MIDI NON sono completati.** Il package è un checkpoint cumulativo di sviluppo, non soddisfa ancora tutte le condizioni di consegna dei due moduli. Le specifiche del 20 ottobre restano vincolanti. Le funzioni non disponibili non vengono sostituite da UI dimostrative, cantanti fittizi, strumenti di riempimento o metriche inventate.

| Funzione | Stato | Evidenza / limite |
|---|---|---|
| SMF0/1/2 e SMPTE | Verificata localmente | Pattern indipendenti; -29 = 30000/1001; metadati persistenti, export multitraccia, import atomico. |
| Editor MIDI avanzato | In sviluppo | Gruppi, undo/redo, trasformazioni, lista eventi, piano roll virtualizzato verificati nel browser. Editor CC/automazioni professionale completo ancora aperto. |
| Preferenze lazy DB e sidebar MIDI | Implementata / verificata localmente | Patch concorrenti per identità, retry/batch, ripristino dopo reload; migrazione sicura delle preferenze native dell’editor. Altre impostazioni native storiche ancora su file. |
| GM FluidSynth/FluidR3 | Verificata localmente | Audio reale diretto, rendering offline isolato e PCM nel worker server. Banco/librerie non inclusi nello ZIP; installer opzionale multipiattaforma pendente. |
| Metronomo MIDI e grafico BPM | Implementata / verificata localmente | Griglia fissa/zone/adattiva, aggiornamento marker, BPM decimali, tastiera ripetuta e overlay senza alterazione geometria traccia. Hardware MIDI da provare. |
| Formato musicale comune / import | Verificata localmente | 16 parti indipendenti, provenienza, alternative con offset persistenti, revision guard, idempotenza, rollback e conservazione media dopo commit. Nessuna equivalenza con riconoscimento di 16 strumenti. |
| Armonizzazione | In sviluppo | Motore MIDI indipendente, 2–8 voci, range/voice leading/no incroci, priorità accordi confermati. Test 4/8 voci. Non collegato ancora a sintesi/UI/coda; qualità musicale non certificata. |
| Basic Pitch ONNX sorgente isolata | Implementata, verifica reale CPU locale | Adapter controllato dall’operatore nel protocollo esistente, checksum modello, coda globale e ledger CPU reali. Output MIDI modificabile; non classificatore multistrumento. |
| Vocal Studio audio/voicebank/lyrics/UI | Bloccata per produzione / non iniziata in parte | Nessun voicebank autorizzato e verificato incluso; DiffSinger/Amphion/RVC/Seed-VC, IT/EN/FR, fonemi e UI da integrare. |
| Multi-Track Audio-to-MIDI produttivo | Non iniziata | YourMT3+/MT3/MR-MT3/Transkun/MT3-Infer, multimodello/STEM, riconciliazione, conflitti, dataset e UI ancora aperti. |
| Catalogo/installazione modelli completi | Non iniziata | Pilot Basic Pitch esclusivamente opt-in; revisione produttiva separata di codice/pesi/dataset/dipendenze pendente. Nessun download implicito. |
| Job dei nuovi moduli end-to-end | In sviluppo | Pilot nel worker/coda/accounting esistente. Mancano UI, checkpoint/cache, cancellazione/retry/recovery completi e workflow con pubblicazione automatica. |
| ASIO, matrice I/O e routing completo | Non iniziata in questo ciclo | Restano routing e capacità preesistenti. Nessun test su interfacce Windows/macOS reali. |
| Compatibilità ROCm/CUDA nuovi modelli | Non verificata | Pilot CPU soltanto. Nessuna misura GPU mancante o non valida resa fatturabile. |

### Prove effettive

- Regressione estesa: **4.281 passati, 36 saltati, 12 deselezionati, zero fallimenti**. Due dei deselezionati (non dipendenti da socket) eseguiti successivamente e passati; restano **10 casi Unix socket** non eseguibili per le restrizioni di bind dell’ambiente locale. Nessun test CI disattivato e nessuna soglia abbassata. I 36 skip comprendono hardware/plugin/piattaforme assenti. Il ciclo esteso precede gli ultimi affinamenti circoscritti, coperti dalla regressione mirata successiva.
- Regressione mirata finale: **38 passati** su SMF, metronomo, preferenze, import musicale, permessi e due casi esclusi dal ciclo esteso. Ulteriore prova JS di migrazione nativa aggiunta e passata (3 test JS comportamentali totali).
- GM reale: **10 test passati**, incluso PCM offline e worker server. Basic Pitch reale: **1 test passato** attraverso coda e ledger, CPU **3,683479 s**, nessuna GPU attribuita. Fixture sintetica di 5 secondi: quattro onset/pitch attesi rilevati entro 50 ms e una nota falsa; precision 0,8, recall 1, F1 0,8889 sulla sola fixture, non un benchmark di brani reali.
- Browser Chromium autenticato con HTTP reale: gruppi/undo/redo, salvataggio e riapertura MIDI, piano roll di un’ora senza bitmap enorme, preferenze DB e sidebar persistenti, BPM da frecce ripetute, overlay con geometria invariata; **zero errori JavaScript**.
- Build C++ ABI 1 riuscita; Ruff e Bandit alle soglie CI, sintassi JS, pip check runtime principale e guardia statica licenze passati. Nessuna nuova build/CI remota o certificazione hardware/ROCm di produzione.
- Sei manuali IT/EN aggiornati (utente, amministratore, VST3), PDF rigenerati e pagine modificate ispezionate visivamente; nessun testo fuori margine nella verifica geometrica. Licenze FluidSynth/FluidR3/Basic Pitch documentate separatamente; non viene dichiarata una revisione completa dei modelli candidati.

Dettagli: `docs/AI_STUDIOS_IMPLEMENTATION_R210.md` e versione `_EN.md`. Report: `validation/r210-studio-*`. Prossimo checkpoint: modello/catalogo e UI Source/Execution/Results sulla coda esistente, poi backend multistrumento e voce con pesi/voicebank autorizzati, infine ASIO/routing e accettazioni hardware. Non chiamare completi i moduli prima di queste prove.

## Ciclo completato — priorità transport e pulsanti griglia metronomo (20 ottobre 2026)

- Baseline cumulativa: decimal-zoom-accounted-usage, SHA-256 `40f8e187a4673c01643fec97eb332b622358d468037ae32edcd22d35aa9e0423`, 2.254 elementi conservati. Versione 0.3.0-r210 e BUILD_INFO invariati.
- Click su righello/timeline/segmento ora inviano il seek al motore; frecce, slider, inizio e immissione numerica condividono il percorso. Il drag dei segmenti resta un’operazione di editing.
- L’ultimo posizionamento esplicito prevale anche durante la preparazione WebAudio/C++ server/native. Bridge nativo serializzato, risposte di stato/controllo obsolete scartate; preparazione nativa in pausa, ultimo seek applicato prima del Play. Il fallback di rendering rispetta ora start_playing=False. Guardia server dopo audio unlock e intento Play/Pausa conservato durante seek ripetuti.
- Pulsanti «Applica e rigenera zona» / «Riporta in Auto»: stile azioni con sfondo e testo coordinati, layout adattivo, accento sull’azione principale. Verificati IT/EN, preferenza OS chiara/scura, contrasto almeno 4,5:1 e azioni corrette.
- Allegato CI: medesimo commit `11e7d366`, confronto testuale zoom già corretto nella baseline; regressione rieseguita e passata. Non è una nuova esecuzione del cumulativo decimal-zoom-accounted.
- **232 test mirati distinti passati, zero fallimenti e zero skip nella verifica finale** (210 + 22), inclusi persistenza zoom, metronomo, editing, bridge nativo, dispositivo null e consumi contabilizzati. I mock legacy sono stati completati per il nuovo stato del transport, mantenendo e rafforzando le verifiche su drag/storico/assenza di seek durante il drag.
- **Browser reale autenticato con HTTP e audio corrente/C++ server**: 6 scenari per motore, avanzamento del clock dal punto richiesto dopo preparazione ritardata/Pausa/Stop, click/frecce/input numerico; zero errori JS. **17 scenari deterministici** di concorrenza del codice transport in Node, incluse risposte/fallimenti obsoleti e Play dopo seek pendente.
- Ruff scope CI + nuovo probe, Bandit alle soglie CI, sintassi JS, pip check, guardia licenze e build C++ ABI 1 passati. Nessun test CI disabilitato o soglia ridotta. Non rieseguita l’intera suite da oltre 4.000 casi in questo ciclo.
- Restano CI remota dopo il commit e accettazione su dispositivi fisici Windows/macOS e server reale/ROCm. Nessun commit/push/tag/release né intervento sul server.
- Report finali: `validation/r210-transport-priority-*`, `validation/r210-transport-browser-*`. Dettagli IT/EN: `docs/R210_TRANSPORT_POSITION_PRIORITY.md`.

## Ciclo completato — zoom decimale, Quality e consumi contabilizzati (20 ottobre 2026)

- Baseline: cumulativo zones-zoom-layout-manuals, SHA-256 7f063c80fc8bb41b6bd0cbd3fafd165dc1fb3129e0810b12b8093e9399330647.
- Il log di checkout CI identifica main al commit `11e7d3666e4e2b75150e45a8d5ef63e62781efca`, dopo il cumulativo precedente.
- Log Quality utente: 4.249 passati, 13 saltati, un fallimento su un confronto testuale obsoleto dello zoom.
- Riproduzione segnalata: PUT progetto rifiuta uno zoom frazionario con int_from_float.
- Completati zoom decimale persistente (25–1200 px/s, finito), cache aggiornata e test comportamentali JavaScript/API/riapertura. Risolto il rifiuto int_from_float anche dei valori dei client precedenti.
- Consumi CPU/GPU accettati esposti come contabilizzati in coda/quote/billing; proiezione subordinata all’evidenza immutabile, nessuna duplicazione con i contatori in raccolta nei report/email. Solo CPU non implica GPU contabilizzata; contatori assenti/invalidi non sono promossi. Origine tecnica mantenuta in audit/API, senza dichiarare una verifica hardware inesistente.
- Aggiornati testi IT/EN, chiavi cache e manuali online/PDF; 6 manuali, 99 pagine totali, pagine modificate verificate visivamente e testo entro i margini.
- Regressione estesa iniziale: **4.219 passati, 35 saltati, 10 esclusi localmente** per socket Unix negati; **11 fallimenti iniziali** (7 permessi persi nella copia locale, 2 assert sulle vecchie etichette, 2 prove temporali C++ sotto carico). Rapporto originale conservato. Nessun test CI disabilitato e nessuna soglia ridotta.
- Riesecuzione finale sul codice aggiornato: **190 passati, zero fallimenti**, inclusi tutti i 9 casi non prestazionali inizialmente falliti e il caso aggiuntivo CPU-only. Prove C++ isolate normale/stress passate, zero underrun; fader 0.88 s / 0.954 s, entro i limiti originali 1 s / 2,5 s.
- Copertura complessiva **75,08%** (soglia CI 70%); linee **78,43%**. Browser reale corrente/C++ passati con salvataggio dei valori frazionari, ancoraggio entro un pixel, riordino, menu, metronomo e autosave; zero errori JS. Ruff, Bandit alle soglie CI, sintassi JS, pip check e guardia licenze passati; C++ ABI 1 compilata.
- Restano la CI remota dopo il commit e le verifiche su dispositivi fisici/server ROCm installato: non sono certificati da queste prove locali. Versione e BUILD_INFO invariati; nessun commit/push/tag/release o intervento di produzione.
- Report: `validation/r210-decimal-zoom-accounted-*`. Dettagli IT/EN: `docs/R210_DECIMAL_ZOOM_ACCOUNTED_USAGE.md`.

## Ciclo completato: metronomo a zone, zoom, layout personale e manuali (r210)

Baseline verificata: `0f295c2201bff0a2af5334049b91aeb1af2607b79396633bff79fcb8b9f96aa0`, 2.201 elementi, preservati nel nuovo cumulativo. Versione 0.3.0-r210 invariata.

- Primo beat a zone allineato all’inserimento; pre-roll conservato nel refresh. Il salvataggio dei marker rigenera il WAV e invalida le riproduzioni preparate. Protetti i risultati del metronomo dagli autosave accodati; rollback e pulizia temporanei in caso di errore.
- Zoom: stesso centro temporale durante preview, rilascio, pulsanti, preset e autosave, con clamp ai bordi del progetto e valori persistiti compatibili con il modello.
- Menu sempre raggiungibili, steppers compatti, barre a icone riordinabili su sei righe, monitor Job AI flottante e preferenze persistenti per utente/native. Pan sopra il valore e pulsanti FX. Gli elementi nascosti per piattaforma/permessi restano nascosti.
- Sei manuali IT/EN, online e PDF, uniformati e aggiornati; 15 schermate reali con dati sintetici, appendici condivise, tabelle e quattro grafici. PDF: utente 26+26 pagine, amministratore 15+15, VST3 8+8. Controllati copertine, font, contenuti finali, asset e limiti pagina; online fruibili anche a 390px.
- Suite estesa: **4.215 passati, 35 saltati, 10 esclusi** per test con socket agente host non disponibile; due prove C++ di latenza/stress fallite nel run concorrente, poi **entrambe passate nella verifica finale isolata**, senza allentare le soglie. Migliorato anche il feedback immediato dell’icona Pausa e il cleanup dei processi dei probe.
- **68 test mirati finali passati**, oltre agli 87 controlli dei contratti precedenti. Browser reale sui motori corrente e C++: generazione sotto autosave accodato, refresh marker durante playback, zoom ancorato, layout/monitor persistenti, menu, mobile e controlli nascosti: passati, zero errori JS.
- C++ reale: avvio 1,233s, fader 0,530s; stress rete/stalli UI: fader 0,737s, zero underrun. Misure locali, non garanzie di produzione. Compilazione C++ ABI 1, Ruff scope CI e nuovi script, Bandit alle soglie CI, sintassi JS, pip check e guardia licenze passati. Rapporti in `validation/r210-zones-layout-*`.
- Restano prove sui dispositivi fisici Windows/macOS e sul server installato/ROCm/proxy reali. Nessun commit, push, tag, release o aggiornamento di produzione eseguito.

Dettagli IT/EN: `docs/R210_ZONES_LAYOUT_MANUALS.md`.

# MTA Audio Editor — Development status

Versione obbligatoria: **0.3.0-r210**. Ultimo ciclo completato: continuità audio C++ e disinstallazione VST3, 19 ottobre 2026.

## Ciclo completato — continuità audio C++ e disinstallazione VST3 (19 ottobre 2026)

- Baseline recuperata dalla Library e verificata CRC/SHA-256: `MTA-0.3.0-r210-vst3-progress-cpp-live-controls-cumulative.zip`, `42fe3889ec2b1affce9de31e2f678716991efa451bee157112c95f9c8e4b21c6` (2.186 file).
- Utente conferma mixer, VU e avvio immediato; segnala microinterruzioni C++, Play/Pausa errato e assenza di disinstallazione VST3.
- Flusso PCM spostato in Worker/AudioWorklet con FIFO limitata, buffering adattivo e clock da campioni consumati. Handshake per reset/generazioni e gestione pausa/seek/Stop; controlli sequenza/finitezza invariati. Ricampionatore sinc/Blackman 64 tap e 1.024 fasi per frequenze diverse, bypass bit-exact alla stessa frequenza. Fallback browser precedenti mantenuto con scheduling contiguo e margine maggiore.
- Evitati seek ridondanti durante letture consecutive dei decoder. Test MP3: 2.813 seek eliminati, campioni identici; nessun vantaggio di velocità dimostrato dal microbenchmark.
- Stato Play/Pausa riallineato dopo la preparazione, icona SVG esplicita, etichette/tooltip e bridge nativi verificati.
- Disinstallazione VST3 opzionali da scheda con conferma singola, pulizia cache opzionale, avviso progetti dipendenti e dati progetto conservati. Autorizzazioni admin, ID allowlist, protezioni traversal/symlink e lock installazione/sessioni/editor; distacco atomico sullo stesso volume e namespace transitorio non eseguibile/discoverable.
- **4.187 passati, 35 saltati, 10 esclusi per socket/agente non disponibili**, zero fallimenti (circa 580s). **16 nuove regressioni finali passate**, compresi gli ultimi controlli aggiunti dopo l'avvio della suite estesa; 23 preparazione/continuità passati e 42 passati con CHOW Tape reale (uno escluso senza display). Nessun test CI disabilitato o soglia ridotta.
- Prove ASGI/Chromium/WebAudio/C++ a otto tracce: zero underrun con ritardi di rete fino a 180 ms e cinque blocchi UI da 450 ms; avvio sessione 1,239 s, risposta volume 0,538 s (0,701 s con rete rallentata). Motore corrente/editor/bozze preservati e zero errori JS. Più buffering rispetto al ciclo precedente in cambio della continuità sotto carico; nessuna garanzia di latenza universale.
- Ruff, Bandit alle soglie CI, license guard, sintassi JS, pip check passati. Tutti i 2.186 file precedenti conservati. Report in `validation/r210-continuity-*`, `r210-continuous-pcm-*`, dettagli IT/EN in `docs/CPP_CONTINUITY_VST3_UNINSTALL_R210.md`.
- Consegna: `MTA-0.3.0-r210-continuous-cpp-audio-vst3-uninstall-cumulative.zip`, intero progetto con CRC/confronto byte per byte/permessi/SHA-256 verificati durante packaging. Restano ascolto e accettazione sul server reale Rocky/HAProxy e sui dispositivi Windows/macOS.
- Versione 0.3.0-r210 invariata; nessuna modifica a produzione o azione Git.

## Ciclo completato — installazione VST3 e trasporto C++

- Baseline: `MTA-0.3.0-r210-ci-sdk-midi-progress-cumulative.zip`; tutti gli sviluppi precedenti vengono conservati.
- Richieste: barra per plugin/stato installazione; VU meter C++, controlli mixer tempestivi e pausa con Spazio.
- Cause individuate: shortcut legata ai vecchi stati; assenza di livelli nel flusso browser; coda PCM fino a oltre un secondo e salvataggio prima di ogni modifica live; pan privo di aggiornamento live.
- Implementati stato/barra per plugin con esiti persistenti; metering DSP stereo e aggiornamenti mixer live senza salvataggio; coda PCM breve e adattiva; shortcut Play/Pausa condivisa.
- Verificati 57 test mirati con CHOW Tape reale (1 escluso senza display), nove nuove regressioni e 44 regressioni legacy. Probe ASGI/Chromium/C++ a otto tracce: volume udibile dopo circa 235 ms; motore corrente e cache verificati. Regressione finale: **4,173 passati, 35 saltati, 10 esclusi per socket/agente non disponibili**, zero fallimenti (487s), con configurazione CI. Nessuna certificazione hardware o produzione implicita.

- Prima regressione locale: 12 test legacy richiedevano la variabile CI `MTA_ALLOW_INSECURE_NO_AUTH=true`; aggiornate inoltre due vecchie asserzioni che pretendevano Spazio=Stop. Tutti nuovamente passati; nessun controllo di autenticazione del prodotto rimosso. I nuovi probe server/browser usano autenticazione reale, con modalità insicura esplicitamente disabilitata.
- Ruff, Bandit alle soglie CI, license guard, pip check, sintassi JS e adapter Node passati. Report in `validation/r210-live-mixer-*`; dettagli IT/EN in `docs/VST3_PROGRESS_CPP_LIVE_CONTROLS_R210.md`.
- Consegna cumulativa `MTA-0.3.0-r210-vst3-progress-cpp-live-controls-cumulative.zip`, intero progetto; tutti i 2.173 file della baseline preservati, con verifiche CRC, byte per byte, permessi e SHA-256 durante packaging. Restano le prove sul server reale/HAProxy e sui dispositivi fisici Windows/macOS.
- Versione **0.3.0-r210** invariata. Nessun commit/push/tag/release o modifica a produzione.

## Ciclo completato — regressioni CI SDK e browser MIDI (19 ottobre 2026)

- Commit del cumulativo precedente confermato dall'utente; baseline `MTA-0.3.0-r210-playback-vst3-paypal-subscriptions-cumulative.zip`, SHA-256 `3c357e5c62eecdb04dcd32597fbda2b625ccf5d7646ae4ca11f58e3d80494bb4`. Tutti i **2.158 file conservati**, inclusi playback, plugin opzionali, abbonamenti e PayPal.
- Log ricevuti: SDK compila probe/ADelay e supera 128 blocchi, poi importa erroneamente `auth/qrcode` dal nuovo catalogo; Quality riporta 4.190 passati e un timeout su `#midiRoute`, copertura 75,43%. Bandit, audit dipendenze Python, Gitleaks e Trivy risultano passati nei log.
- Discovery VST3: percorso dei plugin opzionali spostato nel helper condiviso `runtime_paths.optional_vst3_root`, con sola libreria standard. Installer e discovery condividono il calcolo senza inizializzare autenticazione nel job SDK. Controlli percorsi/permessi e ruoli amministrativi invariati.
- Causa browser: `showMediaProgress` sostituiva il contenuto della finestra MIDI. Creato indicatore audio indipendente con proprietà per richiesta, senza sostituire/nascondere gli editor aperti. Applicato a WebAudio, nativo C++ e server C++; Stop evita riaperture dell'indicatore da risposte tardive. Cache frontend aggiornata con prefisso versione conservato.
- **Cinque nuove regressioni passate**: due processi Python `-I -S` senza site-packages e con import auth/qrcode/catalogo/FastAPI vietati; tre prove Chromium per bozze/lingue/proprietà/Stop e trasporto nativo con bridge controllato. Suite mirata: **56 mirati passati, 10 saltati**; 10 controlli finali metadati/UI passati.
- **SDK Steinberg reale compilato e sette accettazioni ADelay passate con `python -S`**: offline, chain, variable, session, stream, events, native_bridge. Commit SDK `3cdf9ca5d1f5b1b21e0a86832aa4abe55607bd96`; submodule e log nel rapporto dedicato. Nessun SDK/binario esterno aggiunto al package.
- Server HTTP locale + Chromium + WebAudio reali: otto tracce, zero rendering backend e zero errori JS; pannello effetto e valore non applicato preservati dopo playback/Stop. Ulteriore probe con finestra MIDI reale preservata. Nessun dato o pagamento di produzione usato.
- **Regressione finale: 4.164 passati, 35 saltati, 10 esclusi per socket/agente non disponibili**, nessun fallimento (455s). Il controllo del prefisso cache rilevato nel primo passaggio locale è corretto e passato nuovamente; l'ultima regressione usa la correzione. Ruff, Bandit alle soglie CI, license guard, pip check, compilazione Python e sintassi JS passati.
- Test browser live completo del runner conservato e rafforzato con assert sull'editor MIDI durante playback e dopo Stop; resta da riconfermare nella CI con host MTA compilato/plugin esterno. Nessun test CI disabilitato e nessuna soglia ridotta. Hardware Windows/macOS e server ROCm reale non certificati da queste prove.
- Dettagli: `docs/CI_SDK_MIDI_PROGRESS_R210.md`; esiti/JUnit in `validation/r210-ci-*`. Consegna `MTA-0.3.0-r210-ci-sdk-midi-progress-cumulative.zip`, intero progetto, CRC/confronto byte per byte/permessi e SHA-256 verificati nel packaging.
- Versione **0.3.0-r210** invariata. Nessun commit/push/tag/release, modifica a server reali o pagamento effettuato.


## Ciclo completato — playback, plugin opzionali e abbonamenti (19 ottobre 2026)

- Baseline: `MTA-0.3.0-r210-pages-download-cumulative.zip`, SHA-256 `86c93ca9a9989d2c9dd30c901b0b1f4a3fbd76010cdf27a7373017c2a3a8130e`. Tutti i 2.124 file conservati, incluse le precedenti correzioni CI/Pages. I permessi eseguibili POSIX della baseline vengono preservati nel cumulativo.
- Playback: eliminate conversioni integrali inutili per clip/delay; lettura diretta, cache 256 MiB e due decodifiche contemporanee in WebAudio. Anteprime float WAV riconosciute, pubblicazione atomica e cache master basata su identità sorgenti senza rileggere file interi. Rimossi i preload HTMLAudio non riutilizzati.
- C++: grafo a blocchi anche senza VST3/MIDI, sorgenti compatibili lette direttamente; conversione solo dei formati incompatibili. Confronto campione per campione con il render precedente e worker reale isolato con uscita nulla passati. Motore precedente mantenuto; fallback al mix completo solo senza runtime live.
- Preparazione: fasi distinte, nome traccia, conteggio e tempo trascorso, annullamento rispettato. Prova Chromium su otto tracce stereo di 30s: 1,653s al primo avvio, 0,227s al riavvio, zero rendering traccia/master e zero errori JS. Prova ripetibile con `scripts/validate_playback_preparation.py`.
- Catalogo opzionale MVerb, Dragonfly, CHOW Tape e Surge XT con categorie/selezione, consenso licenze, revisioni sorgenti/checksum bloccati, pubblicazione atomica e log di compilazione. Nessun binario dei plugin redistribuito nel package: build locale. Overview IT/EN e licenze incluse; verifica mensile e blocco nuove installazioni dopo 90 giorni senza revisione. Compilati e caricati realmente MVerb e i quattro Dragonfly Linux, con elaborazione stereo non silenziosa. CHOW/Surge e Windows/macOS richiedono ancora prove reali.
- Effetti interni: nome visibile **Lexicon-style reverb**, ID/preset invariati; nuovi pannelli grafici vettoriali, controlli e layout responsive. Nessun misuratore simulato.
- Contratti: modifica CPU/GPU/storage nel periodo corrente senza reset dei consumi; scelta esplicita gratuito/a pagamento. Conservati budget dei job già ammessi e storico dello storage; una modifica successiva non trasforma in pagamento le estensioni gratuite esistenti. Retry con condizioni diverse rifiutati.
- Cessazione immediata: canone proporzionale al tempo trascorso solo con servizio/billing utente abilitati; conservati accounting/extra quota. Differenze prepagate registrate come rimborsi da regolare dal gestore, senza conversione automatica in crediti.
- PayPal Sandbox/Live configurabile, Orders v2 per crediti e saldo canoni (anche dopo cessazione), segreti sigillati, verifica server di identità/importi/catture e webhook, idempotenza e storno crediti rimborsati. Pagamenti singoli: nessun addebito PayPal ricorrente automatico. Nessuna transazione reale effettuata.
- UI abbonamenti: sezioni collassabili, campi su griglia adattabile, permessi spiegati, ricerca incrementale e selezione utenti senza lista statica; eliminata l'opzione crediti disabilitata/ambigua. Asset aggiornati per invalidare le vecchie copie in cache.
- **Regressione estesa: 4.157 passati, 35 saltati, 10 esclusi per socket/agente non disponibili nell'ambiente**. Nessun fallimento. Dopo le ultime rifiniture: **40 test mirati passati**, inclusi browser desktop/mobile, PayPal, quote e playback. Ulteriori 67 passati/10 saltati per integrazione dei contratti di caricamento e script browser del server. Ruff alle stesse scope CI più nuovi helper, Bandit alle soglie CI, licenze, sintassi JS/shell e build C++ ABI 1 passati. Rapporti in `validation/r210-playback-plugins-subscriptions-*`.
- Accettazione ancora aperta: build Windows/macOS e dispositivi fisici, server reale/ROCm, plugin CHOW/Surge, PayPal Sandbox attraverso HAProxy e regolazione rimborsi monetari. Non certificato il server di produzione.
- Consegna: `MTA-0.3.0-r210-playback-vst3-paypal-subscriptions-cumulative.zip`, intero progetto. Verifiche CRC, contenuti byte per byte, file precedenti e SHA-256 eseguite durante il packaging.
- Versione **0.3.0-r210** invariata. Nessun commit/push/tag/release, pagamento o modifica ai server reali.

## Stato precedente — pubblicazione Pages (19 ottobre 2026)

- Baseline: `MTA-0.3.0-r210-docker-windows-core-build-cumulative.zip`, SHA-256 `a5983f5aeef21bc9d3d73e5bed26dc3f2d1bdd06fdfbc29566a2baed3e4e88dc`.
- Run packages `39267934184`: fermo nello step di assemblaggio, prima di configure/upload/deploy Pages.
- Run precedente `39265035765`: annullato dopo 18m50s nello stesso step; processo `gh run download` ancora attivo alla chiusura.
- Artifact sorgente `12192119228`: 5.873.100.542 byte. Il deploy scarica anche tutti gli RPM trattenuti, poi li scarta. Download privo di heartbeat e timeout; causa di rete specifica non dimostrata.
- Obiettivo: bundle Pages separato senza RPM, compatibilità manifest precedenti, avanzamento e timeout espliciti, hashing a memoria limitata. Nessuna pubblicazione remota in questo ciclo.
- Implementati bundle Pages separato e manifest con digest aggiuntivo, senza modificare quello completo per retention. Compatibilità legacy esplicita; errori sul nuovo digest/artifact non causano downgrade.
- Heartbeat ogni 30s, limite download 1.200s per canale e terminazione/attesa subprocess. Hashing incrementale; directory indipendenti per i canali. Workflow packages attivato anche per modifiche agli script, step limitato a 45m e job a 60m.
- **42 test mirati passati**, inclusi tar reale dalla shell del publisher, manifest generato dal codice effettivo del workflow, selezione nuovo/legacy, checksum errato, subprocess riuscito/fallito/bloccato e cleanup. Ruff, Bandit alle soglie CI e controllo licenze passati. L'intera suite non è stata ripetuta: nessuna modifica runtime/audio.
- Consegna: `MTA-0.3.0-r210-pages-download-cumulative.zip`; report in `validation/r210-pages-download-result.json` e JUnit adiacente. Tutti i 2.121 file della baseline conservati; CRC, confronto byte per byte e SHA-256 verificati durante packaging.
- **Accettazione remota ancora aperta**: integrare anche workflow e assembler nel repository packages, poi ripubblicare dal nuovo commit verificato dalla matrice. Non basta rilanciare il vecchio manifest: contiene ancora il bundle da 5,9 GB. Istruzioni in `docs/NATIVE_SERVER_PAGES_ARTIFACT_DEPLOY_IT.md`.
- Versione 0.3.0-r210 invariata; nessun commit/push/tag/release, annullamento job o deploy remoto effettuato.

## Stato corrente — build Docker e Windows

- Baseline: `MTA-0.3.0-r210-ci-license-signed-rpm-cumulative.zip`, SHA-256 `6f1ad7b58a8fb67f898090e76c67a8adf86f900837eab48c5744036678d63930`. Tutti i suoi 2.112 file conservati.
- Docker: il primo stage copia anche `native/third_party/miniaudio` nella directory sorella del core.
- Windows: `NOMINMAX` sul target CMake e chiamate `std::max` resistenti alle macro nel callback audio; nessun warning soppresso.
- **60 test mirati passati**: 39 build/DSP/server più 21 trasporto/cattura/gate CI. Compilazioni isolate con i soli COPY Docker, sia normale sia con macro Win32 iniettate, riuscite; ABI core/trasporto e simboli cattura verificati.
- Ruff, Bandit alle soglie CI e controllo licenze: passati. Aggiornate le note miniaudio.
- L’immagine Docker completa e MSVC reale non sono eseguibili in questo ambiente: conferma richiesta ai runner CI. Non è stata ripetuta l’intera suite in questo ciclo.
- Consegna: `MTA-0.3.0-r210-docker-windows-core-build-cumulative.zip`; rapporti in `validation/r210-container-windows-result.json` e JUnit/log adiacenti. CRC, confronto byte per byte e SHA-256 fanno parte della creazione del cumulativo.
- Versione 0.3.0-r210 invariata; nessun commit/push/tag/release o intervento sui server reali.

## Checkpoint CI precedente (15:16)

- Corrette la collocazione del plugin di prova Quality e la rimozione automatica delle dipendenze nel test RPM firmato. Nessuna modifica al runtime applicativo o ai requisiti RPM.
- **35 test mirati passati**, incluso il license guard che falliva nella CI; Ruff, Bandit e sintassi shell passati. Download reale del plugin bloccato a checksum, elaborazione audio e audit sorgenti passati con fixture esterno. Guard del test distruttivo eseguito e rifiutato correttamente fuori da CI.
- I log allegati confermano per Rocky9, Rocky10 e Alma10: compilazione/payload offline, installazione/reinstallazione e ciclo DNF riusciti. Nuova conferma del test firmato ancora richiesta sulla CI reale.
- Non è stata ripetuta l’intera suite audio in questo ciclo: nessun codice runtime è cambiato; i log Quality ricevuti riportano 4.137 passati e un solo fallimento, quello corretto. Le 4.135 prove locali del ciclo precedente restano una verifica storica, non un nuovo esito di questo ciclo.
- Baseline corrente: `MTA-0.3.0-r210-ci-quality-sast-rpm-fixes-cumulative.zip`, SHA-256 `277524484124d8c473217cb19372c813dcc8473c34a65a6866ad05e695b3566c`; tutti i suoi 2.104 file conservati.
- Consegna: `MTA-0.3.0-r210-ci-license-signed-rpm-cumulative.zip`, verifica CRC e byte per byte e SHA-256. Risultati: `validation/r210-ci-gates-result.json`.

## Checkpoint precedente

- Baseline: MTA-0.3.0-r210-vst3-server-editor-cumulative.zip, SHA-256 a40f80f9ee7e4a94975407ed20d2b31e2192b1139fc602dc5cfedf7f2727e96a.
- Ciclo precedente: 4.128 test passati, 6 saltati, 10 esclusi per l’ambiente. GUI originale VST3, mappe tempo, sidechain, MIDI e acquisizione integrati.
- Segnalazioni CI attuali: Quality non importa numpy prima del controllo ABI; dependency audit non risolve python-rtmidi senza header ALSA; EL10 non risolve il download X.Org; log Rocky9 da analizzare per errore linker.

## Macroaree

| Area | Stato | Evidenza / limite |
|---|---|---|
| Editor, progetti, mixer, motori AI, coda e accounting | Conservati dalla baseline | Nessuna modifica funzionale in questo ciclo; coperti dalla regressione automatica, accettazione reale distinta |
| Motore C++ e hosting VST3/VSTi server/nativo, MIDI e acquisizione | Integrati nel cumulativo precedente | GUI reale, sidechain e MIDI provati localmente; kernel/container e dispositivi fisici restano da validare |
| Quality e audit nativo | Correzioni implementate e prove locali passate | Ambiente pulito/ABI, Ruff, Bandit e audit strict; Python 3.14 GitHub da riconfermare |
| Packaging server RPM/DEB | Correzioni implementate | Display sorgente locale e DEB offline passati; RPM EL9/EL10 da riconfermare in CI |
| Build e installazione native multipiattaforma | Pipeline conservata | Build Windows/macOS/Linux effettive da confermare dopo lo sblocco dei gate |
| ASIO dedicato e SMF2/SMPTE | Non implementati nel ciclo precedente | Lavoro futuro distinto dal ripristino CI corrente |
| Plugin open-source opzionali | Catalogo e installazione sorgente implementati in questo ciclo | MVerb/Dragonfly Linux provati; CHOW/Surge e native da validare |
| AI Vocal Studio, AI Multi-Track Audio-to-MIDI | Backlog futuro, non avviato | Avvio solo su richiesta futura |

## Correzioni implementate

- Quality: installazione di NumPy prima dell’import/controllo ABI Pedalboard, senza upgrade delle versioni NumPy già presenti (compatibilità Intel macOS).
- SAST/audit: header ALSA/JACK provisionati nel job; audit nativo completo e strict mantenuto.
- Display RPM/DEB: tarball sorgente X.Org 21.1.24 originale incluso con licenze e checksum bloccato; nessun download durante la compilazione. Override solo da file locale e con identica verifica digest.
- Rocky9/EL10: libatomic esplicita nei prerequisiti di build e nelle dipendenze RPM; libatomic1 anche nelle dipendenze DEB.

## Verifiche concluse

- 18 test mirati passati (nuove regressioni più packaging).
- Ruff allo scope CI e sui build script modificati: passato. Bandit alle soglie CI e controllo licenze: passati.
- Ambiente Python vuoto: installazione runtime VST3 con NumPy e controllo ABI passati.
- Audit strict dei 12 pacchetti nativi risolti: nessuna vulnerabilità nota. Python 3.12 locale; job Python 3.14 da confermare su GitHub.
- python-rtmidi 1.5.8 compilato da sdist con header ALSA.
- Display ricompilato dal tarball locale: binario identico al precedente, nessun RPATH di build, avvio e frame JPEG passati in modalità test TCP autenticata.
- Nuovo DEB estratto: 293 file applicativi confrontati byte per byte; installazione pip offline, pip check e smoke ABI C++/VST3 passati.

## Esito finale del ciclo

- Regressione finale: **4.135 test passati, 6 saltati e 10 esclusi** per i limiti dell’ambiente (socket agente AF_UNIX). Nessun errore o fallimento nel JUnit; copertura complessiva 76.14%.
- I sei skip riguardano quattro prove opzionali Steinberg SDK, una GUI desktop nativa senza DISPLAY e le API Win32. I test della GUI originale server e browser sono stati eseguiti con plugin reali e display TCP autenticato di test.
- Archivio cumulativo: `MTA-0.3.0-r210-ci-quality-sast-rpm-fixes-cumulative.zip`; conservati tutti i 2.084 file della baseline, con nuovi test, sorgente X.Org e rapporti di validazione. Il processo di consegna verifica CRC, tutti i contenuti byte per byte e SHA-256.
- Risultati del ciclo: `validation/r210-ci-repair-result.json`, JUnit e report audit nello stesso percorso.
- Revisione invariata; nessun commit/push/tag/release o accesso al server di produzione.

## Pendenti / limiti

- Verifica CI GitHub su Rocky9/10 dopo il commit dell’utente.
- Accettazione sul server EL10/LXC: Landlock e plugin Linux effettivi.
- Prove con hardware audio/MIDI, driver UMP e latenza fisica.
- Selettore ASIO dedicato e SMF2/SMPTE fuori dal ciclo precedente.
- Raccolta plugin open-source, AI Vocal Studio e AI Multi-Track Audio-to-MIDI: backlog futuro, non avviato.

## Prossimi passi

L’utente applica il cumulativo e rilancia CI e packaging. Confermare prima Quality/SAST su Python 3.14 e i tre target RPM Rocky9/Rocky10/Alma10; poi build native. Dopo CI verde procedere all’accettazione EL10/LXC e dispositivi fisici. Nessuna certificazione del server è dedotta dalla sola regressione locale.


## Ciclo successivo — CI del 19 ottobre, ore 15:16 Europe/Rome

Nuovi log ricevuti: Quality fallisce solo nel license guard perché il plugin di test CHOW è scaricato nel checkout; le tre build RPM ora compilano, installano e aggiornano, ma il test del repository firmato non risolve alcune dipendenze X11 dopo la rimozione dell’applicazione. Cause confermate nei log:

- Quality: 4.137 passati, 13 saltati, un solo fallimento, `test_source_license_gate`, dovuto al plugin di prova dentro `.external` del checkout. SAST non riporta nuovi errori.
- Tutti e tre gli RPM: compilazione, installazione/reinstallazione e version cycle superati; il test firmato rimuove `xkbcomp` (anche `libXtst`/`xkeyboard-config` su EL9) tramite l’autoremove implicito, poi disabilita i repository che potrebbero reinstallarli.

Correzioni implementate: fixture Quality spostato sotto `RUNNER_TEMP`, con percorso di test corrispondente; disattivazione del solo cleanup automatico nella rimozione preparatoria del test firmato. Controllo licenze, dipendenze RPM, firme e isolamento del repository rimangono attivi. Verifiche mirate concluse: 35 passati; r210 invariata. Nessun commit/push/tag/release o intervento sui server reali. Baseline: MTA-0.3.0-r210-ci-quality-sast-rpm-fixes-cumulative.zip (SHA-256 277524484124d8c473217cb19372c813dcc8473c34a65a6866ad05e695b3566c).


## Prossima verifica richiesta

Dopo l’applicazione e il commit dell’utente: rilanciare Quality e i tre job RPM. Verificare la conclusione del test repository firmato mantenendo attivi `gpgcheck=1`, `repo_gpgcheck=1` e il test dei metadata alterati. Il controllo licenze deve continuare a rifiutare plugin nel checkout, anche sotto `.external`.


## Ciclo Docker — 19 ottobre 2026 ore 15:55 Europe/Rome

Baseline: `MTA-0.3.0-r210-ci-license-signed-rpm-cumulative.zip`, SHA-256 `6f1ad7b58a8fb67f898090e76c67a8adf86f900837eab48c5744036678d63930`. Log allegato: fallisce lo stage `audio-core-build`, `device_transport.cpp` non trova `../third_party/miniaudio/miniaudio.h`. Il Dockerfile copia solo `native/audio_core` e omette il fratello `native/third_party/miniaudio`. Corretto il COPY Docker; entrambe le compilazioni su contesto isolato, normale e con macro Win32 iniettate, sono passate. Revisione invariata.


Aggiornamento nello stesso ciclo: ricevuto anche il fallimento MSVC C2589 sulle chiamate `std::max` del callback. Causa: macro Win32 `max` introdotta attraverso miniaudio. Applicati `NOMINMAX` al target Windows e chiamate resistenti alle macro. 60 test passati (39 build/DSP/server, 21 trasporto/cattura/gate CI). MSVC reale non disponibile localmente. I warning C4324/C4244/C4456/C4245 e la nota `CMAKE_BUILD_TYPE` non sono l’errore fatale segnalato e non vengono soppressi.

## Ciclo sostituzione Madmom per gli accordi — 20 ottobre 2026

**Versione 0.3.0-r210 invariata. Nessun commit, push, tag o release.** Intervento sul cumulativo con checkpoint hardening; nessun codice o asset preesistente eliminato.

- **Implementato:** profili Stable/Accurate/Maximum ora selezionano BTC-HCQT (quando disponibile e ammesso dalla license policy), Chordino e MTA-Chromagram, anziché selezionare Madmom NC o ChordFormer con checkpoint non autorizzati. L'esecuzione Madmom esplicita resta legacy e soggetta a blocco licenze. La selezione del profilo controlla l'ammissione di ciascun candidato.
- **Implementato:** vocabolario armonico automatico ampliato a add9, 9, maj9, m9, mMaj7, dim7, m7b5, 7sus4, 7b5, 7#5, 7b9, 7#9 (oltre a triadi, sus2/4, 7e e seste). Mantenuto il criterio di penalità sulle qualità complesse; la pipeline Balanced/Detailed non distrugge più estensioni riconosciute; il preset Stable offre ancora semplificazione Songbook su richiesta. Analisi del basso e slash chords conservata.
- **Verificato:** 19 test chord/profiles/regressioni mirate superati, inclusi nuovi test sul mantenimento delle alterazioni. Prova estesa su test r209/r210: 59 passati, poi un test nativo Windows/Uvicorn preesistente fallito per attributo `_mta_startup_exception` assente, non modificato in questo ciclo. Non si dichiara verde la regressione integrale.
- **Non verificato:** miglioramento di accuratezza musicale su benchmark annotati, supporto effettivo di BTC-HCQT su CPU/ROCm di produzione, pipeline end-to-end web/native/API con abbonamenti e quote reali, generazione corretta di tutte le estensioni su audio polifonico. Le nuove etichette sono candidate, non garanzia di riconoscimento accurato.
- **Bloccati:** Madmom weights CC BY-NC-SA; ChordFormer checkpoint non autorizzati; UVR e DrumSep pesi con provenienza/diritti non conclusi. Non sono stati riabilitati per il solo fatto di essere gratuiti. Questi ultimi non sono alternative a Madmom per l'estrazione chords e richiedono verifiche separate sui pesi esatti.

## Ciclo MVSep Mega 53 Lead/Backing — 20 ottobre 2026

- **Implementato:** registrato `mvsep-mega53` nel catalogo Lead/Backing; adattatore `app/mega53_runtime.py` per `inference.py` upstream con checkpoint/config esterni, output canonical lead/backing, propagazione errori, cancellazione e nessun fallback silenzioso. Instradamento server/local AI e policy `mvsep-mega53` distinta da checkpoint UVR. Default del selettore impostato a Mega 53, ma policy licenza inizialmente `disabled` (fail closed). Legacy UVR mantenuto.
- **Testato:** test di contratto con stub sintetico, non inferenza musicale reale. Consultare gli esiti di test del package.
- **Bloccato/da verificare:** licenza e fingerprint del checkpoint effettivamente scelto; compatibilità versione MSST/config; prestazioni ROCm/CPU, latenza, VRAM, output reali; benchmark audio comparativo UVR/Mega 53; contabilità web/native/API end-to-end. Nessun download dei pesi o comparazione audio reale eseguiti.
- **Versione:** 0.3.0-r210 invariata; nessun commit/push/tag/release.

## Ciclo UVR KARA 2 checkpoint auto-repair — 20 ottobre 2026

- **Implementato:** all'avvio server/native, thread non bloccante verifica checkpoint `UVR_MDXNET_KARA_2.onnx` solamente dopo admission via `evaluate_model('uvr-kara-2')`. Se mancante o non conforme, il downloader esistente scarica nuovamente in directory temporanea sullo stesso filesystem; SHA-256 pinned obbligatorio prima della sostituzione atomica. Symlink non ammessi, modello errato mai sostituito con download non verificato. `MTA_UVR_KARA2_AUTO_REPAIR=0` disattiva la riparazione. Non viene modificata la licenza/consent dell'operatore.
- **Testato:** 18 test mirati (repair atomico, no download su file valido, download invalido, symlink, licenze/catalogo e funzionalità preesistenti) superati.
- **Non verificato:** download reale dal provider, rete runtime server/native, test integrazione ROCm, inferenza e regressione integrale. In ambiente produzione, le policy licenze devono essere correttamente configurate prima del riavvio.
- **Vincolo legale irrisolto:** UVR upstream richiede crediti MIT per i modelli ma manca conferma specifica titolarità/autorizzazione pesi KARA 2. Uso gratuito senza licenza non è automaticamente autorizzato. Model admission resta bloccata in mancanza di titolo applicabile.

## 2026-10-20 — Curated AI model rights dossiers (0.3.0-r210)
- Implemented: `app/model_rights_dossiers.py` provides curated public reference URLs, scope notes and distinct authorization statuses for UVR KARA 2, DrumSep, ChordFormer, Madmom, SAM Audio and selected DiffSinger banks. The license catalog API exposes `rights_dossier`; the Studio administration UI displays the references without silently filling or accepting an operator's legal attestations.
- Tested: six targeted rights-policy and dossier tests passed; JavaScript syntax check passed. No regression of model admission: uncertain checkpoint permissions remain denied by default. Existing SAM Audio admission remains available under its published SAM License.
- Blocked: commercial reactivation of original Madmom NC weights, exact ChordFormer five weights, and uncertain DrumSep weights absent affirmative permission. All models still require actual checkpoint installation and runtime validation. Dossier data does not constitute a license. Global subscription/API isolation has not been production-certified.
- Next: collect exact checkpoint hashes and original author grants where missing; verify each voicebank independently, run end-to-end billing/auth tests on web/native/token and perform GPU real-audio benchmarks.

### 2026-10-20 — DrumSep rights deep review and authenticated remote model routing (r210)
- Implemented: remote drumsep selection admits `mvsep-mega53` under its own approved license policy, `dsp` under MTA analysis, SAM variants under SAM license; original DrumSep ONNX remains explicitly blocked by default. AI adapter supports Mega 53 per-drum outputs and strict target validation, without bypassing global job authentication or metering.
- Documentary review: `inagoy/drumsep` MIT is verified for repository code; `splitzo/drumsep` asserts MIT for ONNX but cannot establish that upstream weights were granted under MIT. Distinct aufr33/jarredou MDX23C 5/6-stem checkpoints lack formal published weights license (openmirlab/mdxnet-infer). Neither is automatically enabled for commercial service. Original models retained as disabled legacy.
- Tests: targeted routing and Mega 53 adapter: 4 passed; broader DrumSep/license suite: 13 passed, 2 older direct-helper tests fail because production now correctly requires authenticated global AI jobs (do not bypass security; adapt harness with authorized jobs).
- Still blocked: any original weights without evidenced grant; real Mega 53 checkpoint inference, multi-song quality benchmarks, AMD ROCm measurements and full regression.


### 2026-10-20 — DrumSep original-weight rights deep verification
- **Completed:** checked original MIT software LICENSE, license request issues #8/#9, Splitzo ONNX card, OpenMIRLab SHA-verified MDX23C mirror and rights assessment; expanded the curated admin/API dossier.
- **Not unlocked:** neither inagoy Hybrid Demucs original weights nor aufr33/jarredou MDX23C weights have a demonstrated, applicable original author grant.
- **Preserved:** Mega 53 AI drum-part routing, DSP and SAM functional fallbacks and existing authorization enforcement.
- **Next:** obtain an original author grant or validate a separately licensed replacement checkpoint; real ROCm and quality benchmark outstanding.

### 2026-10-20 — Drums vs percussion: licensed AI grouping (r210 unchanged)
- **Implemented:** MVSep Mega 53 native `drums` + `percussion` classes are now extracted from the original mix when "all", "drums_without_percussions" or "percussions" is selected in the percussion workflow. Two distinctly named stems are returned; individual kick/snare/toms mode is retained. The remote worker also supports explicit `targets=["drums", "percussion"]` with fail-closed target checks. DSP remains selectable, with lower and different musical specificity.
- **Tested:** focused Python unit tests for both outputs, rejected missing output, existing Mega 53 part adapter and remote routing; see test results for this cycle.
- **Unverified:** real 53-stem checkpoint installation/inference, quality of drum-vs-non-kit separation, endpoint tests on native/web, ROCm benchmarks, and full regression. Mega 53 classes may overlap; no source reconstruction guarantee.
- **Blocked:** original inagoy/MDX23C DrumSep weights remain restricted due to unresolved upstream authorization. Intel OpenVINO derivative tagged CC BY-NC-SA 4.0 remains a *candidate*, NOT a verified original grant and not enabled for commercial or local inference.

### 2026-10-20 — Neural Vocal Studio external execution contract (0.3.0-r210)
- IMPLEMENTED: optional `neural-external` Studio backend, operator-owned executable/checkpoint, pinned SHA-256, rights policy admission, note/lyric input JSON, isolated per-singer WAV outputs, finite PCM checks, bounded execution and original OddVoices compatibility.
- TESTED: 23 focused tests passed, one skipped (installed CC0 bank required). Python compilation and UI JavaScript syntax checked.
- BLOCKED: no licensed neural singer runtime/voicebank installed or actually executed; no phonemizer training/validation, ROCm performance, neural quality evaluation or complete production E2E. This is **not** completion of professional neural singing.
- NEXT: integrate a verified licensed DiffSinger/other model-specific inference runtime, operator receipts per voicebank and multilingual phonemization, test real inference and edit/re-render persistence with hardware.

### 2026-10-20 — DiffSinger CLI integration (0.3.0-r210)
- Implemented: selectable `diffsinger` backend; OpenVPI `.ds` generation from per-singer monophonic MIDI with rest handling; direct acoustic CLI invocation, waveform validation and 48-kHz conversion; pinned acoustic/runtime/vocoder checks; independent license identity, fail-closed behavior.
- Tested: unit tests for score-to-DS mapping, invalid inputs and checkpoint hash; legacy vocal tests. See `tests/test_r210_diffsinger_bridge.py`.
- **NOT completed:** real neural inference with installed licensed acoustic checkpoint and vocoder; multilingual phonemization; native and AMD ROCm E2E; voice conversion; perceptual benchmark. DiffSinger is not yet certified production-ready.
- Blockers: licensed acoustic voicebanks and vocoder installation, real audio/GPU test assets.
- Next: perform controlled inference and validate license compliance per singer/vocoder; expand phonemization and expressive parameters.

### 2026-10-20 — DiffSinger runtime safety hardening (0.3.0-r210)
- **Implemented:** verified pinned acoustic checkpoint belongs to selected experiment (`checkpoints/<experiment>/`), rejected unsupported score lengths and outputs with unreasonable durations/sample rates before import; preserves previous CLI, models, native and billing paths.
- **Tested:** 23 focused Python tests passed, one skipped (missing installed voicebank); two new runtime/validation regression tests passed. ZIP content and SHA-256 checked at packaging.
- **Still blocked:** actual OpenVPI acoustic inference using an authorized checkpoint and correctly configured vocoder; phoneme dictionaries verified for EN/IT/FR; real ROCm and client end-to-end tests; voice conversion. Do not call the DiffSinger macroarea completed based on contract tests alone.

## DiffSinger deployment preflight — 20 October 2026 (latest cycle)

Version **0.3.0-r210** unchanged; no Git operations.

- **Implemented:** read-only `scripts/check_diffsinger_ready.py` for operator-side inventory and safe SHA-256 verification of DiffSinger executable, acoustic checkpoint, vocoder, installed experiment and policy admission; JSON result with explicit `real_audio_validated=false`. No license overrides, checkpoint downloads or billing exceptions.
- **Tested:** new empty-config, missing-license-identity and tampered-vocoder rejection tests, together with prior bridge/adapter tests: **12 passed**. No real neural model weights were present for inferencing in this cycle.
- **Blocked:** real DiffSinger acoustic/vocoder execution and listening assessment, language-aware bank phonemization for IT/FR, expressive editing/conversion, ROCm and full native/web acceptance. A green preflight is not a completed Vocal Studio certification.
- **Operator action:** install and attest licensed acoustic model/voicebank/vocoder and run `python scripts/check_diffsinger_ready.py --json` on the staging host; run actual sample inference and share non-sensitive diagnostic report for final integration review. Full instructions: `docs/DIFFSINGER_DEPLOYMENT_HANDOFF_R210_IT_EN.md`.

## Checkpoint r210 — Audio-to-MIDI cross-model ambiguity and support audit (2026-10-20)

- **Implemented:** reconciler now refuses an arbitrary assignment when two or more distinct primary events (even on the *same* instrument track) are within timing tolerance for one secondary note; retains that note as an editable, unreviewed alternative.
- **Implemented:** primary-only audit of observed support per note from independent secondary models (`primary_audit`: source note count, supported/unsupported count, and number of independent supporting models). This is *not* an accuracy score, confidence calibration, or verification that an instrument was truly present.
- **Tested:** `pytest -q tests/test_r210_music_reconciliation.py tests/test_r210_yourmt3_checkpoint.py tests/test_r210_midi.py tests/test_r210_vocal_synthesis.py` → **24 passed, 6 skipped**. Skips require independent YourMT3 weights/runtime, PyAV, VSTi or native OddVoices assets. Test selection is not a whole-project regression.
- **Blocked:** 10–16 independent instruments accurately recovered from a full stereo music mixture; real full-mix benchmarking and external runtime weights; independent same-GM performers, instrument-classification ground truth, AMD ROCm and native E2E import. Existing model can emit separate GM program parts but no proven 10–16-part accuracy. **Do not mark the macroarea closed.**
- **Next:** independently authorized YourMT3/MT3 ensemble with reproducible ground-truth fixtures, quality/accuracy benchmarks, edit-and-reopen E2E, and manual hardware acceptance.

## 2026-10-20 — Three-area joint cycle: benchmark and GM stability

- **Implemented / tested:** replaced recursive bipartite audio-to-MIDI score matching with iterative augmenting paths to avoid recursion exhaustion on large note sets; per-instrument precision, recall and F1 are now emitted; per-instrument benchmark cap 20,000 events. GM event scheduling rejects sample rates outside 8,000–192,000 Hz; regression coverage added.
- **Verified:** `pytest -q tests/test_r210_midi_quality_benchmark.py tests/test_r210_gm_event_validation.py tests/test_r210_vocal_synthesis.py tests/test_r210_music_reconciliation.py tests/test_r210_gm_audit.py tests/test_r210_gm_instrument.py tests/test_r210_vocal_multisinger_lyrics.py tests/test_r210_diffsinger_bridge.py tests/test_r210_yourmt3_checkpoint.py` — **75 passed, 4 skipped** (missing CC0 voicebank/native core, FluidR3 GM assets, authorized YourMT3 runtime). No real neural/vocoder or large ensemble benchmark executed.
- **Still incomplete (software, not merely operator acceptance):** DiffSinger IT/EN/FR phonemization and validated neural voice conversion and expression features; validated independent 10–16 instrument transcription in mixed stereo with suitable model(s); complete cross-client GM file playback acceptance. Backend integration and static audit are not proof of quality or closure. User should deploy and test only after licensed assets are installed.
- **Version:** 0.3.0-r210 unchanged. No Git commit, push, tag or release.

## r210 — Standard MIDI File to General MIDI WAV acceptance path (2026-10-20)

- **Implemented and automatically tested:** `scripts/render_gm_midi.py` converts type-0/type-1 SMF MIDI into a stereo PCM_24 WAV using the project's existing FluidSynth/TinySoundFont GM engine. Tempo changes, channel program changes, percussion, event scheduling and bounded-memory block rendering are supported; unsupported SysEx and asynchronous type-2 SMF fail closed. MIDI running status is handled by the pinned `mido` parser. This tool needs the optional `mido` and `soundfile` packages and authorized FluidR3 bank at runtime.
- **Tested:** four new tests (tempo changes, event ordering, type-2 rejection and full MIDI-to-WAV export with a mock synth), and targeted regressions across Vocal Studio/GM/MIDI: 59 passed, seven skipped due to external runtimes/assets. Syntax compilation and cumulative ZIP integrity were checked.
- **Blocked on operator's environment:** actual full-GM bank, auditory acceptance and real render of a MIDI file on target hardware; DiffSinger acoustic+vocoder inference and multilingual voicebank pronunciation; end-to-end 10–16 instrument transcription accuracy evaluation.
- **Remaining software development:** Vocal Studio multilingual phonemization, expressive control and timbre conversion; the specialist multi-instrument Audio-to-MIDI ensemble and independent same-instrument parts; potentially issues exposed by real-model validation. **None of these three macroareas is declared complete.**

## 2026-10-20 — Audio-to-MIDI indexed matching cycle (0.3.0-r210 unchanged)

- **Implemented:** instrument/pitch-indexed and onset-windowed note-candidate construction in `app/studio_midi_benchmark.py`, preserving exact one-to-one augmenting-path matching and tie-breaking. This reduces needless cross-note scans on long multitrack scores; maximum cardinality logic remains unchanged.
- **Implemented:** explicit rejection of NaN and infinite benchmark tolerance inputs.
- **Tested:** 100 seeded randomized polyphonic comparisons against exhaustive candidate construction, 5,000-note benchmark stress fixture, invalid numeric tolerance cases, original MIDI quality tests, GM file rendering and event validation, DiffSinger lexicon/bridge/readiness, and vocal synthesis regression. **61 passed, 1 skipped** (compiled voicebank not installed). Python compileall passed.
- **Blocked by real assets/hardware:** DiffSinger neural model/voicebank/vocoder inference, 10–16 independent instrument transcription quality on real stereo mixes, actual FluidR3 full-GM audition and native/ROCm integration.
- **Not yet completed in software:** general automatic phonemization IT/EN/FR, advanced neural expressivity and timbre conversion, specialist 10–16-player disambiguation and validated ensemble model integration. GM MIDI-to-WAV offline renderer implemented but full end-to-end UI validation remains open.
- **Next actions:** prioritize substantive missing components and, when a legal checkpoint and reference data are available, collect the final real-world quality and runtime evidence. Do not mark any of the three macroareas as complete solely from this cycle.

## 2026-10-21 — Finalization readiness audit (r210; no deployment)

- **Implemented:** hardened offline Audio-to-MIDI benchmark input opening against file-swap/symlink redirection, FIFO hangs, directory inputs and oversized regular files. Uses inode-level file metadata and bounded reads; two regressions added. Preserves model/asset rights admission and all legacy AI/VST functionality.
- **Verified locally:** targeted suites batch A **74 passed, 2 skipped**; batch B **47 passed, 7 skipped**; **121 passed, 0 failed, 9 skipped** combined, no overlapping tests in these batches. ZIP source-preservation and SHA-256 verified independently during packaging. No inference or server access.
- **Not completed or certified:** project-wide regression (prior blocked indirect GitHub egress was not bypassed); actual licensed DiffSinger acoustic/vocoder/voicebank and RVC/Seed-VC runtime inference; real YourMT3/Transkun multitrack accuracy on representative 10–16-instrument stereo recordings; genuine FluidSynth/TinySoundFont GM acceptance on host/native/browser. Missing third-party runtimes and license receipts are not automatically solvable by code-only tests.
- **Handoff:** not yet a defensible statement that only operator QA remains; software integration changes may be required based on runtime evidence. Operator staging tasks: supply authorized checksum-pinned assets, review licenses individually, run real inference and GM audio tests, and provide sanitized reports. Do not activate restricted weights or bypass policy checks. Version remains 0.3.0-r210; no commit/push/tag/release performed.


## 2026-10-21 — Accelerated finalization pass (r210, offline)

- Implemented: benchmark input consistency guard rejects partial or concurrent file changes by comparing bytes read and inode size/mtime/ctime before and after reading; regression test added. This is a software reliability correction, **not** a neural inference or quality benchmark.
- Verified: selected nine cross-area regression modules: **96 passed, 0 failed, 5 skipped**. Skips: 3 missing `espeakng_loader`; 2 reviewed GM/runtime assets or compiled core. No external network was required by this selection. Full repository regression remains uncompleted; previously blocked GitHub egress was not bypassed.
- Status: AI Vocal Studio, AI Multi-Track Audio-to-MIDI and GM are **not yet fully certified / closed**. Actual licensed model inference, representative multitrack ground-truth evaluation, real GM playback and UI/native acceptance require operator-provided authorized environments; resulting software bugs may still require engineering. No deployment or Git operations.

## 2026-10-21 — Single-cycle three-area development review (r210)

- **Software fixed:** isolated GM/MIDI worker (`app/midi_render.py`) now stages WAV output in the destination directory, atomically publishes on success, and removes staged files after failure. Previous renders remain intact if playback processing fails. Two new tests cover successful PCM export and a mid-render fault.
- **Cross-area offline verification:** 112 passed, 0 failed, 7 skipped across thirteen focused modules covering multilingual DiffSinger contracts, managed assets, multitrack reconstruction, checkpoint recovery, score benchmarking, GM MIDI rendering and worker atomicity. Skips: approved GM/compiled core assets (2), PyAV (2), optional VSTi (2), real YourMT3 model (1). No unapproved network activity or fake neural inference. This is **not** the full repository regression.
- **Software not fully certified:** DiffSinger/RVC/Seed-VC/Transkun genuine licensed inference, 10–16 instrument quality/independent performer separation, browser/native GM playback, and complete safe project-wide regression remain unverified. No claim of full macroarea completion or operator-only handoff.
- Version **0.3.0-r210** unchanged; no Git operations or production changes.

## 2026-10-21 — Ten internal engineering and verification passes (r210)

Ten sequential passes: (1) incoming ZIP checksum/CRC; (2) extraction and status inventory; (3) code review of vocal/GM/MIDI; (4) vocal PCM boundary fix; (5) GM worker duration and output block validation; (6) new regression cases; (7) repair of validation ordering revealed by tests; (8) 64-test focused regression; (9) expanded offline cross-area regression; (10) cumulative source preservation and packaging.

- **Implemented:** converted vocal audio cannot exceed normalized PCM +/-1.0; isolated MIDI/GM worker rejects nonfinite, nonpositive or nonnumeric duration *before initializing native instruments*; rejects non-finite and malformed PCM blocks, keeping the prior WAV intact. Added boundary and failure regression cases.
- **Verified:** focused subset **64 passed, 0 failed, 0 skipped**; larger cross-area run **214 passed, 0 failed, 14 skipped** (the focused tests are included in the larger selection; do not add totals). Fourteen skips require `espeakng_loader`, reviewed GM assets/compiled core, approved voicebank and Happy DOM. No real neural inference or external network calls were made.
- **Not complete/certified:** general repository regression, authorized real DiffSinger/Seed-VC/RVC/Transkun inference, genuine 10–16 stem/performer accuracy benchmarks, GM listening and native/browser acceptance. These gates may reveal software fixes, so do not claim that only user testing remains.
- **Release:** r210 unchanged; no Git, server deployment, release or tag.
