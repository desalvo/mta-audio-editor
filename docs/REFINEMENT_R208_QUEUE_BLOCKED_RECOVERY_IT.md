# MTA Audio Editor 0.3.0-r208 — Refinement coda persistente

- Le richieste persistenti non ripristinabili per assenza dell'adapter o incompatibilità del payload entrano in stato `blocked`.
- Le richieste bloccate non occupano gli slot di esecuzione e non impediscono l'avanzamento FIFO delle richieste `queued`.
- Un successivo `recover_queued()` ritenta la ricostruzione dei job bloccati solo quando è disponibile la relativa factory; l'ammissione rimane transazionale mediante `_claim()`.
- I job `blocked` possono essere annullati senza avviare inferenza.
- Le esecuzioni `running` interrotte non vengono riavviate automaticamente perché gli effetti esterni non sono transazionali.

Verifica locale: `PYTHONPATH=. pytest -q tests/test_r208_*` (119 test superati al momento del packaging). Restano da validare gli adapter AI non migrati, il billing transazionale e i benchmark ROCm.
