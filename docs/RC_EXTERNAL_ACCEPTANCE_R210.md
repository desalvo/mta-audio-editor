## Checkpoint corrente — riscossione legacy e prove originali — 30 ottobre 2026

**RC69,0% (29/42),invariata:nessun criterio promosso;l'aumento richiesto non è ottenuto.** Leggere **LEGACY_SUBSCRIPTION_COLLECTION_R210.md** e `validation/r210/legacy-collection-result.json`. Rimborsi senza base originale registrati senza debiti ipotetici;riscossioni legacy preesistenti non verificate sospese prima del provider e dell'allocazione;account IT/EN e aggregati mostrano importi da verificare,revisione privata per proprietario. **779 casi distinti correnti passati,24 nuovi,10 skip Playwright;nessun nuovo collaudo Chromium/provider reale.** Ruff/sintassi/compilazione e quattro gate passano,senza nuovi finding o checker modificati.

A5/C3 restano aperti per prove originali quota/surplus mancanti e migrazione completa non certificata;A4 mantiene anche software/storia/movimenti da completare.Coda operativa in RC_DELIVERY_PLAN_R210.md,senza ripetere i blocchi già verificati. Cumulativo completo:**MTA-0.3.0-r210-pre-RC-legacy-collection-cumulative.zip**,include ACE e la riorganizzazione;non riapplicare il vecchio patch. Tutti i delta da4014a1f restano non committati. Nessuna azione remota.

---

Cronologia precedente,superata dove incompatibile:

## Stato corrente e nuovo ordine RC — 30 ottobre 2026

**69,0% verso RC: 29/42 criteri originali verificati, 13 aperti, E completa (1/7). Nessuna promozione in questa riorganizzazione.** Leggere **RC_DELIVERY_PLAN_R210.md** e `RC_EXECUTION_STRATEGY_R210.json`: primo blocco A4/A5/C3, poi C5/D6; F4/F6 come coda indipendente, campagna target con prerequisiti espliciti. Un solo blocco funzionale; passare a un altro scenario quando manca una prova/ambiente preciso. Ogni resoconto deve riportare percentuale e verificati/42.

Ultimo codice completo: **MTA-0.3.0-r210-pre-RC-ace-observer-isolation-cumulative.zip**; delta documentale successivo, senza nuovo ZIP intermedio. Nessun codice/test/gate/criterio modificato o nuovo collaudo applicativo dichiarato. Tutti i delta da4014a1f restano non committati; nessuna azione remota. Prova del riordino: `validation/r210/rc-reorganization-result.json`. Le priorità e i numeri storici sotto sono superati dove incompatibili.

---

## Checkpoint corrente — B2 verificato con recupero indipendente — 30 ottobre 2026

Leggere **INDEPENDENT_WORKER_RECOVERY_R210.md** e `validation/r210/independent-guardian-result.json`. **29/42 criteri originali verificati (69,0%), da28/42(66,7%);+B2,nessun testo/peso/denominatore modificato.E completa,PRE-RC.** Processo Linux indipendente per albero,subreaper/pidfd e prova kernel ECHILD;scope/claim originali prima del modello,cleanup dopo SIGKILL,CPU reale dell'albero e API amministrative di perdita senza misura inventata o riesecuzione.

**628 casi distinti correnti passati,16nuovi,zero failure/error/skip correnti.** Include serverHTTP reale/token/SIGKILL/recupero originale in entrambi i regimi,vero FFmpeg e figli/nipoti setsid,drain durante cleanup,guardian perso con claim trattenuto e rifiuto di usare il solo client ACE per liberare il servizio esterno.Guardian/quiescenza non effettuano addebiti automatici;esterno ignoto resta sospeso.Cgroup configurati conservano il percorso precedente;nessun requisito di privilegi/cgroup simulato.

Ruff completo e gate passano:307sorgenti app/168finding(0HIGH/21MED/147LOW),C2173,runtime554/780,HTTP30/21.Checker/soglie/soppressioni invariati;5 nuovi LOW revisionati.Nessuna nuova inferenza neurale,fullCI,prova OS/hardware/host remoti.Le prove sorgente-identiche precedenti restano conservate.

Restano **A4,A5,A6,B6,C3,C5,C6,D6,F4,F5,F6,G5,G6**:8 implementazione/review e5 target.B2non richiede di ripetere un'altra campagna preparatoria;proseguire F4 su interpreti/runtime/checkpoint e finanza generale/legacy per C3/C5/D6.B6/F5/F6/G5/G6 mantengono i requisiti originali.Transizione finanziaria globale e RC restano bloccate.

Baseline dichiarata4014a1f;delta restored-rights+adapter-identity+guardian non committato.Cumulativo:**MTA-0.3.0-r210-pre-RC-independent-guardian-cumulative.zip**;conservati4939percorsi/694log input.Nessun commit/staging/push/dispatchCI o intervento reale server/provider/modelli.Commit suggerito cumulativo:`Enforce model rights and recover crashed workers with independent Linux guardians`.Dopo il commit dell'utente verificare Quality/SAST standard;le16 nuove prove sono nella selezione unit ordinaria,senza nuovi opt-in.

---

## Cronologia precedente — superata dove incompatibile con il checkpoint corrente

# Coordinated external RC acceptance — 2026-10-26

