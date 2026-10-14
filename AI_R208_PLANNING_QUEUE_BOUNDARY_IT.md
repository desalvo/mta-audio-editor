# MTA Audio Editor 0.3.0-r208 — planning queue input boundary

## Interventi di questo ciclo
- Validazione anticipata e atomica dei piani di `AIJobQueue`, prima di eventuale eviction.
- Rifiuto di valori non JSON (set, bytes), numeri NaN/Infinity, chiavi non stringa, riferimenti circolari, profondità oltre 32 e dimensioni serializzate oltre 1 MiB.
- Verifica dei contesti di progetto e proprietario vuoti.
- Serializzazione/riserializzazione JSON per isolare i dati conservati nella coda dagli oggetti del chiamante.
- Timestamp di cancellazione impostato una volta sola; nessun job in esecuzione simulato.

## Test
`PYTHONPATH=. pytest -q tests/test_r208_planning_queue_boundary.py tests/test_r177_ai_job_queue.py tests/test_r178_native_mix_and_ai_job_safety.py tests/test_r208_restartable_queued_jobs.py tests/test_r208_job_id_storage_hardening.py tests/test_r207_parallel_job_isolation.py`

Esito: 12 passed. Test della suite completa NON eseguiti.

## Limiti
La coda `AIJobQueue` è locale al processo e tratta solo pianificazioni; non è la coda distribuita di esecuzione AI. Non risultano chiusi con questa patch il lifecycle completo dei job, il metering GPU fatturabile, la certificazione billing, Windows/macOS, gli installer e i collaudi hardware.
Nessuna modifica alla versione 0.3.0-r208. Nessun commit, push, tag o release.
