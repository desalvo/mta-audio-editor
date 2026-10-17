# Native AI, account remoti e notifiche — 0.3.0-r210

La revisione resta 210. Questo intervento si aggiunge integralmente al pacchetto
MTA-r210-ai-job-center.zip; non richiede di scartare le modifiche non ancora
committate del ciclo precedente. Non sono stati eseguiti commit, push o release.

## ACE-Step nelle applicazioni native

Selezionare Locale nell'Arranger autorizza l'installazione e avvia immediatamente
la preparazione in background: download del sorgente ACE-Step v0.1.8, ambiente
Python e dipendenze, avvio API e verifica HTTP di disponibilità. La finestra
mostra fase, avanzamento quando misurabile e output recente. Se la dimensione
totale non è disponibile, il progresso è indeterminato: non viene simulato.
Installato, processo avviato e API pronta sono stati distinti. Un avviso comunica
quando l'API è pronta. La preparazione continua anche chiudendo l'Arranger.

Il runtime uv è incluso nelle nuove build native; Git non è richiesto per il
download iniziale. L'archivio è limitato e validato contro percorsi esterni e
link simbolici. Il completamento dell'installazione viene registrato solo dopo
il successo di uv sync. L'arresto interrompe i processi posseduti dall'app e
invalida le operazioni di preparazione precedenti. Le installazioni parziali
possono essere riprese/riparate dalla sezione Esecuzione.

L'adattatore Python viene copiato dai sorgenti inclusi nella build in una
directory privata ed eseguito con il Python dell'ambiente ACE, evitando di
usare l'eseguibile GUI congelato come interprete. La scelta Locale conserva
l'abilitazione dell'adattatore. Il supervisore macOS non dipende più da /proc
Linux e non dichiara verificata una misura dell'albero processi non disponibile.
Questi casi contribuivano all'errore No trusted AI inference executable.

Gli avvisi di configurazione/errore e i dialoghi iniziali usano la lingua
corrente dell'app. I log originali di installazione mantengono la lingua degli
strumenti. Il pulsante i accanto a Intensità spiega la forza della trasformazione
e chiarisce che non è un controllo del volume.

API pronta non significa modello già caricato: il comando --no-init mantiene
il caricamento dei pesi al primo uso. Occorre una prova reale di generazione
per verificare modello, memoria, accelerazione e compatibilità della macchina.
È necessario ricostruire/installare i pacchetti nativi per ottenere uv e i nuovi
sorgenti inclusi; il solo aggiornamento del server remoto non aggiorna l'app.

## Un account e un token per istanza nativa

Nella connessione remota si specifica il server MTA HTTPS. L'app crea una richiesta
temporanea e apre il browser sul server: login o registrazione, quindi approvazione
esplicita dell'istanza. La richiesta scade dopo 15 minuti. Restano obbligatorie
verifica email e attivazione dell'account previste dal server. Il codice non
permette di aggirarle. In caso di scadenza si avvia una nuova richiesta.

Il token è conservato in un file privato dell'app e condiviso dai motori impostati
in modalità remota. Non viene esposto nell'interfaccia né salvato nel browser.
La riconnessione della stessa istanza revoca il precedente token di quell'utente;
due istanze diverse ricevono token distinti. La rotazione amministrativa conserva
l'identità dell'istanza. Si possono consultare e revocare i propri token dal profilo.
I vecchi collegamenti manuali restano compatibili, ma il nuovo flusso non richiede
di incollare chiavi diverse per ogni motore.

Le richieste usano l'esecuzione AI con accounting del server: i token ottenuti
dal nuovo flusso non possono aggirarla tramite il proxy ACE grezzo. Il token è
associato all'utente; non concede accesso amministrativo o a consumi di altri
utenti. Il riepilogo combina le istanze e mantiene il dettaglio per token.
È conservato il limite di 32 MiB del trasporto WAV remoto; il rendering ACE usa
l'intervallo selezionato. Le altre regole di sicurezza e isolamento restano attive.

## Email e riepiloghi

Il servizio raccoglie in modo persistente inizio effettivo e stati terminali
completato, fallito, annullato o interrotto dei job associati a utenti del server.
Con SMTP/SMTPS configurato e destinatario attivo con email verificata, invia
messaggi HTML con logo MTA incorporato, versione, server, identificativo del job,
token quando presente, stato, orari UTC, risorse e importo anche se zero.
Non include prompt, segreti o errori grezzi nei messaggi.

L'invio avviene in background e non impedisce la generazione. Gli errori SMTP
vengono ritentati con attese crescenti. La consegna è almeno una volta con
Message-ID stabile: un arresto dopo l'accettazione SMTP e prima della conferma
locale può produrre un duplicato. Non viene garantita la consegna da parte del
provider o del destinatario. L'attivazione non invia in massa lo storico precedente.
Senza SMTP non partono notifiche; un job locale offline senza account del server
non ha un destinatario server cui inviare una mail.

Dal profilo/account e dalla pagina Billing si configurano lingua e cadenza del
riepilogo: eredita dal server, giornaliera, settimanale, ogni 30 giorni o disattivata.
In Amministrazione, scheda Utenti, si impostano il default server (settimanale)
e gli override per utente. Disattivare il riepilogo non disattiva le email dei job.
Il primo intervallo parte dall'attivazione/configurazione; il riepilogo include i
job conclusi nel periodo, anche quando erano iniziati nel periodo precedente.

Le nuove viste e mail riepilogano i consumi di calcolo. Gli importi sono stime,
non fatture: storage persistente e altre componenti di servizio restano nei
report/fatture ufficiali Billing. I consumi dei diversi token sono separabili.
Il billing disabilitato per l'utente produce importo zero, conservando il consumo.
Solo dati e fonti già ammessi dalle regole di metering possono contribuire agli
importi. Le stime ACE/profiler GPU sono conservate separatamente, visibili e
sempre non fatturabili. Nessuna abilitazione automatica del billing GPU.

## Collaudo operativo richiesto

1. Su una nuova build macOS/Windows scegliere Locale e seguire installazione,
   avvio e avviso API pronta. Provare arresto, ripresa e riavvio dell'app.
2. Generare una prova breve, controllare la traccia e riaprire il progetto.
   Ripetere una prova lunga fino al completamento e verificare annullamento.
3. Collegare un server indicando solo l'URL; completare login/registrazione e
   approvazione nel browser. Provare ACE e un altro motore remoto e controllare
   lo stesso token nell'accounting. Ripetere con una seconda istanza e verificare
   totale utente e dettaglio per token, quindi la revoca.
4. Configurare e verificare SMTP/SMTPS nella sezione server esistente; impostare
   MTA_PUBLIC_URL all'URL pubblico per identificarlo nelle email. Controllare email
   di inizio/fine/cancellazione/fallimento, risorse e importo zero. Provare un
   errore SMTP controllato e il successivo recupero senza perdita del job.
5. Impostare una cadenza breve per il collaudo dei riepiloghi e verificare default
   server, override utente/admin, periodo UTC e dettaglio fra le istanze.

Non sono state effettuate nuove inferenze hardware, installazioni native reali,
invii SMTP di produzione o modifiche al server in questo ambiente. I test usano
trasporti isolati, processi locali di prova e il JavaScript di produzione. Non si
dichiara completata la certificazione funzionale del server o delle build native.
