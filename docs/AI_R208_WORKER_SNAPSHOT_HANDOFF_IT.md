# MTA 0.3.0-r208 — passaggio worker legacy senza TOCTOU

Il worker esterno consegna ora il WAV tramite un unico snapshot di byte verificato. `_snapshot_preview_wav()` apre `preview.wav` con O_NOFOLLOW (se disponibile), controlla che sia un file regolare privato (link count 1) entro il limite previsto, legge i byte una sola volta, confronta dimensione e timestamp dell'inode prima/dopo la lettura, quindi valida il PCM dello stesso payload. `run_external_worker()` e `run_worker_with_project_audio()` restituiscono i byte validati senza riaprire il pathname.

Test di regressione: `tests/test_r208_worker_snapshot_handoff.py`, più suite worker, artifact e billing selezionata. Il passaggio evita la sostituzione del WAV tra validazione e consegna. Non equivale a certificazione GPU, test dell'inferenza reale o chiusura dell'intera area AI locale/legacy.
