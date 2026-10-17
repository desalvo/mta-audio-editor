# Validazione cumulativa — Native AI, account e mail r210

Data: 2026-10-17 UTC. Versione **0.3.0-r210**, invariata.
Base completa: MTA-r210-ai-job-center.zip, 1469 file.
SHA-256 base: 2d02f4b985608ac330ca6fc272991d03f881703954f22b7025dfbb32a95e7e6b.
Ultimo commit utente noto: 6fd5d6f25523aaed20c8b37d0ae3a69e08c608bf.
Le modifiche del precedente ciclo non ancora committate sono conservate.
Nessun commit, push, tag, release, invio SMTP reale o modifica al server eseguiti.

## Esito finale

- Regressione completa: **3396 passed, 4 skipped, 10 deselected**, zero failure/error.
  Durata 228,84 secondi. JUnit, log completo e coverage XML inclusi.
- Copertura applicazione: **74.59%**, soglia 70% superata.
- Gruppo mirato integrazioni native/account/HTTP/metering: 72 passed.
- Successivo gruppo con sessioni reali, workspace, autorizzazioni e nuovi flussi:
  42 passed. I due gruppi si sovrappongono; non sono 114 casi distinti.
- Ruff app/native/tests/scripts/k8s-wizard.py: superato.
- Node --check app.js, admin.js, ai_usage_panel.js: superato.
- Email HTML italiana e inglese renderizzate localmente con dati fittizi;
  layout italiano ispezionato visivamente, logo incorporato e testi leggibili.
  Non equivale a una verifica su tutti i client email.

I 4 skip riguardano SDK Steinberg/ADelay opzionali assenti. Le 10 integrazioni
AF_UNIX restano escluse con la stessa selezione esplicita del ciclo precedente:
non sono dichiarate superate. I warning sono conservati nel log finale.

## Verifiche significative

Installazione asincrona con consenso, singola preparazione attiva, disponibilità
HTTP distinta dal processo, riparazione/runtime mancante, annullamento anche con
installer silenzioso, rifiuto di path esterni nell'archivio, esecuzione con Python
gestito anche simulando l'app congelata. Un processo Unix reale esercita il ramo
macOS senza /proc e senza inventare misure verificate dell'albero dei processi.
Test JavaScript della notifica pronta anche ad Arranger chiuso, scelta lingua
e pulsante informativo Intensità.

Autorizzazione dispositivo a durata limitata, approvazione solo con account attivo
e verificato, sostituzione atomica del token della stessa istanza, credenziali
private condivise fra motori, URL non sicuri rifiutati, CSRF e isolamento utenti.
Esecuzione remota asincrona: il loop HTTP continua a rispondere durante il worker;
ACE e un altro motore sono attribuiti allo stesso token nei test.

Risorse per utente e token, somma delle istanze, filtro, importo zero con billing
disabilitato, stime GPU separate e non fatturabili. Diagnostica remota persistente
senza promozione a consumo verificato. Annullamento durante il packaging resta
annullato, non riuscito e non fatturabile.

Outbox email persistente, ordine inizio/terminale, deduplicazione operativa,
retry SMTP senza fallimento dell'inferenza, nessun invio senza SMTP, niente
arretrati al primo avvio, MIME HTML/logo/versione/importo zero, nessun prompt
nel messaggio. Riepiloghi con finestra di completamento per non perdere i job
lunghi iniziati prima del periodo. Recupero di un job interrotto seguito da
completamento produce un nuovo evento terminale pertinente.

## Correzioni emerse dalla regressione

Aggiornate fixture precedenti per l'avvio asincrono, traduzioni e rotazione atomica.
La rotazione mappa a 404 anche il token revocato fra controllo ed esecuzione.
L'attribuzione del contesto accetta sia dizionari di test sia righe SQLite delle
sessioni reali; la suite di login/workspace/modelli ha rilevato e verificato questo
caso. L'assenza di identità per l'email non modifica i controlli di autorizzazione.
Le fixture dell'endpoint remoto mantengono il controllo di disponibilità del
worker configurato. Nessun controllo di sicurezza è stato eliminato per i test.

## Limiti e passaggi necessari

Vedere docs/NATIVE_AI_ACCOUNTS_AND_EMAIL_R210.md per configurazione e collaudo.
Occorrono nuove build native per includere uv e gli adattatori; aggiornare solo
il server non modifica le app già installate. Verificare installazione e inferenza
reali su macOS/Windows e generazione ACE/ROCm sul server aggiornato, inclusi job
lunghi, annullamento, notifica e persistenza del risultato. Configurare SMTP/SMTPS
e MTA_PUBLIC_URL per le email; collaudare consegna e riepiloghi reali.

Le nuove mail/viste stimano il costo del calcolo, non includono storage e altre
componenti delle fatture ufficiali. SMTP usa consegna almeno una volta e può
duplicare un messaggio in caso di crash dopo l'accettazione da parte del relay.
Locale offline senza un account server/SMTP non può ricevere notifiche server.
API ACE pronta non certifica modello/GPU. Il profiler GPU resta diagnostico e
non fatturabile. Nessuna nuova certificazione hardware o del server è dichiarata.

## Integrità del pacchetto

Tutti i 1469 file della base sono presenti; 35 file esistenti aggiornati,
nuovi sorgenti, test, asset, documentazione e risultati finali aggiunti esplicitamente.
La procedura verifica CRC e corrispondenza byte per byte con i file di lavoro,
conserva i permessi dei file della base e produce il checksum SHA-256 esterno.
Nessuna cache, credenziale, ambiente Python o immagine privata aggiunta.

Messaggio Git cumulativo suggerito:
Add AI job management and email summaries, automate native ACE setup, unify remote device tokens and accounting, and improve Arranger and admin UX
