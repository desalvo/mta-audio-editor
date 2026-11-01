# MTA 0.3.0-r210 — stato corrente

**Verso la RC: 34/42 = 81,0%, PRE-RC**, perimetro `precommercial-20261030`; A4 e A5 restano chiusi. Nessun criterio è stato promosso in questo checkpoint.

Riprendere da `MTA-0.3.0-r210-pre-RC-worker-startup-isolation-cumulative.zip`, `WORKER_STARTUP_ISOLATION_R210.md` e `validation/r210/worker-startup-isolation/result.json`. Baseline Git confermata `ee4e37fd30c39a72638b303b01ca0cd5b090f272`, full CI `41156985339` verde; commit all'utente, nessuna nuova CI remota.

Corretti i percorsi di avvio worker/guardian/Studio/ACE e Demucs selezionati per escludere l'iniezione da ambiente e usare `-I` per gli script Python indicati. Prove reali di `PYTHONPATH`, `LD_PRELOAD`, guardian, ACE capability e FFmpeg; 764 passati, 11 skip espliciti, nessun fallimento/errore. Gate e Ruff passano; 168 finding riesaminati, zero HIGH. Non è una sandbox né un'attestazione dei runtime o dei modelli.

Restano **A6,B6,C6,F4,F5,F6,G5,G6**. A6 richiede sandbox reali, C6 integrazione e host indipendenti; F4 richiede contratti indipendenti di interpreti/dipendenze e identità del checkpoint effettivo ACE, F6 revisione diritti. Non promuovere i criteri sulla sola base di questo checkpoint.

Commit cumulativo suggerito: `Recover canonical payments and isolate AI worker startup`. Documenti precedenti in `development-history/before-worker-startup-20261101/`.
