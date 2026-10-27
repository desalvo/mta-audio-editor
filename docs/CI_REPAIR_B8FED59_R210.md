# MTA r210 — riparazione CI sul commit b8fed59 — 2026-10-27

Baseline confermata: `b8fed59b6caaf4b9a0a719e12257628ceb717751`.
Run: https://github.com/desalvo/mta-audio-editor/actions/runs/40432353021

## Cause e correzioni

- Quality, job121952833392:6390passati,1fallito,46prerequisiti mancanti;coverage76.01% sopra il gate70%;742.52s. Unico errore: `test_unified_cli_main` lanciava il worker senza `MTA_AI_ADMITTED_POLICY`, ora obbligatoria. Il test usa una decisione reale da `model_license_policy.evaluate` e `admitted_env`,con data root isolata. Non simula né disabilita `verify_plan`. Due casi aggiunti verificano che policy assente o per modello diverso impediscano l'inferenza. Nessuna modifica al codice applicativo.
- SAST, job121952833172: Gitleaks8.24.3 segnala quattro righe JSON con tre SHA256 di sorgenti pubblici: auth prima/dopo hotfix e test export. I digest sono verificati sui file effettivi. `.gitleaks.toml` aggiunge esclusivamente i tre valori completi con ancoraggi; nessuna esclusione di percorsi,regole,intere categorie di hash o commit. Conservati default Gitleaks e44 fingerprint storici. La configurazione corrente si applica anche alla scansione del commit già pubblicato,senza riscrivere la storia.

## Validazione e limiti

42 test mirati passano in6.39s,inclusi2nuovi controlli negativi. Ruff e compilazione del test passano. Report: `validation/r210/ci-b8fed59-policy-regression.xml`.
Lo scanner reale8.24.3 riproduce4rilevamenti con la vecchia configurazione sulle esatte righe CI e0con quella corretta. Due chiavi sintetiche indipendenti,una di64caratteri esadecimali,restano rilevate; valori mai registrati nel dossier. Controlli in `validation/r210/ci-b8fed59-gitleaks-controls.json`. Il report della scansione del commit è separato; vedere il risultato JSON per esito e hash.
Non ripetuti i6390test già verdi né i58casi export invariati. Questa verifica locale non costituisce un nuovo esito CI verde e non certifica dipendenze/Trivy saltati a valle di Gitleaks. Nessun aggiornamento di baseline Bandit/transport necessario: sorgenti applicativi invariati.

## Applicazione e prossimo passo

Il cumulativo `MTA-0.3.0-r210-pre-RC-ci-repair-cumulative.zip` contiene l'intero progetto,hotfix SQLite e tutte le precedenti modifiche/assets/licenze/log. Estrarre nella copia corrispondente e controllare il diff,conservando la propria storia Git. Rispetto all'ultimo cumulativo,i soli cambiamenti eseguibili sono test e configurazione Gitleaks;documentazione e prove aggiornate. SHA256 adiacente e manifest completo nel pacchetto.
Commit suggerito: `Fix admitted-policy CLI regression test and exact public-hash Gitleaks false positives`.
Dopo il commit eseguire la CI standard sul nuovo SHA; ripetere il vecchio run senza nuovo commit userebbe ancora i file difettosi. Non serve la full CI per questo delta. Rimane distinto il workflow manuale `Optional administrative cutover Chromium`,input `admin_cutover_chromium=true`,per i9casi reali della UI già consegnata.
Stato RC invariato:23/42,54.8%,0/7macroaree;PRE-RC. Switching generale bloccato e modalità locale default-off. Nessun commit,staging,push,dispatch o intervento sui server reali eseguito.
