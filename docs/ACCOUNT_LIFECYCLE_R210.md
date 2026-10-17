# Account, SSO, secondo fattore e conservazione — 0.3.0-r210

## Registrazione e approvazione

Google, Facebook e GitHub autenticano tramite i flussi SSO/OAuth dei provider già documentati in [SOCIAL_LOGIN.md](SOCIAL_LOGIN.md). Il provider prova l’identità; l’abilitazione su MTA è una decisione amministrativa distinta. I nuovi account non possono accedere né ottenere token AI finché non sono approvati. I nuovi account social restano inizialmente non attivi. Facebook richiede la conferma email MTA se il provider non certifica l’indirizzo.

Per la registrazione locale dalla pagina `/register`:

1. Inserire username, email e password. La pagina controlla la disponibilità durante la digitazione e blocca l’invio in caso di collisione o verifica non completata. Il backend ripete il controllo e applica vincoli/transazioni: JavaScript non è un controllo di sicurezza sufficiente.
2. Scegliere il secondo fattore: **codice via email** (predefinito) oppure **app Authenticator TOTP**.
3. Aprire il link di verifica email. Solo dopo questa verifica si può accedere alla configurazione del secondo fattore.
4. Per email richiedere e inserire il codice monouso ricevuto. Per TOTP scansionare il QR o inserire la chiave manuale nell’Authenticator e verificare un codice valido.
5. Dopo le due verifiche la richiesta diventa approvabile. L’utente riceve la comunicazione di attesa e gli amministratori ricevono la richiesta via email. La pagina di successo non crea una sessione.
6. In Impostazioni → Utenti gli admin consultano la lista dedicata **Registrazioni e riattivazioni pendenti**, verificano gli stati e approvano. L’utente riceve una comunicazione di approvazione.

Il codice email dura 10 minuti, vale una sola volta, consente al massimo cinque tentativi e può essere reinviato dopo almeno 60 secondi. In archivio viene conservato un HMAC del codice; i corpi delle notifiche inviate sono svuotati. SMTP deve essere configurato e funzionante per usare questo metodo. I messaggi temporaneamente non inviabili restano nella coda durevole e vengono ritentati. La prova SMTP nelle impostazioni consente di verificare il relay; controllare anche la ricezione finale.

Per accedere con password e secondo fattore email, compilare credenziali e premere **Invia codice email**, poi inserire il codice nel campo secondo fattore e premere **Accedi**. Un codice non sostituisce la password. Per TOTP utilizzare il codice dell’app; i due metodi sono alternativi. I requisiti obbligatori valgono per le nuove auto-registrazioni locali, senza rendere inaccessibili gli account preesistenti privi di enrollment. Un TOTP obbligatorio non può essere disattivato semplicemente dalle impostazioni del profilo.

Se il link di enrollment è scaduto o è stato perso, usare **Reinvia conferma email** dal login: per una registrazione con email già verificata ma secondo fattore incompleto viene inviato un nuovo link. I link di enrollment scadono e sono consumati al completamento. I tentativi TOTP del link sono limitati.

## Identità riservate

Username ed email sono univoci, compresi gli account cancellati/disattivati. Non viene creato automaticamente un altro account con la stessa identità. Le identità storiche sono riservate con HMAC legati alla chiave del server, anche dopo la rimozione totale del record utente: non vengono riutilizzate da un nuovo account. Questi digest non sono credenziali e non consentono di scaricare dati o accedere al servizio.

Anche la modifica email riserva il vecchio indirizzo e quello in verifica; gli altri utenti non possono registrarsi con una delle identità riservate. Le conferme e i link vengono inviati al titolare, senza esporli nella risposta pubblica. Le verifiche pubbliche di disponibilità sono intenzionali e richieste dal modulo di registrazione.

## Cancellazione ordinaria

Dal profilo, un utente non amministratore può richiedere la cancellazione digitando il proprio username e confermando. Può anche segnalare la richiesta privacy all’amministratore. Gli admin possono disattivare/cancellare un utente normale dalla lista utenti; questa azione non è più una DELETE SQL distruttiva.

La cancellazione ordinaria:

- Disattiva l’account, revoca sessioni e token AI/modelli e mantiene il record centrale e lo storico di billing/accounting.
- Richiede la cancellazione dei job AI ancora attivi; l’archivio viene creato quando non ci sono più elaborazioni attive. Se un worker sta terminando, la preparazione viene ripresa dal servizio periodico.
- Invia subito la comunicazione di disattivazione e della data limite; un secondo messaggio comunica il link quando l’archivio è pronto.
- Produce uno ZIP con i progetti portabili `.maeproj` e i relativi media, tramite il percorso di esportazione verificato già usato dall’app. L’archivio viene pubblicato solo dopo la chiusura del file completo.
- Crea una URL statica riservata con token casuale, utilizzabile dall’utente disattivato senza una nuova sessione. **Chi possiede il link può scaricare i progetti:** non inoltrarlo. Il download non è indicizzabile e usa intestazioni senza cache e senza referrer.
- Consente di richiedere una copia e di scaricarla fino alla data comunicata. Al termine del grace period elimina progetti e archivio; il download risponde 404 anche prima del passaggio del worker se è già scaduto.

