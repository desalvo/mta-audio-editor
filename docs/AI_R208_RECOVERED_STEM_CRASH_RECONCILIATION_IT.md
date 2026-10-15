# r208 — Riconciliazione delle importazioni stem dopo crash

L'importazione multitraccia registra prima dell'upload un journal fsync nel progetto con l'elenco degli audio e originali già presenti. Entro il lock cross-process, un successivo tentativo riconcilia il journal: se il receipt è già stato salvato preserva tutti i file; altrimenti rimuove soltanto i file nuovi non referenziati nel progetto persistito. Se il journal è malformato o è un symlink, blocca l'operazione senza cancellare dati. La richiesta remota originale rimane disponibile e non viene rieseguita.

**Limiti:** riconciliazione lazy al successivo import nello stesso progetto, non all'avvio; altri importatori che non condividono lo stesso lock potrebbero creare file durante la transazione. Non è una transazione filesystem+DB pienamente atomica e non sostituisce il collaudo crash reale.
