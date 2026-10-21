# R210 — Multi-model fixed benchmark / Benchmark multi-modello a protocollo fisso

## Italiano

`scripts/compare_multitrack_models.py` valuta output JSON *reali* sullo stesso audio e sul MIDI originale. Ogni output deve contenere `notes` con `program` (GM 0–127), `is_drum`, `pitch`, `start_time`, `end_time`. Per le percussioni il gruppo è `drums`. Matching uno-a-uno, identico pitch, programma esatto, onset <= 50 ms, offset <= 100 ms, offset globale **zero**. Nessuna taratura sui riferimenti, nessuna soglia abbassata. Il matching senza programma serve **solo** da diagnostica.

Esempio (aggiungere YourMT3+ solo dopo inferenza reale indipendente):

```bash
python scripts/compare_multitrack_models.py \
  --midi '/path/All Night Long.MID' \
  --prediction 'MR-MT3=/path/mrmt3-results/prediction.json' \
  --prediction 'YourMT3+=/path/yourmt3-results/prediction.json' \
  --output /path/multimodel-score.json
```

La baseline MR-MT3 ROCm completa conservata è: 10.632 note riferimento, 8.853 note previste, 925 abbinamenti rigorosi, F1 9,494%. Questi numeri **non** indicano raggiungimento dell'obiettivo 10–16 strumenti. Il nuovo script **non** esegue né installa YourMT3+ e non sostituisce un benchmark con dati indipendenti.

## English

The offline script compares independently inferred model outputs against the same ground-truth MIDI with fixed zero alignment, exact GM program and pitch, 50 ms onset and 100 ms offset tolerances. It exports aggregate and per-GM-program precision/recall/F1. Program-agnostic matching is diagnostic only. No offset fitting, automatic downloads, inference simulation, or quality pass assertion. YourMT3+ remains untested on this recording until its actual prediction JSON is supplied.
