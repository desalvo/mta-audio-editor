# Coda AI globale e billing GPU — 0.3.0-r210

Questa consegna conserva l'intero cumulativo e la revisione 210. Non effettua commit,
push, tag, release, installazioni sull'hypervisor/server o invii email reali.
La generazione ACE completa è stata confermata dall'utente; la nuova acquisizione
fatturabile deve ancora superare la prova sul suo hardware. I test sintetici
inclusi certificano le regole software, **non certificano l'hardware AMD**.

## Esecuzione comune

Web autenticato e applicazioni native remote utilizzano gli stessi adapter
registrati, la stessa coda FIFO persistente, il limite di concorrenza globale e
il ledger del server. Un'inferenza secondaria dentro un job che possiede già uno
slot lo riutilizza: non si accoda dietro se stessa. L'identità deriva dalla sessione
web oppure dal token server, mai dal piano del client. Le native mantengono un
solo token per istanza/server e utente, condiviso fra tutti i motori.

Sono coperti i protocolli per ACE-Step, Whisper/lyrics, chords, markers, Demucs,
SAM Audio, separazione cantanti, backing vocals e DrumSep. La scelta di modello,
le ancore SAM, le opzioni chords, il BPM e l'origine dei beat attraversano il
confine del worker. I runtime scelgono GPU quando il backend la espone; un backend
CPU non diventa un backend GPU tramite una semplice opzione. DrumSep seleziona,
fra i provider ONNX realmente installati, MIGraphX, ROCm, CUDA e CPU in quest'ordine.
I modelli, i relativi pacchetti opzionali e le licenze/checkpoint autorizzati
restano prerequisiti: configurare un adapter non installa né verifica i pesi.

Gli endpoint legacy di generazione sincrona restituiscono 409 sul server autenticato,
con indicazione di usare generate-jobs; non possono aggirare la coda. Le native
locali e la modalità di sviluppo esplicita MTA_ALLOW_INSECURE_NO_AUTH conservano
il comportamento locale precedente. Non usare questa modalità per un server a
pagamento. Un'ammissione remota orfana non viene rieseguita dopo un crash e non
blocca i job successivi. Per il recupero remoto usare una chiave idempotente.

Il ledger registra queue_job_id: riepiloghi e mail raggruppano i collegamenti,
senza aggiungere una seconda copia dello stesso consumo dalla proiezione della coda.
Le native possono leggere una ricevuta con il proprio token tramite
GET /api/ai-jobs/resources/{job_id}; il token di un altro utente non vi accede.
L'endpoint worker-capabilities espone adapter configurati e stato della calibrazione.

## Installazione dei runtime sul server

Dopo il normale Matrix/Publish e aggiornamento RPM, installare i pacchetti
opzionali nei runtime AI scelti, mantenendo i wheel Torch/ROCm già funzionanti.
requirements-lyrics.txt e requirements-chords.txt indicano le dipendenze del
progetto; SAM e audio-separator possono richiedere ambienti separati. Per Demucs
rimane disponibile native-installers/install_demucs.py con vincoli delle versioni
esistenti. Nessun installer modifica automaticamente i wheel ROCm per rendere
verde una dipendenza incompatibile.

Il nuovo helper verifica gli import nell'interprete scelto e aggiorna atomicamente
il file di ambiente, mantenendo proprietà e altre impostazioni. Esempio per i
runtime che risultano effettivamente installati nello stesso venv:

```sh
python3 /usr/lib/mta-audio-editor-server/native-installers/configure_ai_workers.py \
  --python /opt/mta/venv-ace-step/bin/python \
  --env-file /etc/mta/mta.env \
  --kinds whisper,chords-ml,markers,demucs
```

Non selezionare un motore prima di averne installato le dipendenze: il preflight
fallisce senza cambiare la configurazione. Ripetere l'helper con un altro Python
per SAM/singer-separation, backing-vocals o drumsep. Non occorre usare un unico
venv. Configurare MTA_AI_DRUMSEP_MODEL con il percorso del modello ONNX autorizzato.
I tre modelli karaoke già previsti dall'app mantengono gli stessi identificatori;
MTA_AI_VOCAL_MODELS_DIR seleziona la cache. I checkpoint SAM selezionabili hanno
identificatori facebook/sam-audio-{small,base,large}; l'accesso deve essere già
stato autorizzato dall'operatore. Riavviare mta-server a coda inattiva dopo aver
cambiato ambiente. ACE deve usare il wrapper ace_profile_server.py già previsto
dal ciclo precedente, con ACESTEP_QUEUE_WORKERS=1.

## Unità GPU e regole di fatturazione

La nuova sorgente gpu-kernel-verified utilizza gpu-kernel-union-v1: secondi ottenuti
dall'unione degli intervalli di esecuzione dei kernel GPU del task. Kernel
sovrapposti contano una volta; copie, API CPU, durata dello slot, elapsed e kernel
di controllo sono esclusi. Non è una misura di energia né di occupazione esclusiva
del dispositivo. Le stime amd-smi, DRM, agente Proxmox e profiler diagnostico
precedente restano separate e non autorizzano questo billing.

La cattura è continua, con controlli GPU prima/dopo e corrispondenza delle
correlazioni tra dispatch CPU e kernel GPU. Prove mancanti, alterate, scadute,
riutilizzate, multi-device, sovrapposte o incomplete vengono respinte. CUDA/HIP
graph launch e dispatch da thread non coperti non sono abilitati per questo metodo.
Una cattura oltre 64 MiB / un milione di eventi non viene fatturata. Uno zero
verificato richiede entrambi i controlli acquisiti: un contatore assente non è zero.
Ogni prova è firmata, vincolata al task, al runtime e alla calibrazione; il ledger
conserva digest, identificatore e prova, con controllo contro il riuso fra job.

