# Dipendenze esterne durante l'installazione nativa (r208)

Su RHEL/Rocky/AlmaLinux 9 e 10, se `/usr/bin/ffmpeg` non è fornito dai repository DNF abilitati, l'installer può proporre di installare la configurazione EPEL (`epel-release`) **solo se il pacchetto è reperibile dai repository già attendibili**. Il prompt chiede consenso prima dell'abilitazione. Se manca una sessione interattiva, l'installer fallisce con un messaggio e non autorizza implicitamente la modifica.

In modalità non interattiva il consenso a questa specifica operazione documentata è esplicito tramite `--unattended` (alias `--yes`):

```bash
sudo bash install_mta.sh --native-server early --unattended
```

Per simulare il bootstrap, senza operazioni sul sistema:

```bash
bash install_mta.sh --native-server early --unattended --dry-run
```

Non vengono scaricati RPM arbitrari e non vengono disattivati `gpgcheck` o `repo_gpgcheck`. Se `epel-release` non è disponibile nei repository già abilitati, oppure se FFmpeg resta non disponibile dopo EPEL (ad esempio CRB/CodeReady Builder non configurato), l'installazione si arresta con istruzioni. L'attivazione dei repository Red Hat soggetti a subscription rimane un'operazione dell'amministratore, non automatizzata.

Debian/Ubuntu continuano a risolvere le dipendenze tramite APT dai repository già configurati, senza aggiungere sorgenti esterne.

Questa logica è stata verificata con test locali statici e dry-run; va confermata sulla VM RHEL 10 con i repository e la subscription reali prima di considerarla certificata.
