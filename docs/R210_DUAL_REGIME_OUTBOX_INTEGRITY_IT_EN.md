# Controlli di integrità checkout / Checkout integrity checks

IT: L’audit `audit_checkout_integrity` è di sola lettura e verifica la coerenza fra le ricevute della barriera e gli stati dell’outbox Stripe/PayPal. Non prova l’avvenuto regolamento del denaro, non interroga i provider e non sblocca il cambio di regime. `combined-readiness` riporta gli esiti e blocca i casi non verificabili o pendenti.

EN: The read-only `audit_checkout_integrity` compares checkout fence receipts with Stripe/PayPal outbox states. It does not verify financial settlement, query providers, or enable regime switching. `combined-readiness` includes its results and remains fail-closed for unresolved or inconsistent operations.
