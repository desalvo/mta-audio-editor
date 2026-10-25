# Regime operation transaction helper / Helper transazionale regime

## IT
`app.regime_operation_fence.execute_atomic` assicura ammissione, mutazione SQL e chiusura nella stessa transazione SQLite: i retry già chiusi non ripetono la mutazione. La callback usa la medesima connessione e non deve fare `commit`, `rollback` né operazioni di rete. Sono presenti test di rollback, riavvio, idempotenza e regime errato. Questa NON è ancora una barriera distribuita per job e provider esterni: il cambio di regime rimane disabilitato fino a inbox/outbox dei pagamenti e integrazione degli ingressi.

## EN
`app.regime_operation_fence.execute_atomic` performs admission, SQL mutation and settlement in one SQLite transaction; closed retries do not rerun mutations. Callbacks must use the same connection, and must not commit, roll back or perform network operations. Rollback, restart, idempotency and wrong-regime tests are included. This is NOT a distributed barrier for workers or external payment providers. Regime switching remains disabled until payment inbox/outbox and admission entry points are integrated.
