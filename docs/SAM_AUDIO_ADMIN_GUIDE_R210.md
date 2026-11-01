# SAM Audio: documentazione amministratore r210

RC **34/42 = 81,0%, PRE-RC**; nessun criterio promosso. Il journal ha chiarito che i tentativi Base e Large del 1 novembre 2026 ricevevano `GatedRepoError` HTTP 401 da Hugging Face. È un problema di autenticazione/autorizzazione; quale delle due condizioni si applichi e il risultato della nuova prova non sono ancora confermati.

Le istruzioni, i comandi per verificare l'ambiente senza stampare i token e le precauzioni sono presenti in `app/docs/admin.html`, `app/docs/admin-en.html`, nei rispettivi `MTA-Audio-Editor-Administrator-Manual-IT.pdf` e `...-EN.pdf`, e in `docs/SAM_AUDIO_SETUP.md`. I PDF sono stati rigenerati dalle sorgenti HTML con il generatore del progetto e verificati visivamente. Test manuali: 18 passati. I riferimenti a runtime e variabili dell'installazione osservata sono esplicitamente esempi, non impostazioni universali.

Configurazione comunicata dall'utente: servizio root; `HF_HOME=/var/lib/mta/models/huggingface`; HOME, XDG_CACHE_HOME, HF_TOKEN_PATH, HF_TOKEN e HUGGING_FACE_HUB_TOKEN non impostati nel servizio. Il runtime SAM osservato era `/opt/mta/ai-7f176167db5671ae/sam/bin/python`, soggetto a sostituzione in caso di nuovo runtime. Non è stato registrato alcun segreto. Login, accesso gated e inferenza effettiva restano da verificare sul server dell'utente.

Riprendere da `MTA-0.3.0-r210-pre-RC-sam-admin-docs-cumulative.zip`. Prova: `docs/validation/r210/sam-admin-docs/result.json`. Nessun commit, push o CI remota eseguiti. Commit cumulativo suggerito: `Recover canonical payments and improve AI worker isolation and SAM documentation`.
