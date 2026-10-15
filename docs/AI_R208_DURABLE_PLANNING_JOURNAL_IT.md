# Checkpoint MTA Audio Editor 0.3.0-r208 — Journal opzionale di pianificazione AI

L'impostazione `MTA_AI_PLANNING_DB=/percorso/assoluto/planning.sqlite` abilita il
journal SQLite delle **sole richieste di pianificazione** arranger/remix.
Se non impostata, rimane il comportamento originale volatile in memoria.

Il journal mantiene cronologia, isolamento progetto/proprietario, cancellazione
idempotente, paginazione e limite globale di 128 piani; usa transazioni
SQLite `BEGIN IMMEDIATE` per inserimento, evizione dei soli terminali e
cancellazione. Una nuova istanza può leggere i piani dopo il riavvio.

**Non è una coda di inferenza.** Nessuna elaborazione GPU viene avviata e nessun
consumo, accounting o importo può essere attribuito a questi piani. Le API
esistenti continuano a restituire `generation_available: false`; l'elenco espone
`durable: true` solo se il journal è attivato.

Precauzioni: usare un filesystem SQLite locale affidabile, directory accessibile
solo all'account del servizio e backup coerenti del database. Non impostare il
journal su un filesystem di rete non compatibile con locking SQLite. Non è una
soluzione per sincronizzare progetti e billing in una singola transazione ACID.

Test: inclusi persistenza dopo riavvio, proprietà, cancellazione ripetuta,
capienza fra istanze, concorrenza, validazione input e compatibilità volatile.

Limiti aperti: integrazione completa dei job inferenza native/server,
misure GPU fatturabili, test hardware e sistemi operativi reali, suite globale.