Status: PRE-RC,23/42 original criteria,54.8%,0/7 whole macroareas. No commands below were executed on providers/real servers/target hardware. This is a coordinated evidence request/runbook,not proof or authorization to publish. The user retains commit/deployment control. Work through one source checkpoint and retain exact SHA,configuration,versions,command,exit status,XML/logs and unmet prerequisites. Never turn skips/build success into target acceptance.

## Code prerequisites first

F3 is still incomplete:MODEL_ATTESTATION_PILOT_R210.md now implements the opt-in Basic Pitch trusted-node authenticated loaded receipt exchange;remaining engines/transports still need code and actual-model acceptance. The new parent/child policy envelope is a supported-adapter consistency check,not a remote credential/loaded attestation. Other opaque/runtime adapter load coverage and complete all-executor ownership remain unfinished. Financial conservation and integrated two-way cutover are still pending. Do not blame these implementation gaps on absent sandbox credentials or enable cutover to obtain test evidence.

## One evidence campaign

| Original criterion | Required isolated target and evidence | Existing entrypoint and exact boundary |
| --- | --- | --- |
| A6 | Separate Stripe test and PayPal sandbox data copies with canonical checkout/subscription/capture/refund/dispute/payout lifecycles;no production credentials | tests/test_r210_real_provider_sandbox.py performs two readback/reconciliation checks only. Passing them is partial;historical completeness/multicapture/payout/protection acceptance still requires the complete canonical case set |
| B2/B6 | Delegated private Linux cgroup subtree plus independent authority/worker hosts,controlled supervisor loss/partition/drain | tests/test_r210_real_cgroup_supervisor_loss.py uses MTA_TEST_CGROUP_PARENT and creates its own subtree. Existing same-host HTTPS/SIGKILL fixtures are reused,not relabelled as independent-host acceptance |
| F5 | Installed supported native applications on every supported OS,with real local/remote admission,NC behavior and failure cases | Existing native executable/installer and application regression procedures;record installed artifact hash/OS. A cross-compilation/build does not pass this criterion |
| G5 | Actual isolated Docker,Podman,Kubernetes deployments with persistent data,restart/recovery,ingress and worker boundaries | Existing deployment recipes and runtime validation;record runtime/cluster/manifest/image digests and functional outcomes. Green Docker build is retained partial evidence only |
| G6/F6 | Reviewed actual optional checkpoints/voicebanks and installed OS/GPU/audio/VST targets | Existing real-backend tests and scripts/verify_music_hardware.py. Probe output alone is inventory;actual model/plugin/audio cases plus independent checkpoint rights are required |

For real provider readback,prepare an isolated COPY of sandbox auth.sqlite3 with the corresponding auth secret. Set MTA_SANDBOX_DATA_DIR to that copy,MTA_TEST_STRIPE_SANDBOX_ORDER and MTA_TEST_PAYPAL_SANDBOX_ORDER to its seeded orders,and MTA_TEST_PROVIDER_SANDBOX=1;unset MTA_TEST_OFFLINE. Run `python -m pytest -q tests/test_r210_real_provider_sandbox.py --junitxml=provider-sandbox.xml` from that checkout. These tests assert Stripe test credentials/PayPal sandbox and do not create/capture/refund. Do not use a live server data directory. This pair does not close A6 by itself.

For delegated-kernel recovery,use a disposable delegated cgroup parent,export MTA_TEST_CGROUP_PARENT to its absolute path and run `python -m pytest -q tests/test_r210_real_cgroup_supervisor_loss.py --junitxml=kernel-loss.xml`. The test intentionally starts/kills its own supervisor/worker tree and creates/removes a private subtree. Missing delegation is an unmet prerequisite,not acceptance.

For the changed Transkun loader,run `python -m pytest -q tests/test_r210_checkpoint_weights_security.py --junitxml=checkpoint-security.xml` with the reviewed engine interpreter containing Torch and test dependencies. It tests actual weights-only deserialization/rejection of executable pickle using synthetic tensors;passing it does not certify Transkun inference/accuracy or checkpoint rights. Here it remained skipped because Torch is absent. Do not install arbitrary weights to clear a skip.

A read-only device inventory can be recorded with `python scripts/verify_music_hardware.py --output hardware.json`. Its --exercise-audio/--exercise-rocm options perform real target work and belong in the isolated operator campaign with selected device configuration;inventory alone is not a functional pass. Retain original failed outcomes and subsequent correction proofs.

## Handoff/decision

Collect results once for the same candidate revision;list every failed/skipped/missing test and the exact criterion it affects. Do not rerun source-identical successful evidence merely for this inventory. First complete code integration,then ask the user for one coordinated target campaign and one full CI on the committed candidate. No automatic workflow dispatch/server/provider mutation or publication. RC is declared only when all42 original criteria and target proofs pass;no reweighting/removal of blockers.

## Additional prepared model pilot target

See MODEL_ATTESTATION_PILOT_R210.md for the exact isolated MTA_STUDIO_PYTHON procedure and tests/test_r210_pull_model_attestation_real.py. It uses an existing reviewed Basic Pitch interpreter and pinned weights,no download. This run skipped it;do not convert that missing prerequisite into acceptance. Other engine/transport implementation remains separate.
