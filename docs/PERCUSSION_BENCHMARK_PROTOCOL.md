# MTA Percussion Benchmark & Validation — protocollo riproducibile

Versioni iniziali: corpus **mta-percussion-corpus-1**, metriche **mta-percussion-metrics-1**. I criteri automatici sono congelati nel campo CRITERIA di app/percussion_metrics.py e copiati nei report delle campagne. Un cambiamento del corpus, dei byte audio, del checkpoint, della pipeline o delle opzioni richiede una nuova identità della campagna e una nuova validazione pertinente.

## Stati distinti

1. **Tecnicamente funzionante**: caricamento ed inferenza reali completati, file integri e risorse gestite. Una fixture di test o una traccia di riferimento copiata non prova questo stato per un modello.
2. **Validato automaticamente**: metriche e confronti riproducibili sul corpus richiesto, con regressioni assenti o dichiarate. Il numero di casi mancanti rimane visibile.
3. **Approvato manualmente**: valutazioni d'ascolto registrate e approvazione esplicita dell'utente per le versioni e configurazioni esatte. Gli esiti automatici non autorizzano questa dicitura.

Fino al terzo stato la pipeline rimane **In attesa di validazione umana**. Non viene fissata una soglia numerica arbitraria di qualità “professionale”.

## Corpus iniziale

Il generatore produce **12 casi sintetici originali** e **6 casi negativi/difficili**, con input DRUMS e mix originale, riferimenti esatti con e senza kick e componenti isolate. I segnali sono surrogati procedurali: i nomi congas, bongos, shaker ecc. identificano il problema controllato, non registrazioni acustiche di quegli strumenti.

Le altre **6 voci realistiche** del manifest sono esplicitamente **non disponibili**: non contengono file, checksum né ground truth inventati e non contribuiscono alla copertura dei test di rilascio. Occorrono registrazioni autorizzate e, quando disponibili, stem isolati sincronizzati. FreePats World Percussion, WaivOps WRLD-LP ed Expanded Groove MIDI Dataset sono soltanto candidati da revisionare; nessun loro audio è importato o distribuito. La presenza di MIDI o loop misti non prova l'esistenza di ground truth per singolo strumento.

Sono presenti 44,1 e 48 kHz, mono e stereo, sovrapposizioni temporali, kick indipendente, distribuzione stereo, forti differenze dinamiche, code lunghe, input senza percussioni, silenzio, audio breve, sequenze elettroniche dense e polarità stereo opposta. Il caso multiple-overlap contiene meno percussione in DRUMS rispetto al mix completo e registra due famiglie distinte di riferimenti: la valutazione usa quella della sorgente effettivamente elaborata.

Il corpus si rigenera da sorgenti con diritti originali:

    python -m scripts.generate_percussion_corpus --output /percorso/corpus --seed 42 --duration 12 --controls-report /percorso/controlli.json

Non eseguire questo comando su una directory contenente un corpus diverso: un corpus esistente è immutabile; vengono verificati seed, durata, geometria e checksum. Per variare i dati creare una nuova directory/versione.

Il manifest include seed PCG64, versioni NumPy/soundfile, hash SHA-256 dei file, gruppi, categorie, famiglia della registrazione e split. I derivati della stessa famiglia non possono attraversare train/validation/test. Le onde FLOAT WAV hanno un header RIFF deterministico senza timestamp PEAK: lo stesso generatore/seed e runtime registrato produce gli stessi byte. Il manifest non è una firma di provenienza di dataset terzi.

Per aggiungere registrazioni personali o autorizzate è implementata l'importazione amministrativa di dataset ZIP, con dichiarazione dei diritti, provenienza per ogni caso reale, checksum, geometria audio e controllo delle famiglie/split. Non vengono accettate approvazioni o identità di revisori provenienti dall'archivio. Formato e protezioni: PERCUSSION_DATASET_IMPORT.md.

## Metriche

Le misure vengono calcolate sui file originali di uscita, senza normalizzazione, spostamento, ricampionamento o ritaglio automatici.

