# r210 — CI e accuratezza multistrumento / CI and multi-instrument accuracy

## IT

**CI analizzata:** `logs_107350438982.zip`, job `Quality and unit tests`, fase Ruff: 15 errori (4 import non usati, 10 S108 riferiti a path fittizi in test mock, 1 S311 generatore casuale deterministico). Sistemati nei test con commenti locali e senza disabilitare controlli generali. `47 passed` in pytest mirato. Non è stato possibile eseguire Ruff in questo ambiente perché non installato e PyPI irraggiungibile (errore DNS). Non affermare che la CI remota sia già verde. Il log Playwright contiene alcuni tentativi DNS falliti ma il download Chromium è riuscito; non è il blocco osservato.

**Accuratezza 10–16 strumenti:** il precedente output MR-MT3 reale archiviato non supera la soglia; nessun nuovo checkpoint autorizzato, paired ground-truth o inferenza completa qui. Non dichiarare il lavoro completo. Occorre un insieme di registrazioni stereo originali con almeno 10–16 strumenti sovrapposti, MIDI di riferimento sincronizzati (tracce e programmi GM identificati), autorizzazione d'uso, versioni dei modelli, peso/checkpoint e hash SHA-256. Per ciascun modello registrare recall/precision/F1 rigorosi per strumento, pitch, onset, offset, duplicazioni, strumenti omessi e latenza. Non sostituire inferenze con fixture o rilassare soglie. Evitare di distribuire pesi privi di diritto.

## EN

**CI:** the supplied logs show Ruff failing with 15 findings (4 unused imports, 10 test-only S108 mock pathname literals, 1 deterministic test RNG S311). These are repaired with narrow test-local comments, no project-wide lint disable. Focused pytest: 47 passed. Ruff is not installed and package index DNS resolution failed locally, so remote green CI is not certified. Playwright eventually downloaded Chromium despite fallback DNS errors.

**10–16 instrument accuracy:** archived real MR-MT3 did not pass the unchanged strict gate. No fresh authorized checkpoint, paired stereo/ground-truth multitrack reference, or new whole-model inference here. Require lawful model checkpoints with hashes and aligned original mixes and GM-labeled multitrack references before claiming success. Evaluate strict instrument/pitch/onset/offset matches, false positives/negatives, duplicate tracks, omissions and runtime. Existing thresholds stay unchanged.
