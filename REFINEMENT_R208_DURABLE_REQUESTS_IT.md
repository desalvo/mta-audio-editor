# MTA Audio Editor 0.3.0-r208 — Durable request refinement

## Implementato
- Migrazione incrementale della coda SQLite con `payload_json` e chiave di idempotenza unica; payload JSON massimo 1 MiB.
- L'API interna `read_payload(job_id)` permette a un esecutore autorizzato di leggere i parametri persistiti. I parametri non sono inclusi nelle API pubbliche di stato/coda.
- `start()` rifiuta un replay in conflitto e restituisce il lavoro esistente senza lanciare un nuovo thread per lo stesso id/job key.
- Chiusura condizionale del lavoro da parte del runner che lo aveva acquisito.
- Tempo di esecuzione trascorso esposto nello stato.
- Gli ingressi web Arranger e Remix persistono i parametri Pydantic e accettano facoltativamente `Idempotency-Key` per il dedup delle richieste HTTP.
- Test automatici per persistenza, dedup, isolamento dei payload.

## NON ancora completato (vincoli progettuali reali)
- L'esecuzione dei job legacy, nativi, remoti e sincroni non è tutta centralizzata. Parte di essa usa ancora contesti in memoria.
- Non è implementato un resolver persistente degli adapter che possa riprendere automaticamente una richiesta dopo il riavvio.
- La pubblicazione dei risultati non ha ancora una transazione/outbox idempotente condivisa con lo scheduler e con l'accounting.
- Annullamento effettivo remoto e metering CPU/GPU completo non sono certificati su tutti i backend.
- Installer ROCm/EL10, backend ACE-Step e metriche reali richiedono collaudo hardware.

## Collaudi locali
- `pytest -q tests/test_r208_*.py`: 113 passed.
- `bash -n scripts/install_mta.sh scripts/install_mta_native.sh scripts/install_mta_native_wizard.sh`: passed.
- Non è stata effettuata nessuna installazione né alcun intervento sul server/CT.

# r208 installer trusted worker refinement
- Existing source installer upgrades refresh trusted worker executable/enabled settings alongside ACE-Step URL and trusted host without altering secrets.
- The default native installer delegates configuration to scripts/install_mta_native.sh; hardware wizard paths need EL10 runtime verification.
