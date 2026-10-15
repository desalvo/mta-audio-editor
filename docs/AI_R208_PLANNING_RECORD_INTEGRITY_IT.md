# MTA Audio Editor 0.3.0-r208 — integrità dei record di pianificazione AI

Il journal opzionale SQLite valida ora all'apertura lo schema minimo e controlla l'integrità rapida (`PRAGMA quick_check`). Le letture, la cronologia e la cancellazione dei piani verificano che identificativo, progetto, proprietario e stato memorizzati nel payload corrispondano ai campi indicizzati. I piani con JSON danneggiato, valori non finiti, dimensione eccessiva o struttura invalida vengono rifiutati senza essere trattati come mancanti o automaticamente cancellati.

La cancellazione di un record alterato non ne cambia lo stato: la transazione è annullata. Nessuna migrazione distruttiva è automatica. Le nuove verifiche non rendono il journal una coda di inferenza e non generano uso GPU o fatturazione.

Verifiche: 26 test passati nella selezione sulla pianificazione, inclusi quattro nuovi casi di corruzione/schema. La suite globale, gli installer nativi e il metering GPU reale non sono certificati in questo ciclo.

Limiti: SQLite e filesystem non condividono transazioni ACID con progetti, ledger e backend remoti; la protezione contro race TOCTOU resta parziale. Tutto il codice continua a utilizzare versione 0.3.0-r208.
