# MTA 0.3.0-r208 — Artifact packaging boundary

Il consumatore `app/ai_worker_artifacts.py` ora acquisisce un'unica snapshot limitata di ciascun file prima della validazione e del packaging. Usa `O_NOFOLLOW`, `fstat`, richiede inode regolare con un solo hardlink, limita manifest e file, e convalida JSON/WAV sugli stessi byte destinati all'archivio. Questi controlli proteggono anche il fallback `preview.wav` e il manifest stesso. Non sono una garanzia completa contro scritture concorrenti sullo stesso inode da parte di un processo malevolo: occorre isolare il workspace del worker e bloccare scrittori non attendibili prima del confezionamento.

Test: `PYTHONPATH=. pytest -q tests/test_r208_artifact_packaging_boundary.py tests/test_r208*` — 195 passed. Compilazione Python e controllo Bash eseguiti prima del package.

## Limiti aperti prima della certificazione

- Centralizzazione ed esecuzione misurata di tutti gli adapter legacy e remoti: non comprovata.
- Consumi GPU attestati per singolo job: da integrare e validare sul server EL10/ROCm.
- Crash injection end-to-end, transizioni fra SQLite/FS e riconciliazione con metering reale: da certificare sullo staging isolato.
- Nessun test hardware e nessun intervento su `ollama-02` o CT 130 eseguito in questo ciclo.

Nessuna versione aggiornata, commit o push effettuati.
