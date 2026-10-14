# MTA Audio Editor 0.3.0-r208 — integrazione attestazione CPU remota

## Modifiche del ciclo
- Entrambi gli endpoint di esecuzione remota (`/api/ai-jobs/execute` e `/api/ai-jobs/execute-audio/{kind}`) preparano una dichiarazione CPU HMAC v2 con identificativi di job, richiesta e worker.
- Firma solo per richieste con idempotency key e misure del processo/albero effettivamente isolate; altrimenti non pubblica attestazione.
- `MTA_AI_REMOTE_METERING_SIGNING_KEY_ID` seleziona la chiave dal keyring dell'operatore (`MTA_AI_REMOTE_METERING_KEYS_JSON`).
- `MTA_AI_REMOTE_METERING_WORKER_ID` identifica il worker firmatario (valore definito dall'operatore).
- La risposta iniziale trasporta `X-MTA-AI-Metering-V2` in JSON canonico; esclude sempre le metriche GPU anche se sono riportate per diagnostica.
- Errori di configurazione e chiavi revocate impediscono la finalizzazione della richiesta nella modalità di firma configurata.
- Compatibilità mantenuta in assenza della configurazione di firma.

## Limiti espliciti
La firma autentica la dichiarazione del worker, non la provenienza hardware GPU. Non sono ancora implementati il consumo automatico della dichiarazione dal client remoto, la persistenza dell'attestazione nel result cache per GET, e la consegna contabile end-to-end. Non è una certificazione della misurazione GPU né una prova di atomicità globale tra filesystem e database.

## Test
`PYTHONPATH=. pytest -q tests/test_r208*` — 726 passed; compilazione Python e `bash -n scripts/install_mta.sh` passati.
