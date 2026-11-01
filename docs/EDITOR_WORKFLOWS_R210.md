> Aggiornamento successivo: la sincronizzazione beat è implementata; dettagli e limiti in `BEAT_SYNC_R210.md`. Questo rapporto conserva il checkpoint storico.

> Aggiornamento successivo: vedere `SYNC_EXPORT_SELECTION_R210.md` per comportamento attuale e prove.

# Editor audio, lyrics e trasporto - r210

**RC 34/42 = 81,0%, PRE-RC.** Le richieste di editing sono lavoro di prodotto aggiuntivo: non promuovono da sole uno degli otto criteri RC ancora aperti.

## Realizzato e verificato

- Menu contestuale: scelta traccia audio di riferimento, stima di differenza cromatica e BPM sorgente, BPM di zona del progetto in tempo sorgente e BPM udibili; valori modificabili e applicazione di tempo/pitch alla traccia o all'intervallo selezionato. La stima usa fino a 20 secondi. Se la stima non è disponibile viene chiesto l'inserimento manuale. Il test confronta tonalità e rendering con toni reali e FFmpeg; la stima BPM è inoltre verificata su impulsi sintetici. Nel test HTTP con toni sostenuti il BPM sorgente è volutamente simulato.
- Editor waveform: guadagno da -60 a +24 dB sull'intervallo, aggiornamento immediato delle waveform dopo il commit, undo/redo di sessione tramite cronologia progetto; le sorgenti vecchie e nuove rimangono nella libreria progetto. Test API su campioni reali verifica attenuazione/guadagno, conservazione del resto e ripristino. Il commit consolida le clip della traccia in una nuova sorgente.
- Editor Lyrics + Chords + Markers: delay cumulativo positivo/negativo, con tempi di parole e sillabe e mantenimento degli anchor manuali. Non sposta i tempi di accordi e marker. Rifiuta spostamenti fuori intervallo senza modifiche parziali; undo/redo disponibile nell'editor.
- PDF: il blocco accordi e lyrics a capo rimane sulla stessa pagina quando è abbastanza piccolo; una linea più alta della pagina mantiene almeno la prima riga col chord e continua. Prove su PDF reali multipagina.
- Già presenti e riesaminate: progetti DAW+MIDI e MIDI e conversione, quantizzazione MIDI, origine musicale/metronomo e formati del transport. Le icone di rimozione, eliminazione tracce/intervallo e salva/salva con nome sono già distinte e sono verificate sul mapping effettivo. I controlli di zoom esistono per desktop e mobile, ma non sono certificati sui dispositivi reali.
- Manuali utente online e PDF italiano/inglese aggiornati, incluse le limitazioni e il comportamento del consolidamento. Entrambi i PDF sono stati esaminati visivamente.

## Residui e limiti

Il matching ora segue le variazioni della mappa di destinazione assumendo un BPM sorgente costante; non allinea automaticamente la fase dei beat né segue variazioni del BPM sorgente. Non equivale pertanto alla sincronizzazione completa richiesta su tutti i casi. La qualità della stima tonale e temporale su musica complessa e l'interazione grafica reale richiedono prove aggiuntive. Non sono stati eseguiti test grafici su Windows, macOS, Linux desktop, Android o iOS; il problema zoom riportato su Windows non è confermato risolto sul target. I test sintetici non certificano hardware, qualità musicale o provider.

## Verifiche

Selezione finale **156 passati, 0 skip, 0 fallimenti/0 errori**: `validation/r210/editor-workflows/tests.xml`. Due prove iniziali rosse mostrano il vecchio split PDF e l'assenza del delay lyrics. Ruff, sintassi JavaScript, inventari e revisione Bandit passati; 168 finding riesaminati, 0 HIGH. Nessuna nuova CI remota.

Ripresa: `MTA-0.3.0-r210-pre-RC-editor-workflows-cumulative.zip`. SAM Hugging Face resta da autenticare/verificare sul server; la procedura amministratore precedente è conservata. Restano A6,B6,C6,F4,F5,F6,G5,G6. Baseline Git confermata `ee4e37fd30c39a72638b303b01ca0cd5b090f272`; nessun commit/push. Commit cumulativo suggerito: `Recover payments and improve AI security, audio editing, and SAM setup`.
