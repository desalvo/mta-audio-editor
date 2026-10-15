# MTA 0.3.0-r208 — Upload e conversione senza sovrascritture

## Modifiche end-to-end

- `_copy_limited` distingue la creazione esclusiva riuscita dal rifiuto di un nome già presente: il rollback rimuove solo il file creato dalla richiesta corrente e non cancella la destinazione preesistente.
- Dopo la copia riuscita, esegue `fsync` del file e della directory contenitrice per migliorare la persistenza in caso di interruzione.
- `_normalize_audio_to_project_rate` pubblica la conversione con collegamento esclusivo (`os.link`), rifiutando le collisioni senza sostituire un WAV già presente. Rimuove il temporaneo e conserva la sorgente in caso di conflitto.
- Quattro test comportamentali coprono collisione upload, upload interrotto, upload riuscito e collisione durante conversione.

## Limiti

La correzione non crea una transazione ACID globale, né sostituisce il collaudo su storage e processi server reali. `os.link` richiede che file temporaneo e destinazione siano sullo stesso filesystem, come previsto dalla costruzione del percorso. Non sono stati eseguiti commit, push o interventi su server.
