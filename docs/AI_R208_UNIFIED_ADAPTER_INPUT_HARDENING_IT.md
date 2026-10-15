# MTA Audio Editor 0.3.0-r208 — Protezione ingressi adapter unificato

- La sorgente dell'adapter deve essere esattamente `source.wav` nel workspace privato del job.
- I symlink non sono ammessi, anche quando puntano a un file apparentemente nello stesso workspace.
- L'ingresso viene rifiutato prima di importare un backend di inferenza.
- Regressioni locali: `PYTHONPATH=. pytest -q tests/test_r208_*.py` (182 passed nell'ambiente di sviluppo).

## Limitazioni residue

La protezione dell'ingresso non certifica l'esecuzione hardware degli adapter, la copertura universale degli endpoint AI, l'atomicità tra filesystem e ledger o l'attendibilità della misura GPU. Occorrono collaudi dedicati su ollama-02 con ROCm e crash injection di staging. Nessuna modifica remota effettuata.
