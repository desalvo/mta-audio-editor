# Timeline: tracce vuote e segmenti tra tracce

Stato del 2 novembre 2026: implementazione delle richieste su timeline e lyrics completata; RC generale 34/42 = 81,0%. La nuova CI e la verifica visiva nelle app native restano da eseguire.

## Utilizzo

- Click destro nel pannello tracce o nello spazio della timeline: **Traccia audio vuota**, oppure **Traccia MIDI vuota** nei tipi di progetto che consentono MIDI. Il menu di una traccia inserisce quella nuova subito dopo di essa.
- Click destro su una traccia audio: **Inserisci file del progetto nella traccia…**. Scegliere il file; viene inserito al transport. La destinazione mantiene volume, pan, insert e ritardo propri.
- Copiare/tagliare uno o più segmenti, fare click sulla destinazione e incollare con Ctrl/Cmd+V. Nel menu è disponibile **Incolla segmenti qui**.
- Trascinare un segmento selezionato su un’altra corsia per spostarlo; se ne sono selezionati più di uno si spostano insieme mantenendo le distanze temporali. Il contorno evidenzia la destinazione.
- Segmenti che si sovrapporrebbero nella medesima traccia vengono rifiutati senza applicare modifiche parziali. Tracce MIDI usano i comandi dell’editor MIDI.

| Contesto con focus sulla timeline | Freccia sinistra/destra | Maiusc + freccia |
| --- | --- | --- |
| Segmenti selezionati, strumento Selezione | Sposta i segmenti: griglia attiva oppure 100 ms | Sposta i segmenti di 10 ms, senza snap/magnetismo |
| Nessun segmento selezionato | Muove il transport di 4 pixel alla scala corrente | Muove il transport di 100 ms |

Delete/Backspace elimina i segmenti selezionati. Ctrl/Cmd+A seleziona soltanto i segmenti; il menu delle testate permette invece di selezionare tutte le tracce. Le scorciatoie mantengono l’editing nativo nei campi di testo.

## Sorgenti e recupero

I motori continuano a usare una sorgente per traccia. Un trasferimento tra file diversi prepara una nuova sorgente WAV float PCM con gli intervalli necessari e rimappa i segmenti, conservando posizioni, pause e ritardo della destinazione. Le sorgenti originali rimangono nella libreria del progetto e non vengono sovrascritte. I trasferimenti della stessa sorgente non ricodificano l’audio. Il passaggio mono/stereo duplica il canale mono senza ridurne il livello dei campioni.

Undo/redo mantiene raggiungibili vecchie e nuove sorgenti. Gli archivi del progetto contengono entrambe; riproduzione web/native e export usano lo stesso percorso di rendering già esistente. Pubblicazione serializzata per progetto, verifica dei file appartenenti al progetto, quote e journal di recupero impediscono pubblicazioni parziali. Durante la preparazione non si possono accodare altre modifiche alla timeline.

Il trasferimento richiede una destinazione audio mono/stereo; la somma degli intervalli sorgente e le posizioni sono limitate a 24 ore. Gli originali sono recuperabili finché non si richiede esplicitamente la pulizia dei file inutilizzati. La verifica hardware delle app native rimane separata dalle prove locali di rendering.

## Lyrics

L’import JSON e i risultati delle estrazioni Whisper, comprese separazione con trascrizione e recupero remoto, dividono le frasi da almeno 40 caratteri. La divisione è ricorsiva, vicino alla metà, con preferenza per punteggiatura e congiunzioni: è un’euristica locale, non un parser sintattico completo. Parole indivisibili di 40 o più caratteri restano segnalate.

Tempi di parole e sillabe affidabili vengono conservati; in assenza di corrispondenza i tempi vengono stimati nell’intervallo della frase, usando anche l’inizio della successiva. Gli accordi importati con ancoraggi manuali vengono associati alla riga/parola corrispondente dopo la divisione. Entrambi gli editor segnalano le righe lunghe; nell’editor combinato **Dividi** applica direttamente la divisione e supporta undo/redo. Lo storico dei progetti e gli MTA già importati non vengono riscritti automaticamente.

## Verifiche

Prove su audio reale e file persistiti: copia/spostamento, sorgenti condivise, tracce vuote audio/MIDI, rifiuto sovrapposizioni e spostamenti obsoleti, annullamento dopo errore di decodifica, conservazione degli originali, mono/stereo, intervalli di 1 ms a 44,1 kHz, archivio/riapertura/export WAV, autorizzazione HTTP. Le prove JavaScript eseguono i gestori di produzione per drag, incolla, import file, menu, scorciatoie e undo/redo. Nessuna nuova CI remota o prova hardware dichiarata.
