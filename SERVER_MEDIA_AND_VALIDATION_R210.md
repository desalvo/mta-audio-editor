# Server, media e validazione — 0.3.0-r210

Pacchetto cumulativo successivo a MTA-r210-native-ai-accounts.zip.
Versione e revisione invariate. Tutte le modifiche del ciclo precedente sono
incluse. Nessun commit, push, tag, release o intervento sul server eseguito.

## Import YouTube

L'errore Missing or unsafe media journal era dovuto al riuso della pipeline
asincrona delle tracce senza creare il suo journal prima della copia del download.
Ora l'import crea il journal sotto lock di progetto, registra l'identità dei
file e conserva l'originale con la stessa transazione usata dall'import audio.
Il journal viene riconciliato anche in caso di errore prima dell'avvio del worker.
Si rimuovono solo file posseduti dall'operazione e non pubblicati. Restano attivi
controlli di URL, dimensione, duplicati, autorizzazione e conferma dei diritti.

I test simulano il trasporto yt-dlp ma usano un WAV reale e la pubblicazione nel
progetto. Sul server aggiornato resta da provare un download YouTube effettivo:
restrizioni del servizio remoto e disponibilità del contenuto sono indipendenti
dal journal locale. Il pulsante Import Audio Track è rimosso dalla barra superiore;
il selettore nascosto resta collegato a Import Audio nella sidebar.

## Separazione stems sul web e GPU

La separazione web delle tracce e Import & Separate sono già ammesse alla coda AI
SQLite condivisa. Il problema di disponibilità era il rilevamento di Demucs solo
nel Python dell'applicazione server, che può differire dall'ambiente ROCm di ACE.

MTA_DEMUCS_PYTHON consente ora un interprete configurato esclusivamente
dall'amministratore. La disponibilità viene verificata con un import reale di
Demucs. Il processo usa quell'interprete senza shell o eseguibili scelti via API.
MTA_DEMUCS_DEVICE ammette auto, cpu o cuda; cuda è anche il nome del dispositivo
PyTorch nelle build ROCm. Auto lascia scegliere a Demucs in base al runtime.
Un ambiente Torch CPU continua a usare CPU; la sola presenza fisica di una GPU
non rende accelerata una build CPU.

Anche l'adattatore remoto Demucs e il suo profiler usano l'interprete configurato.
Il nuovo installer abilita soltanto l'adattatore Demucs del registro dei worker,
conservando i percorsi degli altri motori. I token esistenti dell'istanza nativa
restano condivisi: non viene introdotto un token aggiuntivo per gli stems.
Le native remote possono aprire la separazione anche senza Demucs locale.

Il recupero dei job accodati accetta gli hardlink del deposito condiviso MTA solo
quando corrispondono al blob con hash corretto e identità stabile. Hardlink
arbitrari, symlink e sorgenti non sicure restano rifiutati. Prima venivano respinti
anche i file legittimi promossi al deposito condiviso all'apertura del progetto.

### Attivazione sul server indicato dall'utente

Dopo aver costruito e installato il nuovo RPM/DEB, a coda AI vuota:

```bash
sudo python3 /usr/lib/mta-audio-editor-server/native-installers/install_demucs.py \
  --python /opt/mta/venv-ace-step/bin/python \
  --env-file /etc/mta/mta.env --device auto
sudo systemctl restart mta-server.service
```

Questo riutilizza il runtime ACE/ROCm esistente. Il prerequisito è un ambiente
Torch e Torchaudio funzionante e compatibile. L'installer installa Demucs 4.1.0
con vincoli sulle versioni di tutti i pacchetti già installati, inclusi Torch e
Torchaudio: in caso di conflitto si ferma anziché aggiornarli. Non sostituisce
una build ROCm con una CPU/CUDA. Può aggiungere le dipendenze mancanti compatibili.
Verifica l'import prima di aggiornare atomicamente il file di configurazione;
non sovrascrive modifiche concorrenti al file e non riavvia servizi da solo.
Il controllo dei payload RPM/DEB richiede anche questo installer nel pacchetto.
L'installer richiede accesso ai repository dei pacchetti; nessuna installazione
o connessione al server dell'utente è stata eseguita durante lo sviluppo.

Provare quindi Separa dal menu di una traccia esistente, verificare il job nella
lista AI, la creazione degli stems e la loro riproduzione dopo riapertura.
Provare anche coda dietro ACE, annullamento e un job accodato attraverso un riavvio.
L'accelerazione effettiva va verificata sul server: un test con processo simulato
non dimostra che Demucs funzioni su quella GPU o che i suoi consumi siano fatturabili.

## Uso reale dei file e cleanup

La lista File del progetto distingue ora:

- media utilizzati nella timeline, compresi gli asset referenziati tramite source_clip_id;
- clip di libreria riutilizzabili ma eliminabili quando nessuna traccia le usa;
- media riservati a un job o a una pubblicazione in attesa;
- originali e allegati conservati per scelta dell'utente e cancellabili esplicitamente.

