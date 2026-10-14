# MTA Audio Editor 0.3.0-r208 — Stato del software e handoff

## Verifiche locali
- Suite `PYTHONPATH=. pytest -q tests/test_r208*`: 186 test superati.
- La provenienza delle misure CPU trasmesse a `ai_metering_bridge.capture` conserva ora la distinzione `worker` (wait4) / `cgroup` (cgroup v2) e rifiuta valori senza origine riconosciuta.
- Bilanciamento contabile tramite outbox e recovery: modello saga con risorse SQLite e filesystem separate, NON transazione ACID globale.

## Limiti ancora aperti
- Misurazione GPU attendibile, autenticata e attribuita a ogni job su ROCm gfx1151.
- Copertura end-to-end di tutti i percorsi legacy/remoti (Whisper, Demucs, DrumSep, SAM Audio, ACE-Step e analisi accordi): la presenza di adattatori non dimostra una singola coda globale con contabilizzazione uniforme.
- Crash injection completa ai confini tra worker, audio, outbox e ledger; test con processi reali e concorrenza.
- Prove GPU e inferenza reale su ollama-02, Rocky EL10 e ROCm 7.2.4.

## Istruzioni minime non distruttive
Eseguire in staging dopo backup, non su produzione:

```bash
PYTHONPATH=. pytest -q tests/test_r208*
python scripts/certify_ai_r208.py --output ai-r208-static-report.json
python scripts/certify_ai_r208.py --hardware --output ai-r208-hardware-report.json
```

`certify_ai_r208.py` restituisce un verdetto statico, non una certificazione hardware né dell'atomicità.

Non è stato eseguito alcun commit o push. Non è stato modificato CT Proxmox 130. Versione invariata 0.3.0-r208.
