# R210 — Recovery delle prenotazioni / Transition reservation recovery

## IT

Le due API amministrative `GET /api/admin/service-regime/transition-reservations` e `POST /api/admin/service-regime/abort-transition-reservation` permettono di leggere una prenotazione persistente e annullarla dopo un arresto. Il POST richiede JSON `{"transition_id":"...","expected_revision":0}`. Il controllo avviene nella stessa transazione `BEGIN IMMEDIATE`, con verifica di una sola prenotazione attiva, identità e revisione corrispondenti, coerenza del regime e del journal. Un database incoerente fallisce in sicurezza senza liberare il blocco. L'operazione **non** cambia il regime attivo, non riconcilia saldi né elimina pagamenti e non abilita il passaggio al commerciale. L'accesso è amministrativo; i test sono locali con SQLite, senza provider reali.

## EN

The administrative `GET /api/admin/service-regime/transition-reservations` and `POST /api/admin/service-regime/abort-transition-reservation` APIs inspect and safely abort a persistent reservation after a restart. The POST expects `{"transition_id":"...","expected_revision":0}`. Validation and cancellation execute in a single `BEGIN IMMEDIATE` transaction, checking exactly one active reservation, identity, revision, and journal/fence coherence. An inconsistent database fails closed. Cancellation **does not** change the active regime, reconcile balances, remove payments, or enable commercial cutover. Admin authorization is required. Tests use local SQLite and no live payment provider.
