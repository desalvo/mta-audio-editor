# Audio-to-MIDI: quality gate / Soglia di qualità

## Italiano

È disponibile una valutazione **offline e senza download** tra due file `MusicResult` (`mta-music-1`): un risultato di riferimento **revisionato** e il risultato realmente generato da YourMT3 (o altro modello). Eseguire dalla radice:

```sh
python scripts/check_audio_midi_quality.py riferimento.json predizione.json --min-instruments 10 > rapporto.json
```

Il tool restituisce `0` quando entrambe le trascrizioni contengono almeno il numero richiesto di programmi/parti per categoria GM, `2` altrimenti. **Un esito `0` non è una certificazione di accuratezza**: confrontare precision, recall, F1 e righe per strumento. Non esiste una soglia predefinita fittizia. I file di ingresso sono validati tramite `MusicResult`, dimensione massima 16 MiB ciascuno, senza link simbolici. Matching uno-a-uno massimale su programma GM/percussioni, pitch, inizio ±50 ms, fine ±100 ms, modificabili tramite argomenti.

La misura non certifica identità di esecutori con lo stesso programma, qualità sonora, velocity dinamica, bend o controller; le tracce senza note non vengono inventate. Un test sintetico con 16 strumenti verifica l'algoritmo di **benchmark**, non la trascrizione AI.

### Collaudo richiesto sul server di test

1. Installare e verificare runtime YourMT3 autorizzato secondo `scripts/install_studio_yourmt3.py`. Nessun checkpoint viene incluso o scaricato silenziosamente.
2. Eseguire trascrizione di mix stereo legalmente utilizzabili, con partiture MIDI indipendenti di riferimento (almeno 10, preferibilmente 16 strumenti). Conservare WAV, MusicResult effettivo e ground truth revisionato.
3. Eseguire il comando sopra per ogni caso e registrare precision/recall/F1 per strumento, fallimenti e tempi CPU/GPU; valutare il caso limite di strumenti con stesso programma GM, strumenti a percussione e sovrapposizioni polifoniche.
4. Verificare nell'editor importazione, modifica, salvataggio e riapertura delle tracce, e ripetere la prova con ROCm dove supportato dal runtime installato. **Non** assumere automaticamente supporto ROCm del percorso YourMT3 CPU.

Stato r210: pronto il *quality gate*, **non** soddisfatta né dimostrata l'accuratezza end-to-end 10–16 strumenti.

## English

An offline benchmark compares reviewed ground-truth `MusicResult` JSON and real model-generated `MusicResult` JSON, with maximum-cardinality one-to-one note matching by GM program/drums, pitch, onset and offset. Run:

```sh
python scripts/check_audio_midi_quality.py reference.json prediction.json --min-instruments 10 > report.json
```

Exit code 0 means both inputs contain the requested number of GM instrument categories, **not** that AI transcription is accurate. Review instrument-level precision, recall and F1. No pretrained model or checkpoint is distributed, downloaded or automatically licensed by this tool. Synthetic 16-instrument benchmark tests prove only benchmark implementation. Full completion requires verified licensed runtimes and real audio/MIDI pairs, threshold review, project save/reopen tests, and hardware-specific qualification.
