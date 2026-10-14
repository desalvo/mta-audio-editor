# MTA Audio Editor 0.3.0-r208 — checkpoint integrità shared-media

Checkpoint iniziale: MTA-r208-ten-shared-media-gc-closures-cumulative.zip (SHA-256 c06bdaf3d4739a7c711bb7ebbed5e63bb89f96a46d2b6623526b5d668087f52b).

## Cambiamenti effettivi
- Lock POSIX cross-process su storage condiviso: promozione e rescan non possono aggiornare l'indice contemporaneamente da worker/server distinti.
- Rifiuto fail-closed di indice malformato, illeggibile, schema sconosciuto e path indice di tipo non regolare: mai azzerare tacitamente le referenze.
- Verifica dei symlink su directory radice, directory audio, shard blob e file di lock.
- Apertura del file lock con O_NOFOLLOW dove disponibile; verifica che il file sia regolare; unlock anche in caso di eccezione.
- Rescan della pulizia: blocco in presenza di entry immediate sospette nella directory blob.
- Otto test aggiuntivi per schema, corruption, percorsi ostili e lock tra processi.

## Risultati
- 24 test GC/shared-media della selezione iniziale superati.
- 22 test della seconda selezione, inclusi 8 test nuovi, superati.
- Regressione ampia avviata ma non conclusa entro il timeout (45% della selezione senza failure prima dell'interruzione): non equivale a una suite superata.
- Nessun test reale Windows/macOS, GPU o server remoto; non si dichiara completamento globale.

## Residui
Writer legacy, clip library, sample editor, generatori locali, recovery/cancellazione di altri job, integrazione end-to-end native/server/queue/ledger, GPU fatturabile, installer/CI su sistemi nativi e collaudo operativo. Nessuna ACID globale o protezione completa dirfd/openat dai TOCTOU. POSIX flock è un requisito per la nuova mutazione shared-media; verificare gli ambienti Windows separatamente.

Nessun commit, push, tag, release, accesso a server reali o incremento versione.
