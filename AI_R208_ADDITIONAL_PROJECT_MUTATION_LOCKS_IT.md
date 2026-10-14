# MTA Audio Editor 0.3.0-r208 — Serializzazione delle mutazioni aggiuntive

Sono stati estesi i lock cross-process basati su `project_publication_lock(pid)` a 12 operazioni: migrazione FLAC, aggiornamento generale del progetto, azzeramento Lyrics, azzeramento Chords, modifica dei record dei diritti, creazione del metronomo, modifica del BPM di zona, refresh del metronomo, shift adattivo, cambio della modalità transport, creazione della traccia accordi e refresh della traccia accordi.

Il decoratore viene definito prima della prima rotta che lo utilizza. L'acquisizione avviene prima della lettura del progetto e la deallocazione è garantita anche in caso di eccezione; restano invariati le firme FastAPI e i lock interni specifici del metronomo e degli accordi. Non si afferma di aver serializzato tutte le restanti operazioni, inclusi i job asincroni.

Test eseguiti: `PYTHONPATH=. pytest -q tests/test_r207_native_remote_routes.py tests/test_r208*` — 923 passed, 9 warnings. Nessun test ROCm reale, nessun commit o deploy.
