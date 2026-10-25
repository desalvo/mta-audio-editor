# PayPal — allocazioni parziali e osservazioni / Partial allocations and observations

2026-10-24. PRE-RC. Test locali con provider simulato; nessun incasso/rimborso reale. / Local tests simulate the provider; no actual collection/refund.

## Italiano

Da Account o Crediti,**Verifica esito senza incassare** legge ora anche le allocazioni parziali di una contestazione che coinvolge più incassi, quando gli articoli del provider ne dimostrano gli importi esatti. Il server verifica identità, importi per incasso e totale; non usa percentuali o stime. I crediti disponibili e i fondi trattenuti si aggiornano attraverso lo stesso ledger. Dati mancanti, duplicati o contraddittori restano da verificare con l'operatore. Quantità degli articoli e importi monetari non vengono confusi.

Nella sezione amministrativa delle posizioni economiche, l'operatore può aprire **Movimenti PayPal da verificare**. La tabella riservata mostra soltanto le osservazioni ammesse dal provider:parte, direzione, motivo, importo, avvio e fonte. Il significato è diagnostico:l'avvio non prova il completamento. CREDIT, commissione rimborsata o payout dichiarato non sbloccano il saldo. Le commissioni del processore non diventano addebiti o crediti dell'utente.

Non ci sono pulsanti per dichiarare questi movimenti regolati o cancellare il blocco. Per payout e protezioni serve ancora una prova autorevole che colleghi caso, incasso e movimento completato. Errori o una tabella vuota non dimostrano che il pagamento non esista. Aggiornare la verifica dello stesso ordine dopo l'indagine dell'operatore; non reinviare un incasso. Lo storico dei clienti non espone gli articoli privati o i dettagli delle osservazioni. Nel regime NC restano i soli controlli previsti per tale regime.

La vista è limitata e può segnalare troncamento; il registro riservato mantiene le evidenze immutabili. Non è un estratto completo del conto PayPal, una ricevuta fiscale o la chiusura della RC. Consultare anche PAYPAL_DISPUTE_HISTORY_IT_EN_R210.md e OPERATOR_REFUNDS_IT_EN_R210.md per le rispettive procedure.

## English

On Account or Credits,**Verify status without collecting payment** now supports partial disputes spanning multiple captures when the provider's items prove exact allocated amounts. The server checks identities, per-capture amounts and the total; it uses no proportional estimate. Available credits and held funds update through the same ledger. Missing, duplicate or contradictory evidence stays under operator review. Item quantities never multiply an already-disputed monetary amount.

In administrator financial positions, open **PayPal movements requiring verification**. This private table shows permitted provider observations:party, direction, reason, amount, initiation and source. It is diagnostic:initiation is not completion proof. CREDIT, a refunded fee or a reported payout never unlocks the wallet. Processor fees never become user charges or wallet grants.

There is no action to declare these movements settled or clear their hold. Payout/protection settlement still needs authoritative case/capture/completed-movement binding. Errors or an empty table do not prove non-payment. Refresh verification of the same order after operator investigation; do not resend collection. Owner history exposes neither private item data nor movement observations. NC keeps only its permitted controls.

The bounded view may indicate truncation; the private journal retains immutable evidence. This is not a complete PayPal account statement, tax receipt or RC acceptance. See PAYPAL_DISPUTE_HISTORY_IT_EN_R210.md and OPERATOR_REFUNDS_IT_EN_R210.md for the separate workflows.
