# Proprietà dei worker / Worker ownership — r210 PRE-RC

## Italiano

Una ricevuta deve corrispondere al worker originale, alla sua operazione e alla revisione del regime autorizzata. Dopo una modifica incoerente della revisione o l'avvio di una barriera di transizione, heartbeat, rilascio, nuova pubblicazione e contabilizzazione vengono rifiutati. I dati e gli impegni economici rimangono recuperabili: nessuna scadenza del heartbeat autorizza un altro worker a rieseguire il lavoro.

Una ricevuta già conclusa, con fence originale chiusa e contabilità coerente, può confermare la consegna dopo un riavvio o una revisione successiva. Non produce un secondo addebito o una nuova inferenza. Una ricevuta alterata viene rifiutata anche quando i numeri dell'utilizzo coincidono. I controlli sulle risorse e sull'arresto fisico dei processi rimangono obbligatori.

Se la diagnostica indica `worker_claim_integrity_unverified`, conservare database, ricevute, coda e risultati congelati originali. Non azzerare revisioni, cancellare claim, modificare manualmente gli stati o interpretare un PID/heartbeat assente come arresto verificato. Per i worker già strumentati utilizzare il recupero del risultato congelato o la procedura amministrativa di quiescenza/perdita descritta in `WORKER_LOSS_RESOLUTION_HANDOFF_R210.md`. Un processo remoto o legacy senza prova sufficiente resta bloccato.

Questa versione resta **PRE-RC: 22/42 criteri locali, 52,4%, nessuna macroarea interamente accettata**. Il coordinatore tra host e il cambio completo di regime richiedono ancora implementazione e accettazione; il cambio è disabilitato. Il prototipo pull non salvato prima dell'interruzione dell'ambiente non è incluso. Le prove dettagliate e i prossimi interventi sono in `WORKER_EPOCH_HANDOFF_R210.md`.

## English

A receipt must match the original worker, operation and admitted regime revision. Inconsistent revision changes or a transition barrier reject heartbeat, release, new publication and accounting. Original data and economic obligations remain recoverable; an expired heartbeat never authorizes execution by another worker.

An already-finished receipt with a closed matching original fence and consistent accounting can acknowledge delivery after restart or a later epoch. It cannot charge twice or replay inference. Altered receipts fail even when usage amounts match. Resource and physical process-quiescence checks remain mandatory.

If diagnostics report `worker_claim_integrity_unverified`, preserve the original databases, receipts, queue and frozen results. Do not reset revisions, delete claims, manually change statuses or infer termination from an absent PID/heartbeat. Use existing frozen-result recovery or the administrative quiescence/loss procedure in `WORKER_LOSS_RESOLUTION_HANDOFF_R210.md` for eligible instrumented workers. Remote or legacy execution without sufficient evidence remains blocked.

This remains **PRE-RC: 22/42 local criteria, 52.4%, no fully accepted macroarea**. Shared cross-host coordination and complete regime cutover still require implementation and acceptance; switching stays disabled. The interrupted unsaved pull prototype is not included. Exact evidence and next actions are in `WORKER_EPOCH_HANDOFF_R210.md`.
