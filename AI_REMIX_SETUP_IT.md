# Remix / Auto-Remix — r175

AI Arranger dispone ora della modalità distinta **Remix**, attualmente per la sola pianificazione.

`instrument_swap` consente di scegliere tracce esistenti e strumenti sostitutivi; `auto_remix` usa preset e descrizione libera. Rimangono le opzioni di conservazione degli accordi, della struttura, del BPM, della melodia e della voce.

Utilizzo Python: `prepare_remix_plan(project, RemixRequest(...))`. La generazione audio, il collegamento alla UI, l'anteprima non distruttiva e la verifica musicale richiedono ancora implementazione e backend abilitati.
