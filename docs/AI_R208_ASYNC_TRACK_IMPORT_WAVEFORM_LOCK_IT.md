# MTA Audio Editor 0.3.0-r208 — Import tracce e waveform asincroni

## Chiusura locale

- `_track_import_worker`: normalizzazione sample-rate, metadati, waveform e BPM rimangono fuori dal lock. La pubblicazione ricarica il progetto sotto `project_publication_lock(pid)`, verifica che il sample rate non sia cambiato, evita di riaggiungere lo stesso file e applica la stima BPM solo se il progetto aggiornato è ancora senza tracce.
- Il worker viene usato anche dal percorso di download/importazione YouTube.
- `_waveform_worker`: l'analisi della forma d'onda avviene fuori dal lock; sotto lock rilegge il progetto e verifica che la revisione della traccia non sia cambiata prima di applicare i picchi.
- Il worker non cancella il file sorgente se il salvataggio del progetto è già riuscito e un successivo aggiornamento dello stato solleva un errore.

## Verifiche

`PYTHONPATH=. pytest -q tests/test_r207_native_remote_routes.py tests/test_r208*`: 934 superati, 9 warning.

## Limiti

Verifiche locali e in larga parte di codice/endpoint mock; non ancora collaudo multiprocesso reale. L'importazione non garantisce una transazione atomica fra tutti i file audio e `project.json`, e non elimina tutte le possibili race degli altri writer. Nessuna variazione versione, commit o push.
