# r208 — Gate di finalizzazione durante l'esecuzione normale

Il worker dello scheduler ora richiede una ricevuta di pubblicazione audio e, per i job esplicitamente associati al ledger, una consegna billing confermata, prima di registrare `completed` per richieste Arranger/Remix durevoli (`schema_version: 1`). Se una consegna contabile pendente non riesce, il job passa a `interrupted` con ricevuta terminale ed è recuperabile attraverso il coordinatore Outbox, senza rilanciare l'inferenza. Non vengono creati nuovi addebiti implicitamente.

I job legacy in memoria, privi del payload durevole, mantengono la semantica precedente. Questi job non sono recuperabili dopo un crash e richiedono migrazione futura.

## Validazione

`PYTHONPATH=. pytest -q tests/test_r208*` — 149 test superati localmente.

Questo intervento **non completa** il binding autenticato e automatico di tutti gli ingressi AI al ledger, né certifica atomicità end-to-end per tutte le funzioni AI. Restano necessari prove di crash injection con vero billing, audit degli ingressi legacy e test adapter su EL10/ROCm.
