# r210 Cutover mirror recovery / Recupero mirror del cambio regime

## IT

`app.regime_cutover_recovery.recover_committed_mirror` unifica la ripresa del file JSON dopo un cambio SQLite già committato. È una funzione interna, non un endpoint pubblico. Richiede una transazione `BEGIN IMMEDIATE` e che il chiamante garantisca un lock esclusivo inter-processo di manutenzione per l'intera applicazione. Controlla ricevuta, epoca, assenza di operazioni aperte e riallineamento del file senza rilasciare la barriera. È idempotente in caso di ripetizione. Non interroga provider esterni né certifica la copertura dei worker. Il cambio commerciale resta non abilitato.

## EN

`app.regime_cutover_recovery.recover_committed_mirror` coordinates JSON mirror recovery after an already committed SQLite cutover. This is an internal routine, not an HTTP API. Callers must hold a `BEGIN IMMEDIATE` transaction and an exclusive cross-process application-wide maintenance lock. It validates the receipt and epoch, rejects outstanding operations, and reconciles the mirror without releasing the fence. Repeated recovery is idempotent. It does not query external payment providers or certify worker coverage. Commercial switching remains disabled.
