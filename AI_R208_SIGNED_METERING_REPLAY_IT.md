# r208 — Replay durevole delle attestazioni CPU remote

## Implementato

- Il gateway salva con il risultato remoto anche l'envelope CPU HMAC v2, prima di finalizzare la richiesta idempotente.
- Il replay GET verifica sotto lo stesso lock per richiesta SHA-256 del risultato, identità del job, richiesta, worker e firma HMAC.
- Le chiavi sono rilette a ogni accesso: una revoca rende non recuperabile l'attestazione precedentemente firmata (fail closed).
- I risultati legacy senza attestazione restano recuperabili secondo il contratto precedente.
- I segreti HMAC non vengono scritti nel manifest.
- I record attestati restano limitati a CPU/I/O: nessun consumo GPU è considerato certificato.

## Verifiche

Suite locale r208: 735 test superati (incluse prove specifiche di revoca, manomissione, identità e retrocompatibilità).

## Limiti

Rimane da completare il consumo automatico dell'envelope sul client ricevente e la consegna al ledger con recovery end-to-end. La prova crittografica attesta una dichiarazione del worker, non la precisione o l'isolamento della misura hardware. Restano necessari test reali ROCm/EL10.
