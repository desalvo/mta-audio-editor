# CI e chiave cache GPU / CI and GPU cache key

13 novembre 2026, versione 0.3.0-r210 invariata.

## Italiano

La full CI 43328653496, sul commit f1c23c4, è fallita esclusivamente per
`test_frontend_cache_key_matches_release`. Risultato Quality: 1 fallito,
9143 passati, 126 skip, copertura 78,36% (soglia 70% superata).
SAST/audit, compilazione VST3, matrice server 43328653510 e CodeQL
43328653475 sono riusciti. I job di pubblicazione sono stati saltati per
la dipendenza dal Quality fallito: Docker e bundle nuovi non sono pubblicati
da quella run. I quattro casi process-tree non disponibili nel precedente
runner locale non risultano fra i fallimenti della CI completa.

Il template aveva sostituito il prefisso di release nella query cache di
app.js con il solo suffisso del batch GPU. Ripristinato il prefisso mantenendo
il suffisso: `app.js?v=0.3.0-r210-gpu-job-statistics`. Il browser scarica così
lo script aggiornato e l'identità della release resta presente. Nessun test,
soglia o controllo CI modificato; codice GPU, stime e billing invariati.

Riprodotto lo stesso fallimento sul checkpoint originale: 1 fallito / 4 passati.
Dopo la correzione passano 94 test distinti (identità release, statistiche GPU,
coda, Job AI, telemetria ed email). Verificare la nuova full CI sul commit correttivo;
il risultato della run precedente non certifica il nuovo SHA. Le evidenze
JUnit sono conservate nel cumulativo sotto validation/r210/ci-gpu-cache/.

## English

Full CI 43328653496 on f1c23c4 failed only the frontend release cache-key
check: 1 failed, 9143 passed, 126 skipped, 78.36% coverage. Security audit,
VST3 compilation, server matrix and CodeQL succeeded; publication jobs
were skipped because Quality failed.

The app.js cache query now preserves the release prefix and the GPU update
suffix: `0.3.0-r210-gpu-job-statistics`. This preserves browser cache
invalidation and release identity. No test, CI gate, GPU accounting or billing
logic was changed. The original failure was reproduced locally; final local
validation and the new exact-commit CI are recorded in the current handoff.
