# Release candidate gate / Criteri per la release candidate (0.3.0-r210)

**IT** — Il comando `python -m app.rc_acceptance --output /percorso/nuovo-report.json` genera un rapporto JSON e termina con codice 1 quando la RC è bloccata (2 in caso di errore). Nessuna esecuzione autorizza un cambio regime o la pubblicazione. Una prova dichiarata `passed` in un file JSON non è un'attestazione affidabile: il gate la indica come non verificata. Il report è esclusivamente diagnostico e non deve essere usato per controllare deployment automatici permissivi.

**EN** — `python -m app.rc_acceptance --output /path/new-report.json` emits a machine-readable JSON blockers report and exits 1 while RC remains blocked (2 on errors). It cannot authorize administrative cutover or publication. JSON `passed` declarations are untrusted and never constitute authenticated evidence. Do not wire the diagnostic to a permissive deployment gate.

## Blocking acceptance criteria / Criteri ancora bloccanti

- Authenticated Stripe sandbox reconciliation, pending/outstanding settlements and refunds
- Authenticated PayPal sandbox reconciliation, pending/outstanding settlements and refunds
- Webhook retry and inbox/outbox E2E reconciliation
- Distributed AI worker admission/draining, worker fencing and crash/restart E2E
- Administrative transition with cutover, mirror, rollback and guarded reopening E2E
- Billing non-commercial periodic statements and commercial credits/subscriptions E2E
- All AI executor license validation and authenticated remote model rights attestation
- Full CI/regression across migration, DB, concurrency and native apps

**Do not call this build a release candidate until these have been verified.** Keep cutover disabled and the version unchanged. No git writes were performed.
