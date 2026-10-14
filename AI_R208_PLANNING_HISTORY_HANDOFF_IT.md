# MTA Audio Editor 0.3.0-r208 — cronologia della pianificazione AI

Il servizio espone `GET /api/projects/{pid}/ai-jobs` per consultare, con autorizzazione di progetto, i piani della coda locale appartenenti esclusivamente all'utente richiedente. Il risultato include `items`, `total`, `limit`, `offset`, `durable=false` e `generation_available=false`.

Parametri: `limit` 1–100 (default 20), `offset` 0–128 (default 0), `status` tra `planned`, `cancelled`, `completed`, `failed`. Ogni risposta contiene copie indipendenti degli oggetti archiviati. L'elenco è ordinato per inserimento e rispetta la capacità massima già esistente di 128 piani; i piani terminali possono essere espulsi al raggiungimento del limite.

**Vincolo importante:** questa API consulta soltanto `app.ai_job_queue.AIJobQueue`, una coda di *pianificazione* volatile. Non è una API di job di inferenza persistenti: i piani possono andare persi al riavvio e non vengono eseguiti da questa classe. Non associare a questa API accounting, billing o misure GPU.

Test mirati: `PYTHONPATH=. pytest -q tests/test_r208_planning_job_history.py tests/test_r208_planning_queue_boundary.py tests/test_r177_ai_job_queue.py tests/test_r178_native_mix_and_ai_job_safety.py tests/test_r208_web_inference_queue.py tests/test_r208_queue_live_admin_progress.py tests/test_r208_restartable_queued_jobs.py tests/test_r208_queue_persistence_refinement.py tests/test_r208_blocked_queue_recovery.py tests/test_r208_outbox_queue_reconciliation.py`.

Aree ancora aperte: recovery/cancellazione/shutdown di tutti i job di inferenza, verifica integrata native/server e billing, misure GPU attendibili, installer e collaudi piattaforme reali, regressione completa.
