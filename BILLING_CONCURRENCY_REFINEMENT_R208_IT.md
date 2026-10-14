# MTA 0.3.0-r208 — Billing concurrency refinement

- Quattro retry concorrenti identici della consegna contabilizzano il job una sola volta (test).
- Retry identici dopo chiusura periodo ammessi, retry discordanti respinti (test).
- Timestamp espliciti di finalizzazione validati come interi non negativi; bool, float e stringhe respinti.
- Test locali: 132 passed (test_r208*.py e test_r207_billing_atomic_close.py).

Limiti: transazioni atomiche cross-database con la coda, pubblicazione audio e conferma hardware EL10/ROCm non certificate. Nessun commit o deployment.
