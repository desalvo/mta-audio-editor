# MTA 0.3.0-r208 — Binding locale/remoto per le evidenze CPU

Il nuovo `ai_metering_bridge.durable_remote_sink(local_job_id, request_id=..., worker_id=...)` restituisce un callback destinato al client remoto che verifica già l'attestazione HMAC v2. Il callback persiste nel database della coda una corrispondenza immutabile `(job locale, job remoto, richiesta, worker)` e registra le misure CPU tramite `capture`.

- Il binding viene creato sotto transazione `BEGIN IMMEDIATE`.
- Una nuova associazione discordante non sostituisce quella precedente.
- La medesima evidenza può essere ritrasmessa senza duplicare la registrazione.
- Metriche GPU non attribuibili a un agente GPU autenticato vengono rifiutate.
- La chiave HMAC deve essere verificata a monte dal client remoto; questo callback non accetta direttamente prove non verificate dalla rete.

## Limiti e prossime integrazioni

Il callback **non è ancora automaticamente collegato a tutti i percorsi di inferenza remota**. Deve essere inserito nei punti in cui il job locale durevole è noto e la richiesta remota è generata. Il legame con il ledger e la finalizzazione rimane soggetto alla disponibilità delle evidenze misurate e alla Billing Outbox. La presenza di firme HMAC non attesta misure GPU hardware. L'ambiente Rocky EL10 / ROCm resta da certificare.

Sono stati aggiunti test per replay, conflitti di identità, rifiuto di ID non validi e rifiuto di metriche GPU.
