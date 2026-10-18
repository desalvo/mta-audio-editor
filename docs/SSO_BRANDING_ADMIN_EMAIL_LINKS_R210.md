# SSO e collegamenti nelle email amministrative — r210

I pulsanti Google, Facebook e GitHub, visibili solo per i provider abilitati, includono il relativo marchio e stili distinti: Google chiaro, Facebook blu e GitHub scuro. I marchi sono distribuiti nel progetto e serviti da `/static/social/`: aprire il login non scarica immagini o SDK dai provider. I pulsanti hanno testo leggibile, dimensioni coerenti e focus da tastiera.

Il messaggio di registrazione SSO usa il nome del provider effettivo. La richiesta di conferma email dipende dallo stato reale dell’account, non da un testo fisso dedicato a Facebook. Un account già esistente ma non attivo riceve un messaggio di attesa; il controllo di approvazione, OAuth state, PKCE e secondo fattore non viene rimosso.

## Email e navigazione amministrativa

Le notifiche di richiesta approvazione, riattivazione e cancellazione privacy includono sia il collegamento assoluto nel testo sia un pulsante cliccabile nell’HTML. Le notifiche legacy di nuova registrazione e di avvenuta attivazione includono anch’esse il link pertinente. Il collegamento porta alla scheda Utenti e alla sezione corretta, evidenziando il record quando disponibile. Le vecchie email amministrative ancora in outbox ricevono il link al momento dell’invio, senza migrare o riscrivere i messaggi.

Esempi:

- `/settings?tab=users&section=pending&user=42`
- `/settings?tab=users&section=archives&user=42`
- `/settings?tab=users&section=users&user=42`

La base assoluta proviene da `MTA_PUBLIC_URL`; in sua assenza può essere usata la URL pubblica configurata per SSO. Le URL malformate o con credenziali, query o frammenti non vengono inserite nelle email. Se non esiste una base valida, rimangono le istruzioni testuali: non si inventa un hostname e non si usa l’Host ricevuto da richieste esterne.

Se non autenticato, l’utente viene portato al login e poi alla destinazione consentita, anche usando SSO e SSO con TOTP. La preferenza tecnica di navigazione usa il cookie HttpOnly `mta_login_next`, massimo 10 minuti, SameSite=Lax e Secure su HTTPS; non è una credenziale. Le informative IT/EN includono questo cookie. La destinazione è validata con una lista chiusa di pagine e parametri, anche dopo il login. Non sono accettate URL esterne o URL di API che eseguono azioni.

I link non approvano account, non cancellano dati e non saltano l’autenticazione, il ruolo admin, il secondo fattore o le conferme. Non sono stati aggiunti invii amministrativi a destinatari diversi da quelli già previsti dall’applicazione, né nuove email automatiche per eventi che prima non producevano notifiche.

## Provenienza dei marchi

I marchi appartengono ai rispettivi titolari e servono esclusivamente a identificare il metodo di autenticazione. Non implicano patrocinio di MTA.

- Google: `https://developers.google.com/static/identity/images/g-logo.png`; linee guida `https://developers.google.com/identity/branding-guidelines`.
- Facebook: `https://www.facebook.com/images/fb_icon_325x325.png`; risorse `https://www.meta.com/brand/resources/facebook/logo/`.
- GitHub: `GitHub Logos/SVG/GitHub_Invertocat_White.svg`, estratto senza modifiche da `https://brand.github.com/GitHub_Logos.zip`; linee guida `https://brand.github.com/foundations/logo`.

Il pacchetto cumulativo mantiene i documenti legali del ciclo precedente. Non è stato confermato un nuovo commit dopo quel ciclo; il messaggio commit suggerito comprende quindi anche privacy e termini IT/EN. La revisione dell’app resta **0.3.0-r210**.
