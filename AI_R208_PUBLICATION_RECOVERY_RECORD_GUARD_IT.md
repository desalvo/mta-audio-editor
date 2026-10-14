# MTA 0.3.0-r208 — recupero pubblicazione: validazione transazionale

Il recovery delle pubblicazioni audio AI valida i record persistenti prima di invocare la callback applicativa. Sono respinti identificativi, timestamp, digest, stati e metadati JSON alterati. Dopo la callback, la transizione `pending` → `published` impone un compare-and-set sull'identità e sui campi osservati prima dell'invocazione; se il record viene modificato nel frattempo, la transizione viene annullata e resta `pending`.

Anche i replay `stage()` sui record esistenti verificano la consistenza del record prima di accettarlo. Questi controlli non rendono atomica una callback esterna con SQLite: la callback deve rimanere idempotente per `job_id`. Nessun billing avviene in questo modulo. Non sono stati eseguiti test su GPU, OS nativi o server reali.

Test: `tests/test_r208_publication_recovery_record_guard.py` e regressioni outbox/replay/queue.
