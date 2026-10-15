# MTA 0.3.0-r208 — stato della coda AI (implementazione incrementale)

## Implementato in questo cumulativo

- Coda FIFO SQLite transazionale per la **generazione web AI Arranger/Remix**.
- Limite di concorrenza predefinito 1, modificabile da 1 a 32 nella scheda amministrativa **Coda AI**, persistente nel database della coda.
- Un job in attesa mostra `queue_position` e `jobs_ahead` anche nel polling client ogni due secondi.
- API amministrative protette da `require_admin`: elenco, configurazione, riordino, annullamento dei job non avviati.
- Lo stato, la fase e l'avanzamento fornito dal worker sono visibili ai client. CPU/GPU seconds vengono visualizzati se il worker produce metriche misurate; altrimenti N/A.
- Dopo la morte del worker il job viene marcato come interrotto e richiede ritentativo esplicito; **nessun replay potenzialmente duplicante**.
- Pulsante **Test worker / Verifica worker** nella finestra web Arranger: controlla soltanto la configurazione, non effettua inferenza.

## LIMITI IMPORTANTI — non ancora completati

1. **Non è ancora una coda globale di tutti i job AI**. Le chiamate AI legacy, i client remoti, Demucs, Whisper, SAM Audio, DrumSep e le funzioni native non sono ancora state migrate al coordinatore comune. Anche gli endpoint sincroni Arranger possono bypassare il limite.
2. **L'annullamento di una generazione GPU già in esecuzione NON è ancora supportato**. L'API lo rifiuta con HTTP 409, invece di dichiarare falsamente il successo. Per fermare ACE-Step serve la cancellazione effettiva della task ACE e una semantica sicura delle modifiche progetto.
3. I job sono persistiti a database, ma i callback in corso non sono serializzabili: dopo riavvio si devono ritentare manualmente. La coda non implementa ancora replay automatico, lease con fencing token e retry idempotente.
4. **CPU/GPU seconds per job**: sono visualizzati soltanto se gli adapter li misurano e li pubblicano. Non attribuire l'uso della GPU condivisa a un job in maniera fittizia. Il worker ACE-Step in questa versione non espone ancora una misura attestata dell'uso della GPU per task.
5. L'isolamento tra progetti, l'ownership e la protezione da richieste concorrenti attraverso tutti i percorsi devono essere completati prima dell'uso multi-tenant di produzione.

## API parziali

- `GET /api/admin/ai-execution/jobs`
- `GET /api/admin/ai-execution/settings`
- `PUT /api/admin/ai-execution/settings` — JSON `{ "max_concurrent_jobs": 1 }`
- `POST /api/admin/ai-execution/jobs/{job_id}/cancel` (solo queued)
- `POST /api/admin/ai-execution/jobs/{job_id}/move` — JSON `{ "position": 1 }`
- `GET /api/projects/{pid}/ai-arranger/active-generation` — stato della generazione web del progetto

## Validazione mancante

Eseguire Quality completa e l'integrazione EL10 con modello ACE-Step su GPU Radeon 8060S; verificare riordino e limite con più processi Gunicorn, autenticazione admin, comportamento UI, job persistenti dopo restart, contabilità e cancellazione reale quando implementata.
