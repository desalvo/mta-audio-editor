# MTA Audio Editor 0.3.0-r208 — Tre chiusure di scrittura concorrente

Tre percorsi di modifica del progetto, in precedenza non coordinati con la pubblicazione asincrona AI, usano ora `_serialized_project_mutation` e il lock cross-process `project_publication_lock(pid)`:

1. **Sample editor:** gli endpoint `POST /api/projects/{pid}/tracks/{track_id}/sample-editor/edit` e `POST /api/projects/{pid}/tracks/{track_id}/sample-editor/effect-apply` serializzano lettura, modifica audio e salvataggio. La preview resta read-only e non acquisisce il lock.
2. **Condivisioni:** `POST /api/projects/{pid}/shares` e `DELETE /api/projects/{pid}/shares/{user_id}` serializzano la modifica dell'elenco condivisioni rispetto agli altri writer sullo stesso progetto.
3. **Eliminazione progetto:** `DELETE /api/projects/{pid}` verifica l'accesso e cancella il progetto sotto lock, evitando cancellazioni concorrenti con i writer che usano la stessa barriera.

Il decoratore importa il provider del lock al momento della chiamata (senza cambiare le firme FastAPI), per supportare correttamente anche verifiche e sostituzioni controllate del provider nei test.

Validazione: `PYTHONPATH=. pytest -q tests/test_r207_native_remote_routes.py tests/test_r208*` -> **945 passed, 9 warnings**; 8 verifiche mirate incluse. Non testato contro più processi server reali. Rimangono aperti i writer non ancora coordinati, la transazionalità filesystem/progetto e il billing GPU.
