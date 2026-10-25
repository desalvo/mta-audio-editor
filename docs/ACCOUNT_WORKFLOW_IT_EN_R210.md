Aggiornamento 2026-10-24: leggere anche PAYPAL_DISPUTE_HISTORY_IT_EN_R210.md per contestazioni,fondi trattenuti e recupero degli errori nello storico PayPal. / Update 2026-10-24: also read PAYPAL_DISPUTE_HISTORY_IT_EN_R210.md for disputes,held funds and PayPal history error recovery.

# MTA r210 — Account e pagamenti / Account and payments

2026-10-24. PRE-RC. Funzioni locali validate; nessuna certificazione di pagamenti reali o cambio di regime abilitato. / Locally validated workflows; no actual payment certification or enabled regime switching.

## Italiano

Apri **Account** per vedere regime corrente, quote, crediti, piano e periodi. I crediti commerciali, gli importi di abbonamento da regolare e le quote volontarie non commerciali sono separati. Lo storico di un altro regime non autorizza nuovi acquisti nel regime corrente.

Nel regime commerciale, le operazioni disponibili dipendono da permessi, configurazione e piano effettivi. La prova gratuita indica il piano successivo; rinnovo, cancellazione e consenso agli extra usano i valori verificati dal server. La cancellazione non azzera il periodo già registrato. Consulta spazio occupato e rendiconti scegliendo un intervallo valido. Un errore di caricamento mostra dati indisponibili, non costi nulli.

In **Crediti**, conferma esplicitamente l'acquisto prima di aprire Stripe o PayPal. Il ritorno dal provider non prova un accredito: il saldo cambia soltanto dopo verifica effettiva. Se un pagamento è già aperto, riprendi quello esistente; non avviare un altro acquisto. Lo storico offre una verifica autenticata senza nuovo addebito. Se un pagamento PayPal recuperato ha un riferimento verificato ma non un collegamento di approvazione, **Completa pagamento PayPal esistente** richiede una conferma distinta: può incassare l'importo originale tramite il pagamento già aperto, senza creare un nuovo ordine. Una verifica in sola lettura e una conferma di incasso sono azioni diverse. Un esito incerto rimane aperto per verifica; un errore o annullamento nel browser non lo cancella.

Nel regime non commerciale, consulta i rendiconti e scegli liberamente un contributo. Una segnalazione di bonifico non è una ricevuta verificata. Le ricevute richiedono la revisione dell'operatore; i contributi non creano crediti commerciali e le quote non sono debiti né condizioni di accesso. Il saldo commerciale precedente è mostrato come storico. I collegamenti di ritorno PayPal non avviano incassi automatici in questo regime.

La sezione rimborsi mostra soltanto lo storico personale. La richiesta/preparazione di un rimborso e la sua effettiva esecuzione restano nel flusso separato dell'amministratore. Cambiare lingua non ripete le operazioni in corso. In caso di errore, attendi la conclusione e usa **Aggiorna**; non interpretare una schermata obsoleta come conferma del pagamento. Le tabelle larghe possono ricevere il focus e scorrere con la tastiera.

## English

Open **Account** to see the current regime, quotas, wallet, plan and periods. Commercial credits, subscription repayment amounts and voluntary non-commercial cost shares remain separate. Historical records never authorize new purchases under another regime.

Commercial actions depend on actual permissions, configuration and plan. A trial identifies the next plan; renewal, cancellation and overage consent use server-verified values. Cancellation does not reset recorded periods. Check storage and reports using a valid interval. An unavailable report is not a zero-cost report.

On **Credits**, explicitly confirm before visiting Stripe or PayPal. A provider return URL does not fund the wallet; actual verified settlement does. Resume an existing pending payment instead of starting another purchase. History verification performs authenticated readback without collecting a new payment. A recovered PayPal payment with a verified reference but no approval URL offers **Complete existing PayPal payment**: this separate confirmation may collect the original amount on that existing order, without creating another checkout. Read-only verification and collection confirmation are distinct. Uncertain outcomes remain open; browser cancellation, timeout or errors never prove non-payment.

In non-commercial mode, review cost statements and choose any voluntary contribution. A transfer report is unverified until operator review; it is not a receipt. Contributions never mint commercial credits. Cost shares are neither debt nor access restrictions. Previous commercial balances are historical. PayPal return parameters never trigger automatic collection in this regime.

Refund history is private to its owner. Refund preparation/execution is a separate administrator workflow. Changing profile language does not repeat an in-flight action. After an error, wait for completion and explicitly refresh; stale content is not proof of settlement. Wide tables have named focusable keyboard scrolling regions.
