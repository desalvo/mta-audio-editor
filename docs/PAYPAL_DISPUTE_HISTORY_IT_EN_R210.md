# PayPal: storico contestazioni / Dispute history — r210

2026-10-24. PRE-RC. Provider simulato nei test; nessun pagamento reale eseguito. / Tests simulate the provider; no actual payment was executed.

## Italiano

Da **Account** o **Crediti**, apri lo storico personale e scegli **Verifica esito senza incassare**. Dopo la conferma, il server legge il pagamento, i rimborsi e le contestazioni visibili per gli incassi di quell'ordine PayPal. Non crea un acquisto, non incassa e non esegue un rimborso. L'amministratore può usare **Riconcilia dal provider** nella sezione delle posizioni economiche.

Lo storico personale mostra gli eventuali **Fondi del pagamento trattenuti o stornati**, distinti da nuovi addebiti. Una contestazione può ridurre i crediti disponibili o riaprire la stessa somma del recupero di abbonamento. Una risoluzione supportata aggiorna quel saldo una sola volta. Le quote NC e i contributi volontari restano separati.

Se compare una prova finanziaria da verificare o un errore, usa **Aggiorna storico**. Non avviare un altro acquisto e non interpretare l'errore come assenza della contestazione. Le prove già osservate restano registrate; una lettura successiva vuota non le cancella. Quando l'operatore ripristina i permessi o completa le prove, ripeti la verifica dello stesso ordine. Non serve reinviare un incasso.

L'applicazione PayPal del gestore deve avere l'accesso di lettura alle contestazioni. Accesso negato, storico incompleto, allocazioni parziali su più incassi e payout/protezioni non dimostrati richiedono intervento dell'operatore e restano bloccati. Il sistema non esegue stime di ripartizione né cancella esiti incerti. Nel regime NC lo storico rimane consultabile senza azioni finanziarie.

L'operatore non deve considerare questa verifica un estratto completo del conto PayPal, una ricevuta fiscale o il completamento della RC. Per la procedura distinta di preparazione/esecuzione dei rimborsi leggere OPERATOR_REFUNDS_IT_EN_R210.md. Per un pagamento già aperto da completare leggere ACCOUNT_WORKFLOW_IT_EN_R210.md:incassare e verificare in sola lettura sono azioni differenti.

## English

On **Account** or **Credits**, open private payment history and choose **Verify status without collecting payment**. After confirmation, the server reads the payment, refunds and disputes visible for that PayPal order's captures. This creates no checkout, collects no payment and issues no refund. Administrators can use **Reconcile from provider** in financial positions.

Private history shows **Payment funds held or reversed**, separately from new charges. A dispute can reduce available credits or reopen the exact existing subscription repayment amount. A supported resolution updates that balance once. NC cost shares and voluntary contributions stay separate.

After an error or unresolved-evidence notice, use **Refresh history**. Do not start another purchase or treat a failed read as proof that no dispute exists. Previously observed evidence remains recorded; a later empty response cannot erase it. Once the operator restores permission or completes the evidence, verify the same order again. Do not resend collection.

The merchant's PayPal application needs dispute read access. Denied access, incomplete history, partial multicapture allocation and unsupported payout/protection evidence remain blocked for operator investigation. The system does not estimate allocation or reset uncertain outcomes. NC mode retains history without financial actions.

This verification is not a full PayPal account statement, tax receipt or RC acceptance. OPERATOR_REFUNDS_IT_EN_R210.md describes the separate confirmed refund workflow. ACCOUNT_WORKFLOW_IT_EN_R210.md describes completing an existing pending payment; collection and read-only verification are distinct actions.
