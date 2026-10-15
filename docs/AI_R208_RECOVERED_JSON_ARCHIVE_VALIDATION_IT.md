# r208 — Chiusura software: validazione archivi JSON AI recuperati

La fase di applicazione di risultati Whisper/Chords recuperati dal journal o dallo storico remoto verifica ora prima di ogni estrazione che lo ZIP contenga nomi portabili, unici e non ambigui, senza directory né symlink e con limiti per file e dimensione complessiva espansa. L'annotazione attesa deve essere presente esattamente una volta. La verifica precede ogni modifica al progetto, per evitare applicazioni parziali in caso di ZIP non valido.

Test: suite combinata di discovery, import WAV, JSON, stem, transazioni e UI: 49 passed, 9 warnings. Questo certifica il sottosistema di validazione dei pacchetti JSON e gli scenari eseguiti, non l'intera macroarea di generazione/recovery AI né la regressione globale.

Versione: 0.3.0-r208 invariata. Nessun collaudo hardware o deployment eseguito.
