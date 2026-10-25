# Doppio regime: cinque cicli di sicurezza / Dual regime: five safety cycles

**IT.** I cinque cicli hanno migliorato la visibilità degli obblighi contabili, l'integrità dei consuntivi, i rapporti amministrativi e i test. `GET /api/admin/service-regime/reconciliation-report?target=COMMERCIAL` è di sola lettura, riservato agli amministratori. Non autorizza il cambio di regime. Le righe storiche non si cancellano e le tabelle mancanti sono considerate non riconciliate. La transizione rimane disabilitata finché non sono presenti una barriera atomica sulle operazioni, la riconciliazione dei webhook/pagamenti e test end-to-end.

**EN.** Five iterations improved reconciliation visibility, statement integrity, admin reports and regression tests. The admin-only `GET /api/admin/service-regime/reconciliation-report?target=COMMERCIAL` is read-only and does not authorize switching. Historical financial rows remain intact, and absent tables are treated as unreconciled. Switching remains disabled pending an atomic fence for concurrent operations, payment/webhook settlement and end-to-end tests.

**Verified:** 42 focused tests passed and changed modules compiled. **Not verified:** production switches, payment providers, cross-worker concurrency, full CI, native UI. Version: `0.3.0-r210`. No Git operations or deployment.
