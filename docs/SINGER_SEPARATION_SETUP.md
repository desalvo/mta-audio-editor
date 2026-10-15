# Multi-singer separation / Separazione multi-cantante (0.2.0-r276)

## Italiano

In **Separa traccia** o **Importa e separa**, abilita **Separa più cantanti**. Scegli SAM Audio Small/Base/Large e inserisci una riga per cantante nel formato `Nome | inizio | fine`, con tempi in secondi o `mm:ss` riferiti all'inizio dell'audio sorgente, per esempio:

```text
Voce A | 00:12 | 00:17
Voce B | 00:30 | 00:35
Voce C | 01:02 | 01:09
```

Sono supportati da 2 a 8 cantanti. Ogni intervallo deve durare 0,5–60 secondi, contenere **solo quel cantante**, ed evitare di sovrapporsi agli intervalli di altri cantanti. Puoi estrarre tutte le voci o solo una. L'editor produce i file degli stem mantenendo l'origine temporale a 0 ms, non tagliandoli ai tempi di riferimento. Se estrai nuovamente un solo cantante da una traccia originale, MTA aggiorna la traccia di destinazione già presente quando il nome coincide.

**Requisiti**: la variabile d'ambiente `MTA_SAM_AUDIO_PYTHON` deve indicare il Python di un ambiente SAM Audio isolato, installato secondo `SAM_AUDIO_SETUP.md`, con accesso ai checkpoint ufficiali autorizzato su Hugging Face. Non sono inclusi pesi o credenziali.

**Limiti**: funzionalità sperimentale. SAM Audio isola una voce tramite descrizione e riferimenti temporali positivi/negativi, **non** tramite embedding identificativi dedicati al cantante; nei passaggi sovrapposti sono possibili contaminazioni, duplicazioni o scambi tra voci. Non è l'implementazione del modello accademico *Singer-Informed Vocal Source Separation*. La qualità dell'inferenza con checkpoint reali non è ancora stata collaudata. La modalità richiede la pipeline Demucs sul runtime/server e non può essere combinata nello stesso job con Lead/Backing o DrumSep.

## English

In **Separate track** or **Import and separate**, enable **Separate multiple singers**. Select SAM Audio Small/Base/Large and enter one singer per line as `Name | start | end`, in seconds or `mm:ss` relative to the start of the source audio. Provide 2–8 distinct singers, one 0.5–60 second solo interval per singer, with non-overlapping reference intervals. Select **All singers** or one singer. Every output begins at project time zero and retains its full-song alignment; selective re-extraction updates a matching named derived track.

Set `MTA_SAM_AUDIO_PYTHON` to the interpreter of an isolated SAM Audio environment with authorized checkpoints (see `SAM_AUDIO_SETUP.md`). The implementation uses SAM Audio time-span anchors, not a dedicated singer embedding model; overlapped singing and voice identity are not guaranteed. No model weights are shipped, and real-checkpoint validation remains outstanding.
