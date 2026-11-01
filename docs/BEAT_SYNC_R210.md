# Sincronizzazione dei beat e tempo variabile - r210

**RC 34/42 = 81,0%, PRE-RC.** Questo intervento completa il percorso implementativo richiesto per la sincronizzazione di traccia/intervallo; non chiude da solo gli otto criteri RC residui. Nessuna nuova CI remota.

## Funzione

Da una traccia audio selezionata, menu contestuale **Allinea BPM e tonalità**, scegliere un'altra traccia e analizzare. Il riconoscimento degli attacchi usa il flusso spettrale dell'intero intervallo sorgente, traccia i beat e i cambi di tempo, determina la fase ritmica del riferimento e la applica alla mappa musicale del progetto. Supporta mappa fissa, a zone e adattiva, comprese le ripartenze della griglia e le misure con beat in ottavi. La selezione può attraversare più variazioni di BPM. Il BPM sorgente iniziale e il pitch possono essere modificati; il BPM destinazione segue la mappa progetto.

La trasformazione preserva il materiale prima e dopo la selezione, allinea i beat con un rapporto di tempo per intervallo e può anteporre silenzio per allineare un beat iniziale senza tagliare audio. Come gli altri effetti del sample editor, il commit consolida la traccia in una nuova sorgente, aggiorna waveform e mantiene le risorse per undo/redo; il materiale successivo alla selezione si sposta quando cambia la durata. Le stime iniziali di BPM e tonalità usano fino a 20 secondi; la verifica ritmica copre l'intervallo e la porzione di riferimento corrispondente.

Per evitare un risultato ingannevole, l'operazione richiede BPM del progetto noti, almeno quattro secondi, un BPM sorgente iniziale tra 40 e 300 e segnali ritmici rilevabili. Se la fase del riferimento non segue la mappa del progetto, anche solo in una parte successiva dell'intervallo, viene richiesto di sincronizzare prima il riferimento. Se il riferimento termina prima dell'output, il resto segue la griglia del progetto e l'interfaccia lo segnala. I rapporti per segmento sono limitati a 0,25–4 e l'analisi a 6.000 beat; selezioni più grandi richiedono suddivisione. Un filtro FFmpeg temporaneo evita i limiti della lunghezza degli argomenti.

## Evidenze e limiti

Test con impulsi a fase diversa, accelerazione e rallentamento sorgente, mappe a zone e adattive, ripartenza di zona a metà misura, 6/8, tracce con delay, selezione parziale, beat iniziale con silenzio aggiunto, mix sintetico polifonico con levare, pitch manuale, note sostenute, assenza di ritmo, deriva del riferimento dopo 20 secondi, HTTP analisi/applicazione e ripristino sorgente. Il rendering audio usa FFmpeg reale. Le prove non sono un benchmark di accuratezza su brani commerciali: sincopi, cambi bruschi, transienti deboli, introduzioni e materiale polifonico complesso possono produrre stime sbagliate o rifiuti; ascoltare il risultato e correggere il BPM iniziale o la selezione. La lavorazione a segmenti può introdurre artefatti. UI browser/nativa e dispositivi reali non sono stati collaudati in questo ciclo.

Manutenzione RC: restano A6,B6,C6,F4,F5,F6,G5,G6, fra cui prove su provider, host, diritti e hardware. Lo zoom Windows non è stato verificato sul dispositivo segnalato. Autenticazione SAM gated ancora da verificare sul server. Nessun commit, push, tag o CI remota eseguiti.
