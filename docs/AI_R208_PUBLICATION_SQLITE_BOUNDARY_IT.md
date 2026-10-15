# MTA Audio Editor 0.3.0-r208 – protezione dei file SQLite dell'outbox di pubblicazione

Il ciclo aggiunge controlli fail-closed sul database `outbox.sqlite3` e sui file SQLite ausiliari `-wal`, `-shm`, `-journal` prima e dopo l'apertura della connessione. I percorsi esistenti devono identificare file regolari, non link simbolici o directory. Dopo l'apertura, gli inode ausiliari vengono rivalidati prima dell'eventuale aggiornamento dei permessi. La connessione viene chiusa se la validazione fallisce.

Le verifiche non equivalgono a protezione completa contro tutte le condizioni TOCTOU tra controllo e apertura; non conferiscono transazionalità ACID a filesystem, progetto, coda e ledger. Nessuna modifica al formato o alla politica di contabilizzazione.

Test mirati e integrati: 17 passed, 8 warnings (`test_r208_publication_sqlite_boundary.py`, `test_r208_audio_publication_outbox.py`, `test_r208_generated_track_publication_recovery.py`, `test_r208_async_track_import_publication.py`, `test_r208_project_publication_lock.py`). La suite globale e i collaudi GPU/native restano aperti.
