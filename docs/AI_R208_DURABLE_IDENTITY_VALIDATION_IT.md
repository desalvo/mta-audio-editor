# R208 — Validazione identità durevole e confine contabile

Questa iterazione aggiunge verifiche coerenti tra ammissione nello scheduler e lettura dell'identità in ai_metering_bridge.

- Un `actor_user_id` dichiarato deve essere un intero positivo (i booleani sono rifiutati).
- Quando presente, `adapter` deve corrispondere all'operazione immutabile dello scheduler.
- La lettura dell'identità contabile rifiuta adapter dichiarati discordanti.
- I payload storici in cui `actor_user_id` o `adapter` non erano salvati restano compatibili. Questa compatibilità non equivale ad autenticazione: non abilita automaticamente il billing.
- Un job con identità valida continua a richiedere il ledger ove previsto.

Verifiche: `PYTHONPATH=. pytest -q tests/test_r208*` — 300 test passati in ambiente locale. Non certifica inferenze reali, misure GPU, adapter legacy né ACID distribuita.

Ancora aperti: attestazione GPU per job, accounting remoto uniforme, crash injection e verifica su Rocky Linux EL10/ROCm.
