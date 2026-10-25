# Provider financial evidence / Verifica evidenze finanziarie (r210)

IT: `app/regime_provider_settlement.py` esegue letture autenticate dei dati finanziari Stripe e PayPal. Stripe richiede sessione `complete`, `paid`, importo/valuta coerenti e PaymentIntent `succeeded` con importo incassato esatto. PayPal richiede ordine `COMPLETED`, capture `COMPLETED`, identificativi univoci e totale/valuta esatti. Le API non modificano il database e **non** autorizzano accrediti, cutover o release candidate.

EN: `app/regime_provider_settlement.py` performs authenticated read-only Stripe and PayPal settlement evidence checks. Stripe requires complete/paid session, matching exact amount/currency and succeeded PaymentIntent with matching received amount. PayPal requires completed order, completed nonduplicated captures and exact amount/currency. These APIs never mutate the ledger or authorize credits, cutover, or release candidacy.

## Still required / Ancora necessario

- Authenticate and independently reconcile provider refunds, partial refunds, chargebacks and disputes.
- Verify webhook delivery completeness, pending inbox/outbox, legacy liabilities and unsettled subscriptions.
- Bind immutable provider evidence to local order/ledger with atomic state changes, concurrency controls, idempotency and durable audit records.
- Run sandbox end-to-end API tests and failover/concurrency scenarios; run general CI.
- Add currency exponent mapping before accepting zero/three-decimal currencies.

Until these are complete, commercial transitions remain fail-closed. / Fino al completamento, transizioni commerciali bloccate.
