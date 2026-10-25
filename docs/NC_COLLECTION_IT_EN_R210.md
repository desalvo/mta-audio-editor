# MTA r210 — contributi volontari / voluntary contributions

## Italiano — titolare dell'account

Apri Account → Limiti e Quote → Consuntivi e contributi. Puoi consultare ed esportare la tua quota dei costi e gli incassi registrati, senza vedere altri utenti. Il contributo è volontario: non versarlo non blocca il lavoro e non acquista crediti o abbonamenti.

Se il gestore abilita i bonifici, scegli un importo entro la quota disponibile e conferma. Conserva le coordinate e la causale MTA-NC mostrate per quel contributo. L'applicazione non trasferisce denaro: esegui il bonifico presso la tua banca solo se lo desideri, poi usa “Ho eseguito il bonifico”. La segnalazione rimane in attesa di verifica e non prova l'incasso. Istruzioni e stato sono persistenti.

Puoi chiudere una richiesta non ancora inviata dichiarando che non ci sono altri bonifici in attesa. Una segnalazione già inviata richiede riconciliazione; un contributo interamente restituito può essere chiuso senza doverlo versare di nuovo. Lo storico mostra incassi verificati, storni ed eccedenze da rimborsare. Un incasso tardivo dopo la chiusura è interamente un rimborso dovuto. I CSV non sono ricevute fiscali.

## Italiano — amministratore

Nel pannello Web, “Ripartizione costi non commerciale” consente di chiudere un periodo misurato con inizio, fine esclusa, costi documentati e importi già recuperati. Sono supportati costi zero e precisione al secondo. Periodi sovrapposti, job non conclusi o misure non verificabili vengono rifiutati.

La raccolta è disabilitata per default. Configura beneficiario, coordinate/istruzioni e un ID stabile del conto ricevente: mantieni lo stesso ID per lo stesso conto reale. Le modifiche successive non riscrivono i contributi già aperti.

Prima di registrare un incasso, verifica indipendentemente il movimento presso la banca. Inserisci l'importo effettivo, il riferimento della transazione e lo SHA-256 della documentazione esaminata; seleziona la dichiarazione di verifica e conferma. Documento e riferimento in chiaro non vengono persistiti dall'API: conserva la documentazione secondo la tua politica. Il digest collega il documento, ma non certifica da solo la banca. Per il tuo contributo personale serve un altro amministratore.

Registra anche gli eccessi: sono rimborsi dovuti, non crediti. Per uno storno, esegui prima l'operazione esterna e poi registra la documentazione scegliendo l'incasso originale. Il modulo non esegue bonifici o rimborsi. Il riferimento dello stesso movimento non può finanziare più contributi. Richieste non risolte e rimborsi rimangono nella diagnostica; il cambio di regime è ancora disabilitato.

## English — account owner

Open Account → Limits and quotas → Cost statements and contributions. View/export your cost share and reviewed receipts without exposing other users. Contributions are voluntary: unpaid amounts do not restrict work or buy credits/subscriptions.

If bank transfers are enabled, choose an amount within your available share and confirm. Keep the displayed bank instructions and MTA-NC reference. The application does not transfer money. If you choose to send money through your bank, use “I have sent the transfer” afterward. This remains pending independent review and does not prove receipt. Instructions/status persist across reloads.

An unsent request can close after declaring no further transfer is in flight. A reported transfer requires reconciliation; a fully returned contribution can close without forced repayment. History shows reviewed receipts, reversals and excess refund liabilities. A late receipt after closure is entirely refund due. CSV exports are not fiscal receipts.

## English — administrator

Web settings → “Non-commercial cost sharing” closes measured periods with inclusive start, exclusive end, documented costs and prior recoveries. Zero costs and second precision are supported. Overlaps, unsettled jobs and unverifiable measurements fail.

Collection defaults to disabled. Configure recipient/bank instructions and a stable receiving-ledger ID. Keep the same ID for the same real account. Existing contributions retain their original instructions after changes.

Independently verify the actual bank movement before recording a receipt. Enter actual amount, transaction reference and SHA-256 of reviewed evidence; explicitly attest review and confirm. Evidence documents and raw transaction references are not persisted by the API; retain supporting records under your policy. A hash anchors evidence, not bank authenticity. Another administrator must review your own contribution.

Record excess incoming money as refund due, never commercial credit. Execute refunds externally first, then select the original receipt and record the actual movement's evidence. The form never executes transfers/refunds. Duplicate bank references cannot fund multiple contributions. Unresolved transfers/refunds remain readiness blockers; regime switching remains disabled.

Read NC_COLLECTION_HANDOFF_R210.md for authority boundaries, accounting retention, exact tests, reproduction and remaining RC work. No real bank/provider or complete RC acceptance is certified.