La calibrazione conserva fingerprint Torch/HIP/CUDA/GPU/kernel/host e hash del
codice del sensore, con scadenza a 30 giorni. Un cambiamento invalida l'abilitazione.
La cattura verificata non dipende dall'interruttore della diagnostica. Un errore
del profiler dopo inferenza riuscita non ripete l'inferenza: consegna il risultato
senza inventare secondi GPU. Gli errori della vera inferenza restano errori.

**Limite attuale:** il provider integrato è ammesso per ACE-Step, Whisper Python,
Demucs, SAM, singer-separation e markers. Chords può invocare processi/modelli
esterni; DrumSep e audio-separator possono usare ONNX. Per questi runtime la GPU
può lavorare ma non si promuove una traccia Torch parziale o vuota a consumo
fatturabile. Restano accounting CPU verificabile e diagnostica; il loro sensore GPU
universale deve ancora essere integrato e validato. Non dichiarare quindi
completato il billing GPU di tutti i motori.

Con cattura continua il risultato GPU verificato arriva a fine acquisizione;
l'elapsed e le stime diagnostiche non diventano un aggiornamento live fatturabile.
Il precedente monitoraggio live diagnostico resta disponibile quando il provider
verificato non è attivo. La CPU del worker HTTP ACE misura quel worker, non l'intero
servizio ACE: la CPU del servizio resta una stima separata. Un cgroup del solo
client HTTP non include automaticamente un servizio systemd già avviato.

## Calibrazione e attivazione sul tuo server

Usare lo stesso account Unix e MTA_GPU_BILLING_ROOT (default
/var/lib/mta/gpu-billing) per calibrazione, worker e servizio ACE. La directory non
deve essere scrivibile da gruppo/altri; la chiave è privata, mode 0600. Se i
servizi girano con utenti differenti, non allargare i permessi della chiave: occorre
prima uniformare l'identità del sensore o implementare un servizio di firma dedicato.
I comandi seguenti assumono l'account dei servizi già adottato nell'installazione.

```sh
/opt/mta/venv-ace-step/bin/python \
  /usr/lib/mta-audio-editor-server/native-installers/gpu_verified_billing.py status

# A coda inattiva, nello stesso ambiente GPU del servizio ACE:
/opt/mta/venv-ace-step/bin/python \
  /usr/lib/mta-audio-editor-server/native-installers/gpu_verified_billing.py calibrate
```

Il comando esegue warmup, controllo negativo e tre carichi positivi. Exit 0 / ready
true abilita il provider compatibile; exit 2 lascia i consumi GPU non fatturabili.
È una calibrazione operativa iniziale: prima di applicare addebiti reali verificare
un job ACE breve, uno lungo, cancellazione e concorrenza, e confrontare i risultati
con una cattura di riferimento sul server. Controllare nelle ricevute sorgente
gpu-kernel-verified e prova presente. Un valore gpu_seconds da solo non basta.

La pipeline applica **le tariffe gpu_seconds già configurate** e il billing
abilitato per l'utente. Non modifica importi, non abilita utenti esclusi e non
emette fatture automaticamente. Se la tariffa è zero, il consumo viene contabilizzato
con importo zero. Non impostare gpu_energy_joules: questa misura non fornisce energia.
Se una risorsa GPU ha tariffa positiva ma manca la prova richiesta, la chiusura
del periodo si blocca; non viene creato un falso zero. Le prove già contabilizzate
restano utilizzabili per le fatture storiche anche quando la calibrazione scade.

```sh
# Disabilita solo le nuove catture verificate, conserva ledger/prove storiche:
/opt/mta/venv-ace-step/bin/python \
  /usr/lib/mta-audio-editor-server/native-installers/gpu_verified_billing.py disable
```

## Estensioni future

MTA_AI_ENGINE_REGISTRY_FILE punta a un JSON amministrato, assoluto, non symlink,
con massimo 64 nuove voci. I nomi built-in non si possono sovrascrivere da questo
file. Per ciascuna voce: kind (slug), executable assoluto, python opzionale,
gpu_capable booleano, label opzionale. Nessun piano/API può passare eseguibili.
Ogni nuovo adapter passa comunque per coda, token e ledger senza una nuova
allowlist nel client HTTP. Deve rispettare input privati, manifest e cancellazione.

Un adapter revisionato che copra integralmente il lavoro tramite il provider
continuo può dichiarare metering_method: gpu-kernel-union-v1 insieme a
gpu_capable:true e produrre le prove con profile_call/append_report. La sola
indicazione gpu_capable non abilita il billing. Altri runtime necessitano un
provider specifico; non basta firmare una stima o la durata dello slot.

## Prove ancora necessarie prima della certificazione del server

1. Installare il cumulativo e verificare adapter, dipendenze, checkpoint e ACL token.
2. Eseguire calibrazione reale e confronto della misura con riferimento AMD.
3. Provare ACE breve/lungo, cancellazione, crash e due utenti/token contemporanei;
   controllare risultato persistente, prove, contabilizzazione unica e fattura di prova.
4. Provare Whisper/chords/markers e ciascuna famiglia stems sul server e da native.
5. Verificare mail SMTP configurata e ZIP diagnostico scaricabile; qui non sono
   stati contattati servizi SMTP o il server di produzione.
6. Integrare/validare i provider mancanti prima di fatturare GPU ONNX/CLI esterne.

La precedente conferma dell'utente resta valida per generazione ACE completa,
chiusura finestra, aggiunta, riproduzione e persistenza della traccia. Non viene
estesa automaticamente alla nuova misura o a tutti gli altri modelli.
