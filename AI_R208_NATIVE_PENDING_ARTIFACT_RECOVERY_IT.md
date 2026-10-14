# MTA 0.3.0-r208 – Native pending artifact recovery

Chiusura locale: dalla finestra Native AI processing è possibile scaricare l’artifact già completato di una richiesta pendente senza rieseguire l’inferenza. Endpoint autenticato `GET /api/native/ai-workers/pending/{request_id}/artifact` limitato alla modalità single-user nativa; verifica proprietà nel journal e corrispondenza con l’attuale configurazione del worker, recupera esclusivamente via GET e restituisce JSON, WAV o ZIP con intestazioni no-store/nosniff. Il journal rimane finché il risultato non viene consumato dal normale percorso nativo, prevenendo una seconda fatturazione. I token non sono esposti alla UI.

Verifica locale: 869 test r208 superati; smoke endpoint 13 test. Nessun test hardware o modelli reali. L’utente deve ancora scegliere l’importazione nel progetto dell’artifact scaricato; si tratta di recupero/scaricamento, non applicazione automatica alla timeline. GPU billable non implementato.
