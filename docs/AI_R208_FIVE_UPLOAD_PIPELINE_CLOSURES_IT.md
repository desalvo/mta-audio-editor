# MTA Audio Editor 0.3.0-r208 — cinque chiusure della pipeline upload

1. **Stream**: `_copy_limited` usa creazione esclusiva e cancella un upload parziale anche se la lettura o scrittura genera un errore.
2. **Decodifica**: il rifiuto da `ffprobe` non lascia media transitori.
3. **Duplicati**: HTTP 409 non lascia audio parziale e non modifica media già presenti.
4. **Originali**: il fallimento di `preserve_original`, anche dopo scrittura parziale, ripulisce i nuovi originali senza eliminare quelli preesistenti.
5. **Conversione/metadati**: fallimenti di normalizzazione o calcolo durata ripuliscono la sorgente e gli output di conversione appena creati.

Le operazioni sono destinate a essere eseguite sotto il lock di progetto degli endpoint di importazione già integrati. Il rollback riguarda errori rilevati prima del ritorno di `_save_upload`; non copre crash di processo, file di altri writer che non rispettino il lock né l'atomicità globale del commit `project.json` + media.

Verifica locale: `PYTHONPATH=. pytest -q tests/test_r207_native_remote_routes.py tests/test_r208*` → **961 passed, 9 warnings**; cinque test specifici in `tests/test_r208_five_upload_pipeline_failures.py`.
