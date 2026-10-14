# MTA Audio Editor 0.3.0-r208 — Ripristino persistente Lyrics/Chords

## Modifiche
- Whisper/lyrics e analisi chords sono accodati con payload JSON versionato nel database dello scheduler condiviso.
- Il payload contiene progetto, traccia, opzioni del motore e intervallo; il restorer verifica schema, argomenti e presenza della traccia prima di preparare il worker.
- Al riavvio si ricostruiscono le proiezioni dei job consultabili dalle API legacy con lo stesso `job_id`.
- L'evento di cancellazione dello scheduler viene passato al worker ripristinato.
- I job **running** interrotti non vengono riprodotti automaticamente: gli effetti collaterali di un'analisi parziale non sono ancora transazionali; serve revisione/retry esplicito.
- L'abilitazione di questo recovery non rende ancora persistenti gli altri job legacy di stem separation/model download, né certifica la contabilizzazione dei worker remoti.

## Verifiche
`PYTHONPATH=. pytest -q tests/test_r208*` — 211 superati. La suite è locale e non sostituisce i test di inferenza effettiva su EL10/ROCm.

## Operazioni
Nessun commit/push. Versione invariata 0.3.0-r208. Nessuna modifica a CT 130 o ollama-02.
