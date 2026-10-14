# R208 — Riconciliazione automatica delle importazioni stem all'avvio

All'avvio del servizio MTA il server cerca journal `.recovered-stems-pending.json` nei progetti validi e li riconcilia sotto `project_publication_lock`. Per importazioni non confermate elimina esclusivamente i nuovi file non referenziati nello snapshot iniziale, mentre preserva quelli registrati nel progetto. Journal danneggiati o altri errori rimangono intatti e vengono registrati nei log per intervento manuale. Non riesegue modelli e non modifica il billing.

Test locali: `PYTHONPATH=. pytest -q tests/test_r208*.py` — 886 superati. Il recovery resta limitato all'importer stem che utilizza il journal dedicato; non fornisce una transazione distribuita tra tutti gli importatori.
