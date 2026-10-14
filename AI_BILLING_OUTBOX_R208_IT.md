# MTA 0.3.0-r208 — Consegna contabile persistente (opt-in)

## Implementato

`app/ai_billing_outbox.py` registra una intenzione immutabile di finalizzazione
associando un job di inferenza a un job **già creato** nel ledger. La consegna
usa `finish_job_idempotent()`, un lock interprocesso e un ACK persistente.
Dopo un crash tra commit nel ledger e ACK della Outbox, il retry riconosce
la stessa finalizzazione; in caso di conflitto l'operazione si arresta.
All'avvio del server viene tentata la consegna delle registrazioni pendenti,
senza interrompere il recupero della coda in caso di errore nel ledger.
Non vengono fabbricati consumi o addebiti e non vengono creati job billing
in modo implicito.

## Verifica riproducibile in ambiente isolato

```bash
PYTHONPATH=. python -m pytest -q \
  tests/test_r208_billing_delivery_outbox.py \
  tests/test_r208_audio_publication_outbox.py \
  tests/test_r208_outbox_queue_reconciliation.py
PYTHONPATH=. python -m pytest -q tests/test_r208*
python scripts/crash_inject_ai_outbox_r208.py
python scripts/certify_ai_r208.py --hardware --output ai-hardware-probe.json
```

Questi comandi non arrestano servizi. Il probe hardware controlla il runtime,
ma non esegue i modelli e non certifica gli adapter.

## Blocchi per la certificazione end-to-end

- Creare il job di billing con user_id attendibile *prima* dell'inferenza e
  salvare il legame durevole con il job dello scheduler (anche dopo retry HTTP).
- Rendere la conferma contabile un prerequisito del `completed` visibile.
- Associare esclusivamente misure reali autenticate alla finalizzazione,
  e definire policy sui casi senza misurazione verificabile.
- Verificare race fra cancellazione, pubblicazione e contabilizzazione,
  nonché concorrenza di diversi job sullo stesso progetto.
- Certificare ogni adapter con inferenza reale su EL10/ROCm e raccogliere
  evidenze di risultati, cancellazione, consumo e recupero.

## Criterio di sicurezza

Non collegare automaticamente `register()` agli endpoint Arranger/Remix
finché non è garantita l'identità del soggetto fatturato. L'API Python è
volutamente interna. Questa implementazione è una **consegna contabile
idempotente**, non una transazione distribuita ACID né una certificazione
exactly-once end-to-end.
