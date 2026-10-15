# MTA 0.3.0-r208 — recupero delle richieste AI dopo il riavvio del client

## Nuova funzionalità

- `GET /api/ai-jobs/requests?limit=50&offset=0&state=completed` restituisce l'elenco autenticato delle richieste AI persistenti del solo proprietario, con ordine stabile, paginazione fino a 100 e filtro opzionale di stato.
- Il nuovo helper `app.ai_remote_client.list_remote_requests(...)` permette alle app native di recuperare gli identificativi delle richieste anche dopo aver perso lo stato volatile al riavvio.
- I dati comprendono `request_key`, `state`, `job_id`, `created_at`; non vengono esposti fingerprint, token o dati di altri proprietari.
- L'elenco non avvia inferenze, non addebita risorse e non sostituisce il recupero autenticato dell'artifact: per i risultati completati si usa `recover_audio` con `request_key` originale.
- Sono controllati input, risposte, isolamento, paginazione, stati terminali e record incoerenti nelle pagine richieste.

## Limitazioni e verifiche residue

- La discovery dipende dalla persistenza del database di autenticazione sul server. Per un risultato remoto, il payload deve ancora essere presente nella cache entro il relativo TTL.
- L'elenco fotografa uno stato che può evolvere; il client deve verificare il risultato o il suo stato prima dell'utilizzo.
- I test automatici coprono il percorso API e la libreria client con worker simulati, non l'effettiva UI delle piattaforme desktop né l'inferenza su GPU reali.
