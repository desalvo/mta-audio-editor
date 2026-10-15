# r208 — Barriera durevole per cancellazione remota

La route autenticata `POST /api/ai-jobs/request-cancel/{request_key}` registra un tombstone per una richiesta in stato `admitted`. Il client dispone di `cancel_remote_request(...)`, che non ritenta l'inferenza. I risultati tardivi non possono più finalizzare la richiesta. L'operazione è idempotente e limitata al proprietario; i job già completati rimangono completati, non retroattivamente cancellati.

**Limite:** la barriera non interrompe fisicamente un worker già in corso. Manca il trasporto del segnale di cancellazione al processo/adapter remoto, nonché l'attestazione GPU per job. Una risposta `worker_stop_guaranteed: false` segnala espressamente il limite. Il codice mantiene invariata la versione 0.3.0-r208.
