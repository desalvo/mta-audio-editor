# R210 — Offline regime readiness report / Rapporto offline di readiness

## Italiano

L'operatore può eseguire **solo su uno snapshot locale** del database SQLite:

```bash
python -m app.regime_readiness_cli --db /percorso/snapshot.sqlite --current NON_COMMERCIAL --target COMMERCIAL --output readiness.json
```

La connessione è `mode=ro`, `PRAGMA query_only=ON`. Il report contiene inventario finanziario, fence, stato inbox/outbox e prenotazioni worker, laddove lo schema è disponibile. Non crea tabelle e non modifica il database. Il file JSON è creato con permessi 0600 ed esistenza esclusiva, evitando sovrascritture. Uscita `1` indica che un rapporto è stato emesso **ma la transizione NON è autorizzata**, uscita `2` segnala un errore di input/I/O. Nessun codice indica una transizione approvata. Non eseguire sul database di produzione, né utilizzare il report come prova di sincronizzazione dei nodi o dei provider. Non sostituisce le interrogazioni autenticate Stripe/PayPal o il cutover distribuito.

## English

An operator can run the same command against an **offline local SQLite snapshot**. Database access is read-only (`mode=ro`, `query_only=ON`) and the report is a sanitized JSON diagnostic of financial inventory, fences, webhook inbox/outbox, and worker claims when schemas are present. JSON output uses exclusive creation and mode 0600. Exit status `1` means the diagnostic was produced but **does not authorize transition**; status `2` means an input/IO error. No exit code grants permission to switch. Never point at live production databases. Provider-authenticated reconciliation, distributed quiescence, and global regression remain required.

## Validation scope

Local CLI integration tests exercise report creation, non-modification of SQLite bytes, unavailable schema, path validation, write-only-new-output behavior and nonzero exit codes. Expanded selected service-regime test suite results in `docs/validation/r210/offline-readiness-regression.log`. Not a certification of the complete platform.
