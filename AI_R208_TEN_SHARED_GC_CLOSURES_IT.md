# MTA Audio Editor 0.3.0-r208 — shared media e garbage collection

Checkpoint iniziale: MTA-r208-gc-fail-closed-cumulative.zip; SHA-256 3ae4a000c9c17e2569176e08c959cb72e8016db827080c9d5cbd9976a621abc9.

## Dieci chiusure di integrità con test end-to-end dedicati

1. Rifiuto degli indici shared-media presentati come symlink durante il caricamento.
2. Rifiuto degli indici shared-media presentati come symlink durante la scrittura.
3. Esclusione dei symlink audio locali dalla promozione nello storage condiviso.
4. Blocco della promozione in presenza di blob condivisi rappresentati da symlink.
5. Verifica SHA-256 del blob già presente prima di associarlo al progetto.
6. Rescan fail-closed: una lettura errata del progetto vieta la rimozione di blob non referenziati.
7. Blocco della pulizia se la directory radice dell'audio condiviso è un symlink.
8. Nessuna rimozione dei symlink orfani nello storage condiviso.
9. GC worker: nessun retry infinito quando l'eliminazione non produce progressi; journal persistente conservato.
10. Recovery all'avvio: directory progetto symlink escluse dalla ripresa GC.

Sono state inoltre aggiunte la verifica del contenuto dopo la copia nel blob condiviso, la fsync della directory dei blob pubblicati e la rimozione dei file temporanei di copia anche in caso di errore.

## Test
- 10 nuovi test mirati superati.
- 36 test nella selezione estesa superati, 8 warning di deprecazione.
- Nessun test Windows/macOS, hardware GPU o server reale in questo ciclo.

## Limiti aperti
- Nessuna transazione ACID distribuita tra filesystem, progetti, code e ledger.
- Le operazioni shared-media tra processi distinti non hanno un lock distribuito.
- Permangono potenziali race TOCTOU con sostituzioni concorrenti dei percorsi; i controlli symlink e digest non sostituiscono un'implementazione dirfd/openat completa.
- Recovery degli altri job, writer legacy, integrazione native/server, metering fatturabile GPU, installer e collaudo operativo restano da validare/completare.
- Il precedente gruppo di dieci chiusure media-lifecycle non è dimostrato presente nel checkpoint di partenza.

Nessun commit, push, tag o release. Versione invariata 0.3.0-r208.
