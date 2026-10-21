# MR-MT3 Merish5 full-song alignment study / Studio di allineamento

## Italiano

I risultati ROCm reali sono completi (122/122 finestre). 10.632 note MIDI di riferimento, 8.853 note MR-MT3. Il matching rigoroso fisso, offset zero, produce 925 corrispondenze (F1 9,49%). Lo studio diagnostico scansiona da -1 a +1 secondo in passi di 50 ms: massimo rigoroso 1.452 note a +100 ms (F1 esplorativo 14,90%); massimo ignorando il programma GM 2.296 a +250 ms (F1 esplorativo 23,57%). Sono valori ottimistici ottenuti scegliendo il ritardo *sullo stesso riferimento* e NON sostituiscono la baseline né certificano accuratezza. Occorre misurare indipendentemente il ritardo audio/MIDI prima di attribuirgli un punteggio ufficiale. Nessuna soglia o checkpoint modificato.

Per riprodurre con gli asset esterni, eseguire dalla radice del progetto:

```bash
python scripts/evaluate_mrmt3_alignment.py --midi '/path/All Night Long.MID' --prediction /path/mrmt3-results/prediction.json --output /path/alignment-report.json
```

Il MIDI originale ha un SysEx malformato; la lettura usa `mido.MidiFile(..., clip=True)` senza modificare il file di origine. La scansione è diagnostica e non corregge o modifica `prediction.json`.

## English

Real ROCm inference completed 122/122 windows: 10,632 reference MIDI notes and 8,853 MR-MT3 predicted notes. Strict fixed zero-offset matching yields 925 matches (9.49% F1). A post-hoc timing sensitivity sweep from -1 to +1 seconds in 50-ms increments finds 1,452 strict matches at +100 ms (exploratory F1 14.90%), and 2,296 program-agnostic matches at +250 ms (exploratory F1 23.57%). These optimistic in-sample values MUST NOT replace the unshifted benchmark or certify quality. Independently measure alignment on audio, not by optimizing on ground truth, before any acceptance scoring. No checkpoint or thresholds changed. The command above reproduces the diagnostics.
