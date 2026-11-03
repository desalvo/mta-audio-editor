# Timeline: Unisci, split sui segmenti e verifica delle richieste precedenti

## Comportamento

Il comando **Unisci** sulla barra orizzontale è disponibile quando sono selezionati esattamente due segmenti audio adiacenti della stessa traccia. Lo stesso comando è presente nel menu contestuale della timeline. Una pausa o una sovrapposizione non viene corretta implicitamente: il comando rimane disabilitato finché la selezione non è valida. Per unire contenuti provenienti da tracce diverse occorre prima trasferirli sulla stessa traccia.

Quando i segmenti provengono da intervalli consecutivi della stessa sorgente, l'unione modifica solo i metadati. Quando gli intervalli della sorgente sono discontinui, viene creata una nuova sorgente WAV float senza perdita: i campioni vengono concatenati mantenendo le posizioni sulla timeline e tutte le altre clip della traccia. I parametri di mixer, gain, delay, pitch e tempo restano parametri della traccia: non vengono applicati una seconda volta ai campioni. Le sorgenti precedenti e quella nuova rimangono nella libreria del progetto per undo/redo e salvataggio/esportazione dell'archivio. Il progetto viene pubblicato solo dopo la preparazione della nuova sorgente; quota e intervalli obsoleti vengono controllati prima della pubblicazione, e un errore elimina soltanto i nuovi file di proprietà dell'operazione.

Lo split **S** e il comando contestuale utilizzano prima i segmenti selezionati della timeline. Non richiedono più una selezione di tracce nella barra laterale. Questo include **Ctrl/Cmd+A** con lo strumento Dividi attivo: si dividono i segmenti selezionati attraversati dall'esatta posizione del transport, rispettando il delay della traccia e l'offset della sorgente. Se nessun segmento è selezionato, rimane disponibile il precedente comportamento sulle tracce selezionate. Un punto già coincidente con il bordo di un segmento non genera segmenti vuoti. La selezione resta sui risultati dello split.

I segmenti selezionati possono essere cancellati con Delete/Backspace e copiati/tagliati anche dopo il passaggio allo strumento Dividi. I campi di testo mantengono i normali shortcut di modifica del testo. **Unisci**, trasferimenti e inserimento di file del progetto utilizzano il percorso di pubblicazione che conserva la storia undo/redo.

## Funzioni già presenti e ricontrollate

- Selezione timeline distinta dalla selezione delle tracce laterali.
- Transport spostabile con frecce dopo il focus sulla timeline; Shift+frecce sposta esattamente di 100 ms.
- Con strumento Select e segmenti selezionati le frecce muovono i segmenti, mantenendo collisioni/snap; Shift bypassa snap e magnetismo con il nudge più fine di 10 ms rispetto al normale nudge di 100 ms.
- Import lyrics: righe da 40 caratteri in su divise ricorsivamente vicino al centro, preferendo punteggiatura e congiunzioni. È un'euristica linguistica, non un parser sintattico neurale. Timing parola/sillaba affidabile mantenuto; quando manca viene stimato proporzionalmente. Una parola singola senza spazi non viene spezzata arbitrariamente.
- Editor lyrics: avviso visibile per righe da 40 caratteri in su e comando Dividi.
- Menu contestuale: tracce audio/MIDI vuote secondo il tipo di progetto e inserimento sulla traccia di audio già nella libreria del progetto.
- Copia/incolla e drag tra tracce con sorgenti differenti, conservando originali, timeline, undo/redo e riapertura dell'archivio.

## Verifiche e limiti

I test nuovi eseguono il listener tastiera e le funzioni JavaScript effettive, verificando Ctrl+A → S senza tracce laterali, split al millisecondo con delay positivo/negativo, subset di segmenti, no-op ai bordi, undo/redo e payload Unisci. Le prove audio reali a 48 kHz stereo confrontano i campioni prima/dopo l'unione, riaprono l'archivio e verificano la conservazione delle sorgenti. Sono coperti selezioni errate, cambi di sorgente/tempo concorrenti, quota ed errori di decoding senza residui. I test API verificano persistenza e rifiuto dell'accesso non autorizzato.

Le suite precedenti su lyrics lunghe, frecce/Delete, tracce vuote e trasferimento vengono riusate sui rispettivi percorsi invariati. XML corrente: `validation/r210-timeline-completion.xml`. Queste prove non sostituiscono un collaudo visuale su browser e applicazioni native reali. Le nuove funzioni sono implementate; nessun criterio RC originale viene promosso soltanto in base al numero di test.

Risultato corrente dopo il recupero e l’integrazione degli hook main: **76 test passati, 13 casi nuovi, zero fallimenti/errori/skip**; Ruff e sintassi JavaScript superati. Il gruppo completo include gli shortcut, l’endpoint Unisci autorizzato e la persistenza. Gli hash dei sorgenti correnti, aggiornati dopo l’audit della cronologia condivisa, sono registrati in `validation/r210-timeline-completion-result.json`. Le 11 richieste di implementazione di questa area sono coperte, mentre il collaudo visuale browser/nativo resta distinto.
