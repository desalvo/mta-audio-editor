# MTA Audio Editor 0.3.0-r208 — Ownership delle copie originali

## Modifiche

- `preserve_original()` crea la destinazione con apertura esclusiva `xb`, evitando sovrascritture e rimozioni di file di altre operazioni.
- In caso di errore nella copia, rimuove esclusivamente il file creato da quella invocazione e conserva file già esistenti.
- Dopo la scrittura valida, sincronizza il contenuto e la directory tramite `fsync`.
- `_save_upload()` non elimina più indiscriminatamente i file nuovi trovati in `originals/` alla fine di una transazione fallita; elimina soltanto la copia di cui ha registrato il percorso e l'identità inode/dispositivo, e soltanto se non apparteneva già allo snapshot precedente.
- File di altri job creati durante un upload fallito rimangono intatti.

## Verifica

Suite r208 con rotte r207: 983 test passati, 9 warning. Test specifici per collisione, errore di copia parziale e conservazione dei file di job concorrenti.

## Limiti

Il controllo tramite inode non sostituisce una transazione ACID del filesystem e del file `project.json`. I test sono locali e non sostituiscono test su storage reale con crash forzati. Nessun cambiamento del protocollo di fatturazione GPU.
