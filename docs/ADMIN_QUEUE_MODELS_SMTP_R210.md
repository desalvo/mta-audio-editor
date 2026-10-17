# Gestione coda, spazio modelli e prova SMTP — r210

La versione resta **0.3.0-r210**. Questo intervento parte dal pacchetto cumulativo Early build / zoom nativo, già committato dall’utente. Nessuna operazione Git o pubblicazione è stata eseguita.

## Coda AI

In Impostazioni → Coda AI la ricerca e la paginazione sono eseguite sul server, sull’intera tabella SQLite, senza il vecchio limite alle prime 500 voci. Pagina predefinita da 20 righe; sono accettati interi da 10 a 100. Ordinamento per creazione decrescente e ID stabile. Ricerca letterale per ID job, ID progetto, operazione, stato e ID utente, con filtri di stato/visibilità. Le wildcard SQL inserite dall’utente sono trattate come testo.

Un unico pulsante **Gestisci cronologia** apre i controlli di selezione. Si possono selezionare singole voci o la pagina corrente, passare alle altre pagine mantenendo la selezione, scegliere l’azione e indicare una motivazione. Cambiando ricerca o filtri la selezione viene azzerata. La verifica e conferma riporta il numero di job prima dell’applicazione. La selezione viene ricontrollata sul server contro la ricerca corrente; massimo 5000 ID. I job attivi devono prima essere cancellati e terminare.

- **Disabilita**: conserva la voce, esclude il calcolo dai report correnti per utente/token, accounting e billing. **Riabilita** ripristina la contabilizzazione originale; non converte stime in misure né altera il flag originario di fatturabilità.
- **Elimina**: applica un tombstone definitivo, rimuove la voce dalle normali liste anche degli utenti ed esclude i consumi come sopra. Non è la precedente funzione di archivio personale, che lasciava immutati i totali. Le voci eliminate si consultano tramite il filtro audit, senza ripristino.
- Misure originali, prove GPU, risultati, receipt e log amministrativo sono conservati. Non vengono cancellate le tracce prodotte o i progetti. Il loro spazio persistente eventualmente fatturabile resta spazio realmente occupato e non viene falsificato dall’eliminazione della voce AI.
- La transazione è atomica: se una voce non è ammissibile, nessuna viene modificata. Le esclusioni restano valide anche con replay tardivo del ledger collegato.
- I periodi già fatturati sono protetti: la gestione rifiuta le modifiche ai job inclusi, invece di riscrivere fatture o snapshot. Per tali periodi occorre una rettifica contabile esterna esplicita.
- Le ripartizioni GPU stimate conservano l’occupazione temporale originaria dei job esclusi: l’esclusione di un utente non aumenta la quota degli altri. Le stime restano distinte dalla misura verificata e non aggirano alcun gate GPU.

Le tabelle `ai_job_dispositions` e `ai_job_disposition_audit` conservano ID job, disposizione, data, admin e motivazione nel database auth. `ai_compute_jobs.accounting_excluded` è una migrazione additiva. Il comportamento di archivio personale rimane distinto da queste azioni amministrative.

## Dimensioni modelli AI

Il riepilogo precedente contava solo l’albero Demucs gestito. Ora comprende le cache note Demucs/CoreML/ONNX, Whisper/lyrics, Torch, Hugging Face, chords, DrumSep, vocal separation e ACE locale. I pesi condivisi da snapshot Hugging Face o link sono contati una sola volta per inode. Non vengono caricati modelli in RAM e non vengono conteggiati gli ambienti Python come pesi.

Il catalogo distingue la disponibilità del modello al download dalla presenza reale dei pesi. In assenza di pesi verificati la dimensione è **non nota / da scaricare**, non un falso 0 B. I checkpoint Demucs già presenti nella cache Torch sono rilevati quando è disponibile la mappa di firme del modello. Marker di installazione senza pesi non bastano a dichiararlo installato.

Il totale riguarda i file visibili al processo server nelle cache note. File sotto un diverso account del servizio ACE o su un host ACE remoto non sono magicamente misurabili dal server MTA. Configurare le variabili di cache coerentemente tra servizi e permessi di lettura; un rilevamento con errori di accesso è indicato come parziale. Le impostazioni riconosciute includono `MTA_DATA_DIR`, `XDG_CACHE_HOME`, `TORCH_HOME`, `HF_HOME`, `HF_HUB_CACHE`, `MTA_LYRICS_MODEL_DIR`, `MTA_DRUMSEP_MODEL_DIR`, `MTA_ACE_MODEL_CACHE`, `MTA_LEAD_BACKING_MODEL_DIR` e `MTA_AI_VOCAL_MODELS_DIR`, oltre alle directory Demucs esistenti.

## SMTP

**Verifica connessione** resta separato da **Invia email di prova**. Il secondo richiede un singolo destinatario e invia realmente un messaggio multipart testo/HTML con logo MTA, revisione, build e server. Usa i valori correnti del modulo; una password vuota conserva quella salvata. Non salva implicitamente il modulo e non invia ad altri utenti. Configurazione e invio richiedono admin e l’header di integrità delle API.

Il successo indica che il server SMTP ha accettato il messaggio, non che sia arrivato nella casella finale. Un rifiuto del destinatario è un errore. Controllare posta/spam, autorizzazione del mittente e log del relay; verificare SPF/DKIM/DMARC quando necessario. I test automatici usano un SMTP simulato e non inviano email reali.

## Login social

La guida completa è [SOCIAL_LOGIN.md](SOCIAL_LOGIN.md), disponibile anche da Web App → Login social. Google, Facebook e GitHub sono predisposti, con interruttore generale spento per default. Le credenziali effettive e la pubblicazione dell’app presso i provider devono essere predisposte dall’amministratore.

## Prove sul server installato

1. Con oltre 20 job controllare cambio pagina, 10/100 righe, ricerca di una voce vecchia e selezione fra pagine.
2. Disabilitare un job di prova non fatturato e confrontare report per utente/token, poi riabilitarlo; eliminare un altro job di prova verificando i filtri audit e la conservazione della traccia.
3. Verificare i totali modello contro le directory effettive dei servizi; distinguere modelli scaricabili da quelli scaricati.
4. Inviare la prova SMTP a una propria casella, poi verificare consegna e contenuto.
5. Abilitare un provider alla volta, testare da browser privato, conferma email Facebook, approvazione e TOTP. Solo credenziali e callback reali possono concludere la validazione dei provider.

La certificazione completa del server/GPU continua a dipendere dalle prove funzionali sull’hardware installato. Questo pacchetto non costituisce una nuova certificazione della misura fisica GPU.
