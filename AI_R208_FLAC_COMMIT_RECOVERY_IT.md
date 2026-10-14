# r208 — Commit FLAC e pulizia crash-safe

- Pubblicazione dei file convertiti con fsync della directory prima di rendere autorevole il nuovo project.json.
- Ripristino dei riferimenti in memoria e della modalità di storage se fallisce il salvataggio delle referenze.
- Accodamento durevole dei nuovi FLAC non pubblicati; nessuna cancellazione diretta di file potenzialmente referenziati.
- Eliminazione degli originali soltanto dopo il commit: reconciliation con project.json e prima passata di GC sincrona per compatibilità; il journal rimane recuperabile dopo un crash.
- Test dedicato di iniezione errore sul commit, oltre ai test FLAC di integrazione con ffmpeg.

## Limiti
La conversione FLAC non è una transazione unica fra filesystem e database. La riconciliazione ripristina la consistenza dopo interruzioni nelle condizioni testate; resta necessaria certificazione reale con storage e worker remoti. Attribuzione GPU attendibile e billing remoto ancora da completare. Nessun test EL10/ROCm eseguito qui.