Eliminare una traccia conserva ancora la clip riutilizzabile: è il comportamento
precedente e mantiene la possibilità di riutilizzarla. Quella clip non viene più
mostrata genericamente come file in uso. L'eliminazione esplicita del suo file,
quando non serve ad alcuna traccia/job, rimuove prima la voce di libreria in modo
durabile e poi elimina il media. Un errore di commit non autorizza la cancellazione.

Il nuovo comando Pulisci media inutilizzati richiede conferma, elimina le clip
di libreria inutilizzate e gli audio orfani, e pulisce i temporanei obsoleti.
Conserva originali, allegati, source MTA, media della timeline e input dei job.
Ricarica il progetto dopo l'operazione e azzera la cronologia relativa ai media
rimossi per non ripristinare riferimenti a file già eliminati.

All'apertura del progetto la manutenzione automatica elimina gli audio orfani e
i temporanei riconoscibili più vecchi di 24 ore, mantenendo la libreria intenzionale.
I temporanei vengono conservati mentre ci sono job/pubblicazioni attivi. Il GC
usa lo stesso lock di pubblicazione e ricontrolla i riferimenti prima dell'unlink.
I journal malformati non autorizzano pulizie distruttive. I job vecchi senza un
localizzatore preciso riservano conservativamente gli input del progetto finché
terminano; la riserva viene rilasciata con lo stato terminale. Non è una misura
di consumo né una dichiarazione che il file sia presente nella timeline.

La pulizia riguarda i file del progetto. I blob condivisi ancora referenziati da
altri progetti sono conservati; il rescan globale del deposito condiviso resta
l'operazione amministrativa esistente. Non si elimina automaticamente un originale
caricato dall'utente solo perché in quel momento non è rappresentato da una traccia.

## Stato della validazione del server

L'utente ha confermato la generazione completa della traccia AI Arranger sul
server. Si aggiunge alle conferme precedenti su generazione breve, annullamento,
chiusura della finestra, traccia aggiunta e riproducibile dopo riapertura, e
funzionamento del profiler. La CI verde e l'installazione RPM precedenti restano
confermate per quelle build, non per l'RPM ancora da costruire da questo ZIP.

Restano da verificare sulla nuova build:

1. Import YouTube reale; stems web su GPU/CPU e coda condivisa, annullamento,
   recupero dei job accodati dopo riavvio e persistenza/riproduzione degli stems.
2. Per la generazione lunga, se non già controllato: durata e riproduzione del
   risultato completo dopo chiusura/riapertura, stato terminale 100% e nessun worker
   rimasto attivo dopo completamento o annullamento.
3. Cleanup con progetto vuoto, clip riutilizzabili, duplicati e più progetti che
   condividono media; file della timeline e dei job preservati.
4. Download ZIP diagnostico dall'interfaccia aggiornata, CPU finale distinta da
   stime e GPU non disponibile/diagnostica identificata correttamente.
5. Token di due istanze dello stesso utente, isolamento fra utenti, report totali
   e per token; email SMTP di inizio/fine/annullamento/fallimento e riepiloghi delle
   funzionalità aggiunte nel pacchetto precedente.

Non si dichiara la certificazione completa sulla sola base dei test automatici.

## Misure GPU e billing: cosa manca

Il profiler funzionante e la generazione riuscita non modificano l'idoneità
contabile. I collector DRM campionati, l'agente Proxmox e le durate del profiler
sono esplicitamente diagnostici nel codice corrente. I loro valori restano
separati dalle misure verificate e non entrano automaticamente in fattura.

Per abilitare il billing GPU occorre ancora implementare e validare:

1. Una definizione della risorsa tariffata: tempo degli engine per processo,
   tempo cumulativo dei kernel HIP o una distinta unità di servizio. Le unità
   hanno significati diversi e richiedono tariffe/report coerenti.
2. Un provider autorevole per singolo job, con attribuzione dei processi/task,
   copertura dichiarata e raccolta fino a flush/sincronizzazione finale. Il token
   dell'agente da solo non certifica la completezza del contatore sottostante.
3. Prove controllate sul sistema reale: carico noto, generazione breve/lunga,
   job concorrenti e attività GPU estranea, reset, annullamento, crash e timeout.
   Campioni mancanti, contatore zero non verificato o profilo incompleto devono
   produrre misura non valida e nessun addebito GPU.
4. Persistenza dell'evidenza verificata nel ledger con fonte, unità e versione
   del metodo; gestione dei retry senza doppio addebito, audit e riconciliazione.
5. Integrazione e collaudo del provider su ogni motore interessato, inclusa la
   separazione web: entrare nella coda non equivale ad avere già metering verificato.
   Solo dopo si abilita la tariffa e si esegue una fattura di prova riconciliata.

Il codice rifiuta campi GPU fatturabili provenienti da fonti non ammesse. Questo
controllo resta attivo. Le quote GPU slot eventualmente disponibili sono stime
di allocazione del servizio, non misure hardware di utilizzo, e mantengono tale
qualifica. Non è stato abilitato nuovo billing GPU né modificata alcuna tariffa.
