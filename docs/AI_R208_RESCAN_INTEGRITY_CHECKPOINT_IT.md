# MTA Audio Editor 0.3.0-r208 — fail-closed shared-media rescan

Checkpoint di partenza: MTA-r208-cross-process-shared-store-cumulative.zip; SHA-256: 8fbf5092cdf9f1ee4d579fbd4088ea7c9b6e37a0c80f2b06fc759afa0f4feb7a.

## Chiusure effettive
- Il rescan verifica l'indice esistente prima di qualsiasi modifica; un JSON illeggibile o schema futuro non può essere sovrascritto silenziosamente.
- Le directory di progetto con identificativo valido ma metadata mancanti, symlink o file non regolari segnano il rescan come incompleto: nessuna cancellazione di blob.
- I riferimenti audio non validi non vengono interpretati come assenza di riferimenti.
- Se il rescan è incompleto, non viene pubblicato neppure un indice parziale quando delete_unreferenced=False.
- Copertura con sei regressioni nuove, inclusa la preservazione esatta dell'indice esistente e del contenuto dei blob.

## Test
- Selezione storage/GC/recovery: 51 passed, 8 warnings.
- Regressione globale tentata ma non completata entro il limite; non dichiarata superata.

## Limiti da non confondere con chiusure
- Writer legacy, sample editor, generatori, completamento uniforme job lifecycle e adapter native/server richiedono ulteriori verifiche funzionali.
- Non certificato metering GPU fatturabile, installazione Windows/macOS e collaudi hardware.
- Nessuna ACID globale fra filesystem, progetto, queue e ledger.
- Cross-process lock POSIX da collaudare/portare su Windows.
- Nessun accesso a server reali, nessun commit/push/tag/release; versione e revisione invariati.
