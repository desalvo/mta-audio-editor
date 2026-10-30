# MTA 0.3.0-r210 — CI41125188767: drain senza interferenze

**RC:69,0% (29/42),invariata;nessun criterio originale promosso.**

Baseline utente: `d3b17b6ebed8e512e5d6edb043b2a9f336d2b597`,tree `558c52e759b5b9dc72aa821e37779f260f29080c`. Tutti i4321blob tracciati coincidono con il cumulativo CI41104 prima delle modifiche. Il precedente fix Authenticode è committato e non è il nuovo errore.

## Esito remoto e causa

Dei tre job indicati,SAST124301626141 e VST3 SDK Linux124301626537 riescono. Quality124301626818 fallisce soltanto nel caso arranger di `test_registered_local_worker_heartbeat_publication_and_single_charge_finish_under_drain`:7686passati,1fallimento,50skip,copertura76,57%(soglia70%). Dieci job dipendenti saltati;workflow complessivo fallito.

Riprodotto anche localmente sul caso remix. L'osservatore `service_admission.inspect` prendeva il flock esclusivo per l'audit pur sapendo che erano ancora aperte ammissioni originali. Un accesso concorrente del guardian o heartbeat al database richiede il flock condiviso non bloccante:veniva quindi respinto. Lo stack acquisito mostra esattamente `ai_process_guard.run -> worker_process_guard.register -> auth.db -> regime_service_lease.lease -> FenceBlocked`. Il rifiuto poteva lasciare il ledger originale running con proprietà conservata,oppure causare una cancellazione;il semplice timeout finale del test nascondeva questa causa.

## Correzione

In `app/service_admission.py`,finché esistono ammissioni aperte,lo snapshot restituisce `drained:false` e `pending.verified:false,count:null,reason:active_admissions`,senza prendere il flock esclusivo e senza dichiarare assenti gli obblighi. Dopo la chiusura di tutte le ammissioni,esegue l'audit originale sotto lock del journal e flock esclusivo,con gli stessi controlli di build,integrità e obblighi.

Nessuna scadenza automatica,eliminazione di ammissioni o accettazione di un worker incerto;nessun timeout aumentato,checker/soglia modificato o test disabilitato. Il conteggio attivo e la chiusura originale restano autoritativi. Le tre revisioni legate ai sorgenti sono aggiornate per il solo file modificato;un sito middleware AST identico passa dalla riga492alla499,senza nuova classificazione.

## Verifiche

- Due nuove regressioni deterministiche falliscono entrambe sul codice originale:lock esclusivo durante attività ammessa e accesso database del partecipante originale respinto nella finestra dell'audit.
- **114casi distinti passano,0fallimenti,0skip**:drain/API/processi,worker TLS,cutover,proprietà/pubblicazione/contabilità differita,inventario e precedente fix diagnostica.
- **10processi pytest indipendenti** ripetono ciascuno i due casi arranger/remix e le due regressioni:40esecuzioni riuscite,già incluse nei114casi distinti.
- Ruff,compilazione e quattro gate passano. Bandit168finding invariati(0HIGH/21MEDIUM/147LOW),nessun ID aggiunto/rimosso. Inventari:555sorgenti/780confini,308sorgenti/173siti,21sorgenti/30trasporti.
- Python locale3.12.14;nuova CI Python3.14 da confermare dopo commit. Non è dichiarato un nuovo full-CI o collaudo target esterno.

Prove complete in `docs/validation/r210/ci-41125/`. Cumulativo completo: **MTA-0.3.0-r210-pre-RC-ci-41125-cumulative.zip**;tutti i contenuti precedenti,asset,licenze,log e metadati ZIP conservati.

Commit suggerito: `Keep drain status polling from interrupting admitted workers`

Solo questo fix,test,revisione e stato seguono il commitd3b17b6. Nessun commit/push/tag/dispatchCI/rilascio o intervento server/provider eseguito. Restano13criteri originali aperti;criteri e pesi invariati.
