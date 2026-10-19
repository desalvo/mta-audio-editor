# r210 - Metronomo a zone, layout personale e manuali / Zone metronome, personal layout and manuals

## Italiano

Baseline: `MTA-0.3.0-r210-continuous-cpp-audio-vst3-uninstall-cumulative.zip`, SHA-256 `0f295c2201bff0a2af5334049b91aeb1af2607b79396633bff79fcb8b9f96aa0`. Tutti i 2.201 elementi precedenti sono conservati nel cumulativo; versione **0.3.0-r210** invariata.

- Il primo beat del metronomo a zone coincide con l'inserimento, anche fuori beat e dopo uno o più marker. Pre-roll, limite Stop e impostazioni manuali per identità dei marker restano disponibili; il refresh parziale conserva la fase e il pre-roll.
- Spostare/aggiungere/rimuovere/disabilitare marker aggiorna il WAV durante il salvataggio del progetto. Il risultato ritorna con peaks e revisione audio coerenti; i client invalidano cache e trasporto già preparato, compresi C++ server e trasporto nativo. Una generazione fallita conserva metadati/audio precedenti e rimuove il temporaneo. Un riferimento ritmico già eliminato non blocca il salvataggio dei marker.
- I menu contestuali vengono ricollocati quando si espandono le categorie; hanno altezza limitata e scorrimento interno. I controlli BPM, semitoni e offset/delay hanno pulsanti compatti separati dal testo.
- Impostazioni o pulsante di configurazione della barra: trascinamento/frecce per il riordino, fino a sei righe, barre Transport/progetto ed editing indipendenti. Pulsanti a icona con tooltip e nomi accessibili; i comandi nascosti per autorizzazione/piattaforma restano nascosti. Le modifiche si applicano al salvataggio del layout.
- Job AI: posizione neutra sotto la navigazione, maniglia trascinabile, frecce e Home da tastiera, posizione limitata alla finestra. Layout e posizione sono salvati per account sul server, e in `native-editor-layout.json` nelle app native. La tabella `editor_layout_preferences` segue la cancellazione dell'utente con foreign key in cascata. Nessuna preferenza di un utente viene usata da un altro.
- Lo zoom timeline conserva il tempo al centro della vista durante l'anteprima e dopo il rilascio. Pulsanti, preset e autosave usano lo stesso riferimento. La posizione viene limitata ai bordi del progetto quando necessario. Il valore persistito rispetta il formato intero previsto dal modello.
- Mixer: etichetta Pan sopra il valore; pulsanti FX per canali e master. Il feedback dell’icona Pausa C++ è immediato anche mentre si completa la richiesta al server. I probe isolano e terminano il proprio gruppo di processi temporanei.
- Manuali utente/amministratore/VST3 IT ed EN aggiornati, online e PDF. Capitoli finali ricondotti al contenitore tipografico comune, indice riallineato e metadati della copertina aggiornati. Quindici schermate reali da server di prova con dati sintetici; appendici condivise con matrici per tipo di applicazione, risorse, limiti, prestazioni locali osservate e grafici. I suggerimenti hardware sono stime di dimensionamento, non certificazioni. Corrette anche le guide online che esponevano Markdown grezzo.

Le prove sono riproducibili con `scripts/validate_editor_layout.py` e `tests/test_r210_zones_layout.py`. Impostare `MTA_LAYOUT_PROBE_CPP=1` e `MTA_AUDIO_CORE_PATH` a una libreria compilata per la prova browser C++. I rapporti finali sono in `validation/r210-zones-layout-*`.

Online VST3: `/docs/user/vst3` e `/docs/user/vst3/en`; PDF autenticati: `/docs/pdf/vst3/it` e `/docs/pdf/vst3/en`. I manuali utente/amministratore mantengono gli indirizzi già previsti.

Restano necessarie prove sull'installazione reale Windows/macOS, sui dispositivi audio/MIDI fisici e sul server di produzione. Nessun commit, push, tag, release o intervento sul server reale è stato eseguito.

## English

The cumulative baseline and its 2,201 entries are retained; **0.3.0-r210** is unchanged. Zone clicks now start exactly at insertion, including off-beat insertion and pre-roll. Saving marker edits regenerates actual WAV audio and publishes matching peaks/revision; browser and native playback invalidate prepared audio. Failed generation preserves the preceding state and removes its temporary file.

Context menus stay inside the viewport as categories expand, with internal scrolling. Numeric steppers no longer overlap values. Both toolbars provide accessible icon buttons, custom order and up to six rows. The AI monitor has a neutral default, draggable/keyboard-operable handle and bounded position. Server preferences belong to the authenticated account; native preferences persist on disk. Hidden platform/permission controls remain hidden. Timeline zoom retains its temporal center through preview, release, step buttons, presets and autosave, subject to project scroll boundaries.

All six IT/EN user, administrator and VST3 PDFs share consistent chapter formatting and detailed technical appendices. Online manuals include the same content; screenshots use a disposable local server and synthetic data. Sizing guidance and previous local performance measurements are explicitly distinguished from real-platform certification. See the final validation reports and scripts referenced above. Physical Windows/macOS/device acceptance and production validation remain outstanding; no Git or production actions were performed.
