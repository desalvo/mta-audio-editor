# MTA 0.3.0-r208 — Stato e limiti del ciclo

## Verifica del sorgente
Questo cumulativo deriva dall'archivio `MTA-r208-recovery-cancel-race-cumulative.zip`, non da una directory di lavoro meno recente. L'ultimo archivio includeva gia' la protezione del race tra recovery e cancellazione.

## Correzione
`ai_request_dedup.request_status` rifiuta esplicitamente chiavi non stringa prima di accedere al database, con `ValueError`, senza propagare `TypeError`. Aggiunti test parametrizzati per input non validi.

## Verifica
`PYTHONPATH=. pytest -q tests/test_r208*`: 812 passed, 9 warnings.

## Limiti aperti
Il sistema non garantisce ancora l'interruzione fisica di tutti i worker remoti; la telemetria GPU fatturabile per job e la certificazione hardware ROCm restano incomplete. Non si dichiarano oltre 100 modifiche funzionali per questo ciclo.
