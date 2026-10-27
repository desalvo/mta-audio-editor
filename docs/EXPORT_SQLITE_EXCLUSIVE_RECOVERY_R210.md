# Export audio: recupero della contesa SQLite / SQLite contention recovery

27 ottobre 2026 · MTA Audio Editor 0.3.0-r210 · PRE-RC

## Risultato e causa verificata

Il traceback del 27 ottobre fallisce durante l'autenticazione, prima del codice MP3:
`security_middleware → session_user → init_auth_db → fence_held → SELECT sqlite_master`.
Il precedente intervento eliminava le scritture superflue durante il polling, ed era verificato con un writer `BEGIN IMMEDIATE`. Un lock che impedisce anche nuove letture richiede un percorso diverso: anche una connessione SQLite in sola lettura può ricevere `SQLITE_BUSY`/`SQLITE_LOCKED`.

Il nuovo test riproduce esattamente questa classe di errore con `BEGIN EXCLUSIVE` su una connessione reale separata. L'archivio diagnostico fornito contiene 972 eventi strutturati e nessun testo SQL o proprietario delle transazioni. Non consente di identificare quale transazione tenesse il lock sul server. La correzione gestisce la contesa e il recupero; non dichiara eliminata una causa del writer che non è stata osservata.

## Comportamento consegnato

- La lettura della barriera riusa la connessione del chiamante e una lettura coerente; una lettura autonoma attende al massimo 250 ms. Il timeout precedente viene ripristinato e una transazione del chiamante non viene mai confermata o annullata dal controllo della barriera.
- Un autentico errore SQLite BUSY/LOCKED produce HTTP 503 con `code: database_busy`, `Cache-Control: private, no-store` e `Retry-After: 1`. L'autenticazione non viene memorizzata né aggirata e il cookie non viene cancellato per una lettura indisponibile. Una revoca commessa durante il lock produce 401 alla prima lettura successiva.
- Soltanto GET/HEAD possono essere indicati come ripetibili. Il browser prova fino a quattro letture dopo un 503 esplicitamente classificato. Se il polling resta occupato, attende e continua sullo stesso ID del job; non invia un altro export.
- Un export già completato può riprovare il download originale dopo la contesa. Questa ripresa è abilitata soltanto nei callback di export progetto, traccia e karaoke; i callback generali che potrebbero modificare dati non vengono rieseguiti. Salvataggio, notifica terminale e callback finale avvengono una volta dopo un download riuscito.
- Stato della barriera mancante o schema danneggiato restano indisponibili e non ripetibili automaticamente. Errori SQL di programmazione non vengono riclassificati come lock. Il parametro della risorsa `app.js` cambia per richiedere il JavaScript aggiornato al browser.

Non vengono modificati il journal mode del database, le transazioni monetarie, le autorizzazioni originali o i controlli del cutover. Non vengono terminati writer o eliminati file SQLite.

## Prove riproducibili

`docs/validation/r210/export-exclusive-result.json` contiene identità dei casi, hash dei sorgenti e rapporti: **143 casi distinti passati, 22 nuovi, nessun errore/fallimento/skip residuo**. I 106 casi funzionali comprendono 12 esportazioni reali progetto/traccia MP3/WAV/FLAC, sei sotto writer riservato e sei con lock esclusivo durante polling e download; i file scaricati vengono verificati con ffprobe. Le prove comprendono autenticazione, revoca, timeout/rilascio della lease, schema mancante, rifiuto del replay delle mutazioni e recupero amministrativo. Altri 37 casi verificano i gate di sicurezza/trasporto. I conteggi sovrapposti non vengono sommati.

Node esegue le funzioni effettivamente consegnate di API, polling e download, con errori controllati sui confini HTTP. È una prova del comportamento JavaScript, non una nuova accettazione Chromium o hardware/mobile. Le verifiche Chromium precedentemente accettate per E5 vengono riutilizzate. Nessuna CI completa invariata viene ripetuta.

