# MTA 0.3.0-r210 — stato corrente

**Verso la RC: 34/42 = 81,0%, PRE-RC**, perimetro `precommercial-20261030`; A4 e A5 chiusi, nessun criterio promosso in questo checkpoint.

Riprendere da `MTA-0.3.0-r210-pre-RC-sam-admin-docs-cumulative.zip`, `SAM_AUDIO_ADMIN_GUIDE_R210.md` e `validation/r210/sam-admin-docs/result.json`. Baseline Git confermata `ee4e37fd30c39a72638b303b01ca0cd5b090f272`; ultima full CI nota `41156985339`, nessuna nuova CI remota. Commit all'utente.

Il journal dei tentativi SAM Base e Large ha identificato `GatedRepoError` 401: autenticazione/autorizzazione Hugging Face. L'utente ha comunicato servizio root, `HF_HOME=/var/lib/mta/models/huggingface` e assenza di token nell'ambiente. La procedura è ora nei manuali amministratore HTML e PDF IT/EN e nella guida SAM, con verifica non divulgativa e avvertenza sui percorsi specifici della macchina. Il login, il consenso gated e la nuova prova sul server non sono ancora confermati. 18 test manuali passati; entrambe le versioni PDF ispezionate visivamente.

Restano **A6,B6,C6,F4,F5,F6,G5,G6**. Commit cumulativo suggerito: `Recover canonical payments and improve AI worker isolation and SAM documentation`. Stato precedente in `development-history/before-sam-admin-docs-20261101/`.
