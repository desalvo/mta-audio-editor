# r210 — Zoom decimale e consumi contabilizzati / Decimal zoom and accounted usage

## Italiano

Lo zoom personalizzato è persistito come numero decimale finito, tra 25 e 1200 px/s. Sono accettati anche i valori prodotti dai client precedenti, come 175.61600000000007: il salvataggio automatico non fallisce più con int_from_float. I preset musicali e gli step mantengono la precisione; resta l’ancoraggio temporale del punto visibile, entro la precisione in pixel del browser.

Quality falliva per un confronto testuale obsoleto, non per una perdita delle impostazioni. Il controllo è sostituito da regressioni che eseguono il commit JavaScript, salvano attraverso PUT, leggono attraverso GET e riaprono i dati persistiti. I limiti e il rifiuto di NaN/Infinity sono verificati.

I consumi CPU/GPU accettati dal server sono esposti nella coda come consumi contabilizzati e alimentano quote e billing secondo la configurazione vigente. La proiezione richiede la corrispondenza con l’evidenza immutabile del job; non basta un numero nel contatore progressivo. Report e mail evitano di ripetere lo stesso consumo tra dati contabilizzati e contatori in raccolta. La provenienza tecnica resta nell’audit e nei campi API compatibili; non viene dichiarata una verifica hardware quando non esiste. Non sono modificati tariffe, autorizzazioni, validazione, prezzi storicizzati, regole di abbonamenti/crediti o dati contabili precedenti.

## English

Custom zoom persists as a finite decimal between 25 and 1200 px/s. Values emitted by older clients, including 175.61600000000007, are accepted without int_from_float autosave failures. Musical presets and steps retain precision. The visible temporal anchor is preserved within browser pixel precision.

The Quality failure was a stale source-text assertion. Behavioral regressions execute the JavaScript commit and save/reopen through the project API and storage. Bounds and non-finite values remain validated.

Server-accepted CPU/GPU consumption is displayed as accounted usage in the queue and contributes to quotas and billing under the existing configuration. Projection requires matching immutable job evidence. Reports and emails do not duplicate settled resources as live counters. Technical provenance remains in audit/API compatibility fields; no hardware verification is claimed without evidence. Rates, permissions, validation, subscription/credit rules and historic accounting remain unchanged.

Validation results and remaining platform checks are recorded in DEVELOPMENT_STATUS.md and validation/r210-decimal-zoom-accounted-*.
