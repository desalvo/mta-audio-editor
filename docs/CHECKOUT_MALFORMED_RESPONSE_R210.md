# Recupero checkout con risposte malformate — r210

Baseline: commit ee4e37fd30c39a72638b303b01ca0cd5b090f272, full CI 41156985339 verde; 4361 blob confrontati con il cumulativo ci-41152 senza differenze.

Risposte di creazione Stripe/PayPal non oggetto, o PayPal con collegamenti non validi o identificatore non testuale, ora producono errore gestito invece di AttributeError/TypeError. Anche la risposta OAuth PayPal non oggetto viene rifiutata esplicitamente. L'outbox resta incerto e conserva il tentativo, perciò un nuovo tentativo non effettua una seconda POST.

Test: 62 casi distinti passati tra checkout, recupero, preventivi e pagamenti; uno dimostra creazione remota simulata, risposta malformata, recupero autenticato e acquisizione idempotente. Ruff, scansione Bandit completa (309 file, 168 finding ID identici: 0 HIGH, 21 MEDIUM, 147 LOW), inventari AI, service admission e remote transport superati. I controlli e le disposizioni esistenti non sono stati allentati. La CI e provider reali non sono stati rieseguiti.

Questa è una correzione parziale di A5: gli altri esiti e recuperi ancora aperti nel piano restano da completare. RC invariata 32/42 = 76,2% (precommercial-20261030), non completamento totale prodotto.

Commit suggerito: Handle malformed checkout responses without duplicate dispatch
