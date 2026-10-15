# MTA Audio Editor 0.3.0-r208 — Importazione MTA serializzata

## Chiusura end-to-end locale

Sia il worker asincrono `_mta_import_worker` sia l'endpoint diretto `/api/import` acquisiscono `project_publication_lock(project_id)` prima di leggere il progetto e chiamare `import_mta`. La funzione di importazione scrive file audio, allegati e `project.json`; perciò il lock copre l'intero processo di estrazione e salvataggio, non soltanto l'ultimo `save_project`.

La validazione iniziale del file (`ffprobe`) nel worker rimane fuori dal lock. Il lock viene rilasciato automaticamente anche in caso di eccezione. Il percorso MTA è limitato a un progetto appena creato, ma la serializzazione protegge eventuali writer concorrenti che acquisiscono il medesimo lock.

## Verifiche

- `tests/test_r208_mta_import_project_lock.py`: sequenza di acquisizione, rilascio su errore e lock nell'endpoint diretto.
- `PYTHONPATH=. pytest -q tests/test_r208* tests/test_r207_native_remote_routes.py`: 937 superati, 9 warning.

## Limiti

Il blocco comune non crea una transazione distribuita fra estrazione dei media e salvataggio del progetto. Il collaudo reale con più processi FastAPI resta da eseguire. Nessuna modifica a billing GPU, server ROCm, revisione o repository Git.
