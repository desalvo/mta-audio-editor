# MTA 0.3.0-r208 — Chiusura confini filesystem del journal AI

Questo checkpoint conserva tutte le modifiche precedenti e non abilita inferenza o billing dalla pianificazione.

## Modifiche
- Controllo con lstat di ogni antenato del file SQLite, rifiutando symlink e componenti non directory.
- Rifiuto di file database non regolari e dei sidecar SQLite (-wal, -shm, -journal) non regolari.
- Convalida all'inizializzazione e ad ogni apertura del database, inclusa una seconda verifica dopo la connessione.
- Chiusura della connessione in caso di errore di validazione.
- Quattro test di regressione per symlink agli antenati, sidecar prima/dopo startup e sostituzione del DB dopo startup.

## Verifiche
- 22 test planning/security superati.
- 27 test AI/planning selezionati superati.
- 44 test legacy AI, API e planning superati; 8 warning di deprecazione.
- Versione e revisione invariati: 0.3.0-r208.

## Limiti
Queste modifiche riducono il rischio di path substitution, ma non eliminano completamente ogni race TOCTOU tra controllo del pathname e apertura SQLite. Non costituiscono una transazione ACID globale né una certificazione GPU o multipiattaforma. Il lifecycle esecutivo AI, l'integrazione native/server, billing/accounting e i collaudi reali restano da concludere.
