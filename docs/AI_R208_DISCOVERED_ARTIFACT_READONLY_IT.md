# r208 — Download autenticato degli artifact scoperti sul server

Il pannello native AI Workers consente di scaricare un risultato remoto già completato e scoperto tramite lo storico persistente, anche in assenza della ricevuta nel journal locale.

- Endpoint di sola lettura `GET /api/native/ai-workers/remote-history/{kind}/artifact/{request_id}`.
- Le credenziali rimangono sul server nativo; l'endpoint rivalida l'ownership tramite la discovery `completed` e il token del worker attualmente configurato.
- Il recupero richiama la procedura esistente di download e verifica delle attestazioni; non avvia inferenze, non aggiorna il journal e non importa nel progetto.
- I download forniscono `Cache-Control: no-store`, MIME limitati (JSON/WAV/ZIP) e identificatori validati.
- Richieste assenti, incomplete o non visibili al token configurato non sono recuperabili.

**Limite esplicito:** non si può stabilire la provenienza progettuale dell'artifact con il solo storico server: l'import automatico continua a richiedere una ricevuta locale verificata. La discovery di richieste oltre la finestra di 10.000 record non è supportata da questo endpoint.

Test: `PYTHONPATH=. pytest -q tests/test_r208_discovered_artifact_download.py tests/test_r208_native_remote_history_ui.py tests/test_r208_native_pending_artifact_e2e.py`.
