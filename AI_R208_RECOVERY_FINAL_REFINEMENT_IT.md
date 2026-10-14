# MTA Audio Editor 0.3.0-r208 — recovery billing dopo pubblicazione

## Modifica verificata localmente

Il coordinatore `app/ai_finalization.py` ricostruisce una consegna contabile mancante dopo una pubblicazione audio confermata, **solo** se il job richiede billing e il bridge conserva misure persistenti utilizzabili. La creazione del job ledger e la registrazione nell'Outbox sono idempotenti; la consegna è sottoposta alle verifiche già presenti. In assenza di evidenze affidabili il completamento rimane bloccato (fail closed). La ricostruzione opera solo nel percorso `reconcile(..., deliver_billing=True)`.

## Prove

`PYTHONPATH=. pytest -q tests/test_r208_*.py` — 176 passati in ambiente locale. Due nuovi scenari: crash tra pubblicazione audio e Outbox billing, e rifiuto senza misurazioni.

## Limiti non certificati

Questo **non** equivale a certificazione di atomicità ACID fra filesystem, scheduler e ledger; serve crash injection end-to-end reale in staging, con recovery e riconciliazione dei tre sistemi. Non risultano certificati i consumi GPU su Radeon 8060S né tutti gli adapter reali EL10/ROCm. La copertura degli endpoint AI legacy e remoti richiede ulteriore revisione. Non eseguire crash injection su servizi di produzione.

## Collaudo operatore

Su una istanza di staging isolata e dopo backup: eseguire `python scripts/crash_inject_ai_outbox_r208.py`, `python scripts/certify_ai_r208.py --hardware --output ai-hardware-probe.json`, poi una inferenza reale per ogni adapter e verificare una sola pubblicazione, una sola riga ledger e stato completato dopo riavvio, con metriche coerenti o job bloccato quando non disponibili.
