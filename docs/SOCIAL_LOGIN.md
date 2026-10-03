# Social login: Google, Facebook e GitHub

MTA Audio Editor supporta OAuth 2.0 per Google, Facebook e GitHub. Tutti i provider sono **disabilitati per default**. Un pulsante social compare nelle pagine Login/Registrazione solo quando il provider è abilitato e sono presenti Client ID e Client Secret.

## Comportamento degli account

Al primo login social viene creato un utente `user` con `active=false`. L'indirizzo email è acquisito dal provider e considerato già verificato (`email_confirmed=true`), quindi non viene inviata la mail di verifica dell'indirizzo. L'utente vede una pagina che spiega che il profilo è in attesa di approvazione e non può entrare nell'applicazione. Un amministratore deve approvarlo da **Administration > Utenti**. Al momento dell'approvazione MTA Audio Editor invia automaticamente all'utente la mail di conferma dell'abilitazione. Se SMTP non è configurato, l'approvazione resta valida ma l'invio viene registrato come errore nei log.

Per gli account locali il flusso resta: registrazione -> email di verifica -> approvazione amministratore -> email di abilitazione. La verifica dell'email, da sola, non abilita l'account.

Per sicurezza MTA Audio Editor non collega automaticamente un nuovo login social a un account locale già esistente con la stessa email. Anche le identità social sono vincolate a `(provider, subject)` nel database.

## Variabili di ambiente

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

`MTA_PUBLIC_URL` deve essere l'URL HTTPS pubblico dell'applicazione, senza slash finale. In produzione è fortemente raccomandato perché determina in modo stabile le callback OAuth dietro reverse proxy/Ingress.

## Callback da registrare presso i provider

- Google: `https://mta.example.com/oauth/google/callback`
- Facebook: `https://mta.example.com/oauth/facebook/callback`
- GitHub: `https://mta.example.com/oauth/github/callback`

### Google

Creare un'applicazione/credential OAuth Web in Google Cloud, configurare la schermata di consenso e aggiungere la callback sopra tra gli Authorized redirect URIs. Impostare Client ID/Secret nelle variabili `MTA_OAUTH_GOOGLE_*`, poi porre `MTA_OAUTH_GOOGLE_ENABLED=true`. L'app richiede `openid email profile` e accetta solo email dichiarate verificate da Google.

### Facebook

Creare un'app in Meta for Developers, abilitare Facebook Login, configurare il Valid OAuth Redirect URI e rendere disponibile il permesso `email`. Impostare App ID come `MTA_OAUTH_FACEBOOK_CLIENT_ID`, App Secret come `MTA_OAUTH_FACEBOOK_CLIENT_SECRET`, quindi `MTA_OAUTH_FACEBOOK_ENABLED=true`. Se Facebook non restituisce un'email utilizzabile, la registrazione viene rifiutata senza creare un utente.

### GitHub

Creare una GitHub OAuth App e impostare Authorization callback URL alla callback indicata. Copiare Client ID e Client Secret nelle variabili `MTA_OAUTH_GITHUB_*`, quindi porre `MTA_OAUTH_GITHUB_ENABLED=true`. L'app richiede `read:user user:email`; se l'email pubblica non è disponibile usa l'elenco delle email verificate e preferisce quella primaria.

## Docker Compose

Le variabili sono già predisposte in `docker-compose.yml` e restano false/vuote per default. È sufficiente valorizzarle nell'ambiente o in `.env`, senza inserire segreti nell'immagine.

## Kubernetes

`k8s/base/secret.example.yaml` contiene le chiavi vuote per Client ID/Secret. Inserire i valori reali nel Secret usato dal Deployment. Nel manifest base i tre flag `*_ENABLED` sono `false`: impostare a `true` solo i provider desiderati (preferibilmente con un overlay Kustomize o manifest specifico dell'ambiente). Non committare i Client Secret reali.

## SMTP

Configurare **Administration > SMTP / SMTPS** per ricevere le notifiche di nuova registrazione e per inviare automaticamente all'utente la conferma quando l'amministratore approva il profilo. I login social non usano SMTP per verificare l'email.
