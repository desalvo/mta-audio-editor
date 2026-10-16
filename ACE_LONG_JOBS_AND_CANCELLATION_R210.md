# ACE-Step: brani lunghi e cancellazione — 0.3.0-r210

Aggiornamento: [avvio lento e cancellazione involontaria](ACE_COLD_START_R210.md)
corregge il timeout HTTP breve introdotto nel controllo del task. Le richieste
idempotenti di controllo/stato vengono ora ritentate entro il budget totale.

## Analisi della prova lunga

Il job `5011abc47294421fb153577ba3d6cf76` è fallito dopo 608 secondi,
nonostante il limite Arranger di 60 minuti. Lo ZIP ricevuto contiene soltanto
`ace_adapter_failed`, senza errore upstream dettagliato: non consente di
provare retroattivamente quale eccezione interna abbia causato quel job.

Il sorgente ACE-Step v0.1.8, commit fissato dall'installer MTA
`dce621408bee8c31b4fcf4811682eb9359e1bc94`, contiene però il limite indipendente
`ACESTEP_GENERATION_TIMEOUT`, predefinito a **600 secondi**, in
`acestep/core/generation/handler/generate_music_execute.py`. La funzione attende
il thread `service-generate` con `join(timeout=...)`, poi solleva TimeoutError
senza terminare quel thread. Questo difetto è coerente con il fallimento dopo
circa dieci minuti e con la GPU che continua a lavorare per qualche istante.
Non è evidenza sufficiente per diagnosticare esaurimento di memoria GPU.

Fonte upstream:
https://github.com/ace-step/ACE-Step-1.5/blob/v0.1.8/acestep/core/generation/handler/generate_music_execute.py

## Correzione

Il launcher MTA imposta un tetto tecnico finito di 14.520 secondi (240 minuti più
120 secondi di margine) prima di importare ACE, e ricrea le route prima
inizializzazione affinché anche il limite della query non resti a un'ora.
Questo tetto non sostituisce il limite del job: l'adapter trasmette il valore
scelto nell'Arranger, da **1 a 240 minuti**, al controllo del singolo task.
Il supervisore MTA conserva il proprio limite totale; l'adapter riserva fino a
due minuti al download prima della sua scadenza. Non si elimina alcun watchdog.

Il tempo per task viene controllato all'ingresso/uscita dell'inferenza e ai
checkpoint dei moduli PyTorch. La configurazione di un task è immutabile: un
secondo aggiornamento non può prolungarne il budget. Il controllo copre il
thread principale e il vero thread GPU; non usa thread injection o kill del
servizio condiviso. La tabella dei controlli è limitata a 512 task.

Nuove API ACE, con la stessa autenticazione upstream:

- `GET /mta/runtime`: capacità del runtime, limiti e modalità cooperativa.
- `POST /mta/tasks/{task_id}/control`: budget oppure richiesta di cancellazione.

Queste API si riferiscono a ID di task validati e non accettano PID, comandi o
percorsi. Non vanno esposte direttamente al browser.

L'adapter registra l'ID ACE nel piccolo sidecar privato del job. Se fallisce
richiede l'annullamento ad ACE. Se viene terminato dal supervisore/cgroup, è il
processo server a leggere il sidecar e inviare tale richiesta. Il servizio ACE
non appartiene al cgroup dell'adapter: uccidere solo quest'ultimo non bastava.

Gli errori upstream vengono classificati usando messaggi fissi (timeout interno,
memoria GPU, errore backend, controllo rifiutato) anche nello ZIP diagnostico.
Non si conservano prompt o messaggi di errore remoti arbitrari.

## Pulsante nell'Arranger

Per un job in coda, bloccato o in esecuzione, il pulsante diventa **Cancel job /
Annulla job**. Funziona anche riaprendo l'Arranger o dopo un refresh. Dopo il click
mostra **Cancelling job / Annullamento in corso**, impedisce richieste duplicate
e continua a leggere lo stato del server. Al termine torna alla generazione.

