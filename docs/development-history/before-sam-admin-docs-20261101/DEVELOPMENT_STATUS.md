# MTA 0.3.0-r210 — stato corrente

**Verso la RC: 34/42 = 81,0%, PRE-RC**, perimetro `precommercial-20261030`; A4 e A5 chiusi, nessun nuovo criterio promosso.

Riprendere da `MTA-0.3.0-r210-pre-RC-sam-model-load-diagnostics-cumulative.zip`, `SAM_MODEL_LOAD_DIAGNOSTICS_R210.md` e `validation/r210/sam-model-load-diagnostics/result.json`. Baseline Git confermata `ee4e37fd30c39a72638b303b01ca0cd5b090f272`, ultima full CI nota `41156985339`; commit all'utente, nessuna nuova CI remota.

Corretta una regressione nel precedente avvio SAM con Python isolato; aggiunte classificazioni sicure per cause note di caricamento e una fase separata per il trasferimento al dispositivo. **La causa effettiva dei due errori della diagnostica utente non è nota**: servono la riga del journal originale o una nuova prova sul servizio reale. Test sintetici non attestano modello né GPU. Selezione finale 338 passati, 0 skip, zero fallimenti; gate di sicurezza e Ruff passano.

Restano **A6,B6,C6,F4,F5,F6,G5,G6**. Il nuovo lavoro non chiude F4 e non sostituisce le prove provider, multihost, runtime e diritti. Dettagli e comando journal nel rapporto.

Commit cumulativo suggerito: `Recover canonical payments and harden AI worker startup and SAM diagnostics`. Documenti precedenti in `development-history/before-sam-model-load-20261101/`.
