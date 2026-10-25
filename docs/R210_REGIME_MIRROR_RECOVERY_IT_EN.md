# R210 — Recupero della configurazione del regime / Regime mirror recovery

## IT

`app.regime_cutover_mirror` fornisce `inspect_mirror()` e `reconcile_mirror()` per un cutover **già registrato in SQLite**, quando il file `service-regime.json` non è stato ancora aggiornato. Richiede una transazione `BEGIN IMMEDIATE`, ricevuta del cambio locale, stato SQLite coerente e barriera di transizione ancora attiva. Il recupero non apre la barriera e non abilita il regime commerciale.

L'operatore deve fermare i servizi e worker, impedire altre scritture al file con un lock di manutenzione valido per tutti i processi, predisporre un backup consistente e invocare il recupero solo tramite un percorso di manutenzione approvato. Non esiste ancora un endpoint di attivazione. Il file esterno viene sostituito atomicamente e sincronizzato su disco; una revisione sconosciuta o un symlink sono rifiutati. L'operazione è idempotente se il file contiene già il regime/revisione attesi. L'atomicità tra filesystem e SQLite non è garantita: la barriera rimane chiusa e il recupero deve essere ripetibile dopo un crash.

**Non pronto per produzione:** rimangono la copertura integrale di worker e provider, la certificazione delle posizioni economiche, l'attivazione del nuovo regime e le prove end-to-end.

## EN

`app.regime_cutover_mirror` provides `inspect_mirror()` and `reconcile_mirror()` for a cutover **already committed in SQLite** when `service-regime.json` still reflects the old regime. The caller must own a `BEGIN IMMEDIATE` transaction; a matching cutover receipt, consistent SQLite state, and held transition barrier are required. Recovery never releases the barrier or enables commercial billing.

An operator must stop services and workers, ensure a cross-process maintenance lock on the configuration, take a consistent backup, and invoke the recovery only through an approved maintenance path. No activation endpoint is provided. Atomic replacement and filesystem synchronization protect the external file; unexpected revisions and symlinks are rejected, and retries are idempotent. Because SQLite and the filesystem cannot share an atomic commit, recovery remains crash-retryable while the barrier stays held.

**Not production ready:** full worker/provider coverage, financial reconciliation, activation, and end-to-end testing remain pending.
