# r208 — Tre chiusure di concorrenza manutentiva

1. GET /api/projects: il recupero amministrativo dei progetti legacy acquisisce il lock cross-process per progetto, ricarica il record aggiornato e assegna la proprietà solo se ancora nulla. Previene la perdita di aggiornamenti e la riattribuzione di progetti assegnati da altri processi.
2. GET /api/projects/{pid}: manutenzione storage, migrazione metadata di clip, base BPM e canali vengono eseguiti interamente sotto il lock condiviso, prima del caricamento, preservando altri writer coordinati.
3. POST /api/projects/{pid}/tracks/{track_id}/estimate-bpm: lettura traccia, inferenza del tempo e salvataggio del progetto sotto il lock condiviso, evitando di sovrascrivere modifiche concorrenti.

Tre test comportamentali simulano acquisizione/rilascio, corretta sequenza e mancata riattribuzione della proprietà. La misura BPM tiene il lock durante l'inferenza: scelta conservativa, può rallentare altri editor dello stesso progetto. Non viene dichiarata un'atomicità filesystem-DB generale o una certificazione multiprocesso su hardware.
