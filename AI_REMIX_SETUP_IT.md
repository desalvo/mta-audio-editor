## r177 — Pianificazione job Remix

POST `/api/projects/{pid}/remix/jobs` crea un piano autenticato e non distruttivo, annullabile attraverso le API job AI. Nessuna generazione audio effettiva finché il worker non sarà verificato.

# Remix / Auto-Remix — r175

AI Arranger dispone ora della modalità distinta **Remix**, attualmente per la sola pianificazione.

`instrument_swap` consente di scegliere tracce esistenti e strumenti sostitutivi; `auto_remix` usa preset e descrizione libera. Rimangono le opzioni di conservazione degli accordi, della struttura, del BPM, della melodia e della voce.

Utilizzo Python: `prepare_remix_plan(project, RemixRequest(...))`. La generazione audio, il collegamento alla UI, l'anteprima non distruttiva e la verifica musicale richiedono ancora implementazione e backend abilitati.


## r176: accesso e stato
Il catalogo è disponibile via GET /api/ai-arranger/catalog e i piani via POST /api/projects/{pid}/ai-arranger/plan o /api/projects/{pid}/remix/plan. Autenticazione e permessi di progetto obbligatori. La generazione POST /api/projects/{pid}/remix/generate restituisce 503 finché non viene installato un worker verificato; non modifica i media.

### Gestione delle tracce generate (r185)
I risultati vengono **aggiunti come nuove tracce** al progetto senza sostituire gli originali. Master Out include mute, solo, fader, pan ed effetti. La generazione richiede un worker AI esterno configurato: ACE-Step non è ancora incluso.
