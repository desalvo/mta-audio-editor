# MTA 0.3.0-r208 — Rollback delle copie con identità inode

Correzione end-to-end per due punti della pipeline upload.

- `_copy_limited` registra `(st_dev, st_ino)` del file creato tramite `xb` usando `fstat` sul descrittore aperto. Se copia o `fsync` falliscono, il rollback elimina il percorso soltanto se punta ancora allo stesso file regolare. Un percorso sostituito da un altro processo non viene cancellato.
- `preserve_original` applica la medesima verifica nel ramo di errore, impedendo che il fallimento di copia cancelli l'originale creato da una seconda operazione.
- La creazione esclusiva e il normale `fsync` dei contenuti rimangono invariati; anche il comportamento di pulizia dei nuovi file parziali è preservato.

Test: `tests/test_r208_inode_guarded_copy_cleanup.py`, più regressione r208 / route r207: 985 test superati, 9 warning.

Limiti: la verifica inode non costituisce una transazione ACID; rimangono necessari test su storage reale e con terminazione forzata. Nessuna revisione incrementata; nessun commit o push.
