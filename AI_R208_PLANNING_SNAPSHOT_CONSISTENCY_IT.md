# MTA Audio Editor 0.3.0-r208 — Planning snapshot consistency

## Interventi
- `get` esegue audit e recupero nella stessa transazione SQLite, impedendo che la seconda lettura osservi uno stato differente dalla prima.
- `list` valida e decodifica i record della pagina prima della chiusura della transazione di lettura.
- `cancel` esegue l'audit dei record del medesimo progetto/proprietario dentro la transazione `BEGIN IMMEDIATE`, prima della modifica; un record non coerente blocca l'operazione.
- L'audit conserva l'isolamento per proprietario: corruzioni nei dati di altri proprietari non vengono esposte e non blocca una cancellazione autorizzata.
- Quattro test di regressione dedicati a snapshot, audit e rollback.

## Validazione
`PYTHONPATH=. pytest -q tests/test_r208_planning_snapshot_consistency.py tests/test_r208_planning_* tests/test_r177_ai_job_queue.py tests/test_r178_native_mix_and_ai_job_safety.py`

Risultato: 33 passed. Il journal resta esclusivamente una coda di pianificazione: non esegue inferenze e non contabilizza GPU. Nessuna validazione su hardware GPU o Windows/macOS. La suite globale non è stata eseguita.

## Aree ancora aperte
Collegamento effettivo fra pianificazione e coda di esecuzione, retry/recovery/cancellazione end-to-end dell'inferenza, integrazione native/server, attestazione GPU per billing, packaging e CI native, collaudi su piattaforme reali.
