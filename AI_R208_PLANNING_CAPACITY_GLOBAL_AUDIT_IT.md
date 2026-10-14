# MTA Audio Editor 0.3.0-r208 — Audit del journal di pianificazione

Interventi cumulativi del ciclo:

- Vincolo dell'istanza del journal all'identità filesystem (device/inode) del database inizializzato: una sostituzione successiva con un altro database SQLite valido viene rifiutata.
- Prima dell'eviction a capacità massima, controllo fail-closed **di tutti** i record persistenti, anche quelli non candidati alla cancellazione: ID, progetto, proprietario, stato e struttura del piano devono essere coerenti con le colonne indicizzate.
- Nessuna cancellazione e nessun inserimento in caso di record alterati; rollback della transazione SQL.
- Due test di regressione aggiunti per sostituzione con database valido e corruzione di record non terminale.

**Ambito:** pianificazione AI, non worker di inferenza. Nessun costo o misura GPU generata. Non certifica i flussi completi native/server, gli installer multipiattaforma o l'accounting su hardware reale.

Regressione selezionata: 33 passed. Nessuna suite globale completa eseguita.
