# MTA Percussion Benchmark & Validation — ascolto manuale guidato

**Stato corrente: In attesa di validazione umana.** Nessuna approvazione professionale deriva dai test del software, dall'audio sintetico, dalla disponibilità di un adapter o dalla sola compilazione delle metriche.

## Aprire e riprendere una campagna

Aprire **Benchmark e validazione AI** dal relativo comando amministrativo. Preparare il corpus sintetico originale se non è già disponibile. Il catalogo distingue modelli pronti, non installati, configurati con installazione ancora da verificare, non autorizzati, incompatibili e privi di adapter; la verifica di installazione è un'operazione esplicita. L'attivazione di un modello è distinta dalla verifica dei suoi diritti e dalla sua qualità.

Creare una campagna **sperimentale** per esplorare una configurazione oppure una campagna **di rilascio** per il confronto finale. Scegliere i modelli autorizzati e i dataset preparati, il seme riproducibile e le categorie. Il kick è incluso per default; clap e timpani sono esclusi finché non richiesti esplicitamente e supportati dall'adapter. Un'opzione non supportata deve risultare incompatibile, senza essere applicata soltanto nel nome del report.

**Esegui / riprendi casi pendenti** conserva gli esiti già verificati. **Riprova casi falliti** è un comando distinto. La selezione delle campagne salvate permette di riaprire risultati e valutazioni. L'export ZIP comprende report, valutazioni e audio disponibili; il ripristino usa il relativo ZIP senza sovrascrivere una campagna esistente.

**Confronta campagne / versioni dei modelli** affianca le misure di due campagne salvate. Confrontare sempre gli stessi casi, riferimenti e opzioni delle categorie: cambiamenti di corpus o configurazione non dimostrano un miglioramento attribuibile al solo modello. I nomi e le versioni dei risultati non ancora valutati rimangono nascosti.

## Primo batch: 6–10 casi, non l'intero corpus

Quando esistono output di modelli realmente eseguiti e tecnicamente validi, ChatGPT deve leggere il report della campagna ed individuare un primo gruppo di circa otto casi. Usare i casi suggeriti dal report e i relativi identificativi esatti; non presentare questo elenco generico come prova già eseguita.

| Caso rappresentativo | Verifica d'ascolto |
| --- | --- |
| Congas e snare simultanei | Le congas mantengono l'attacco; il rullante non entra nell'output. |
| Bongos e tom | I bongos restano completi e le code dei tom non vengono recuperate come percussioni accessorie. |
| Shaker e hi-hat | Lo shaker non scompare e l'hi-hat non viene scambiato per lo shaker. |
| Tamburello e crash | I sonagli restano naturali, senza code di crash o buchi nei transienti. |
| Cowbell e ride | Il cowbell resta distinto dalle oscillazioni e dalla coda del ride. |
| Kick e percussioni accessorie | Confrontare sia kick incluso sia escluso, senza spostare gli attacchi. |
| DRUMS senza percussioni accessorie | L'output resta silenzioso o trascurabile; segnalare eventi inventati o bleed. |
| Stereo e dinamiche differenti | Non devono collassare posizione stereo, attacchi deboli o escursione dinamica. |

Alle prove sintetiche devono seguire registrazioni musicali reali autorizzate e prove difficili. Campioni di una stessa registrazione non sono esempi indipendenti e devono restare nello stesso insieme di dati.

## Ascolto cieco A/B

Per ogni caso aprire **Ascolto cieco**. I candidati vengono identificati da etichette opache come Candidate A e Candidate B. L'ordine casuale riproducibile e il collegamento al modello sono gestiti dalla campagna sul server; il browser non inventa nuovi ordinamenti né associazioni.

