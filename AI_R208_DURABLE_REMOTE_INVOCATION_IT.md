# MTA 0.3.0-r208 — Invocazione remota durevole e metering

## Implementazione
- `ai_metering_bridge.infer_durable_remote`: interfaccia interna per job Arranger/Remix durevoli.
- Deriva una chiave di idempotenza stabile da `local_job_id`, anche dopo un riavvio.
- Richiede un worker valido, keyring operatore attivo, verifica rigorosa richiesta/risultato e attestazione HMAC v2.
- Le evidenze verificate vengono consegnate al sink che associa in modo immutabile job remoto e job locale, evitando attribuzioni GPU non autenticate.
- Errori di rete e misure assenti non consentono fallback all'inferenza locale.

## Verifiche
Suite `tests/test_r208*`: 760 superati; `compileall app` e `bash -n scripts/install_mta.sh` superati.

## Limiti
L'interfaccia è disponibile ma non è ancora agganciata automaticamente a ogni chiamante della piattaforma. La misura GPU job-specific, la certificazione crash end-to-end e le prove EL10/ROCm restano aperte. Questi interventi non costituiscono oltre 100 modifiche funzionali indipendenti.
