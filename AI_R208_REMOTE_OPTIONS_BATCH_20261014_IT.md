# MTA 0.3.0-r208 — Batch esteso opzioni dei worker AI remoti

La versione resta 0.3.0-r208. Nessun commit, push o accesso all'hardware.

## Interventi coperti

Il contratto di ammissione delle opzioni è ora condiviso tra il client remoto nativo e il decoder del server; i controlli sono applicati ricorsivamente prima del trasporto e dell'esecuzione.

1. Campo `source_audio` vietato al livello principale.
2. `source_audio` vietato nei nodi annidati.
3. `input_path` vietato nei nodi annidati.
4. `output_path` vietato nei nodi annidati.
5. `command` vietato nei nodi annidati.
6. `executable` vietato nei nodi annidati.
7. `cwd` vietato nei nodi annidati.
8. `shell` vietato nei nodi annidati.
9. Chiavi vietate negli oggetti contenuti in liste.
10. Rifiuto chiavi vuote.
11. Rifiuto chiavi con backslash.
12. Rifiuto chiavi con newline.
13. Rifiuto chiavi con tabulazione.
14. Rifiuto chiavi con byte NUL.
15. Rifiuto chiavi con DEL.
16. Lunghezza massima delle chiavi.
17. Limite massimo degli elementi nelle liste.
18. Limite massimo delle chiavi negli oggetti.
19. Limite delle stringhe dei valori.
20. Rifiuto caratteri Unicode surrogate isolati.
21. Limite della profondità massima ricorsiva.
22. Limite sul numero totale dei nodi.
23. Rifiuto numeri NaN.
24. Rifiuto numeri +Infinity.
25. Rifiuto numeri -Infinity.
26. Rifiuto tuple nel client prima della conversione JSON.
27. Rifiuto set non JSON.
28. Rifiuto bytes non JSON.
29. Rifiuto chiavi non stringa nel client prima della conversione JSON.
30. Rifiuto chiavi duplicate nel JSON del server, anche se annidate.
31. Rifiuto dei valori JSON non-oggetto.
32. Compatibilità di roundtrip di opzioni valide con valori misti.

## Verifiche eseguite

- `PYTHONPATH=. pytest -q tests/test_r208_remote_options_tree_contract.py tests/test_r208*`: **434 test passati**.
- `python -m compileall -q app`: passato.
- `bash -n scripts/install_mta.sh`: passato.
- ZIP con checksum SHA-256 e test di integrità ZIP.

## Residui

Questo batch migliora il perimetro di validazione: non attesta l'esecuzione dei modelli ROCm, non completa il metering GPU autenticato per job e non prova la contabilizzazione remota end-to-end. Restano da completare e certificare separatamente.
