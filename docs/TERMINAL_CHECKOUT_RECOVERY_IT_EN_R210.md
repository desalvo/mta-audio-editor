# MTA r210 — checkout recovery / recupero dei checkout

PRE-RC; cambio amministrativo del regime disabilitato. Nessun rimborso o addebito viene eseguito dal recupero amministrativo del riferimento o dalla riconciliazione in sola lettura.

## Italiano — amministratore

1. Nel pannello finanziario, un tentativo con esito incerto conserva il proprio ID locale. Se conosci l'ID esatto della sessione Stripe o dell'ordine PayPal, inseriscilo nel controllo di verifica e conferma. Non inserire URL, importi o credenziali. Il server verifica identità, titolare, importo, valuta e merchant presso il provider configurato.
2. La conferma del riferimento significa che l'oggetto del provider è stato ritrovato. Non significa che il cliente abbia pagato. Usa poi la riconciliazione canonica disponibile sullo stesso ordine.
3. Un checkout scaduto/annullato viene chiuso soltanto con prova autenticata sufficiente e assenza di movimenti. La posizione risultante è non finanziata, con netto zero; non attribuisce crediti. Un ordine aperto, in elaborazione o con prove incomplete rimane pendente.
4. Un timeout, un 404 o la cancellazione nel browser non autorizzano a ricreare l'ordine. Se il riferimento è sconosciuto, il caso resta da verificare. Un pagamento notificato dopo una chiusura incompatibile resta un conflitto durevole da risolvere, senza accredito automatico.

## Italiano — titolare dell'account

Un pagamento PayPal pendente può mostrare il collegamento per riprendere l'approvazione oppure il pulsante per verificare un pagamento già approvato, se il riferimento è noto. Controlla l'importo e conferma: il normale flusso autenticato del tuo account può finalizzare la cattura PayPal. La conferma appare soltanto quando il server restituisce effettivamente lo stato pagato. I recuperi dell'abbonamento estinguono il debito indicato e non caricano il portafoglio; gli acquisti di crediti seguono il rispettivo ordine. Se il riferimento è sconosciuto, attendi la verifica amministrativa senza ripetere l'acquisto per aggirare il blocco.

## English — administrator

1. An uncertain creation keeps its original local order ID. If the exact Stripe session ID or PayPal order ID is known, enter it in the verification control and confirm. Do not enter URLs, amounts or credentials. The server checks identity, ownership, gross amount, currency and configured merchant.
2. A confirmed reference means the provider object was found; it does not mean payment succeeded. Run the canonical reconciliation action for that order next.
3. A terminal unpaid checkout closes only with sufficient authenticated evidence and no money movements. Its position is unfunded with zero net and grants no credits. Open, processing or incompletely proven orders remain pending.
4. A timeout, 404 or browser cancellation does not authorize order recreation. Unknown references remain under review. An incompatible paid notification after terminal closure remains a durable conflict without automatic credit.

## English — account owner

A pending PayPal order may offer its approval URL or a button to verify an already approved payment when the reference is known. Review the displayed amount and confirm; the normal authenticated owner flow may finalize PayPal capture. Payment is confirmed only after the server actually reports paid. Subscription recoveries settle the named receivable without funding wallet credits; credit purchases follow their own order. Unknown-reference orders require administrator review.

## Operational limits / limiti operativi

These controls do not enable regime switching, resolve every legacy liability, execute operator refunds or prove complete provider dispute/payout history. Consult TERMINAL_CHECKOUT_HANDOFF_R210.md for reproducible tests, exact limits and remaining acceptance. Provider sandbox lifecycle and platform acceptance remain pending.
