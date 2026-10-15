# MTA Audio Editor 0.3.0-r208 — Pubblicazione stem in batch

## Modifiche
- Il worker di separazione prepara e normalizza tutti gli stem prima di modificare il progetto persistito.
- I riferimenti delle tracce vengono pubblicati con una sola chiamata a `save_project` (scrittura atomica di `project.json`).
- Se un'eccezione o una cancellazione precede tale pubblicazione, i file appena creati vengono rimossi senza eliminare le tracce precedenti.
- I file audio sostituiti vengono cancellati solo dopo la pubblicazione del nuovo stato del progetto.
- Le analisi opzionali Lyrics e Chords restano successive al commit del batch e mantengono la loro gestione non fatale.

## Limiti
- Un arresto improvviso durante la preparazione può lasciare file nuovi non referenziati: è necessaria una pulizia differita sicura prima della certificazione.
- `save_project` può richiamare la conversione FLAC secondo la policy del progetto; il suo comportamento va testato specificamente durante la certificazione multitraccia.
- Gli aggiornamenti BPM e quelli opzionali Lyrics/Chords restano operazioni indipendenti.
- Nessun test ROCm eseguito qui; non è certificata l'intera transazione multirisorsa o la contabilizzazione GPU.

## Test
`PYTHONPATH=. pytest -q tests/test_r208*`: 230 test superati nell'ambiente locale.
