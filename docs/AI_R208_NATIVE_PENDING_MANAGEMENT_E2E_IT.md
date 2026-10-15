# MTA 0.3.0-r208 — Gestione richieste remote native pendenti

La finestra **Native AI processing** visualizza le richieste remote rimaste in sospeso dopo errori di rete o riavvii. Il comando **Check status / Verifica** interroga in sola lettura lo stato durevole sul server con la stessa configurazione remota e il token corrente, **senza effettuare un nuovo POST di inferenza**.

Endpoint native single-user protetti: `GET /api/native/ai-workers/pending` e `GET /api/native/ai-workers/pending/{request_id}/status`.

Le registrazioni nuove contengono request ID, tipo di adapter, URL e timestamp; non memorizzano bearer token né audio. La risposta di lista non espone l'URL. Le richieste legacy prive di metadati restano pendenti e non vengono automaticamente riavviate. I journal non leggibili sono segnalati e conservati. La verifica rifiuta identificativi non presenti nel registro, credenziali cambiate e modalità non remota. Il comando non cancella né fattura né avvia job; il recupero degli artifact resta nel percorso `native_ai_routing.infer` con lo stesso identificativo.

Limiti: non è ancora una dashboard operativa globale dei job del server. Non sostituisce la validazione con server reale e perdita di rete. Il metering GPU fatturabile resta non implementato.
