# MTA Audio Editor 0.3.0-r208 — Integrità producer/consumer artefatti AI

## Intervento
- Ogni artefatto emesso dall'adapter unificato viene associato a SHA-256 nel manifest atomico.
- Il consumer ricalcola SHA-256 sui byte verificati con file descriptor prima di assemblare il package.
- Una sostituzione a contenuto differente, anche a lunghezza invariata, impedisce la pubblicazione.
- I manifest legacy senza SHA-256 restano accettati per compatibilità; **non** garantiscono il controllo end-to-end contro alterazioni precedenti alla lettura.
- La firma crittografica del producer e la contabilizzazione GPU verificabile non sono incluse in questo intervento.

## Test locali
201 test r208 superati; sintassi Bash e compilazione Python passate.

## Residui non certificati
Centralizzazione di tutti gli adapter legacy e remoti; autenticazione delle misure GPU per job; integrazione end-to-end e test hardware EL10/ROCm.

Non sono stati eseguiti commit/push, né modificati CT 130 o ollama-02.
