# MTA 0.3.0-r208 — Protezione inode nella pubblicazione AI

Il recupero dell'outbox di pubblicazione audio verifica ora che WAV staged e lock siano file regolari e non symlink. La lettura del WAV usa O_NOFOLLOW (ove disponibile), fstat e verifica device/inode del percorso; dopo la callback di pubblicazione viene verificata nuovamente l'identità del file prima della transizione a published. La pulizia cancella il file solo se appartiene ancora allo stesso inode. L'outbox continua a richiedere che la callback sia idempotente, perché un crash dopo la pubblicazione nel progetto ma prima del commit SQLite può causare un replay.

Test aggiunti: symlink WAV, sostituzione del WAV durante callback, symlink lock. Regression selezionata: 20 passed su outbox, riconciliazione, billing delivery e metering bridge. Non sono stati eseguiti benchmark GPU né la suite globale. Persistono i limiti non-ACID fra file, progetto, queue e ledger e le limitazioni delle primitive POSIX su altre piattaforme.
