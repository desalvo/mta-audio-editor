# MTA 0.3.0-r208 - Finalizzazione validazione telemetria billing

- `finish_job` e `finish_job_idempotent` rifiutano i valori esplicitamente non-mappa anziche trasformarli in `{}`.
- `_validate_usage` rifiuta NaN, infinito e interi non convertibili in float in modo deterministico.
- Conservati i controlli su provenienza GPU, risorse supportate, limiti e non negativita.
- Test dedicati: 29 passed, 8 warnings.
- Suite r208 baseline prima della correzione: 1209 passed, 13 warnings.
- Collaudo completo post-correzione, piattaforme native e GPU non certificati.