| Misura | Significato e limite |
| --- | --- |
| SDR | Energia del riferimento divisa per l'errore non riscalato. |
| SI-SDR | Proiezione a guadagno comune sul riferimento, dopo rimozione della media per canale. |
| Miglioramento SI-SDR | Differenza rispetto allo stesso input, soltanto quando entrambi i valori sono finiti. |
| Recupero/perdita di energia | Stima del guadagno della componente desiderata e sua energia proiettata; non equivale al conteggio degli eventi recuperati. |
| Bleed | Regressione congiunta sulle componenti escluse, controllando il riferimento desiderato. Snare, tom, hi-hat, cymbals e kick rimangono distinti. Sorgenti correlate producono un flag di non identificabilità. |
| Tempo e drift | Correlazione limitata a ±250 ms, rifinitura a campione, confronto della prima e seconda metà. Se la correlazione è insufficiente il risultato è non verificato. |
| Stereo | Correlazioni e rapporti di energia per canale, errore del segnale side e della correlazione fra canali. |
| Transienti | Novità dell'inviluppo RMS a 5 ms, eventi mancanti/spuri entro tolleranza 20 ms, differenze di picco, spostamenti e errore nelle code 50–250 ms. È una euristica diagnostica, non un detector di strumenti. |
| Casi negativi | Energia e RMS dell'uscita spuria; nessuna divisione per un riferimento silenzioso. |

I valori non definiti sono JSON null e hanno uno stato esplicito: silent_reference, perfect_reconstruction o no_recovered_target. Non vengono serializzati NaN o Inf né sostituiti da punteggi artificialmente elevati. Una ricostruzione perfetta non ha un SDR finito: il report conserva questo stato.

## Integrità e limiti

Vengono controllati leggibilità, campioni finiti, frame, frequenza, canali, nuovi campioni saturati, polarità invertita e lag/drift quando identificabili. Differenze di geometria non vengono corrette in silenzio. Salti di campione molto maggiori rispetto all'input sono segnalati per ispezione; il test è euristico e non certifica l'assenza di ogni discontinuità.

I calcoli impongono un limite di 16 milioni di campioni decodificati per file e ampiezze finite limitate, per impedire working set o aritmetica non controllati. I brani oltre questo limite devono essere suddivisi in estratti registrati; i sei slot reali includono un test di lunga durata ancora da fornire. Non viene dichiarata la convalida di brani lunghi mediante un estratto non registrato.

L'assenza di ground truth permette di controllare la geometria del file, ma non dimostra qualità, assenza di drift o fedeltà alla sorgente. I warning sono conservati. I gruppi sintetico, reale e negativo devono restare separati nelle statistiche; un'interferenza non identificabile non diventa zero bleed.

## Esecuzione dei candidati

Il runner deve usare soltanto adapter e checkpoint installati/autorizzati attraverso i normali controlli del motore. Non sono ammessi comandi eseguibili arbitrari nei manifest. Il modello non installato, non autorizzato o privo di adapter rimane in uno stato distinto dal fallimento di inferenza e da un file di uscita non valido. CPU/GPU, RAM/VRAM e tempi non disponibili vengono indicati come tali.

Ogni risultato è associato ai byte del checkpoint e degli input, alle opzioni (inclusione del kick e classificazioni ambigue), al prompt, al runtime e alla pipeline. I risultati già verificati possono essere riusati soltanto se identità e file coincidono. Nessun ensemble viene avviato automaticamente.

## Controlli diagnostici realmente eseguiti

Lo script può analizzare i riferimenti invariati come controllo degli algoritmi. Questi controlli producono file reali e metriche reali ma **non eseguono un separatore**: non rappresentano il benchmark di Mega 53 o di qualsiasi altro modello. I risultati del ciclo corrente sono in validation/r210-percussion-reference-controls.json, con manifest e riepilogo della generazione. Le prove di regressione del generatore e delle metriche sono in tests/test_r210_percussion_metrics.py.

## Ascolto e decisione

La campagna produce estratti, input integrali, riferimenti, uscite e report. Il confronto cieco usa etichette Candidate A/B/C, ordine riproducibile, loop della medesima sezione e controlli di volume. Il matching di livello è soltanto una copia d'ascolto; non altera gli originali delle metriche.

La revisione parte da 6–10 casi rappresentativi e prosegue sui problemi rilevati. L'utente assegna punteggi da 1 a 5 a isolamento, contaminazione (5 = trascurabile), naturalezza, transienti, completezza e qualità complessiva; sceglie professionale/con limitazioni/non accettabile e può commentare. ChatGPT guida il confronto usando i report e i riscontri ricevuti, senza dichiarare ascolti o approvazioni non effettuati.


## Limite attuale dei contatori risorse nel report

In questa versione recuperata il campo resources del benchmark non legge ancora alcun contatore dal ledger: CPU/GPU restano null anche se il worker ha già registrato misure disponibili. Anche i picchi RAM/VRAM restano null. Il worker_job_id conserva il collegamento al job autorevole per una verifica separata. Null significa dato non acquisito dal report, non consumo zero. Il benchmark non modifica il ledger e non inventa stime; l’integrazione della lettura dei contatori rimane da completare.
