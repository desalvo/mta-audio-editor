# r210 — MR-MT3 resumable inference / Inferenza riprendibile

## Italiano

- Aggiunto `scripts/run_mrmt3_resumable.py`: inferenza CPU offline reale per finestre, salvataggio atomico di token numerici JSON e manifesto legato agli hash SHA-256 di PCM e modello. Risultati di input/modello differenti non possono essere riutilizzati come fossero dello stesso benchmark.
- Verificato con il checkpoint SafeTensors derivato dal file MR-MT3 autorizzato e l'audio Merish5 originale (estratto WAV reale di 12 secondi). Primo comando: 1/6 finestre; seconda esecuzione: 2/6; terza esecuzione: 6/6 senza ricalcolare le prime due.
- Totale generato: **165 note**, identico al precedente esperimento da 12 secondi; 0 eventi invalidi, 2 note chiuse a fine decoding. Regressioni mirate: **27 passed, 0 failed**.
- I numeri di accuratezza precedenti restano insoddisfacenti: 4 corrispondenze con programma su 176 note completate del riferimento secondo il confronto diagnostico precedente. Nessun miglioramento artificiale dell'F1, nessuna soglia abbassata.
- Questa prova non completa l'audio di 248 secondi e non certifica accuratezza su 10–16 strumenti. La separazione strumentale continua a essere una questione di qualità del modello, non un problema risolto dalla persistenza.

## English

- Added `scripts/run_mrmt3_resumable.py`: real offline CPU inference with atomic per-window numeric JSON and audio/model SHA-256 manifest. Stale or mismatched windows are rejected.
- Real 12 s Merish5 waveform and reviewed MR-MT3 SafeTensors checkpoint: checkpointed 1/6, resumed 2/6, completed 6/6 windows without recalculating saved windows.
- **165 generated notes**, equal to the earlier 12-second run, no invalid decoding events, two automatically closed notes; **27 focused tests passed**.
- Instrument-aware accuracy remains below target; no 10–16-instrument quality claim or full-track benchmark claim.

### Offline execution

Place the external reviewed dependencies and weights in your own environment. Do not put copyrighted recordings, checkpoints or wheel caches inside the source distribution. For example:

```sh
PYTHONPATH="/path/to/mt3-runtime:/path/to/mt3-infer:$PWD" python scripts/run_mrmt3_resumable.py \
  --audio /path/to/mix.wav --model /path/to/model.safetensors \
  --output /path/to/work-results --max-windows 4
```

Exit status `2` intentionally means more windows are pending, `0` means a complete `prediction.json` exists; other errors are failures. Repeat the same command to resume. Inference output is evidence of execution, not measured accuracy without independently validated reference matching. No Git operations or deployment.
