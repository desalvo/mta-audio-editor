# Recuperi di abbonamento / Subscription recoveries — 0.3.0-r210

## Italiano

Un rimborso di un canone già regolato può lasciare un importo di abbonamento da recuperare. La pagina Account mostra il riferimento del rimborso, il residuo e quanto risulta regolato. Il canone e questi recuperi restano separati dai crediti per extra quota: pagare un recupero non ricarica il portafoglio.

Con PayPal configurato e regime commerciale attivo, scegliere **Regola con PayPal** e confermare l’importo. Il server ricalcola il preventivo; se il residuo è cambiato, aggiornare la pagina. PayPal regola centesimi: un’eventuale frazione eccedente rimane un rimborso dovuto dal gestore, visibile nel riepilogo. Tornando da PayPal, il server verifica il pagamento prima di aggiornare il residuo.

Se esiste già un checkout, **Riprendi pagamento PayPal** riapre lo stesso pagamento. Se l’esito della creazione è incerto e non c’è un collegamento confermato, contattare l’amministratore: il sistema conserva l’operazione e impedisce una nuova richiesta di incasso per lo stesso debito. Il pulsante di annullamento del provider o un timeout non costituiscono prova di annullamento finanziario.

Un rimborso o una contestazione sul pagamento di recupero può riaprire il residuo. Se una contestazione viene successivamente risolta e il debito era già stato pagato di nuovo, l’eccedenza resta da rimborsare dal gestore. Non viene trasformata automaticamente in crediti. L’esecuzione dei rimborsi del gestore resta un’attività distinta ancora da completare; il riepilogo non prova che siano già stati eseguiti.

L’amministratore trova il dettaglio nello storico dell’utente e i totali nel pannello delle posizioni economiche: **Recuperi abbonamenti da incassare** e **Rimborsi recuperi dovuti dal gestore**. Può usare la riconciliazione autenticata esistente per importare uno stato canonico del provider. In caso di dati mancanti il risultato è “Non verificabile”, mai un saldo zero inventato. Queste informazioni non abilitano il cambio di regime e non sono ricevute fiscali.

## English

A refund of an already-settled subscription fee can leave a subscription amount to recover. Account shows the refund reference, outstanding balance and effective repayment. Subscription fees and recoveries remain separate from overage credits: a recovery payment does not top up the wallet.

When PayPal is configured and the service is commercial, select **Repay with PayPal** and confirm the amount. The server requotes the balance; refresh if it changed. PayPal settles cents, so any rounding surplus remains a refund due from the operator and is shown in the summary. On return, the server verifies payment before refreshing the balance.

If a checkout already exists, **Resume PayPal repayment** opens the same payment. If creation has an uncertain outcome without a confirmed URL, contact the administrator. The operation is retained and a second collection request for that debt is blocked. A provider cancel button or a timeout does not prove financial cancellation.

A refund or dispute on the recovery payment can reopen the balance. If a dispute is later resolved after another payment covered the debt, the excess remains refundable by the operator. It is not automatically converted into credits. Executing operator refunds is a separate workflow still to be completed; the summary does not claim those refunds have already happened.

Administrators can inspect per-user history and the actual global **Subscription recoveries outstanding** and **Repayment refunds due from operator** totals. Existing authenticated provider reconciliation can import canonical payment state. Missing financial data is “Unverifiable”, never an invented zero. These reports do not enable regime switching and are not fiscal receipts.

La cancellazione definitiva resta nella procedura amministrativa già esistente. I vincoli finanziari non bloccano una cancellazione autorizzata dei dati dell’utente ritirato; la deroga è limitata a quell’utente e alla singola operazione, senza cancellare dati di altri utenti.

Permanent account erasure remains in the existing administrator workflow. Financial immutability does not block authorized erasure of the retired owner; the exception is limited to that owner and operation and does not remove other users’ records.

## Integration contract and safe reproduction

Authenticated owner request, using the existing same-origin CSRF header:

```http
POST /api/account/paypal/checkout
Content-Type: application/json
X-MTA-Request: 1

{"kind":"subscription_reversal","refund_id":"<original-PayPal-refund-id>","expected_due_micro":3000000,"request_id":"<stable-unique-request-id>"}
```

`expected_due_micro` must match the current exact owner balance. The provider amount is computed by the server; arbitrary amount fields are rejected. The response supplies the saved checkout URL and local order ID. Account GET returns `transactions.subscription_reversals` and `repayment_available`; administrator user views use the same accounting. Capture is owner-scoped at `/api/account/paypal/<local-id>/capture`; provider webhook verification and canonical readback remain mandatory for provider notifications.

Tests use isolated fixture databases and provider responses. Run only the affected tests when extending this workflow:

```bash
MTA_TEST_OFFLINE=1 python -m pytest -q --timeout=45 tests/test_r210_subscription_repayment_e2e.py tests/test_r210_subscription_repayment_browser.py
```

The broader regression scope and real-environment limitations are recorded in TEST_MATRIX_R210.md. This checkpoint remains PRE-RC.
