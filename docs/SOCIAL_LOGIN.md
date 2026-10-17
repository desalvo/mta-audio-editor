# Login social del server MTA Audio Editor 0.3.0-r210

## Abilitazione amministrativa

Il login social è **disattivato per default**, anche quando sono presenti vecchie credenziali OAuth nell’ambiente. Solo un amministratore può configurarlo in **Impostazioni → Web App → Login social**. L’accesso locale resta disponibile: conservare sempre un amministratore locale funzionante, password e secondo fattore di recupero.

1. Configurare DNS, certificato HTTPS valido e URL pubblico definitivo, per esempio `https://mta.apps.desalvo.eu`. Il browser deve poter raggiungere lo stesso dominio durante l’intero accesso. Non usare l’IP privato del container come callback pubblica.
2. Nel pannello MTA impostare **URL pubblico HTTPS**, senza percorso, query, credenziali o porta diversa da 443. Salvarlo lasciando il login social disabilitato. Il modulo mostrerà le callback da copiare esattamente nei provider.
3. Creare le applicazioni presso i provider seguendo le sezioni successive. Ogni server/ambiente deve usare credenziali e callback appropriate; preferire applicazioni separate per test e produzione.
4. Per ciascun provider desiderato inserire Client ID/App ID e Client secret/App secret, attivare il provider e infine l’interruttore generale. Salvare. Una configurazione abilitata con credenziali mancanti viene rifiutata senza modifiche parziali.
5. Provare da una finestra privata: `/login` e `/register` mostrano i pulsanti solo per provider abilitati e completi. Testare anche annullamento, callback errata e un utente che non sia sviluppatore dell’app provider.
6. Approvare il nuovo utente da **Impostazioni → Utenti** dopo l’eventuale verifica email. Il login social non conferisce il ruolo admin e non evita l’approvazione.

Le credenziali sono cifrate nel database con la chiave di autenticazione del server. Le API amministrative restituiscono solo l’indicatore di secret presente. Un campo secret vuoto conserva quello salvato; **Rimuovi secret salvato** lo elimina esplicitamente. Per rotazione, generare un nuovo secret presso il provider, salvarlo in MTA, provare l’accesso e revocare il precedente. Proteggere insieme database e chiave nei backup; senza chiave i secret salvati non sono recuperabili.

## Callback esatte

| Provider | Callback di esempio |
| --- | --- |
| Google | `https://mta.apps.desalvo.eu/oauth/google/callback` |
| Facebook | `https://mta.apps.desalvo.eu/oauth/facebook/callback` |
| GitHub | `https://mta.apps.desalvo.eu/oauth/github/callback` |

Sostituire il dominio con quello del proprio server. Mai wildcard. Schema, host, percorso e slash finale devono corrispondere alle callback mostrate da MTA. L’URL configurato in MTA prevale sull’host interno visto dal reverse proxy. Impostare anche `MTA_PUBLIC_URL` allo stesso URL per i link inviati via email. Preservare Host e schema HTTPS nel proxy; non pubblicare direttamente le porte interne del container.

## Google

