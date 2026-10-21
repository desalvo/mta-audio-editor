# r210 — Post-commit Audio-to-MIDI diagnostic cycle / Diagnostica Audio-to-MIDI

## Italiano

L'archivio iniziale MTA-r210.zip è stato verificato: 91.122.810 byte, SHA-256 `21d1ef79c5adf4ee9d7e2559bcec2207ab697e6b2daacec1223d8deb7158c810`, test CRC completo positivo per 3.080 membri. L'estrazione è riuscita. Sono stati letti `docs/DEVELOPMENT_STATUS.md`, i README IT/EN e `docs/R210_QIXUAN_MIDI_NATIVE_IT_EN.md`.

È stata aggiunta al valutatore una decomposizione *diagnostica* delle sovrapposizioni pitch, programma GM e onset: `error_diagnostics`. I contatori non applicano il vincolo sulla fine della nota, non sono uno-a-uno e **non contribuiscono a matched_notes, precision, recall, F1 o alla soglia di 10–16 strumenti**. Servono solo a distinguere meglio confusione fra programmi e problemi di tempo/durata; non costituiscono inferenza neurale né risultati scientifici di accuratezza.

Ripetuto il quality gate sul `validation/r210-mrmt3-final-result.json` (output conservato di una precedente inferenza *reale*, non una nuova inferenza): benchmark exit 2, 5 programmi rilevati, 0 note abbinate, F1=0. Riscontri diagnostici: 13 note con pitch nel riferimento, 13 anche con onset nella tolleranza ignorando GM; solo 1 con programma GM e pitch corretti e 1 con programma, pitch e onset. Questo restringe la diagnosi ai programmi/identità strumentali, ma **non prova che cambiare il programma risolverebbe il problema**; restano durata e matching uno-a-uno.

L'archivio non contiene checkpoint `.pth`, `.onnx` o `.safetensors` da usare per nuove inferenze. Questa sessione non ha acquisito nuovi pesi né prodotto nuove inferenze. Di conseguenza il lavoro software/modelli per l'accuratezza 10–16 strumenti **resta aperto** e non può essere classificato come collaudo dell'utente. Per un avanzamento sostanziale del modello servono checkpoint legalmente disponibili e una prova reale riproducibile. La distinta banca Qixuan IT/FR da 474.466.435 byte non risultava disponibile come file locale in questa sessione; non se ne dichiara l'installazione.

Test post-commit: 19/19 test benchmark, 32/32 suite mirata combinata, compilazione Python riuscita. I 19 sono inclusi nei 32, non si sommano. Nessuna nuova regressione totale è stata eseguita; lo stato storico resta distinto. Nessuna soglia allentata; nessun commit, server, versione, licenza o modello alterato.

## English

Input ZIP: exact expected size and SHA-256 confirmed, all 3,080 entries passed CRC. Status, both READMEs and previous report inspected. New `error_diagnostics` explicitly measures non-exclusive overlaps in pitch, GM instrument identity and onset; it never affects strict matching or quality-gate exit status. Replay of archived **actual** MR-MT3 inference output still fails: 5 programs, zero strict matches, F1=0, exit 2. Thirteen predictions share pitch/onset with some reference note regardless of program; just one shares program/pitch/onset. These are diagnostic overlaps, not one-to-one matches or new inference. Checkpoint files are absent from the cumulative source ZIP, so no new model inference or 10–16-instrument closure is claimed. Focused suite 32 passed, Python compilation passed; no entire-suite rerun. Missing Qixuan bundle remains unverified. Existing version, model admission, third-party assets and licensing are unchanged.
