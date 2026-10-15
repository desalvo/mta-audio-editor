# MTA Audio Editor 0.3.0-r208 — validazione stato pubblicazione AI

## Modifica implementata

In `app/ai_publish_outbox.py` le letture `status(job_id)` e `published_jobs()` verificano i record persistenti prima di dichiarare una pubblicazione completata. Sono validati identificativo job, identità progetto, SHA-256 audio, metadata JSON canonico, stato, timestamp iniziale e timestamp di completamento. Stati `published` senza `published_at` valido vengono rifiutati (*fail closed*). Anche `published_jobs()` valida ogni record dell'outbox prima di restituire la lista, evitando che dati danneggiati vengano ignorati dal recovery globale.

## Test

- 18 test superati: status, outbox, replay, boundary SQLite e riconciliazione.
- 21 test superati: stage inode guards, billing outbox, metering bridge, recovered track e validazione status; 8 warning di deprecazione.
- 4 nuovi casi di test.

## Confini della chiusura

Non è stata eseguita la suite globale e non sono stati effettuati test GPU, Windows o macOS. La validazione di record SQLite non garantisce l'autenticità contro un attaccante che può riscrivere coerentemente tutti i campi: è richiesta un'ulteriore certificazione del protocollo e del lifecycle dell'inferenza reale. Non esiste una transazione ACID unica che includa filesystem, queue, progetti e billing ledger.