1. Ascoltare lo stem DRUMS originale e il riferimento percussion, se disponibile.
2. Confrontare A e B nello stesso intervallo. Il passaggio mantiene la posizione temporale; **Ripeti questo estratto** ripete l'intervallo indicato dal caso.
3. Usare volume e waveform per individuare gli eventi; la waveform non sostituisce il confronto sonoro.
4. Confrontare la **copia di ascolto con livello comparabile**, quando disponibile, e il **file originale**. Le copie di ascolto non modificano i file usati dalle metriche.
5. Abilitare **Audio integrale** per verificare code, passaggi più lunghi e drift fuori dall'estratto.
6. Compilare la scheda senza conoscere l'identità del candidato. L'identità viene mostrata dopo il salvataggio della valutazione di quel candidato; le identità non ancora valutate restano nascoste.

## Scheda per ciascun estratto e candidato

Tutti i sei voti sono obbligatori e vanno da 1 a 5; nessun voto viene selezionato automaticamente.

| Criterio | Significato del voto 5 |
| --- | --- |
| Isolamento | Le percussioni desiderate sono ben isolate. |
| Contaminazione | Interferenza di snare, tom e cymbals assente o trascurabile. |
| Naturalezza | Suono naturale, senza artefatti percepibili. |
| Transienti | Attacchi originali conservati. |
| Completezza | Eventi percussivi desiderati conservati. |
| Qualità complessiva | Estratto musicalmente utilizzabile. |

Aggiungere una scelta finale per l'estratto: **Accettabile per uso professionale**, **Accettabile con limitazioni**, oppure **Non accettabile**. Specificare nei commenti i difetti concreti e il momento in cui si verificano. Esempi: “hi-hat nello shaker a 00:13”, “conga con attacco perso a 00:17”, “ride presente nella coda del cowbell”.

Per la scelta professionale compare una conferma di ascolto separata, inizialmente deselezionata: va spuntata personalmente prima di salvare la valutazione del singolo estratto. Cambiare scelta o salvare la scheda azzera la conferma. La conferma professionale dell'estratto non registra l'approvazione finale della campagna, che conserva il proprio comando distinto.

La scheda è salvata sulla campagna e sull'identificativo opaco del candidato: il server la associa ai file e alla configurazione esatti. Il browser non può sostituire l'hash dell'output o il nome del modello nel payload della valutazione. Una scelta professionale su un singolo estratto **non approva l'intera campagna**.

## Giro successivo guidato

ChatGPT deve confrontare i voti e le note con i risultati tecnici e proporre soltanto le prove necessarie: altri casi shaker/hi-hat, differenti prompt o sorgenti mix/DRUMS/Other, confronto con e senza post-processing, oppure nuove registrazioni realistiche autorizzate. Per ogni nuovo profilo vanno ripetuti i casi influenzati dalle modifiche. Prima dell'approvazione finale va eseguito il benchmark completo richiesto.

Gli estratti, le varianti e i riferimenti da ascoltare devono essere indicati con campagna, caso e candidato. Non dichiarare di avere ascoltato file che sono stati soltanto misurati o ispezionati a livello strutturale.

## Approvazione finale separata

Il pannello **Approvazione finale della campagna** resta bloccato finché il server segnala dati mancanti, benchmark incompleto, esiti tecnici non validi o schede insufficienti. In particolare, un corpus composto soltanto da sintetici non sostituisce le registrazioni reali richieste per il rilascio.

Solo quando i criteri sono soddisfatti appare una conferma esplicita inizialmente deselezionata: l'utente dichiara di avere completato l'ascolto e approva l'esatta configurazione. Il comando registra la conferma sulla relativa impronta della campagna. Modifiche rilevanti a modello, checkpoint, pipeline, configurazione o corpus richiedono nuova validazione.

## Evidenza del software e limiti

L'interfaccia è verificata con test Node che eseguono il JavaScript applicativo attraverso un DOM e risposte API di test: catalogo, creazione e ripresa, payload protetti, A/B sincronizzato, copie di ascolto, voto obbligatorio, export/ripristino e conferma finale distinta. Questi test non costituiscono rendering browser reale, inferenza neurale, valutazione percettiva o approvazione umana. Le prove reali e i risultati della campagna devono essere riportati nei documenti generati da quella campagna.
