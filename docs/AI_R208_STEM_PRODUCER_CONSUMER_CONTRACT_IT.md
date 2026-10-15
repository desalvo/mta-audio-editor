# MTA 0.3.0-r208 — contratto produzione/importazione stem

Chiusura software del contratto per gli archivi stem: il produttore accetta solo file WAV `.wav`, JSON `.json` e testo `.txt` coerenti con i tipi dichiarati. L'importatore impone già queste condizioni. L'allineamento impedisce al worker di pubblicare un pacchetto che il destinatario respingerebbe per estensione del testo. Le verifiche di manifest, SHA-256, limiti, nomi riservati e collisioni cross-platform rimangono attive.

È stato aggiunto un test reale in-process produttore→ZIP→importatore→progetto con WAV, JSON e testo, verifica di unica traccia e ricevuta persistente, oltre alla regressione negativa del testo con estensione scorretta.

Esito: 39 test mirati superati (8 warning); 33 test di integrazione e stem superati (8 warning). Regressione globale e r208 completa non certificate in questo ciclo; collaudi su Windows/macOS e hardware reale ancora da effettuare.
