# r210 — Durable AI worker claims / Prenotazioni durevoli dei worker AI

## IT

`app/regime_worker_claims.py` introduce una prenotazione persistente per ogni job di ledger già ammesso dalla barriera `regime_fence_operations`. Ogni operazione deve far parte della medesima transazione SQLite di scrittura controllata dal chiamante (`BEGIN IMMEDIATE`). `claim` impedisce a un secondo worker di acquisire lo stesso job; la ripetizione con la stessa coppia worker/token è idempotente. `heartbeat` verifica l'identità e l'esistenza della barriera ancora aperta. `finish` chiude la prenotazione, senza modificare automaticamente accounting e contabilità. Nessuna scadenza temporale può trasferire automaticamente un job incerto a un nuovo worker: il recupero richiede l'accertamento esterno che il worker precedente sia fermo.

**Limitazioni:** API di coordinamento sviluppata e testata localmente, ma non ancora integrata in tutti gli esecutori e code AI distribuite. SQLite deve essere condiviso e accessibile con garanzie di serializzazione reali; non assumere che un volume di rete implementi correttamente il locking. Nessuna autorizzazione al cambio di regime o ai pagamenti reali. `combined_readiness` è fail-closed se manca lo schema delle prenotazioni o se sono presenti esecuzioni attive. Gli obblighi Stripe/PayPal devono essere verificati indipendentemente.

## EN

`app/regime_worker_claims.py` adds persistent execution ownership for ledger jobs already enrolled in `regime_fence_operations`. Operations require a caller-owned serialized SQLite write transaction (`BEGIN IMMEDIATE`). `claim` prevents a second worker from taking over the same job; retries by the same worker/token are idempotent. `heartbeat` verifies ownership and the open fence receipt. `finish` releases execution ownership without silently settling billing or accounting. No time-based lease expiry can automatically reassign an uncertain job; recovery requires independent verification that the previous worker is stopped.

**Limits:** The coordination API has local tests but is not wired into every AI queue, scheduler and remote executor. A shared SQLite database requires reliable transaction locking; do not assume network filesystem locks are safe. Provider settlement, distributed quiescence and complete transition are not certified. `combined_readiness` remains fail-closed on missing claim schema or active claims; payments and administrative cutover stay disabled.
