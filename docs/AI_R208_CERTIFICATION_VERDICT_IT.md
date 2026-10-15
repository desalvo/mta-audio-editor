# MTA Audio Editor 0.3.0-r208 — Certification gate

## Esito

**Atomicità end-to-end: NON CERTIFICATA.** Il registro `terminal_receipts` è aggiornato insieme allo stato del job nella stessa transazione SQLite; `app/ai_billing.py` utilizza una finalizzazione idempotente in un ledger separato e la pubblicazione audio avviene su filesystem. Non esiste una singola transazione che coinvolga tutte e tre le risorse. Senza un outbox consumato in maniera idempotente, riconciliazione e publication staging verificati con crash injection, la proprietà exactly-once end-to-end non è dimostrabile.

**Adapter EL10/ROCm: NON CERTIFICATI in questo ambiente.** Sono richiesti test reali con Rocky Linux EL10, ROCm 7.2.4, gfx1151; il controllo locale non implica l'esecuzione remota sul server ollama-02.

## Controlli eseguiti

- Test locali mirati scheduler, blocked-recovery e billing idempotente.
- Static gate `python scripts/certify_ai_r208.py` (sola lettura).
- Per produrre prova dell'hardware, eseguire `python scripts/certify_ai_r208.py --hardware --output ai-hardware-probe.json` **sul server EL10**, in ambiente con PyTorch e ROCm disponibili. Il probe non modifica i servizi né usa API remote.

## Criteri mancanti per la certificazione

1. Commit idempotente dell'evento di billing associato alla ricevuta terminale; retry dopo crash in ogni punto del processo.
2. Stage del risultato audio, pubblicazione atomica per job e riconciliazione di output già pubblicati dopo crash.
3. Test di concurrency, cancellation, recovery e billing con fault injection su file system e database separati.
4. Smoke-test reali ACE-Step, Whisper, Demucs, DrumSep, SAM Audio, vocal separation e chord analysis su EL10/ROCm con raccolta log sanitizzati.
5. Verifica che CPU/GPU seconds siano misure attribuibili al job e non stime del tempo trascorso.

Questo gate non dichiara superati i criteri 1-5.
