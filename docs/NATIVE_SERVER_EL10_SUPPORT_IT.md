# MTA Server — EL10 (0.3.0-r208)

Supporto *target*: Red Hat Enterprise Linux 10, Rocky Linux 10, AlmaLinux 10 e derivati Enterprise Linux 10 compatibili, x86_64. La certificazione completa richiede un esito verde della nuova matrice CI e una prova su VM RHEL 10 sottoscritta; i container Rocky/Alma non sostituiscono una VM systemd/SELinux.

## Dipendenze

- Python 3.12 e relativo modulo pip, FFmpeg con `/usr/bin/ffmpeg`, CA certificates, GPG, DNF.
- Su EL10, `ffmpeg-free` è disponibile nei repository Fedora EPEL 10. Configurare EPEL e i repository OS necessari prima dell'installazione, secondo le policy dell'organizzazione. L'installer MTA **non abilita repository esterni automaticamente**.
- Il repository di pacchetti MTA `early` usa la stessa firma GPG sulle distribuzioni supportate e contiene un RPM x86_64.

## Test sicuro su VM EL10 dedicata

```bash
sudo dnf install -y curl gnupg2 ca-certificates
bash scripts/server_packages/el10_preflight.sh
bash scripts/install_mta.sh --native-server early --dry-run
```

Per la prova **di installazione reale** (solo VM usa-e-getta):

```bash
sudo bash scripts/install_mta.sh --native-server early
rpm -q mta-audio-editor-server
systemctl status mta-server.service mta-billing-scheduler.timer
curl -fsS http://127.0.0.1:8000/api/health
```

Non eseguire su CT 130 o server già in esercizio. Se il preflight indica FFmpeg assente, non disabilitare le verifiche RPM né forzare le dipendenze.

## Copertura CI introdotta

- Contenitori `rockylinux/rockylinux:10`, `almalinux:10`: allestimento wheelhouse Python 3.12, RPM, install/reinstall, dati e configurazione persistenti, upgrade/downgrade, firme GPG e indici DNF.
- RHEL 10 ufficiale: collaudo manuale richiesto perché il runner GitHub non dispone della sottoscrizione Red Hat né di una VM RHEL 10 con systemd e SELinux.
- Workflow `CI / Production image`: rimosso import `subprocess` inutilizzato rilevato da Ruff nel job fallito; l'esito della nuova CI va confermato da GitHub.

Versione progetto invariata: `0.3.0-r208`.

## Repository RPM separati EL9/EL10 (integrazione publisher r208)

La CI carica il pacchetto Rocky Linux 10 verificato come artifact
`mta-server-rpm-el10-unreleased-test`; AlmaLinux 10 è usato come secondo
ambiente di validazione del medesimo target EL10. Il publisher richiede
sia l'artifact EL9 sia EL10, applica la retention di due versioni per target,
controlla le firme RPM e crea indici GPG separati:

- `rpm/early/el9/` e `rpm/early/el10/`
- `rpm/stable/el9/` e `rpm/stable/el10/` (solo dopo una release stable)

L'installer `install_mta.sh --native-server early` seleziona `el9` oppure
`el10` da `/etc/os-release`, senza richiedere URL/fingerprint manuali.
Il publisher gestisce la migrazione dei pacchetti EL9 dalla precedente
struttura `rpm/<canale>/packages/`, senza usare i vecchi indici firmati.

Per applicare la modifica al repository di pubblicazione
`desalvo/mta-audio-editor-packages`, sincronizzare anche
`packaging/pages-repository/scripts/assemble_pages.py` in
`scripts/assemble_pages.py`, poi rifare il deployment Pages. Il nuovo
publisher richiede un **nuovo** run verde della Native Server Offline
Runtime Matrix sul medesimo commit. NON utilizzare un vecchio run: non
contiene l'artifact EL10 pubblicabile.

Test reali ancora necessari: installazione DNF su una VM RHEL 10 con
systemd/SELinux, upgrade/rollback, HTTP health e billing scheduler.
