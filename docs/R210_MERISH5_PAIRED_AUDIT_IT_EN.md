# R210 — Merish5 audio/MIDI paired audit / Audit coppia audio/MIDI

## Italiano

- Materiale fornito dall’utente (non redistribuito): `All Night Long.MID`, `All Night Long_rec1.MP3` e il checkpoint `mt3.pth`.
- Il checkpoint MR-MT3 ha SHA-256 `b8a3807ed265059abd25ad7f68142c06c35e8f6144dcaa45bd55946a3745398f` (controllato su file locale). Non costituisce da solo un runtime neurale utilizzabile.
- Un comando riproducibile: `python scripts/audit_paired_midi.py "All Night Long.MID" "All Night Long_rec1.MP3" --output paired-audit.json`.
- Risultati: 10.632 Note On, 15 canali con note, 21 programmi melodici distinti, 24 coppie canale/programma e nessun note-on rimasto aperto o note-off spaiato. MP3 stereo 48 kHz, 248,136 s; MIDI SMF0, 480 PPQN, 245,011329 s.
- Il parser rigoroso rileva un byte dati invalido; la lettura tollerante non cambia l’originale. Il delta di durata non dimostra lo spostamento temporale. I cambi programma sono importanti per assegnare correttamente le note.
- 43 test mirati superati. Non è stata eseguita nuova inferenza MR-MT3 o misurato nuovo F1, né effettuata la regressione CI completa. Non dichiarare concluso l’obiettivo 10–16 strumenti. La prossima attività software è allestire runtime verificato/isolato e misurare i modelli, poi correggere i difetti emersi, mantenendo le soglie invarianti.

## English

- User-supplied material, not redistributed: paired MIDI and stereo MP3, plus the exact SHA-verified MR-MT3 checkpoint.
- `scripts/audit_paired_midi.py` audits provenance and symbolic reference events: 10,632 note-ons over 15 note-bearing channels; 21 unique melodic GM programs and 24 channel/program combinations. No unpaired starts/ends. MP3 248.136 s; MIDI 245.011329 s.
- Strict parsing detects an invalid MIDI data byte, and tolerant parsing preserves the original file. Different total duration is not evidence of alignment offset. Instrument program changes require note-time-aware reference labeling.
- 43 focused tests passed. No fresh model inference, no quality F1 improvement, no full CI run and no 10–16-instrument closure are claimed. Reproducible source-bound neural runtime and rigorous benchmarking remain required.
