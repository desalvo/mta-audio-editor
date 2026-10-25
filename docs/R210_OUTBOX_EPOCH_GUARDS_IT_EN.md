# Outbox epoch guards / Protezione epoca outbox

## Italiano
`mark_attempt_uncertain` e `confirm` richiedono una ricevuta di checkout commerciale ancora aperta nella stessa revisione del regime correntemente attivo. Il controllo si svolge nella transazione SQLite già posseduta dal chiamante, senza chiamate di rete. I tentativi ripetuti con la stessa conferma rimangono idempotenti. Una transizione prenotata o una revisione cambiata blocca ogni nuova modifica dell'outbox. I pagamenti con esito remoto incerto devono essere riconciliati presso il provider; non vengono cancellati o ritentati automaticamente. I controlli non abilitano il cambio amministrativo.

## English
`mark_attempt_uncertain` and `confirm` require an open commercial checkout admission under the current service regime revision. They validate within the caller-owned SQLite transaction without network access. Matching repeated confirmations remain idempotent. Reserved transitions or changed epochs prevent further outbox state mutations. Uncertain remote outcomes require provider-side reconciliation and are neither silently cancelled nor blindly retried. These checks do not enable administrator regime switching.
