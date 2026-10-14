# MTA 0.3.0-r208 — verifica PCM nei worker locali e legacy

Il validatore dei WAV generati da worker esterni, il confezionatore di artifact AI e la pubblicazione locale di Arranger/Remix verificano ora che la lettura dei campioni PCM restituisca esattamente `frames * channels * sample_width` byte. Non basta più una dimensione file tollerata di 4096 byte rispetto all'intestazione: i campioni mancanti causano un rifiuto prima di importazione o pubblicazione.

File modificati: `app/ai_worker_protocol.py`, `app/ai_worker_artifacts.py`. Nuovi test: `tests/test_r208_worker_pcm_complete.py` (troncamenti di 1, 8 e 40 byte e caso valido). La suite mirata selezionata supera 23 test; una seconda selezione su worker, adapter, artifact e recovery supera 59 test (alcuni test sono comuni alle due selezioni).

## Limiti residui
Non sono stati eseguiti i modelli AI reali né i collaudi GPU/CPU in tutte le piattaforme native. Il solo controllo PCM non certifica l'intera area di generazione locale, inclusi installer, disponibilità dei modelli, cancellazione e flussi UI completi. Nessuna operazione è stata eseguita su server reali.
