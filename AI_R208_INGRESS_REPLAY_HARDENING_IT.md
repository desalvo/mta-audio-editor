# r208 — Ingress e replay HTTP: stato del ciclo

Versione invariata: 0.3.0-r208. Nessun commit o push.

## Correzioni
- Le route `POST /api/projects/{pid}/ai-arranger/start-generation` e `/api/projects/{pid}/remix/start-generation` trasformano i conflitti durevoli di `ai_arranger_runtime.start()` in HTTP 409, invece di restituire un errore server 500.
- Dopo l'attivazione, la risposta utilizza lo stato corrente dello scheduler anziché il precedente snapshot accodato.
- Test mirati verificano conflitto HTTP nei due endpoint, replay identico e rifiuto del replay con identità utente differente.

## Verifiche locali
- `PYTHONPATH=. pytest -q tests/test_r208*`: 191 passed.
- Restano da validare live adapter remoti/legacy, misure GPU imputabili al singolo job e crash injection end-to-end su EL10/ROCm.
- Si tratta di una saga recuperabile, non di una singola transazione ACID tra filesystem, queue e ledger.

## Passaggio operativo
Il collaudo hardware finale su ollama-02 non è stato eseguito e non deve essere considerato certificato. Il CT Proxmox 130 non è stato modificato.
