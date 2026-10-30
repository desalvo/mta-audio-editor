# MTA 0.3.0-r210 — CI41098492290 — 30 ottobre 2026

**RC69,0% (29/42),invariata;nessun criterio originale promosso.** Il commit dell'utente `d6ca2860538cab6a08e38ea91c40ff7c60479a47` è la nuova baseline:4306blob tracciati confrontati col tree `1d3e79af0d301bc7958025b1b0a47031c5d7bde0`,tutti identici alla copia locale prima della correzione.

## Causa e correzione

Il job SAST124210367281 fallisce allo step **Secret scan**:Gitleaks8.24.3 classifica come generic-api-key tre SHA256 pubblici in `app/studio_assets/transcription_source_contracts.json`,righe11,66,103. Sono le impronte dei file YourMT3 `amt/src/extras/auth2/token_data.json`,`amt/src/tests/tokenizer_test.py`,`amt/src/utils/tokenizer.py`;non i contenuti dei file e non credenziali.

Aggiunte in `.gitleaks.toml` soltanto tre espressioni ancorate all'intero digest esatto,nella allowlist già esistente. Regole predefinite attive;nessuna esclusione di percorso,commit o regola. `.gitleaksignore`,workflow,dipendenze,sorgenti applicativi,test e contratto MT3 restano identici. L'hash del contratto resta `2610e877a8f9e963050f1601b5a832e23f0ae83a7e04edfa87f42aa4cff06492`:nessuna modifica dei pin o dei controlli runtime per risolvere il falso positivo.

## Verifica

Gitleaks8.24.3 ufficiale,checksum dell'archivio verificato e binario SHA256 `e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad`. Riprodotti esattamente i3rilievi alle stesse righe;dopo la correzione il contratto passa con0rilievi/exit0. I3digest modificati negli stessi campi e una credenziale sintetica separata producono4rilievi/exit2:la regola continua a rilevare valori nuovi. La canary resta fuori dal progetto e dalla consegna;gli esiti salvati sono redatti.

La scansione senza storia dell'intera cartella mantiene35vecchi rilievi,contro44con la configurazione originale:zero nuovi. Tali segnalazioni ricompaiono senza i fingerprint storici legati al commit,già presenti in `.gitleaksignore`;non sono nuove eccezioni e questa verifica non viene dichiarata scansione storica pulita. Il delta consegnato viene controllato separatamente.

Il log remoto Quality124210367296 conferma **7683test passati,50saltati,1027warning,76,56%copertura su soglia70%,960,31secondi**. Non ci sono failure nel riepilogo dei test. È il profilo unit standard;non è una nuova full regression né accettazione dei target mancanti. Run ora completato con esito failure:Quality e VST3 SDK riusciti,solo SAST fallito allo step Secret scan;10job dipendenti/pubblicazioni saltati. Il job Quality è confermato success dal risultato finale API e dai log. Il job VST3 SDK Linux è riuscito. Nel job SAST sono riusciti license guard,Bandit e audit dipendenze;Trivy è stato saltato dopo il fallimento del secret scan. I build dipendenti possono essere saltati per il fallimento del run:non sono nuove prove target.

Nessuna nuova suite applicativa invariata ripetuta localmente:app,test e inventari di sicurezza restano identici ai byte del commit appena collaudato. Nessuna CI remota del fix ancora eseguita. Prove e limiti in `validation/r210/ci-41098-gitleaks/result.json`,`ci-41098492290-observation.json` e `ci-41098-baseline-comparison.json`.

## Ripresa

Cumulativo completo:**MTA-0.3.0-r210-pre-RC-ci-41098-cumulative.zip**,tutti i percorsi/log/asset/licenze/metadati del precedente legacy-collection conservati. I delta precedenti sono ora committati in `d6ca2860538cab6a08e38ea91c40ff7c60479a47`;il solo nuovo delta è la configurazione del secret scanner e la documentazione/prova di questa correzione. Versione0.3.0-r210 invariata;RC e cambio generale ancora disabilitati.

Dopo il prossimo commit dell'utente controllare lo step Secret scan e il successivo Trivy,poi l'esito standard complessivo. Non è stato richiesto né eseguito un nuovo dispatch/retry remoto. Riprendere quindi `RC_DELIVERY_PLAN_R210.md`:A4/A5/C3 e i residui di esecutori/diritti/target restano aperti;questa riparazione della CI non modifica criteri,pesi o percentuale.

Commit suggerito,limitato al delta dopo `d6ca2860538cab6a08e38ea91c40ff7c60479a47`:

`Allow exact public MT3 source digests in secret scans`
