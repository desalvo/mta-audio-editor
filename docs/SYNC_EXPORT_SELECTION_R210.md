> Aggiornamento successivo: fase beat e BPM sorgente variabile sono stati implementati; dettagli e limiti in `BEAT_SYNC_R210.md`. I punti seguenti descrivono il checkpoint storico.

# Checkpoint: tempo a zone, selezione tracce ed export MTA

RC **34/42 = 81,0%, PRE-RC**. Nessun criterio RC residuo è stato promosso; nessuna nuova CI remota.

- Il matching segue le variazioni della mappa BPM di destinazione, incluse le zone e i punti adattivi, assumendo che il BPM della sorgente sia costante. Gli intervalli sono ripartiti sulla timeline di destinazione e processati con rapporti diversi; ogni segmento ha durata finale controllata. Più di 512 segmenti distinti richiedono la suddivisione della selezione. Una stima di BPM è indicativa e può essere modificata; la stima tonale resta basata sulla traccia di riferimento.
- **Non completato:** la fase dei beat non viene rilevata né allineata automaticamente; una sorgente con tempo variabile non viene seguita beat per beat. Il processamento a segmenti può produrre artefatti alle giunzioni. Le prove sono sintetiche: servono casi musicali reali e interazione grafica.
- Ctrl/Cmd+A seleziona tutte le tracce, come la nuova voce del menu contestuale. Nei campi editabili è conservata la selezione testo; finestre di dialogo escluse dalla scorciatoia.
- L'export MTA configurato offre normalizzazione facoltativa a picco dBFS. Gli slot temporanei float vengono sommati senza clipping per misurare il picco e ricevono tutti lo stesso fattore prima della codifica. Silenzio e clipping di un singolo slot causano un errore esplicito; gli insert master attivi non sono compatibili e vanno disattivati. Il picco misurato è pre-MP3: codifica e dispositivo possono modificare il livello. Il progetto rimane invariato.
- Test con segnali reali su attenuazione, amplificazione, cancellazione di fase, lunghezze differenti, export/deoffuscamento/decodifica MTA, mappa a zone/adattiva e selezione UI simulata; non è un collaudo su dispositivi M-Live o una prova browser completa.
- Manuali utente IT/EN HTML e PDF aggiornati. Procedure SAM Audio e manuali amministratore conservati nel pacchetto.

Restano A6,B6,C6,F4,F5,F6,G5,G6 e i controlli su hardware, sistemi operativi, diritti/provider e ambiente reale già documentati. L'autenticazione SAM sul server resta da verificare. Nessun commit o push eseguito.
