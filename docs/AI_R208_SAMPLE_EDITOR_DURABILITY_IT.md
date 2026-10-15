# MTA Audio Editor 0.3.0-r208 — sample editor durable publication

## Checkpoint di partenza
MTA-r208-rescan-integrity-cumulative.zip; SHA-256 400faf106c786e6676d9959d39e507b7ffc4ad8f6c235235d5a7af9a53652235.

## Modifiche verificate
- Il commit dei campioni audio usa il lock di pubblicazione del progetto, coordinato fra processi sui sistemi POSIX.
- Il rendering temporaneo è copiato su file staged esclusivo, con fsync prima della pubblicazione.
- Durata e waveform vengono calcolate prima di modificare i metadati della traccia.
- Il risultato viene pubblicato con replace atomica e sincronizzazione della directory.
- Errori di analisi o salvataggio ripristinano lo stato in memoria e puliscono i soli file prodotti da questa transazione.
- Se il salvataggio ha già pubblicato project.json prima di segnalare un errore, il WAV referenziato viene conservato per recovery.
- Gli input staged via symlink non vengono accettati.

## Verifiche
23 passed: cinque nuovi test sample-editor, più verifiche shared-storage/GC già esistenti.
La precedente suite completa NON è stata ripetuta. I collaudi Windows/macOS e GPU reali non sono stati eseguiti.

## Limiti
Rimane la finestra di crash fra pubblicazione del file WAV e aggiornamento del JSON, senza un journal transazionale generale. Il lock POSIX non fornisce una soluzione multipiattaforma Windows. Restano da completare e/o certificare writer legacy, clip library, generazione locale, lifecycle completo AI, integrazione native/server, billing, GPU metering e CI/installer.
Nessun commit, push, tag, release, accesso a server o mirroring schedulato; versione 0.3.0-r208 invariata.
