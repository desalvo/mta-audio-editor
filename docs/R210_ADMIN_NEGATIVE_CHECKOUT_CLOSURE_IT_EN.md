# MTA 0.3.0-r210 — Negative checkout closure / Chiusura checkout negativi

## IT

Endpoint amministrativo autenticato: `POST /api/admin/service-regime/close-negative-checkout`, body JSON esatto `{ "provider": "stripe", "order_id": "<id locale>" }` (oppure `paypal`). **L’endpoint non consulta il provider**: richiede che una verifica esterna affidabile sia stata già registrata nell’outbox come esito negativo (`cancelled` / not_created). In una transazione `BEGIN IMMEDIATE` controlla il ledger economico e chiude ordine e barriera solo in assenza di evidenze di pagamento/cattura/rimborso. La ripetizione è idempotente; stati incerti sono rifiutati. Richiede privilegi admin. Non cambia il regime e non emette movimenti finanziari. Test locali: 63 passed; nessuna integrazione reale con provider collaudata.

## EN

Authenticated admin endpoint: `POST /api/admin/service-regime/close-negative-checkout`, exact JSON body `{ "provider": "stripe", "order_id": "<local id>" }` (or `paypal`). **The endpoint does not contact the provider**: it requires previously trusted external verification to have been recorded in the outbox as a negative (`cancelled` / not_created) result. Within one `BEGIN IMMEDIATE` transaction it checks the financial records and closes the local order and fence only with no evidence of payment/capture/refund. Retries are idempotent; uncertain states are rejected. Admin privileges required. It does not change the active regime or issue financial transactions. Local tests: 63 passed; no live provider validation.