Portali: [Google Cloud Console](https://console.cloud.google.com/) e [documentazione OAuth web server](https://developers.google.com/identity/protocols/oauth2/web-server).

1. Creare o selezionare un progetto dedicato. Aprire **Google Auth Platform** (in alcune interfacce: APIs & Services → OAuth consent screen).
2. In **Branding** inserire nome riconoscibile, email di supporto, contatto sviluppatore, home page e privacy policy del servizio. Configurare i domini autorizzati e verificarne il possesso quando richiesto dal portale. Il logo del provider è soggetto alle regole di branding Google.
3. In **Audience** scegliere l’audience corretta. Internal riguarda l’organizzazione Workspace prevista; External consente utenti esterni. Durante Testing aggiungere esplicitamente i test users autorizzati. Un login funzionante per il proprietario non prova l’accesso per tutti.
4. In **Clients** creare un OAuth client di tipo **Web application**, non Desktop/Android/iOS. In **Authorized redirect URIs** incollare la callback Google completa. Questo flusso server non richiede uno script Google né JavaScript origins aggiuntive.
5. In **Data Access** autorizzare solo `openid`, `email`, `profile`: MTA non richiede Drive, Gmail o accesso ad altri dati. Copiare Client ID e secret nel provider Google in MTA.
6. Per il pubblico completare i requisiti di pubblicazione/verifica indicati da Google e portare l’app nello stato appropriato. I requisiti dipendono dall’audience, dal branding e dagli scope: il salvataggio in MTA non pubblica l’app Google.
7. Attivare Google e il login social in MTA, salvare e provare. Un errore `redirect_uri_mismatch` richiede il confronto carattere per carattere delle callback; `access_denied` può dipendere da audience, test users o policy Workspace.

MTA usa authorization code con PKCE S256, scambia il codice sul backend e legge il profilo UserInfo via HTTPS. Accetta per Google solo email con `email_verified=true`. I token provider sono usati per il login, non sostituiscono i token AI MTA e non vengono conservati come token di accesso AI.

## GitHub

Portali: [Developer settings / OAuth Apps](https://github.com/settings/developers), [creazione OAuth App](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app), [web application flow](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps).

1. Accedere con il proprietario appropriato (account o organizzazione), aprire **Settings → Developer settings → OAuth Apps → New OAuth App**.
2. Compilare Application name, Homepage URL pubblico e descrizione. In **Authorization callback URL** incollare la callback GitHub mostrata da MTA. Per ambienti separati creare OAuth Apps separate.
3. Registrare l’app, copiare il Client ID e generare un Client secret. Trasferirli nel modulo GitHub in MTA; non inserirli in repository, log o frontend.
4. Non abilitare GitHub Device Flow per questa integrazione web: il meccanismo di autorizzazione delle native app AI MTA è distinto dal device flow GitHub.
5. MTA richiede soltanto `read:user user:email`, senza `repo`, amministrazione organizzazioni o permessi di scrittura. Legge le email verificate e preferisce quella primaria: non è necessario rendere pubblica l’email sul profilo GitHub.
6. Abilitare provider e interruttore generale, quindi provare il primo consenso e il successivo accesso. Eventuali restrizioni dell’organizzazione GitHub/SSO possono richiedere approvazione dell’organizzazione.

Il flusso usa authorization code e PKCE S256. MTA rilegge l’identità dal provider a ogni accesso. Un cambio di username GitHub non crea una nuova identità, perché il collegamento usa l’ID stabile del provider.

## Facebook / Meta

Portali: [Meta for Developers](https://developers.facebook.com/apps/), [Facebook Login web](https://developers.facebook.com/docs/facebook-login/web/), [sicurezza Facebook Login](https://developers.facebook.com/docs/facebook-login/security/).

Le denominazioni del portale dipendono dal tipo di app e dal relativo use case. La configurazione di accesso al pubblico, permessi e verifica va completata nel dashboard Meta: il solo switch MTA non la sostituisce.

1. Creare un’app Meta con un use case che supporti **Facebook Login per utenti web**. Non scegliere un prodotto limitato a un diverso flusso business/embedded. Associare l’eventuale business portfolio richiesto dal dashboard.
2. In **Settings → Basic** configurare nome, contatto, App Domains (solo il dominio), URL privacy policy e modalità/URL di eliminazione dei dati utente. Il servizio deve fornire realmente queste informazioni e un processo di eliminazione conforme alla propria policy; MTA non crea automaticamente pagine legali pubbliche né una callback di eliminazione Meta.
3. Aggiungere la piattaforma Website e il Site URL HTTPS. Nel prodotto Facebook Login abilitare **Client OAuth Login** e **Web OAuth Login**, mantenere HTTPS e la verifica stretta delle redirect URI quando disponibili.
4. Inserire in **Valid OAuth Redirect URIs** la callback Facebook esatta mostrata da MTA. Usare lo strumento di convalida della redirect URI del dashboard se presente. Non inserire soltanto la home page o una wildcard.
5. Copiare **App ID** come Client ID e **App Secret** come Client secret in MTA. Non usare Client Token al posto dell’App Secret. Gli endpoint Graph usano la versione predefinita assegnata all’app Meta: mantenerla supportata e ripetere i test quando Meta ne richiede l’aggiornamento.
6. MTA richiede `email,public_profile`. Controllare in App Review / Permissions and Features il livello di accesso richiesto per utenti esterni e completare le verifiche o revisioni indicate da Meta. In Development soltanto ruoli/test users autorizzati possono normalmente accedere; completare i requisiti e attivare la modalità pubblica prevista dal dashboard prima di aprire il servizio agli utenti reali.
7. Provare con un tester e poi con un account esterno. Se manca un’email utilizzabile, MTA rifiuta il profilo senza inventare indirizzi. Il provider può non restituirla per account senza email o consenso mancante.
8. Facebook non fornisce in questo flusso il flag Google `email_verified`: MTA richiede quindi la verifica tramite propria email **prima dell’approvazione e del login**. Configurare SMTP e provare l’invio dall’apposita pagina. Se la mail non arriva usare `/resend-verification` dopo aver corretto SMTP.

Una app funzionante solo con l’amministratore Meta non è pronta per il pubblico. Requisiti di review, business verification e disponibilità dei permessi vanno verificati nel dashboard corrente: la documentazione Meta può cambiare e non è stata interamente recuperabile durante questo intervento (risposta HTTP 429).

## Sicurezza, account e secondo fattore

La coppia `(provider, subject)` identifica l’utente. MTA **non collega automaticamente** un nuovo provider a un account locale o social con la stessa email: in quel caso utilizzare il metodo già associato. Disabilitare un provider non cancella identità, progetti, token o dati dell’utente; impedisce nuovi login tramite quel provider. Le sessioni già emesse seguono la normale durata/revoca.

Lo stato OAuth è legato a un cookie HttpOnly, scade dopo dieci minuti ed è monouso. Un secondo fattore TOTP già abilitato viene richiesto anche dopo il login social, prima di creare la sessione. Il challenge TOTP scade dopo cinque minuti ed è limitato a cinque tentativi. Gli account nuovi restano utenti non attivi finché approvati. Usare HTTPS reale e conservare un metodo locale di recupero amministrativo.

Le native app non devono ricevere i secret OAuth. Per usare le inferenze remote, accedere/registrarsi sul server, attendere l’approvazione e completare l’autorizzazione dell’istanza nativa AI MTA. I token AI restano associati all’utente e all’istanza; il login provider non attribuisce scope amministrativi o billing autonomi.

## Installazioni esistenti e variabili di ambiente

I valori legacy vengono letti come valori iniziali solo finché non è salvata la configurazione amministrativa. Il master switch resta spento per default: abilitarlo esplicitamente nell’interfaccia. Dopo il primo salvataggio il database è autorevole; modificare soltanto l’ambiente non cambia i provider salvati. Non committare secret reali in Compose, manifest Kubernetes o file di esempio.

```text
MTA_PUBLIC_URL=https://mta.example.com
MTA_OAUTH_GOOGLE_ENABLED=false
MTA_OAUTH_GOOGLE_CLIENT_ID=
MTA_OAUTH_GOOGLE_CLIENT_SECRET=
MTA_OAUTH_FACEBOOK_ENABLED=false
MTA_OAUTH_FACEBOOK_CLIENT_ID=
MTA_OAUTH_FACEBOOK_CLIENT_SECRET=
MTA_OAUTH_GITHUB_ENABLED=false
MTA_OAUTH_GITHUB_CLIENT_ID=
MTA_OAUTH_GITHUB_CLIENT_SECRET=
```

Docker Compose e i manifest di esempio conservano i flag false e credenziali vuote. Per Kubernetes usare Secret e un overlay locale, senza registrare i valori nel Git del progetto. Mantenere persistenti database e chiave auth tra aggiornamenti RPM/DEB/container.

## Verifica operativa e diagnosi

- Pulsante assente: controllare switch generale, switch provider, Client ID, secret presente e URL pubblico. Salvare e ricaricare `/login` in finestra privata.
- Callback non valida: confrontare l’URL mostrato da MTA con quello registrato, inclusi HTTPS e percorso. Non correggere aggiungendo wildcard.
- Login funziona solo per sviluppatori: controllare audience/test users Google, modalità e accessi Meta, policy GitHub/organizzazione.
- Profilo rifiutato: controllare email verificata Google/GitHub, email presente Facebook e account già registrato con la stessa email.
- Stato scaduto/non valido: riavviare da `/login` nello stesso browser; non copiare callback tra browser o riutilizzare il codice. Cookie e chiave auth devono rimanere stabili; sincronizzare l’orologio del server.
- Account in attesa: confermare l’email se richiesta e attendere l’approvazione amministrativa.
- TOTP: usare un codice corrente, controllare l’orologio dell’autenticatore; dopo cinque errori ricominciare il login.
- Test SMTP: il messaggio “accettato” verifica la sottomissione al server SMTP. Controllare anche inbox/spam, SPF/DKIM/DMARC e log SMTP per la consegna finale.

I test automatici simulano provider e SMTP. La validazione finale richiede credenziali reali, consenso, callback attraverso il proxy e consegna della mail sul server installato. Non si dichiara il login certificato senza queste prove.

## Ciclo di vita e MFA locale (aggiornamento r210)

Approvazione, richieste pendenti, notifiche durevoli, cancellazione, riattivazione, archivi e sandbox sono documentati in [ACCOUNT_LIFECYCLE_R210.md](ACCOUNT_LIFECYCLE_R210.md). Per le nuove registrazioni locali il secondo fattore è obbligatorio: può essere un codice email oppure Authenticator. Entrambe le verifiche precedono l’approvazione amministrativa. La cancellazione ordinaria conserva identità e storico centrale; la cancellazione totale privacy richiede una procedura amministrativa distinta.
