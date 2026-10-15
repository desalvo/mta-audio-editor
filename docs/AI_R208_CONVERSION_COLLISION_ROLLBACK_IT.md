# MTA Audio Editor 0.3.0-r208 — rollback collision-safe delle conversioni

## Problema
Il cleanup di `_save_upload` cancellava un nome WAV di conversione presunto, senza verificare se il file fosse stato realmente creato dall'upload. In caso di collisione su un WAV già presente, il tentativo fallito poteva quindi cancellare materiale preesistente.

## Intervento
- L'upload conserva l'identità filesystem `(st_dev, st_ino)` dei file creati e durante il rollback cancella soltanto i file con la stessa identità, evitando di reclamare il file WAV di un'altra importazione.
- Un file di conversione viene acquisito nella lista di rollback soltanto se il suo nome non era già occupato al momento del tentativo e la conversione restituisce il nuovo percorso.
- Se `subprocess.run(ffmpeg)` solleva un'eccezione, il WAV temporaneo di conversione viene rimosso.

## Verifiche
- Collisione nella conversione durante `_save_upload`: WAV preesistente preservato, nuovo upload eliminato, nessun temporaneo residuo.
- Eccezione del processo ffmpeg: audio originale preservato, destinazione preesistente preservata, temporaneo rimosso.
- Suite locale: 980 test superati e 9 warning con `PYTHONPATH=. pytest -q tests/test_r207_native_remote_routes.py tests/test_r208*`.

## Limiti
Non è una transazione ACID complessiva. Il cleanup delle copie `originals/` necessita ancora di ownership più rigorosa se processi esterni possono scrivere quella directory senza usare il lock condiviso. Collaudo operativo multiprocesso e ROCm ancora aperto.
