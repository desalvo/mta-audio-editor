# Collaudo unattended MTA Audio Editor 0.3.0-r208

Il runner `scripts/unattended_certification_r208.py` usa solo la libreria standard Python e non modifica servizi né progetti. Va eseguito **separatamente su ogni piattaforma** con Python e dipendenze di test del progetto già installati; un singolo PC non certifica altri sistemi operativi.

## Linux e macOS

```sh
python3 scripts/unattended_certification_r208.py --profile full --timeout 8400 --output certification-results
```

## Windows (PowerShell)

```powershell
py -3 scripts\unattended_certification_r208.py --profile full --timeout 8400 --output certification-results
```

## Modalità

* `--profile quick`: gate statico + piccolo test rapido, adatto a verificare l'ambiente.
* `--profile full`: gate statico + intera directory `tests` + inventario hardware non distruttivo. Ogni fase ha timeout, 8400 secondi per default (140 minuti).
* `--profile hardware`: gate statico + inventario delle capacità hardware; **non** esegue un job GPU reale.
* `--hardware-required`: richiede la presenza di almeno uno strumento di rilevamento hardware funzionante. Non certifica la GPU.
* `--archive /percorso/MTA-...zip`: verifica l'integrità ZIP e il checksum nel file `.zip.sha256` adiacente.

Il risultato è nella directory indicata in `--output`: `report.json`, `report.md`, `*.log`, `static-gate.json` e, se pertinente, `hardware-probe.json`.
Exit code: `0` verifiche richieste tutte superate; `1` test fallito, timeout o verifica d'integrità fallita; `2` verifica saltata (es. pytest non installato). Il report segnala sempre esplicitamente le certificazioni che questo runner non può effettuare.

## Cosa resta da fare davvero a mano

1. **Preparazione ambiente (una volta per OS):** installare le dipendenze richieste dal repository e gli strumenti di compilazione/driver appropriati. Per esecuzione automatica ripetuta usare CI/runners di Windows, macOS, Linux; il comando `full` va eseguito su ognuno.
2. **Interfaccia e installazione native:** aprire l'app su Windows, macOS, Linux; verificare installer, apertura/salvataggio, audio reale, plugin VST e flussi AI remoti. Sono prove pratiche non coperte dal runner.
3. **Server GPU reale:** preparare un sistema isolato/test (non produzione), autorizzare l'esecuzione di job AI reali, confrontare consumi misurati e addebiti; simulare annullamento e crash/restart. Il runner esegue solo sonde non distruttive, non questi workload.
4. **GitHub Actions:** pubblicare il codice su un branch di test solo con la tua autorizzazione ed eseguire/verificare i workflow di CI. Il runner offline non invia codice a GitHub.
5. **Feedback:** consegnare `certification-results/report.json`, `report.md`, eventuali `.log` falliti e l'archivio diagnostico server. Evitare dati personali/segreti nei log condivisi.

I punti 2 e 3 richiedono necessariamente piattaforme e risorse fisiche/virtuali effettive, benché molti scenari possano in seguito essere automatizzati con harness specifici. La certificazione di atomicità tra coda SQLite, ledger billing e filesystem necessita prove sotto crash.

Non incrementa VERSION/REVISION, non esegue commit, push, tag o release.
