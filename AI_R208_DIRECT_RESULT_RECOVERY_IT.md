# MTA 0.3.0-r208 — Recupero diretto dei risultati AI remoti

## Problema risolto
Un worker poteva pubblicare in modo durevole un risultato nella cache, seguito da un crash prima del commit dello stato SQL del job. L'endpoint di stato riconciliava correttamente la pubblicazione, mentre l'endpoint di download `/api/ai-jobs/request-result/{request_key}` continuava a leggere lo stato `admitted` e restituiva `409` finché il client non interrogava prima l'endpoint di stato.

## Correzione
L'endpoint di download utilizza ora `reconcile_published()` prima di autorizzare la lettura. La riconciliazione richiede un artifact esistente, completo e verificato e finalizza soltanto una richiesta tuttora `admitted`; non richiama alcun worker e non esegue una seconda inferenza. Richieste cancellate o fallite rimangono terminali; isolamento per user_id invariato. In assenza di cache integra, lo stato resta `admitted` e il download viene rifiutato.

## Test
`PYTHONPATH=. pytest -q tests/test_r208_remote_*.py tests/test_r207_ai_request_idempotency.py tests/test_r208_reconcile_cancellation_race.py`

Esito del ciclo: 500 superati. Sono presenti quattro nuovi test per recovery diretto, cache corrotta, cancellazione e isolamento per proprietario. Questo risultato non sostituisce i benchmark GPU né i collaudi delle app native.
