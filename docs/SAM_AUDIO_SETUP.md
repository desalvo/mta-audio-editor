# SAM Audio: workflow ritirato / retired workflow — r210

SAM Audio e la separazione di singoli cantanti non sono più disponibili. Non installare runtime, checkpoint o credenziali per questi workflow. Le richieste e i job legacy sono rifiutati esplicitamente prima di inferenza o pubblicazione, senza ripetizione o sostituzione automatica del modello.

SAM Audio and individual-singer separation have been removed from runtime, native packages, model catalogs and setup tools. Legacy requests are explicitly rejected; another engine is never selected silently. Standard stem separation uses Demucs. DSP and the existing Mega53 integration retain their own behavior and rights checks. DrumSep weights remain denied until independently authorized.

Per i nuovi modelli di percussioni consultare [PERCUSSION_BENCHMARK_PROTOCOL.md](PERCUSSION_BENCHMARK_PROTOCOL.md) e [PERCUSSION_SEPARATION_MODELS.md](PERCUSSION_SEPARATION_MODELS.md). La validazione tecnica e l'approvazione professionale sono fasi distinte.

## Informazioni storiche di configurazione

Nel servizio segnalato dall'utente: utente `root`; `HOME` e `XDG_CACHE_HOME` non impostati; `HF_HOME=/var/lib/mta/models/huggingface`; `HF_TOKEN_PATH`, `HF_TOKEN` e `HUGGING_FACE_HUB_TOKEN` non impostati. Il journal storico conteneva `401 Unauthorized` / `GatedRepoError` nel caricamento dei checkpoint. Queste informazioni restano registrate per interpretare le vecchie diagnosi, non costituiscono istruzioni di attivazione. Non inserire token nei log o nei documenti.

For the full retirement scope and preserved history, see [SAM_REMOVAL_R210_IT_EN.md](SAM_REMOVAL_R210_IT_EN.md).
