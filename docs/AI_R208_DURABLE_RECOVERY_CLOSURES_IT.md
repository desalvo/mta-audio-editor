# MTA Audio Editor 0.3.0-r208 — Recovery durevole degli upload

Versione e revisione invariate. Nessun commit, push, tag, release o accesso a server reali.

## Cinque chiusure funzionali

1. **Rollback dopo errore di pubblicazione:** aggiunta, sostituzione e worker asincrono controllano il progetto persistito prima di eliminare il file. Un errore successivo all'atomic replace di project.json non autorizza la cancellazione di audio già referenziato. Se il progetto non è leggibile, il cleanup resta conservativo. La sostituzione conserva anche file condivisi da altre tracce.
2. **Identità persistente dei media:** i journal ordinari, degli stem recuperati e asincroni conservano dispositivo e inode dei file registrati. Il recovery non elimina una sostituzione con identità differente; una seconda registrazione dello stesso percorso con inode diverso è rifiutata. La copia originale asincrona registra l'identità prima di scrivere i contenuti.
3. **Preflight completo del recovery:** il journal degli stem valida entrambe le snapshot, compresi duplicati e nomi non sicuri, prima della prima cancellazione. Tutti e tre i recovery rifiutano directory audio/originals simboliche e identità malformate senza iniziare il cleanup.
4. **Retirement durevole dei journal:** le directory dei media vengono sincronizzate prima di eliminare il journal; la directory del progetto viene sincronizzata dopo. Un errore di fsync dei media lascia il journal disponibile per riconciliazione successiva.
5. **Avvio asincrono con gestione degli errori:** sync_mode invalido è rifiutato con HTTP 400 prima delle scritture. Se il thread non può partire, il job viene segnato fallito, la ricevuta è riconciliata e l'API restituisce HTTP 503 invece di lasciare upload e job accodati senza worker.

Correzioni collegate: ripristinati permessi eseguibili dei file con shebang e aggiunto shebang/permesso eseguibile dell'adapter unificato. Aggiornati due controlli storici che cercavano il vecchio percorso di pubblicazione Lyrics/Chords e BPM; la loro aspettativa non corrispondeva già all'archivio di partenza. Le fixture di upload ora configurano anche il percorso dei journal.

## Verifiche

- Suite estesa locale: **2886 passed, 4 skipped, 11 deselected, 11 warnings**. Gli 11 esclusi comprendono 10 prove che richiedono socket Unix, vietati dall'ambiente, e una prova che richiede CMake, non disponibile qui. I 4 skip richiedono Steinberg SDK/ADelay.
- Regressione storica r208 e route remote r207: **1001 passed, 10 deselected, 10 warnings**; risultato completo in `validation/r208-final.log`.
- Nuova suite comportamentale: **26 passed**, comprendenti arresto reale con SIGKILL e due processi concorrenti, con recovery che attende il lock e conserva la pubblicazione del writer.
- Ruff sui moduli di recovery e nuovi test: superato; controlli F su main e adapter unificato: superati. Compilazione Python: superata.
- La suite estesa precede soltanto la rimozione di una variabile locale inutilizzata, poi verificata con la regressione r208 finale. Nessuna certificazione hardware o esecuzione della CI remota è implicita.

## Compatibilità e limiti

I journal preesistenti restano leggibili: le identità sono un campo aggiuntivo opzionale, senza bump di versione. Per voci senza identità permane il comportamento storico basato su snapshot o nomi predeclared. Non esiste una transazione ACID globale fra filesystem, JSON, queue e ledger. Restano da chiudere le finestre fra creazione e registrazione dei media, i writer legacy non coordinati e il recovery di processi ancora attivi in altre istanze; i test introdotti non simulano perdita elettrica o guasti del dispositivo di storage. Il controllo delle directory simboliche non è una garanzia contro ogni race di rinomina ostile.

Il metering GPU fatturabile resta da validare su hardware con misure attribuibili e autenticate. Le diagnostiche AMD SMI non diventano misure fatturabili. Inferenza reale, installer nativi sulle piattaforme target e verifica completa di tutti gli adapter restano necessari per il collaudo operativo. Nessun mirroring schedulato è stato aggiunto.

## Commit suggerito cumulativo

Harden MTA r208 native and server AI execution, remote recovery, authenticated CPU accounting and billing, adapter integration, concurrent project publication, durable media journals, inode-safe rollback, crash reconciliation and packaging
