# r208 — Provisioning idempotente del ledger AI

Aggiunto `ai_billing.provision_inference_job(inference_job_id, user_id, kind)`.

- Ammette solo utenti autenticati con ID positivo, operazioni `arranger` o `remix` e identificativi validi.
- Rispetta l'opt-in esplicito dell'utente: se il billing non e' abilitato non crea record.
- Deriva un ID ledger stabile dall'ID dell'inferenza e mantiene il vincolo di unicita' nel DB del ledger.
- Crea job e snapshot hardware in una singola transazione del ledger; retry e chiamate concorrenti restituiscono lo stesso ID.
- Blocca le richieste discordanti di utente o operazione.

**Limite**: questa funzione non e' ancora chiamata automaticamente dalle route di ammissione. In assenza di un protocollo di recupero dell'ammissione multi-database, agganciarla dopo lo start asincrono introdurrebbe un race tra esecuzione e billing, mentre chiamarla prima della persistenza della coda potrebbe creare un job contabile orfano. Restano quindi l'integrazione con l'ammissione (registrazione durevole dell'intento, recupero dei job contabili orfani e controlli di finalizzazione) e il collaudo EL10/ROCm.

Verifica: `PYTHONPATH=. pytest -q tests/test_r208_*.py` (162 test superati nell'ambiente di sviluppo).
