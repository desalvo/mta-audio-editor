# MTA Audio Editor 0.3.0-r208 — Serializzazione delle mutazioni del progetto

Il server utilizza ora `project_publication_lock(pid)` per le operazioni ordinarie di modifica delle tracce e dei clip: sostituzione, eliminazione, delay, sincronizzazione metronomo, movimento, auto-sync, auto-mix, eliminazione intervallo, aggiornamento dei clip e istanziazione dei clip. Si tratta dello stesso lock già utilizzato da pubblicazione AI e importazione di WAV/JSON/ZIP recuperati.

Un wrapper sincrono o asincrono, applicato **prima** della registrazione FastAPI, preserva le firme degli endpoint e acquisisce il lock prima di caricare il progetto. Il rilascio avviene sempre, anche in caso di eccezione. Il wrapper non viene applicato agli endpoint che già acquisiscono il lock internamente, per evitare deadlock.

I test coprono tutte e dieci le firme, l'ordine di lock/esecuzione e il rilascio in caso di errore async. Suite r208 + route r207: 911 test superati, 9 warning. Non è ancora dimostrato l'isolamento globale di **tutti** gli endpoint che modificano il progetto: il lavoro sulle mutazioni non comprese in questo gruppo resta aperto. Nessun test su server ROCm reale.
