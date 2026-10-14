# MTA Audio Editor 0.3.0-r208 — planning capacity fail-closed

## Intervento
Quando il journal SQLite opzionale di pianificazione raggiunge MAX_JOBS, il record terminale da eliminare viene ora decodificato e validato contro identificativo, progetto, proprietario e stato indicizzati prima della cancellazione. Payload JSON danneggiati o identità incoerenti provocano rollback di tutta la transazione: nessun nuovo record è accettato e il record sospetto viene mantenuto per la diagnosi. Il comportamento di evizione dei record terminali validi è invariato.

## Verifica
`PYTHONPATH=. pytest -q tests/test_r208_planning* tests/test_r208_durable_planning_journal.py tests/test_r208_planning_job_history.py` — 28 passed.

## Limiti
Si tratta di pianificazione, non di esecuzione inferenze, worker GPU o contabilità. Restano necessari test end-to-end estesi, Windows/macOS e hardware GPU reale.
