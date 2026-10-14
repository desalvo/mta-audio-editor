# MTA 0.3.0-r208 — ammissione AI differita e ledger

Questa revisione persiste l'ammissione Arranger/Remix prima di attivare il worker. Se esiste un utente autenticato con billing abilitato, `provision_inference_job` crea o recupera l'identità ledger in modo idempotente. Un errore lascia il job `blocked` con messaggio `Ledger admission needs reconciliation`, senza attivare il worker. All'avvio del server le ammissioni persistenti vengono riconciliate prima del recupero della coda.

L'account amministrativo legacy con ID 0 non è automaticamente fatturabile. Il provisioning non crea consumi GPU/CPU fittizi né addebiti impliciti per utenti con billing disabilitato.

## Limiti di certificazione

Non è ancora garantita la chiusura di ogni job billable nel ledger: manca la trasmissione idempotente dei consumi misurati dal worker al billing outbox lungo tutti i percorsi di inferenza. Le tre risorse (database coda, archivio dei progetti, database billing) non sono un'unica transazione ACID. Gli adapter non sono stati collaudati su EL10/ROCm.

## Prove locali

`PYTHONPATH=. pytest -q tests/test_r208*` e `bash -n scripts/install_mta.sh`.

## Collaudo richiesto dopo il completamento software

Su ambiente di staging `ollama-02`: backup di progetti e database, inferenza reale di ogni adapter, crash injection su copia isolata, confronto di job/published WAV/ledger prima e dopo reboot; evitare l'interruzione diretta dei servizi produttivi.
