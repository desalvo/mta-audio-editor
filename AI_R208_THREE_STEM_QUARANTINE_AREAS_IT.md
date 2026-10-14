# R208 — Tre aree operative della quarantena stem

1. Inventario persistente delle operazioni di quarantena: `.recovered-stems-quarantine.json` contiene ricevuta, file originario, identificativo del file in quarantena e stato. `review_quarantine` riporta anche la presenza fisica.
2. Ripristino amministrativo senza sovrascrittura: `restore_quarantined` controlla il journal pendente, l'audit originale, i symlink, la destinazione e crea il file solo se assente. Il lock interprocesso è gestito dal rispettivo endpoint HTTP. Un secondo tentativo viene rifiutato.
3. API operatore: GET `/api/projects/{pid}/recovered-stem-orphans/quarantine` e POST `/api/projects/{pid}/recovered-stem-orphans/restore`, entrambe con autorizzazione sul progetto. L'endpoint di quarantena precedente registra ora anche il ledger persistente.

Regressione locale integrata: 45 test passati, 8 warning. La suite r208 globale non è stata completata. Non effettuati test reali su sistemi di produzione.