L'API browser è
`POST /api/projects/{pid}/ai-arranger/generations/{job_id}/cancel`:
richiede autenticazione, intestazione di integrità della richiesta e accesso al
progetto. Rifiuta job di altri progetti o operazioni diverse da Arranger/Remix.
Resta valida anche l'API di annullamento amministrativa già esistente.

Una cancellazione impedisce la pubblicazione di una nuova traccia e non rende
fatturabile un risultato incompleto. Lo stato del worker MTA annullato non è una
certificazione che ogni kernel GPU sia già terminato: il servizio ACE arresta il
lavoro al prossimo checkpoint utile. Un singolo kernel lungo o un modello
compilato può ritardarlo fino al ritorno in Python. L'interfaccia lo segnala.
Se il backend non possiede le nuove API (404/405), MTA scarta comunque il
risultato ma non può garantire l'arresto del servizio remoto. Non ferma altri job.

## GPU live

ACE esegue la diffusione in un thread figlio `service-generate`. La cattura viene
ora avviata in quel thread: i campioni progressivi e stop/export del profiler
appartengono al thread che esegue il modello. Si profilano i kernel osservati
nella fase `service_generate`; altre fasi (preparazione, codifica/decodifica
esterna) possono non essere incluse. Non è accounting GPU completo o esclusivo.
Il comportamento senza handler compatibile mantiene il fallback precedente.
I secondi restano diagnostici, mai consumi GPU verificati o fatturabili.

## Installazione e prova sul server

Completare il normale ciclo commit, CI, Matrix/Publish e installazione RPM.
Non eseguire aggiornamenti mentre un job è attivo. Non serve reinstallare modelli
né modificare il sorgente ACE. Quando tutti i job sono terminati, nel container:

```bash
python3 /usr/lib/mta-audio-editor-server/app/configure_ace_gpu_profiler.py --base /opt/mta
systemctl daemon-reload
systemctl restart mta-ace-step.service
systemctl restart mta-server.service
```

Il launcher usa ora controllo task e profiler insieme. Se la configurazione
upstream richiede una API key, verificarne la presenza anche nella configurazione
client MTA; non pubblicarla né incollarla nei log condivisi.

1. Ricaricare il browser: generazione breve (10 s), contatore GPU, chiusura
   automatica, traccia riproducibile e persistente dopo riapertura.
2. Avviare una generazione e premere **Annulla job**. Verificare che il pulsante
   passi per l'annullamento, che non venga aggiunta una traccia e che il carico
   GPU si fermi dopo il successivo checkpoint. Riavviare una generazione breve.
3. Ripetere il brano lungo con 60 minuti, controllando il superamento dei dieci
   minuti e il risultato finale. Scaricare lo ZIP sia in caso di successo sia
   di fallimento. Nessuna certificazione della prova lunga è già acquisita.
4. Per verificare il budget ridotto, impostare 1 minuto su un lavoro più lungo:
   deve fallire per timeout senza pubblicare la traccia. Il timeout totale
   comprende upload/elaborazione/download, non la durata del brano.

La procedura aggiorna il launcher anche sulle installazioni già esistenti, senza
sovrascrivere le altre variabili del servizio né richiedere una reinstallazione.
Disabilitare il launcher con `configure_ace_gpu_profiler.py --disable` rimuove
anche il controllo task: il backend originale torna ai propri limiti.

## Validazione e limiti

Test automatici: superamento simulato dei 600 s, budget finito/immutabile,
cancellazione prima e durante l'esecuzione, vero thread figlio, cleanup hook,
autorizzazione API e integrità richiesta, sidecar dopo kill del subprocess,
consegna HTTP reale al backend simulato, classificazione sicura e pulsante UI.
Le prove CPU non certificano arresto, prestazioni o profiling su ROCm.
La generazione lunga, la cancellazione e i nuovi campioni GPU sul server reale
restano da validare. Il billing GPU rimane disabilitato; nessun allentamento dei
controlli cgroup, del ledger o delle misure valide.
