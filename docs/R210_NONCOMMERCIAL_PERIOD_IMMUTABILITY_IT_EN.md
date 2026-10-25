# IT — Immutabilità dei consuntivi non commerciali

Alla creazione di un consuntivo persistente, la medesima transazione SQLite crea trigger di protezione su `ai_compute_jobs` e `nc_period_statements`. La chiusura rifiuta modifiche tardive dei consumi nell'intervallo `[start, end)`, incluso lo spostamento di job tra periodi. Gli intervalli non ancora chiusi continuano a funzionare. È necessario pianificare la migrazione per gli archivi storici già chiusi prima di questa modifica. I privilegi di amministrazione del file SQLite possono rimuovere i trigger: conservare backup protetti e prove di integrità esterne.

## Verifiche

71 test di regressione mirata superati. Non sono stati eseguiti provider sandbox, CI generale o test di produzione. Il cambio del regime non è abilitato.

# EN — Noncommercial statement immutability

Creating a persistent statement also installs database triggers in the same SQLite transaction to prevent retroactive inserts, edits or deletes in the metered job ledger within the finalized `[start, end)` interval, and edits/deletes to finalized statements. Open periods remain writable. Previously closed historical statements require a migration to activate guards without another close. Database file administrators can remove triggers, so protected backups and external audit evidence remain essential.

## Verification

71 focused regression tests passed. No live payment sandbox, whole-project CI or production testing was performed. Service regime switching remains disabled.
