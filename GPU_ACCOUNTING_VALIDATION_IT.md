# Validazione dei sensori GPU — AMD ROCm e NVIDIA

Il sensore diagnostico non equivale a un contatore completo e verificato per il billing. Per attribuire i consumi GPU a un utente occorre delimitare il job e i relativi processi, distinguere i client DRM duplicati, verificare la semantica dei contatori del driver e riconciliare il processo quando termina. I contatori di potenza dell'intera scheda NON si possono attribuire automaticamente all'utente, nemmeno se il suo job ha usato la GPU.

## Cosa eseguire sul server VM/LXC

Copia `scripts/gpu_accounting_probe.py` sul server e avvia, idealmente con lo stesso account di sistema del worker MTA:

```sh
python3 gpu_accounting_probe.py --duration 90 --interval 0.2 --output gpu-accounting-probe.json
```

Mentre il programma campiona, avvia dall'interfaccia MTA **un job AI GPU reale di 30-60 secondi**. Se sono presenti sia AMD sia NVIDIA, ripeti un job per ogni acceleratore; in più prova due job contemporanei di utenti diversi. Esegui anche:

```sh
uname -r
cat /proc/self/cgroup
ls -l /dev/kfd /dev/dri/renderD* 2>/dev/null
cat /sys/fs/cgroup/cgroup.controllers
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>/dev/null
rocm-smi --showdriverversion 2>/dev/null
```

Condividi `gpu-accounting-probe.json`, l'output dei comandi e indica soltanto: distribuzione/versione Linux, VM oppure LXC, modelli GPU e se il job è realmente riuscito. **Non inviare** `/etc/mta/*.env`, token API, password, file audio, nomi dei progetti o log contenenti segreti. Controlla il JSON prima di condividerlo.

## Criteri per abilitare la fatturazione

- Il processo del job e **tutti** i figli devono essere isolati in un cgroup v2 dedicato e terminare prima della lettura finale.
- Le metriche CPU provengono dal cgroup del job, non dall'host.
- I contatori GPU devono essere per client/processo e coprire il ciclo di vita completo, compresi i processi effimeri; i campioni di fdinfo da soli non lo garantiscono.
- VRAM è una grandezza di memoria, non tempo GPU. Energia per job non è derivabile in modo rigoroso dalla potenza totale della scheda condivisa.
- Per il disco si considerano esclusivamente i file persistenti attribuiti all'utente, mai temporanei/cache.
- In assenza delle garanzie sopra, GPU e energia rimangono **non fatturabili**; occorre un'integrazione specifica con strumenti e driver realmente disponibili sul server.
