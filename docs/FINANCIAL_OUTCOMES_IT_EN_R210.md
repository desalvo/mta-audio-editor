# Esiti dei pagamenti / Payment outcomes — r210

## IT

Per un checkout rimasto in attesa dopo tentativi falliti, aprire Account → Il tuo storico pagamenti, oppure la pagina Crediti. Confermare Verifica esito senza incassare. Il server legge il provider: non avvia, annulla, incassa o rimborsa un pagamento. Se l’intento è già annullato e l’intero storico supportato dimostra assenza di fondi, il checkout locale diventa Annullato, il vecchio collegamento di ripresa viene rimosso ed è possibile un nuovo acquisto. Il saldo non viene ricaricato dalla chiusura senza incasso.

Un errore, una pagina incompleta, fondi autorizzati/incassati/rimborsati/contestati, valori mancanti o uno storico oltre il limite mantengono il blocco. Un errore del browser o del provider non è prova di mancato incasso. Se la verifica non risolve il caso, contattare l’amministratore con l’ID locale; non reinviare automaticamente l’acquisto. L’amministratore dispone della stessa verifica autenticata nel pannello di riconciliazione, senza un nuovo comando di incasso.

Se lo storico segnala prove finanziarie ancora da verificare, il messaggio non è un addebito aggiuntivo. Un ordine può risultare pagato pur avendo una contestazione o prove successive irrisolte. Gli esiti definitivi PayPal non vengono sostituiti automaticamente da documenti incompatibili; il gestore deve investigare. Ripetere la verifica del checkout non garantisce la risoluzione di una contestazione. Lo storico resta privato e, nel regime non commerciale, di sola lettura. Contributi volontari e crediti restano separati. Aggiorna storico rilegge i dati; un errore rimuove i vecchi comandi e messaggi.

## EN

For a checkout still pending after failed attempts, open Account → Your payment history, or the Credits page. Confirm Verify status without collecting payment. The server reads the provider; it never creates, cancels, captures or refunds a payment. If the intent is already canceled and the complete supported history proves no money movement, local status becomes Cancelled, the old resume link disappears and a new purchase becomes available. Closing an unpaid checkout does not add wallet credits.

Errors, incomplete pages, authorized/captured/refunded/disputed funds, missing fields or history beyond the bound preserve the hold. A browser/provider error does not prove that no money was collected. Contact the administrator with the local ID if verification cannot resolve the outcome; do not automatically resubmit the purchase. The administrator uses the same authenticated reconciliation panel without a new collection command.

An unresolved financial evidence warning is not an additional charge. A locally paid order can have a dispute or unresolved later evidence. Final PayPal outcomes are not automatically replaced by incompatible documents; operator investigation is required. Checkout verification does not guarantee dispute resolution. History remains private and read-only in non-commercial service. Voluntary contributions and wallet credits remain separate. Refresh history rereads the data; failed loading removes stale controls and messages.

## Limits / Limiti

Only the supported strictly failed/zero-exposure Stripe history is eligible. Unknown, financially nonempty or unsupported histories remain blocked. Real merchant validation, provider-wide history, original subscription permanent-loss resolution, actual operator refunds, full platform/accessibility and cutover acceptance remain open. No real provider/server was used. RC not reached; switching disabled. Technical details and exact test provenance: FINANCIAL_OUTCOME_HANDOFF_R210.md.