Per riprodurre la regressione nuova:

```sh
python -m pytest -q tests/test_r210_export_exclusive_contention.py tests/test_r210_export_auth_contention.py
node tests/export_sqlite_busy.cjs
```

Il primo tentativo del nuovo caso auth avviava scheduler estranei al test e incontrava una contesa già prima dell'iniezione. La fixture finale usa il server già installato senza avviarne gli scheduler, come i test di export precedenti. La sequenza iniziale è conservata nei rapporti; tutte le asserzioni di autenticazione/output restano attive.

## Applicazione sul server

Il cumulativo `MTA-0.3.0-r210-pre-RC-export-sqlite-recovery-cumulative.zip` comprende tutte le modifiche precedenti non ancora confermate dopo `772fbe7508cc08266466a3746bb51f0fe5d0179b`, più questa correzione. Non è un aggiornamento già distribuito. Installare con il normale processo del progetto un server costruito da questo cumulativo, quindi riavviare i processi API che usano il codice precedente e ricaricare la pagina. Non sovrascrivere dati o configurazioni del server con una directory di lavoro.

Il file installato normalmente è `/usr/lib/mta-audio-editor-server/app/regime_service_lease.py`. Nel codice corretto compare `def fence_held(connection=None)`; sono presenti anche `app/sqlite_availability.py` e il richiamo a `fence_held(con)` in `auth.init_auth_db`. Nel browser la risorsa è `app.js?v=0.3.0-r210-export-busy-recovery`.

Dopo l'aggiornamento avviare un solo export MP3 e lasciarlo completare. Una breve attesa per il database deve riprendere lo stesso job e consegnare un file riproducibile. Se l'attesa resta permanente, raccogliere orari, endpoint, log correlati e una nuova diagnostica: occorre individuare la transazione/processo che mantiene il lock. Non cancellare `auth.sqlite3`, journal, WAL o file di lease per forzare il recupero. Questo intervento non certifica la disponibilità in presenza di un lock permanente o di corruzione.

## Continuità dello sviluppo

Il lavoro C2 sul drain, interrotto per dare priorità a questo difetto segnalato, è conservato come checkpoint **inattivo e non accettato** in `docs/development-pending/C2_SERVICE_ADMISSION_WIP.patch` e relativo JSON/README. Il codice operativo del cumulativo non importa né abilita quel protocollo. Le prove preliminari del checkpoint non sono incluse nei 143 casi correnti. Prima dell'integrazione occorrono inventario completo dei punti di ingresso, prove delle sessioni lunghe, handoff fra build e revisione finale. Non applicare la patch a un server reale.

Stato formale invariato: **24/42 criteri originali (57,1%), 0/7 macroaree, RC non raggiunta**. La correzione di una regressione non promuove un criterio nuovo. Nessun commit, push, dispatch CI, accesso a provider o modifica al server reale è stato eseguito.

## English handoff

The reported failure precedes MP3 encoding: authentication reads the cutover barrier and SQLite rejects its schema read. A reserved-writer test did not cover reader-blocking exclusive contention. Reuse the caller's connection, bound independent barrier reads, and return a private typed503 on actual BUSY/LOCKED. Authenticate afresh after release; never use positive authentication caches or infer an absent barrier. Missing/corrupt barrier evidence remains unavailable. Only GET/HEAD are retryable; mutations and general completion callbacks are never replayed. Original-job polling and export-only completed-download recovery preserve one execution/save/final notification.

143 distinct affected cases pass,22 new;actual FFmpeg/ffprobe verifies project/track MP3/WAV/FLAC. Production transaction ownership is unknown from the redacted diagnostics. No deployment occurred. Use the normal server installation/restart process and reload the browser to obtain the new static version. Persistent contention still requires identification of its original writer. Preserve all previous uncommitted Stripe/E5/legacy changes and the inactive C2 development checkpoint;24/42 remains PRE-RC.
