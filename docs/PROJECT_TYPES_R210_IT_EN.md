# Tipi di progetto / Project types — 0.3.0-r210

## Italiano

Il menu **Nuovo progetto** e **Info progetto → Tipo progetto** espone:

| Tipo | Tracce attive |
|---|---|
| Multitrack DAW (audio) | Audio |
| Multitrack DAW + MIDI | Audio e MIDI |
| MIDI | MIDI |
| MTA8 / MTA16 | Audio; mapping a 8/16 slot all'esportazione |

La scelta può essere cambiata anche dopo aver creato/importato il progetto, dal pulsante **Converti tipo progetto** in **Setup** o **Info progetto**. Prima del salvataggio vengono mostrati i conteggi delle tracce che resteranno attive e di quelle conservate inattive. Le tracce incompatibili con il nuovo tipo vengono **conservate inattive**, complete di clip, note, controller, espressione, strumenti e riferimenti ai file originali. La finestra Info progetto mostra il numero di tracce conservate. Tornando a un tipo compatibile, queste tracce vengono ripristinate automaticamente. Non è una trascrizione audio→MIDI né un rendering MIDI→audio: per queste elaborazioni restano i comandi appositi.

Le tracce inattive non partecipano a playback, mixer, export del mix o generazione del metronomo, ma i file rimangono protetti dalla pulizia automatica e dalla cancellazione manuale. Sono incluse negli archivi progetto `.maeproj` e nelle copie, così la conversione rimane reversibile anche dopo la riapertura/importazione. Il sample rate non può cambiare finché esistono tracce attive **o conservate**, per evitare riferimenti con una diversa base audio.

I progetti precedenti che contengono già MIDI in un tipo allora non distinto vengono migrati a **Multitrack DAW + MIDI**, mantenendo tutte le tracce attive. I vecchi progetti solo audio mantengono il loro tipo. I nuovi progetti applicano i vincoli anche sul server: import MIDI, pubblicazione Studio, import audio, registrazione, bounce e autosave non possono aggiungere tracce del tipo sbagliato. I job Studio e le generazioni vengono respinti prima dell’ammissione in coda quando il loro output è incompatibile, evitando un’inferenza costosa destinata a fallire in pubblicazione. Un conflitto restituisce HTTP 409 con invito a cambiare tipo nelle Info progetto. Nel tipo MIDI, il comando metronomo apre direttamente la creazione del metronomo MIDI.

I nuovi tipi non sono estensioni MTA da scrivere direttamente: l'export MTA richiede una scelta esplicita MTA8/MTA16, come per un progetto DAW. L'export MIDI e il rendering dei MIDI attivi rimangono distinti dal salvataggio del progetto.

## English

**New project** and **Project info → Project type** offer audio-only Multitrack DAW, mixed **Multitrack DAW + MIDI**, MIDI-only **MIDI**, and audio-only MTA8/MTA16. Existing projects can switch modes without dropping content, using the explicit **Convert project type** button in Setup or Project info. The dialog previews the resulting active/preserved track counts, and a failed HTTP request leaves the editor state unchanged. Incompatible tracks are preserved inactive with their complete musical data, media references and plugins; switching to a compatible type restores them automatically. This is a reversible content-mode change, not audio transcription or instrument rendering.

Inactive media stays protected from automatic/manual cleanup and survives portable `.maeproj` export/import. Sample rate changes are blocked while active or preserved tracks exist. Legacy mixed projects migrate to the mixed mode without hiding their MIDI; existing audio-only documents retain their type. Server-side publication and persistence enforce the selected mode, so a client cannot bypass it via autosave or an import endpoint. New mixed/MIDI modes choose an explicit MTA8/MTA16 target for MTA export.

Evidence: `validation/r210-project-kinds.log` and `tests/test_r210_project_kinds.py`, covering all modes, rejected incompatible persistence/HTTP publication, migration, reversible conversion, original MIDI events/controllers, portable archives and protected media lifetimes.
