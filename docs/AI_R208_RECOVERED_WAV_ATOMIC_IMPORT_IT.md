# Importazione atomica dei WAV recuperati — 0.3.0-r208

La route autenticata `POST /api/native/ai-workers/pending/{request_id}/import-wav/{pid}` esegue il recupero del solo artifact gia' completato (GET remoto) e l'importazione audio mentre mantiene il lock cross-process del progetto. La presenza di una traccia col nome deterministico della richiesta viene controllata sotto lo stesso lock: due finestre non possono importare simultaneamente la stessa richiesta.

Controlli: identita' native e accesso al progetto, identificativo richiesta valido, journal ancora di proprieta' locale, configurazione originaria ancora disponibile, tipo MIME audio/wav, header RIFF/WAVE e nessuna seconda inferenza. La richiesta originaria rimane nel journal per evitare doppia contabilizzazione. JSON e ZIP non sono importati nella timeline.

Collaudo: 873 regressioni r208 superate; manca collaudo operativo con server remoto reale. Il lock esistente richiede POSIX flock sul server.
