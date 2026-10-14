# r208 — Client nativi: recupero durevole dopo risposta persa

I sette adapter configurati tramite `native_ai_routing.infer` condividono ora un journal persistente `remote-pending` sotto la directory della configurazione nativa (`MTA_NATIVE_REMOTE_JOURNAL` per override).

Prima del POST viene salvato su disco, con fsync, l'identificativo di idempotenza; la chiave associa URL, token, adapter, opzioni JSON e byte WAV mediante SHA-256. In caso di risposta persa, crash, artifact non valido o ledger non disponibile, il journal rimane. La successiva richiesta con gli stessi dati usa soltanto `recover_after_lost_response` (GET status + GET result) e non effettua una seconda inferenza. Al successo, il journal viene eliminato. Chiavi danneggiate fanno fallire l'operazione in modalità chiusa.

Garanzia locale verificata con mock di trasporto: nessun secondo POST a seguito della perdita della risposta e nessuna cancellazione della richiesta pendente in caso di fallimento. Validazione in un server Rocky/ROCm reale ancora necessaria. Per ritentare volontariamente una nuova inferenza dopo un errore terminale occorre una procedura esplicita di reset del journal, non implicita: ciò evita doppie fatturazioni accidentali.

Il journal non contiene token né audio, soltanto un id UUID. Il fingerprint include il token per separare gli utenti e dipende dal contenuto. La protezione riguarda il percorso `native_ai_routing.infer` e i chiamanti che lo utilizzano; non certifica i backend AI esterni che adottano altre pipeline.
