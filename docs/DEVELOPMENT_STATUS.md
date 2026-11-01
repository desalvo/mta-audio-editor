# Aggiornamento CI e Merish5 / Xynthia2

RC **34/42 = 81,0%, PRE-RC**. Baseline Git confermata `f544db6acb02216b33e0cdc6e69610f7102180c2`; la CI 41340688815 falliva su due import non utilizzati, ora corretti e Ruff completo locale passato. L'export usa `.mta`, CBR 320 kbit/s e stream di durata uguale. **Il caricamento su Merish5 rimane aperto**: il confronto con un originale MTA16 evidenzia differenze strutturali/metadata; serve un MTA8 originale e la prova hardware. Dettagli: `MERISH5_CI_41340688815_R210.md`. Nessun commit o CI remota dopo la correzione.

---

# Aggiornamento - sincronizzazione beat r210

RC **34/42 = 81,0%, PRE-RC**. Ripresa: `MTA-0.3.0-r210-pre-RC-beat-sync-cumulative.zip`; dettagli e limiti in `BEAT_SYNC_R210.md`. Rilevamento beat di sorgente e fase riferimento con mappe progetto fisse, a zone e adattive implementato; ascolto reale e UI nativa restano da verificare. Nessuna nuova CI remota, nessun commit.

---

## Checkpoint precedenti (storici)

# Aggiornamento - matching, selezione ed export MTA

RC **34/42 = 81,0%, PRE-RC**. Ripresa: `MTA-0.3.0-r210-pre-RC-sync-export-selection-cumulative.zip`, dettagli in `SYNC_EXPORT_SELECTION_R210.md`. Matching a zone/adattivo con BPM sorgente costante; fase beat e sorgenti a tempo variabile ancora da completare. Select all e normalizzazione MTA implementati. Nessuna nuova CI remota, nessun commit.

# MTA 0.3.0-r210 - stato corrente

**Verso la RC: 34/42 = 81,0%, PRE-RC**, perimetro `precommercial-20261030`; A4/A5 chiusi, nessun criterio promosso in questo checkpoint.

Riprendere da `MTA-0.3.0-r210-pre-RC-editor-workflows-cumulative.zip`, `EDITOR_WORKFLOWS_R210.md` e `validation/r210/editor-workflows/result.json`. Baseline Git `ee4e37fd30c39a72638b303b01ca0cd5b090f272`, ultima full CI nota `41156985339`; commit all'utente, nessuna nuova CI remota.

Implementati matching tempo/pitch a zona costante con riferimento e valori modificabili, guadagno e undo/redo waveform, delay lyrics e protezione PDF chord/lyrics. I tipi progetto, MIDI quantize, transport musicale e le icone erano già presenti e sono stati verificati. La sincronizzazione con fase automatica e BPM sorgente variabile resta incompleta; qualità musicale e zoom Windows/macOS/Linux/Android/iOS richiedono collaudi reali. Manuali utente HTML/PDF IT/EN aggiornati.

Selezione finale 156 passati, 0 skip, zero fallimenti/errori; Ruff e gate di revisione passano. Restano **A6,B6,C6,F4,F5,F6,G5,G6**; accesso SAM gated ancora da verificare sul server. Dettagli e limitazioni nel rapporto.

Commit cumulativo suggerito: `Recover payments and improve AI security, audio editing, and SAM setup`. Versioni precedenti in `development-history/before-editor-workflows-20261101/`.
