# r210 — Gate di chiusura / Closure gate (2026-10-21)

## Italiano

**Corretto:** cache di stadi Audio-to-MIDI con payload di risultato invalido: nuovo calcolo (mai inferenza simulata) e nuova scrittura del checkpoint. Protezione da eccezioni della decompressione. Test regression dedicato.

**Provato:** 108 superati, zero falliti, zero saltati nella regressione offline di 11 moduli. Il risultato non certifica inferenze neurali reali e non equivale alla regressione generale.

**Non completabile/certificabile qui:** checkpoint/voicebank/vocoder autorizzati e compatibili per DiffSinger, RVC, Seed-VC, Transkun; benchmark multi-strumento con ground truth; riproduzione e ascolto GM su piattaforme finali; UI browser/native; regressione generale con blocchi rete noti da analizzare. Possono emergere ulteriori difetti software. Nessun server è stato aggiornato.

## English

**Changed:** invalid-schema Audio-to-MIDI stage checkpoints are treated as cache misses and recomputed through the actual stage runner. Decompression failures are likewise treated as corrupt checkpoints; no fictitious model result is substituted.

**Verified:** 108 passed, 0 failed, 0 skipped across 11 offline test modules. This is neither real checkpoint inference nor a full repository regression.

**Outstanding:** separately licensed authorized checkpoints, voicebanks, vocoders, auxiliary models and SoundFonts, plus actual inference and instrument-level benchmarks, target GM listening, native/browser acceptance, and controlled full regression. Additional software changes may be needed after these validations. No production changes.
