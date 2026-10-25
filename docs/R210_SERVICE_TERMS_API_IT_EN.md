# IT — Regolamenti del servizio, stato verificato

L'endpoint `GET /api/service-regime/terms?lang=it|en` pubblica in sola lettura la bozza IT/EN per il regime attivo e l'hash SHA-256. `/api/service-regime` espone il regime e `/api/admin/service-regime` continua ad avere il cambio disabilitato. Le quattro bozze sono nei file `docs/legal/SHARED_INFRASTRUCTURE_*`; nessuna è ancora un testo contrattuale approvato. Il link About apre `/terms/it` o `/terms/en`, i percorsi già supportati dall'app: questi ultimi non sono ancora verificati come equivalenti alle nuove bozze del servizio.

Eseguiti: 20 test passati delle suite `test_service_regime_core.py`, `test_service_regime_commercial_gates.py`, `test_service_regime_terms_public.py`. Compilazione Python e sintassi JS superate. Non eseguita suite completa; transizioni contabili, billing periodico NC e interfaccia amministrativa di cambio regime sono aperti. Non usare in produzione come doppio regime completo.

# EN — Service terms, verified status

The read-only endpoint `GET /api/service-regime/terms?lang=it|en` returns the active-regime draft in IT/EN plus its SHA-256. `/api/service-regime` exposes the regime and `/api/admin/service-regime` deliberately keeps transitions disabled. The four legal drafts are in `docs/legal/SHARED_INFRASTRUCTURE_*` and are not legally approved contractual terms. The About link opens existing `/terms/it` or `/terms/en` endpoints, not yet verified as equivalent to the new regime-specific drafts.

20 scoped tests passed: core, backend commercial guards, and public terms. Python compilation and JS syntax passed. No full regression was run; atomic financial transitions, NC periodic billing and administrative switching UI are outstanding. Do not deploy as a completed dual-regime service.
