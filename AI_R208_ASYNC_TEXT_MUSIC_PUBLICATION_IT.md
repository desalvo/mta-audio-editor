# MTA 0.3.0-r208 – pubblicazione asincrona Lyrics, Chords e Markers

## Chiusura implementata

Il worker `_text_music_worker` esegue l'inferenza fuori dal lock cross-process del progetto e protegge mediante `project_publication_lock(pid)` il blocco di rilettura/modifica/salvataggio di Lyrics, Chords e Markers.

Per Lyrics e Chords la pubblicazione rifiuta modifiche alle annotazioni avvenute dopo la lettura iniziale del progetto: i risultati dell'analisi non sovrascrivono modifiche concorrenti. Per Markers la fusione con i marker esistenti avviene sulla copia del progetto appena riletta sotto lock, conservando i marker manuali e scartando i nuovi marcatori vicini a quelli già presenti.

## Verifiche

`PYTHONPATH=. pytest -q tests/test_r208* tests/test_r207_native_remote_routes.py` → 931 passed, 9 warnings. I tre test aggiuntivi verificano copertura delle tre pubblicazioni, esclusione dell'inferenza dal lock e controllo dei conflitti Lyrics/Chords prima del salvataggio.

## Limiti

Non costituisce certificazione con processi distribuiti su host differenti; i lock POSIX sono validi solo su filesystem che supportano correttamente flock condiviso. Il worker di importazione tracce asincrono e altri writer del server richiedono ancora una revisione specifica. Il mirroring dei repository NON fa parte di MTA Audio Editor.
