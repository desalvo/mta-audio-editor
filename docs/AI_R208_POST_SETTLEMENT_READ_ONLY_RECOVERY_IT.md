# MTA Audio Editor 0.3.0-r208 — recupero post-settlement senza reinferenza

## Implementato

- `app.ai_remote_client.remote_request_status`: interrogazione GET autenticata del record durevole, con validazione di URL, token, chiave, dimensione del JSON, stato e identificativo worker.
- `app.ai_remote_client.recover_after_lost_response`: recupero read-only dopo risposta HTTP persa; risolve la richiesta tramite GET dello stato e recupera l'artefatto soltanto se completata; attesta nuovamente risultato e misurazioni CPU tramite la funzione di replay esistente.
- Stati `admitted`, `failed`, `cancelled` non autorizzano POST, reinferenza o addebiti nuovi.
- Attesa opzionale limitata, interrompibile tramite cancellazione; di default un solo status lookup.
- 14 nuovi test che coprono replay, stato inconcludente, risposta corrotta, errore rete, annullamento, digest e limiti delle configurazioni.

## Verifiche

Suite `pytest -q tests/test_r208*`: 840 passed, 9 warnings (14 ottobre 2026).

## Limiti e lavoro aperto

La nuova API di recupero è disponibile e verificata, ma non è ancora collegata automaticamente a tutte le schermate delle app native. Non sostituisce la verifica sui worker reali e non garantisce metering GPU. Il metering remoto CPU mantiene le verifiche di firma già esistenti; un recupero con `metering_sink` richiede le relative chiavi.
