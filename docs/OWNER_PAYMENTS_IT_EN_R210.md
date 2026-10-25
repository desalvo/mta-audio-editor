# Pagamenti personali / Personal payments — MTA r210

## IT

Aprire Account → Il tuo storico pagamenti, oppure Account → Crediti e scorrere allo storico. Sono checkout registrati su questa installazione: lo storico non è un estratto completo del provider né una ricevuta fiscale. Canone, recupero canone e crediti sono indicati separatamente. Un pagamento in attesa non conferma un incasso o un debito aggiuntivo. Usare Altri pagamenti/Pagamenti precedenti per le altre pagine e Aggiorna storico per rileggere i dati.

Riprendi checkout esistente apre, dopo conferma, il collegamento originale del provider. Non avvia un secondo acquisto. Verifica esito senza incassare legge l’esito autenticato dal provider e aggiorna i registri locali solo quando le prove sono coerenti; non crea, incassa o rimborsa un pagamento. Un ordine PayPal approvato può rimanere in attesa: verifica esito non equivale alla conclusione del checkout. Il normale ritorno dal provider dopo un’approvazione resta un flusso distinto.

Finché un acquisto crediti rimane irrisolto, non è possibile avviarne un altro con Stripe o PayPal, anche dopo un aggiornamento della pagina o con un taglio diverso. Per un canone è bloccato un secondo checkout dello stesso periodo. Riprendere o verificare quello esistente. Se manca il riferimento, contattare l’amministratore indicando l’ID locale: non reinviare l’acquisto. Chiudere la scheda, annullare nel browser, un timeout o un errore 404 non dimostrano l’assenza di un incasso. L’amministratore deve verificare l’identità del pagamento con gli strumenti riservati prima di ogni recupero del riferimento.

Lo storico resta visibile se non si è più abilitati a nuovi acquisti. Nel regime non commerciale è di sola lettura: contributi volontari e consuntivi dei costi restano nel loro pannello separato e non diventano crediti. Dopo un errore di caricamento i vecchi comandi di recupero vengono rimossi; usare Aggiorna storico. Non interpretare dati mancanti come saldo o debito pari a zero.

## EN

Open Account → Your payment history, or Account → Credits and scroll to the history. These are checkout records on this installation, not a complete provider statement or tax receipt. Subscription fees, subscription repayments and credits are identified separately. Pending status is not proof of a charge or an additional debt. Use More payments/Previous payments to browse and Refresh history to reload.

Resume existing checkout confirms and opens the original trusted provider link without starting another purchase. Verify status without collecting payment reads authenticated provider evidence and reconciles the local ledger only if the evidence agrees. It never creates, captures or refunds a payment. An approved PayPal order may remain pending; status verification does not complete checkout. The normal provider return after approval remains a separate existing payment flow.

An unresolved credit checkout blocks fresh credit purchases across Stripe and PayPal, including after reload or with another denomination. A pending subscription checkout blocks a second checkout for the same period. Resume or verify the original. Missing references require the administrator and the displayed local ID; do not submit another purchase. Closing/cancelling the browser, a timeout or a 404 does not prove absence of money movement. Only the administrator's independently verified identity recovery can bind an unknown reference.

Existing local records remain visible after losing new-purchase eligibility. In non-commercial service history is read-only; voluntary transfers and cost statements stay in their separate panel and do not become credits. Failed history loads remove old recovery actions; use Refresh history. Missing data does not mean a zero balance or zero obligations.

## Acceptance limits / Limiti

Local fixture/API/Chromium validation only. No real merchant, bank or server was used. Complete provider-wide histories, unknown legacy outcomes, original subscription risks, actual operator refund execution, full accessibility/native acceptance and administrative cutover remain pending. Release Candidate not reached; switching disabled. Current technical continuation: OWNER_PAYMENT_RECOVERY_HANDOFF_R210.md.
