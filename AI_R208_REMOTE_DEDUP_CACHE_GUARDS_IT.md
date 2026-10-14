# MTA 0.3.0-r208 — finalizzazione e pulizia cache remota

## Modifiche del ciclo

- La finalizzazione del record di idempotenza richiede un ID job esplicito in stato `completed`, rifiuta ID in stato `failed` e non può modificare un record già finalizzato con esito o ID differente. Una ripetizione con identici stato e ID resta idempotente.
- Non è possibile finalizzare una richiesta inesistente o appartenente a un altro utente senza ricevere errore.
- `purge_expired()` condivide il lock per richiesta di `save()` e `load()`, controlla i file usando l'apertura senza seguire symlink e rifiuta gli hardlink. Un file aggiornato da un writer non viene cancellato sulla base di metadati scaduti letti prima di ottenere il lock.
- Aggiunti test di regressione per finalizzazione immutabile, isolamento dell'utente, symlink, hardlink, dry-run e rimozione corretta.

## Verifiche locali

`PYTHONPATH=. pytest -q tests/test_r208* tests/test_r207_ai_request_idempotency.py`: 290 passed (8 warnings deprecazione framework).

## Limiti e lavoro ancora aperto

Le correzioni non equivalgono alla certificazione end-to-end del billing per tutti gli adapter. Restano da verificare su worker reali l'attribuzione GPU attendibile, i percorsi remoti/legacy e il crash recovery del ciclo inferenza–misurazione–outbox–pubblicazione. La cache dei risultati resta opzionale e i dati temporanei possono richiedere un timer di pulizia esterno su installazioni poco usate.
