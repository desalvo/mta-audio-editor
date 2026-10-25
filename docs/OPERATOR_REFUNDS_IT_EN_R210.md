# Rimborsi amministrativi / Operator refunds — r210

PRE-RC, 24 ottobre / October 2026. Il cambio di regime resta disabilitato / Regime switching stays disabled.

## Italiano

In /admin riconcilia prima il pagamento tramite il pannello del regime. Nel pannello Rimborsi dei pagamenti scegli il pagamento e, per PayPal, lo specifico incasso; inserisci l’importo EUR esatto (virgola o punto, massimo due decimali) e un motivo documentato. «Prepara rimborso» riserva la posizione senza inviare denaro. Il secondo pulsante «Invia rimborso al provider» mostra una conferma distinta per importo e ordine. Il rimborso ritorna al metodo originale; non è possibile indicare un beneficiario o URL diverso.

Preparato significa nessun invio: puoi annullare la preparazione. Esito incerto significa che l’invio potrebbe essere avvenuto: non puoi annullarlo, reinviarlo o aprire un secondo rimborso per quell’ordine. Se la risposta è andata persa, recupera l’ID del rimborso dal provider e usa «Verifica esito senza reinvio». L’ID viene letto dal provider con le credenziali originali e deve coincidere con operazione, incasso e importo. 404, timeout, errore o un ID estraneo non provano che il rimborso non esista. Se l’ID o la configurazione originale non sono disponibili, la posizione rimane aperta per indagine del gestore. Non esiste un comando per azzerare l’incertezza.

In attesa indica un esito pendente o una riconciliazione ancora incompleta. Solo «Rimborso verificato e riconciliato» conferma sia la ricevuta sia l’aggiornamento del registro contabile locale. Un errore dopo l’invio richiede aggiornamento/verifica, mai un nuovo invio. Un rimborso di crediti modifica il saldo; quello di un abbonamento o di un recupero può riaprire l’esatta obbligazione precedente. Rimborsare un recupero eccedente elimina il debito di rimborso del gestore senza creare crediti. Le commissioni e gli altri rischi non vengono cancellati automaticamente.

I proprietari vedono lo stato riservato dei propri rimborsi in /account e /account/credits. Non possono ordinare rimborsi né leggere dati di altri utenti, credenziali o motivi amministrativi. I rimborsi aperti bloccano la cancellazione definitiva dell’account; quelli chiusi rientrano nella procedura autorizzata di cancellazione. La lista candidati è limitata ai primi 200 pagamenti locali riconciliati con residuo; lo storico è paginato. Nessun collaudo su denaro reale è stato effettuato in questo checkpoint.

## English

In /admin reconcile the payment first using the regime panel. In Payment refunds select the payment and, for PayPal, the exact capture; enter exact EUR (comma or dot, at most two decimals) and a documented reason. Prepare refund reserves the position without sending money. Send refund to provider has a separate amount/order confirmation. Refunds return to the original payment method; a different recipient or arbitrary URL cannot be supplied.

Prepared means no dispatch: preparation can be cancelled. Uncertain means the refund might have been sent: cancellation, reposting and another refund request for the order are blocked. If the response was lost, obtain the exact refund ID from the provider and use Verify outcome without resending. The server reads and binds it to the operation, original capture/payment and amount using the original merchant configuration. A 404, timeout, error or unrelated ID never proves non-execution. If the ID or original configuration is unavailable, the operation stays open for merchant investigation. There is no uncertainty-reset control.

Pending means provider completion or local canonical reconciliation is incomplete. Only Refund verified and reconciled confirms both the authenticated receipt and actual local accounting update. After a dispatch error, refresh/verify; never send again. Credit refunds change the wallet. Subscription/repayment refunds can reopen the exact original obligation. Refunding surplus repayments clears the operator refund liability without minting wallet credit. Fees and other risks are not automatically written off.

Owners see private refund status in /account and /account/credits. They cannot order refunds or read other owners, merchant credentials or administrator reasons. Open refunds prevent final account erasure; terminal records follow the authorized erasure procedure. The candidate list is bounded to the first 200 reconciled local positions with a remainder; history is paginated. No real-money acceptance was executed in this checkpoint.
