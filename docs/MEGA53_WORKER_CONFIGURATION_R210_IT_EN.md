# Mega 53: configurazione del worker / Worker configuration

La separazione con Mega 53 usa il worker registrato `drumsep`. Se Demucs o le percussioni sono eseguiti su un server remoto, la configurazione di Mega 53 deve essere presente nel processo che esegue quel worker, non soltanto nel server o nell'app che avvia il job. Il worker deve essere registrato, autorizzato e attivo. Non viene installato né scaricato automaticamente alcun checkpoint.

Servono il checkout ufficiale Music Source Separation Training contenente `inference.py`, il file YAML associato a Mega 53 v1.0.21, il checkpoint originale verificato e un ambiente Python compatibile con dipendenze e acceleratore. Scaricare i componenti dalla [release originale v1.0.21](https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/tag/v1.0.21), verificando i diritti applicabili e i prerequisiti dell'installazione. Gli stem sono stime che possono sovrapporsi; la qualità non è stata certificata professionalmente in questo ambiente.

Esempio di sole impostazioni, con percorsi **da adattare** all'installazione:

```ini
MTA_MEGA53_ROOT=/opt/mta/mega53/Music-Source-Separation-Training
MTA_MEGA53_CONFIG=/opt/mta/mega53/model.yaml
MTA_MEGA53_CHECKPOINT=/opt/mta/mega53/model.ckpt
MTA_MEGA53_PYTHON=/opt/mta/mega53/venv/bin/python
```

`MTA_MEGA53_ROOT` deve contenere `inference.py`; YAML, checkpoint e interprete devono essere file regolari con percorsi assoluti, leggibili dall'utente che esegue il worker. Verificare il checkpoint tramite `sha256sum /percorso/effettivo/model.ckpt`: il valore previsto è `c62820893bbf86d4e734f966bd142d9157cfc8bb8e79e9d8f9ea553f3ff3519f`. Il percorso nell'esempio non installa né individua automaticamente il file. Su systemd l'installazione standard legge `/etc/mta/mta.env`; dopo aver configurato il servizio corretto, riavviarlo quando non vi sono job. In container, variabili e mount devono essere configurati nel container che esegue il worker. Non pubblicare token o il contenuto completo dell'ambiente di servizio nella diagnostica.

Per esecuzione nativa locale o worker unificato sullo stesso host, un controllo preliminare segnala la configurazione assente prima di avviare Demucs. Il controllo non presume di conoscere l’ambiente di un worker separato. Con metering cgroup, la diagnostica usa una categoria e un suggerimento fissi senza pubblicare percorsi; altri processi remoti possono restituire un errore generico e richiedere il controllo del loro journal. In nessun caso viene scelto silenziosamente un altro modello. Le richieste del server passano dal worker registrato e contabilizzato; la modalità nativa locale continua a usare il runtime locale. L'estrazione del gruppo drums/percussion usa il mix originale, mentre kick/snare/toms usano lo stem drums. Se si richiede solo percussion, non viene eseguita una seconda inferenza identica.

## English

Mega 53 uses the registered `drumsep` worker. The absolute upstream checkout (`MTA_MEGA53_ROOT`, containing `inference.py`), matching YAML (`MTA_MEGA53_CONFIG`), original v1.0.21 checkpoint (`MTA_MEGA53_CHECKPOINT`) and optional compatible interpreter (`MTA_MEGA53_PYTHON`) must be available to the process actually running that worker. A remote worker or container needs its own configuration and mounts. Verify the checkpoint using the SHA-256 above; no checkpoint is downloaded automatically. Restart the affected service after configuration when no jobs are running. The standard systemd environment file is `/etc/mta/mta.env`. No real-model inference or professional-quality approval is implied by the tests in this package.

Il fingerprint delle nuove campagne di benchmark comprende anche il runtime Mega 53 e l’adapter unificato locali: le campagne precedenti non certificano questa versione e richiedono una nuova campagna. Questo fingerprint locale non attesta il codice installato su un worker remoto.

## Checkpoint via web

In Amministrazione → Modelli AI è possibile caricare esplicitamente il checkpoint originale e verificarne SHA-256. Il file gestito viene pubblicato solo se la verifica riesce; un override `MTA_MEGA53_CHECKPOINT` ha precedenza e impedisce tale installazione. Questo passaggio non installa il runtime upstream o le dipendenze, né configura worker remoti. I percorsi presenti non dimostrano che l’inferenza funzioni.

In Administration → AI models, an administrator can explicitly upload and SHA-256 verify the original checkpoint. The managed file is published only after successful verification; an `MTA_MEGA53_CHECKPOINT` override takes precedence and prevents that installation. This does not install the upstream runtime or dependencies, or configure remote workers. Existing paths do not prove inference.

## Installazione guidata completa sul nodo locale / Guided local installation

In Amministrazione → Modelli AI, confermare le licenze, scegliere l’acceleratore e premere «Installa Mega 53». Il job scarica il commit sorgente fissato, lo YAML e il checkpoint v1.0.21 ufficiali, verifica le impronte e carica rigorosamente i pesi nell’architettura in un ambiente dedicato prima di attivarlo. Sono richiesti Git, Python, spazio disco e accesso Internet. Il download del checkpoint è di circa 1,37 GB, oltre a PyTorch e dipendenze; l’installazione può essere annullata. Gli override MTA_MEGA53_* impediscono l’attivazione gestita. La presenza del modello non certifica l’inferenza o la compatibilità GPU. Un worker remoto richiede configurazione e installazione sul nodo che esegue effettivamente il job; l’interfaccia del server centrale non lo configura da remoto.

In Administration → AI models, review the licenses, choose the accelerator and press “Install Mega 53”. The job checks out the pinned source, downloads the official v1.0.21 YAML and checkpoint, verifies their hashes and strictly loads the model in an isolated runtime before activation. Git, Python, storage and Internet access are required. The checkpoint download is approximately 1.37 GB, plus PyTorch and dependencies. Cancellation is supported. MTA_MEGA53_* overrides prevent managed activation. The strict load does not certify inference or GPU support. Remote workers must be configured on the execution node; the central web UI does not configure them remotely.
