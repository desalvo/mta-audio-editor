# MTA 0.3.0-r208 — recovery WAV e regressione estesa

- Gli WAV recuperati dal journal nativo vengono denominati usando l'intero request_id di 32 caratteri, non più il prefisso di 12: elimina collisioni fra job diversi che condividono il prefisso e conserva l'identità end-to-end fra progetto e interfaccia.
- Il job quality di GitHub Actions dispone ora di timeout esplicito di 120 minuti, mantenendo la soglia minima di copertura esistente.
- Regressione `tests/test_r208* tests/test_r180_worker_protocol_and_pdc.py`: 1153 passed, 12 warnings in 36.44s (prima dei tre nuovi test).
- Regressione dedicata comprensiva dei tre nuovi test: 12 passed, 8 warnings.
- Limiti: non certificati test GPU reali né pacchetti installer su tutte le piattaforme; gli import di artifact scoperti senza journal locale restano non automatici per evitare attribuzioni non verificate.
