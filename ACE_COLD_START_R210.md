# r210 — avvio ACE lento e cancellazione involontaria

## Causa confermata dalla riproduzione

Il journal del tentativo `e65dbf78074846c59de9b0442958785a` mostra il caricamento
lazy dei modelli dopo l'accettazione del task ACE. Il controllo MTA viene
accettato durante questa fase; al successivo ricampionamento 44100 → 48000 Hz
il checkpoint solleva `TaskStopped: MTA ACE task cancelled`. ACE intercetta
l'eccezione nella preparazione dell'audio e la presenta come `Invalid source audio`.
Questo traceback non dimostra un WAV danneggiato.

La regressione era nell'adapter MTA: il POST che imposta il budget aveva un
timeout socket di soli tre secondi. Se l'API rimaneva occupata a caricare i
modelli, l'adapter falliva e il cleanup inviava automaticamente `cancel=true`
allo stesso task. Il successivo annullamento durante il ricampionamento era
quindi una conseguenza del fallimento della richiesta di controllo.

Il comportamento è stato riprodotto usando il sorgente esatto del precedente
archivio cumulativo (SHA-256
41cf55c9909e819758b32aef3b5f6cfce45ee82e0e82ebd2254be40ccbe4c1d6)
contro un vero server HTTP con risposta al controllo ritardata di 3,25 secondi:
TimeoutError e sequenza `cancel=false`, poi `cancel=true`, senza audio prodotto.
L'evidenza sintetica è in `validation/r210-cold-start-reproduction.log`.

## Correzione

- L'adapter attende fino a 30 secondi per una richiesta di controllo, con timeout
  ridotto quando il budget totale residuo è inferiore.
- Timeout di trasporto, errori temporanei di connessione e HTTP 429/502/503/504
  nelle richieste idempotenti di controllo/stato vengono ritentati mantenendo
  lo stesso ID. La configurazione immutabile del task può essere ritrasmessa
  senza estenderne la scadenza.
- L'upload `/release_task` viene eseguito una sola volta. Un suo errore ambiguo
  non viene ritentato automaticamente, per evitare generazioni duplicate.
- Durante l'attesa l'interfaccia riceve uno stato di backend temporaneamente
  indisponibile; nessuna percentuale o misura CPU/GPU viene inventata.
- HTTP 401/403 e gli errori di validazione restano bloccanti. Le compatibilità
  404/405 con il backend precedente sono conservate.
- Alla scadenza del budget effettivo l'adapter fallisce e richiede l'arresto del
  task, come prima. Il supervisore/cgroup conserva il proprio limite totale.
  La cancellazione esplicita continua a interrompere l'adapter e a inoltrare la
  richiesta ad ACE dal server, anche se il worker attende una risposta HTTP.

I retry riguardano soltanto controllo e polling: non rilanciano il modello, non
ricreano il job, non rendono fatturabile una misura incompleta e non resettano il
timer totale. L'API ACE è invariata rispetto al precedente pacchetto.

## Aggiornamento e prova sul server

Versione mantenuta a **0.3.0-r210**. L'archivio include integralmente il progetto
precedente, GPU live, worker unificati, timeout lunghi e pulsante Annulla.
L'ultimo commit utente rilevato è
`1c7f9724b06bdd77ecf4c2de11392646380a4ddf`; questo ciclo corregge l'adapter a
partire da quel lavoro. Non sono stati effettuati commit/push/tag/release.

1. Eseguire commit, CI, Matrix/Publish e installazione del nuovo RPM come di
   consueto, a job terminati. Conservare il launcher ACE già configurato.
2. Per verificare proprio il percorso che falliva, riavviare ACE a job terminati
   (`systemctl restart mta-ace-step.service`), attendere la disponibilità dell'API
   e lanciare come prima generazione una prova da 10 s con profiler attivo.
   L'attesa iniziale del modello non deve produrre un annullamento automatico.
3. Verificare chiusura automatica, traccia aggiunta, riproduzione, persistenza
   dopo riapertura e campioni GPU quando disponibili. Scaricare la diagnostica.
4. Provare una cancellazione volontaria, poi riprendere il test del brano lungo
   con limite di 60 minuti e verificare il superamento dei dieci minuti.

Non servono modifiche alla traccia originale, reinstallazioni dei modelli o
aggiornamenti dell'agente Proxmox per questa correzione. I controlli di misura e
il billing restano invariati: GPU diagnostica non fatturabile. Le prove su
ROCm, l'arresto dei kernel al checkpoint e il completamento del brano lungo
restano da validare sul server reale.

## Test di regressione

Il nuovo test HTTP reale ritarda il controllo oltre i vecchi 3 s e verifica la
produzione audio, un solo upload e nessuna richiesta di cancellazione. Esegue
sia il modulo Python sia il subprocess installato fuori dal package.
Altri casi simulano errori ripetuti di trasporto/503/429 durante controllo e
polling, il rispetto del budget breve e gli errori di autenticazione/validazione.
Le suite precedenti continuano a verificare cancellazione, API/ACL, profiling,
accounting e pubblicazione degli artefatti. Nessuna GPU ROCm è presente nel runner.
