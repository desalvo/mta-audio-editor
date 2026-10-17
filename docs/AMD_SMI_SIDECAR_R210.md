# AMD-SMI affiancato su gwads07 — r210

Il collector di produzione continua a usare AMD-SMI Debian 6.1.2. Questo
strumento prepara una **prova separata** di AMD-SMI 26.2.2 dal tag ROCm 7.2.4,
commit `97f5574fe2fdc7bef44fb01545347912ee9f1779` del repository ufficiale
[ROCm/rocm-systems](https://github.com/ROCm/rocm-systems/tree/97f5574fe2fdc7bef44fb01545347912ee9f1779/projects/amdsmi).
ROCm 7.2.4 identifica qui il sorgente userspace: non viene installata la suite ROCm
sull'hypervisor e non è necessario spostare ACE dal container.

I binding Python AMD richiedono anche i simboli CPU: viene compilata nello
stesso prefisso la componente userspace ESMI ufficiale, tag `esmi_pkg_ver-4.2`,
commit `fae8e8e7af086bcf974d406bbac0c6e1ed1a25f9`. Non viene installato né
caricato un driver HSMP. Anche questo sorgente è verificato prima del build.

## Installazione sul nodo che esegue CT 130

Eseguire **su gwads07**, come root, dalla directory del progetto estratto:

```sh
apt-get install --no-install-recommends git build-essential cmake pkg-config libdrm-dev python3
python3 scripts/install_amdsmi_sidecar.py
python3 scripts/install_amdsmi_sidecar.py --install
```

La prima esecuzione verifica soltanto i prerequisiti. La seconda scarica il
sorgente ufficiale, verifica il commit, compila con due processi e pubblica
`/opt/mta-amdsmi/rocm-7.2.4`. Occorrono accesso HTTPS a GitHub e spazio per la
compilazione. `--jobs 1` riduce il carico. Il tag è fissato: se cambia il commit
la compilazione viene rifiutata. Una destinazione già presente viene lasciata
intatta. Non eseguire più installazioni contemporaneamente.

Non vengono eseguiti `cmake --install`, `ldconfig`, pip, DKMS, modifiche ai
repository APT, sostituzioni dei pacchetti Debian o riavvii. Il servizio agente,
il suo collector, i socket, il kernel Proxmox e ACE-Step restano nella
configurazione corrente. La libreria e i binding Python provengono dallo stesso
build; il launcher verifica il percorso della libreria caricata e rifiuta il
fallback alla libreria di sistema. La directory temporanea di compilazione
viene eliminata anche dopo un errore; il prefisso viene pubblicato solo dopo
aver verificato il caricamento della libreria.

## Verifica sul vero hardware

```sh
amd-smi version
/opt/mta-amdsmi/rocm-7.2.4/bin/amd-smi --mta-library-info
/opt/mta-amdsmi/rocm-7.2.4/bin/amd-smi version
/opt/mta-amdsmi/rocm-7.2.4/bin/amd-smi process --json
```

Avviare poi una generazione ACE da MTA e, **mentre è attiva**, acquisire:

```sh
/opt/mta-amdsmi/rocm-7.2.4/bin/amd-smi process --json > /root/mta-amdsmi-new-process.json
```

Conservare l'output delle versioni e di `--mta-library-info`, oltre al JSON del
processo. Se compare un errore del driver o di caricamento, fermarsi a questi
risultati: la configurazione in produzione continua a funzionare con il
collector precedente. Non sostituire `/usr/bin/amd-smi` e non impostare variabili
ROCm o LD_LIBRARY_PATH globali.

## Interpretazione e billing

Nei campioni precedenti il PID ACE è visibile ma manca `drm-engine-gfx` nei suoi
fdinfo: AMD-SMI può quindi riportare GFX zero senza aver misurato il lavoro HIP.
Anche il sorgente nuovo legge quel campo per il tempo GFX. La nuova versione
può aggiungere informazioni sull'attività, tra cui CU occupancy se supportata
da GPU e driver; non garantisce il recupero del tempo GPU mancante.

CU occupancy è una misura di occupazione, non un contatore cumulativo di
secondi GPU attribuibili al job. Un valore zero senza prova del contatore resta
**non verificato**. Nessun dato di questa prova diventa fatturabile. Il profiler
ACE già incluso nel pacchetto rimane un'opzione diagnostica distinta e deve
essere ancora provato sul ROCm reale: vedi [docs/ACE_TASK_GPU_PROFILER_R210.md](ACE_TASK_GPU_PROFILER_R210.md).

Per tornare allo stato precedente basta smettere di usare il percorso isolato:
nessun servizio è stato riconfigurato. L'eventuale rimozione della directory
isolata è facoltativa e va fatta solo dopo averne controllato percorso e manifest.

## Stato della validazione

Lo script ha test automatici per prefissi, preflight, build isolato,
ABI/provenienza della libreria e gestione degli errori. La validazione locale
è descritta in `validation/r210-amdsmi-sidecar-validation.md`.
La compatibilità di AMD-SMI 26.2.2 con kernel Proxmox e Radeon 8060S di gwads07
richiede l'esecuzione sopra; questo pacchetto non certifica il tempo GPU né il
billing e non certifica nuovamente il server.