Impostare `MTA_PUBLIC_URL` al dominio HTTPS pubblico effettivo perché i link nelle email siano assoluti e corretti dietro proxy. La sezione admin dedicata mostra gli archivi, le URL ancora valide, le scadenze e le richieste privacy. Gli amministratori non possono usare questa funzione per cancellare il proprio account amministrativo; occorre preservare un accesso amministrativo funzionante.

## Riattivazione

Dalla pagina login aprire **Riattiva account cancellato/scaduto** e inserire email o username. La risposta pubblica rimane generica. Il titolare riceve un link monouso; dopo la conferma la richiesta compare tra quelle pendenti ed è comunicata a utente e amministratori.

L’approvazione riattiva lo stesso account e lo stesso storico. Non riabilita i vecchi token e invalida i link degli archivi di recupero. Se i progetti non erano ancora stati eliminati restano disponibili; se il grace period è già trascorso, la riattivazione non li ricrea. Una richiesta ancora in attesa non proroga la scadenza dei progetti.

La riattivazione riguarda gli account conservati dalla cancellazione ordinaria. La cancellazione totale confermata è distinta e non ha un ripristino automatico dalla sandbox.

## Cancellazione totale e sandbox privacy

L’azione è amministrativa e separata dalla cancellazione ordinaria. Prima cancellare/disattivare l’account e attendere che l’archivio sia pronto. L’interfaccia richiede lo username esatto e **due conferme successive**. Il server impone conferme monouso, con scadenza e legate a admin, account e modalità: non basta inviare un booleano nel primo POST.

- **Totale senza dati contabili**: consentita soltanto se non esistono record di utilizzo, compute, fatture o campioni storage associati. In caso contrario viene rifiutata.
- **Privacy con quarantena**: rimuove il record account e i dati contabili dal database centrale attivo, comprese le fatture associate richieste esplicitamente dall’operazione. I report correnti non vedono più tali dati. Questa azione non va confusa con l’esclusione di singoli job nella Coda AI, che protegge le fatture già chiuse.
- Prima della rimozione, i dati contabili, le relative prove e gli intenti di settlement vengono salvati in un file privato cifrato. I dati di autenticazione, le sessioni, i token e i secret MFA non vengono conservati come materiale di recupero dell’account.
- Le righe collegate vengono individuate tramite ownership, collegamenti job e chiavi esterne, per comprendere anche estensioni delle tabelle contabili. Nessun altro account viene eliminato a causa di un collegamento amministrativo di approvazione.
- La pulizia dei database della coda, degli intenti contabili e delle cache dei risultati ha una consegna durevole da riprendere dopo un’interruzione. Un errore durante la transazione centrale non lascia un file sandbox non committato.
- Il grace period dei progetti resta separato: archivio e dati di consegna rimangono disponibili fino alla loro data limite, anche se il record account è già rimosso. Non vengono cancellati anticipatamente dalla quarantena contabile.
- La sandbox scade dopo **N giorni**, predefinito **365**. I progetti scadono dopo **X giorni**, predefinito **60**. Entrambi sono configurabili in Impostazioni → Utenti, con valori interi tra 1 e 3650. Le nuove impostazioni si applicano alle cancellazioni future: non cambiano silenziosamente le date già comunicate.

La cancellazione automatica riguarda i dati gestiti dall’applicazione. Le copie eventualmente create da backup esterni del database o del filesystem hanno una propria gestione e non vengono modificate da MTA. Questa funzione descrive il comportamento tecnico e non dichiara una conformità legale automatica.

## Esecuzione periodica e sicurezza operativa

Il servizio account parte con il server, opera a intervalli di circa un minuto e riprende la preparazione degli archivi, la pulizia pendente, le scadenze e l’invio delle notifiche. Gli archivi usano un claim SQLite per evitare doppia preparazione con più processi server. I file di retention risiedono in `.account-retention` nella directory dati, con directory 0700 e file 0600. Non collocare questa directory sotto un document root pubblico.

Non è necessario cambiare la revisione o creare nuove release per modificare le scadenze dalle impostazioni. Le native app in modalità locale a utente unico non espongono le funzioni amministrative/account del server.

## Prove dopo l’installazione

1. Registrare un utente locale con email MFA, verificare collisioni case-insensitive, email e OTP; tentare l’approvazione prematura e verificare il rifiuto. Ripetere con Authenticator.
2. Controllare le email di attesa agli utenti, le richieste agli admin, la lista pendenti e l’email dopo approvazione. Provare il successivo login e il rifiuto di codici riutilizzati/scaduti.
3. Registrare un utente SSO reale: consenso provider, approvazione MTA distinta e notifiche. Per Facebook verificare l’eventuale passaggio di conferma email.
4. Cancellare un utente di prova con progetti e consumi. Verificare revoca token, conservazione dei totali contabili e download portabile dalla mail e dalla lista admin.
5. Richiedere la riattivazione, approvarla e verificare che i vecchi link/token non tornino validi.
6. Su dati di prova eseguire la cancellazione privacy con entrambe le conferme e controllare la scomparsa dai report attivi e la presenza della sandbox con la scadenza prevista.

I test automatici simulano SMTP e provider. Consegna email, URL attraverso l’Ingress, SSO reale e ripristino di un progetto esportato vanno provati sul server installato. Le nuove funzioni non certificano nuovamente l’hardware o la misura GPU.
