# r208 — Persistenza del risultato remoto e chiusura contabile

Gli endpoint `POST /api/ai-jobs/execute` e `POST /api/ai-jobs/execute-audio/{kind}` ora richiedono il salvataggio durevole del risultato nella cache prima di segnare la richiesta idempotente come `completed`. Se la cache rifiuta il risultato o genera un errore I/O, la richiesta viene marcata `failed` e il server risponde `503`. La stessa chiave di idempotenza non può avviare una seconda inferenza, evitando una seconda contabilizzazione.

La misura effettiva dei consumi GPU per singolo job non è certificata; il sistema non converte il tempo di esecuzione in consumo GPU. La restituzione del risultato al chiamante e la persistenza nel database del ledger non costituiscono una transazione ACID unica con il filesystem: sono necessari test di crash reali e recovery su EL10/ROCm.

Test: `PYTHONPATH=. pytest -q tests/test_r208*` e verifiche mirate in `tests/test_r208_remote_cache_failure_gate.py`.
