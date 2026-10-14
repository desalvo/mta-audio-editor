# r208 — Integrazione dell'esecuzione remota durevole Arranger/Remix

La route persistente Arranger/Remix usa `app.ai_durable_remote_executor` quando l'operatore imposta `MTA_AI_DURABLE_REMOTE_URL`, `MTA_AI_DURABLE_REMOTE_WORKER_ID`, `MTA_AI_DURABLE_REMOTE_TOKEN`. Senza URL resta attivo il percorso locale esistente.

L'esecutore produce un WAV sorgente tramite il motore audio per `master` oppure una singola traccia con insert. Le selezioni legacy che contengono più tracce vengono rifiutate (nessun mix implicito). Il risultato remoto passa per attestazione HMAC, acquisizione CPU e registrazione dell'intenzione contabile *prima* della pubblicazione tramite Outbox. Non si attribuisce alcun consumo GPU non provato. La cancellazione è verificata prima della richiesta e prima della pubblicazione; la cancellazione durante il trasporto richiede ancora implementazione cooperativa remota.

Questo percorso richiede credenziali e keyring di attestazione server-side, non provenienti dalla richiesta HTTP. È una prima integrazione reale per Arranger/Remix, non certifica il resto degli adapter, i consumi GPU o il percorso EL10/ROCm.

Regressioni locali: `PYTHONPATH=. pytest -q tests/test_r208*` → 777 passed. I test non sono benchmark hardware e non raggiungono 100 interventi funzionali indipendenti.
