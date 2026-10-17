# Tempi GPU progressivi e worker AI — 0.3.0-r210

## Aggiornamento successivo: brani lunghi e annullamento

Vedere [docs/ACE_LONG_JOBS_AND_CANCELLATION_R210.md](ACE_LONG_JOBS_AND_CANCELLATION_R210.md)
per il timeout interno ACE di 600 secondi, il budget per task, la cancellazione
dall’Arranger e la cattura nel vero thread figlio della diffusione. La cattura
ACE ora riguarda `service_generate`; non comprende necessariamente le altre
fasi GPU del job. Anche questa modalità richiede una nuova prova hardware.

## ACE-Step: cosa cambia

La prova breve del 16 ottobre su Radeon 8060S/ROCm nel container Rocky ha
confermato 66,898005 secondi di attività kernel, completamento al 100%, chiusura
della finestra, aggiunta della traccia, riproduzione e persistenza dopo riapertura.
Quella prova validava il profiler a fine job. La nuova modalità **a finestre**
richiede una nuova prova hardware: non è ancora certificata per il billing.

Con il profiler ACE attivo, il collector tenta di chiudere una finestra ogni
cinque secondi, al successivo ingresso in un modulo PyTorch sul thread di
inferenza. Sincronizza la GPU, ferma il profiler, legge gli eventi kernel e
pubblica la somma delle finestre raccolte prima di iniziare una nuova cattura.
Le sovrapposizioni dentro ciascuna finestra sono unite; le finestre sono separate
da sincronizzazione/stop/start. Una variazione del dispositivo viene rifiutata.

Il collector non esporta tracce da un thread HTTP mentre la cattura è attiva.
Gli hook vengono rimossi alla fine anche dopo un errore. Un errore di profiling
non rilancia l'inferenza e non deve impedire la produzione audio.

L'adapter MTA legge il report opzionale anche durante il polling. La finestra
Arranger mostra `GPU: ~… s (kernel HIP; parziali; diagnostica, non fatturabile)`
quando esiste un campione positivo. Prima del primo campione mostra che la
profilazione è in corso. Non ricava secondi GPU dall'elapsed o dall'utilizzo
globale della scheda. Il risultato finale rimane consultabile riaprendo
l'Arranger dello stesso progetto, finché il job è conservato nella coda.

L'aggiornamento non è continuo: una singola operazione lunga, un modello compilato
che non attraversa hook Python o un runtime senza hook può lasciare il valore
fermo fino al checkpoint successivo o alla fine. Il profiling aggiunge overhead e
può influenzare compilazione e tempi. Le finestre escludono gli intervalli di
esportazione, le copie e le attività di runtime estranei a PyTorch: il risultato
è attività kernel osservata, **non accounting completo né esclusivo** del job.
Il limite di 64 MiB/un milione di eventi viene verificato per ogni traccia
esportata; le tracce temporanee vengono eliminate e non sono scaricabili.

## Attivazione ACE

Eseguire il normale ciclo commit/CI/Matrix/Publish e installare il nuovo RPM.
Non aggiornare o riavviare servizi mentre è in corso la prova lunga precedente.
Poi, quando ACE è libero, dentro il container Rocky:

```bash
python3 /usr/lib/mta-audio-editor-server/app/configure_ace_gpu_profiler.py --base /opt/mta
systemctl daemon-reload
systemctl restart mta-ace-step.service
systemctl status mta-ace-step.service --no-pager -l
```

Il primo test della nuova modalità deve essere breve, 10 secondi di audio:
controllare se i secondi GPU compaiono durante l'inferenza, attendere la chiusura,
riaprire l'Arranger per il valore finale e scaricare la diagnostica. Il tempo
dell'audio e il tempo di calcolo sono grandezze diverse. Se il runtime non espone
checkpoint utili, la raccolta finale resta il fallback.

Disattivazione quando ACE è libero:

```bash
python3 /usr/lib/mta-audio-editor-server/app/configure_ace_gpu_profiler.py --disable
systemctl daemon-reload
systemctl restart mta-ace-step.service
```

## Altri motori AI

La raccolta comune è integrata nel percorso dei **worker unificati**. Non cambia
automaticamente i backend locali legacy, Core ML, un servizio remoto privo di
questa integrazione o la configurazione dei modelli. Richiede PyTorch con ROCm
e l'attivazione esplicita dell'amministratore:

```text
MTA_AI_TORCH_PROFILER=true
```

Per i pacchetti server la variabile va aggiunta, senza cancellare le altre, a
`/etc/mta/mta.env`, quindi va riavviato `mta-server.service` quando non ci sono job.
Il percorso unificato deve essere già configurato secondo
[docs/AI_UNIFIED_WORKERS.md](../docs/AI_UNIFIED_WORKERS.md); la variabile diagnostica
non installa librerie, modelli, token o worker e non reindirizza i job locali.
Il virtualenv che esegue ciascun worker deve avere il relativo runtime ROCm.

| Backend unificato | Punto di raccolta / limite |
|---|---|
| Whisper Python | Nel processo che esegue il modello; il fallback CLI esterno non è coperto |
| Demucs | Wrapper del vero sottoprocesso `demucs.separate`, non del padre in attesa |
| SAM Audio | Wrapper del sottoprocesso SAM |
| Separazione cantanti SAM | Somma delle invocazioni sequenziali; dispositivo coerente richiesto |
| Chords ML | Eventuali operazioni PyTorch nel worker; altri runtime non coperti |
| Backing vocals | Eventuali operazioni PyTorch; non certifica componenti ONNX/altre librerie |
| DrumSep ONNX | Tempo GPU ONNX non misurato da questo collector; nessuna stima sostitutiva |

Un runtime non supportato o una cattura senza eventi non diventa un consumo GPU
zero verificato. I modelli non ancora provati su hardware restano da validare
singolarmente; i test automatici usano backend/eventi simulati.

Il server sovrascrive l'identità diagnostica con il vero ID ledger. I worker
scrivono solo un piccolo report atomico nella directory privata del job. Il
server ne valida identità, fonte, valori finiti, durata e dispositivo. Le copie
persistenti sono limitate a 512 job, separate dal ledger dei consumi; la lettura
restituisce gli ultimi 50 report con stato del job e tipo di motore.

L'amministratore può consultarli in **AI Billing → Attività kernel GPU · Diagnostica**
con il pulsante Aggiorna, oppure tramite:

```text
GET /api/admin/ai-billing/gpu-profiler
```

Il polling dei worker raccoglie i nuovi report a intervalli di almeno due
secondi. Non è un contatore nelle singole finestre legacy di separazione o
trascrizione. I report vengono inclusi anche nello ZIP diagnostico, sotto
`gpu_profiler_workers`. La finestra Arranger mostra invece direttamente il dato
ACE progressivo e finale. Nessun prompt, audio o trace raw è conservato qui.

## Billing e limiti ancora aperti

`gpu_seconds_estimated` e i report diagnostici non vengono aggiunti a `usage`,
alle attestazioni di consumo remoto o alle fatture. `gpu_metered` e
`billing_eligible` restano falsi per queste misure. CPU verificata dal worker e
CPU stimata del servizio ACE mantengono le loro distinte origini.

Restano da verificare su hardware: frequenza e stabilità dei campioni live,
overhead, inferenze lunghe, ciascun motore installato, cancellazione e concorrenza.
Completezza, attribuzione esclusiva ed eventuali runtime esterni richiedono
ulteriore lavoro prima di autorizzare il billing GPU. Non viene dichiarata la
certificazione completa del server. Versione mantenuta a **0.3.0-r210**.
