# MTA Audio Editor 0.3.0-r208 — pacchetti e distribuzione firmata

## Prove aggiunte, da eseguire tramite CI

- Ubuntu 24.04 VM disposable, systemd PID 1: installazione effettiva, controllo dell'endpoint HTTP, persistenza di configurazione e progetti, installazione versione di test `0.3.0~early.207`, aggiornamento alla `.208`, downgrade alla `.207` e ritorno alla `.208` con stato persistente. Entrambe le versioni di test usano lo stesso payload applicativo: esercitano i meccanismi del package manager, NON costituiscono una prova di compatibilità funzionale tra due release diverse.
- Rocky Linux 9 disposable: analogo ciclo DNF con RPM `0.3.0-0.207.early` e `0.3.0-0.208.early`; controllo import applicativo e stato. Il container non ha systemd PID 1, pertanto il test systemd Rocky su VM resta separato.
- Rocky: creazione chiave CI effimera, firma del pacchetto RPM reale, verifica con `rpm --checksig`, firma e verifica di `repomd.xml`, rifiuto di metadati manomessi e installazione con `gpgcheck=1` e `repo_gpgcheck=1` da repository DNF locale.
- Ubuntu: test preesistente di firma APT effimera, rifiuto dei metadati Release manomessi, installazione dal repository firmato (solo fixture).

## Vincoli per il rilascio effettivo

Le chiavi di CI sono effimere e non autorizzano un rilascio pubblico. Il rilascio `early`/`stable` richiede, nell'ambiente di pubblicazione isolato: chiave GPG definitiva, fingerprint controllato fuori banda, firma RPM di ogni pacchetto, firme APT Release/InRelease e RPM repomd.xml, pubblicazione atomica degli indici su HTTPS e prove di installazione su host puliti configurati con la chiave di produzione. Le credenziali non vanno mai inserite nel sorgente, negli artifact o nei log CI.

## Esclusioni esplicite

Un vero rollback di un package manager dopo *scriptlet fallito* o interruzione improvvisa non è garantito da APT o DNF: lo stato pacchetto potrebbe restare parzialmente configurato. Occorrono backup/restore verificati e una prova distruttiva su snapshot di VM, prima di migrare un host esistente. I test della virtualenv non garantiscono un rollback di transazione APT/DNF. Nessun test modifica CT 130.

## Stato

La CI è predisposta ma i nuovi job non sono stati eseguiti remotamente per la revisione di questa directory. Non dichiarare ancora la certificazione completa o la pubblicazione completata.
