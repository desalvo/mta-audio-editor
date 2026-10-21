# Plugin opzionali e importazione media nelle app native — r210

## Correzioni del 20 ottobre 2026

La finestra dei VST3 opzionali usava gli endpoint amministrativi del server anche nelle app native. Il middleware nativo li bloccava correttamente; la finestra cercava poi di interpretare il messaggio di blocco come JSON. Le native ora utilizzano endpoint locali dedicati per catalogo, licenze, installazione, avanzamento e disinstallazione. Questi endpoint non sono utilizzabili sul server web. Sul server resta necessaria l'autorizzazione amministrativa; sulle richieste di modifica resta il controllo CSRF. L'accettazione esplicita delle licenze resta obbligatoria.

Una risposta inattesa non JSON mostra ora un errore leggibile con il codice HTTP, nella lingua dell'interfaccia. Restano gli stati e le barre di attività dei singoli plugin. L'installazione effettiva richiede ancora il toolchain C++ e le dipendenze indicati dal catalogo: questa correzione non li sostituisce.

L'importazione YouTube falliva su Windows mentre sincronizzava la directory del journal mediante un'operazione POSIX. Il percorso di pubblicazione e recupero ora usa una funzione comune: su Windows sincronizza i contenuti dei file nei punti previsti senza aprire directory come file; su POSIX mantiene la sincronizzazione obbligatoria delle directory e propaga gli errori. Sono preservati scritture atomiche, journal, controlli di identità dei file, protezione dei collegamenti simbolici e pulizia limitata ai file posseduti dall'operazione. Su Windows non si dichiara la stessa garanzia di persistenza delle directory dopo perdita di alimentazione disponibile con fsync su POSIX.

## Workspace e file del progetto

Nelle native Windows il workspace in `%LOCALAPPDATA%\MTA Audio Editor` è previsto. Contiene dati di lavoro e cache; l'archivio `.maeprojz` rimane nel percorso scelto dall'utente, per esempio Documenti. Non spostare o eliminare manualmente il workspace mentre un progetto è aperto. Il problema corretto era l'operazione sulla directory, non il fatto che il percorso contenesse spazi o si trovasse in AppData.

## Verifiche e limiti

I test API coprono catalogo e licenze native, job di installazione con compilazione simulata, polling, validazione della disinstallazione, consenso e CSRF, ruoli server e indisponibilità degli alias locali sul server. I test Chromium coprono selezione degli endpoint, stati/progress e risposte non JSON in IT/EN. I test media usano un provider YouTube locale che produce un WAV reale e verificano importazione, rilettura del progetto e rollback sotto una politica che rifiuta l'apertura POSIX delle directory. Non sono prove di download YouTube in rete né di compilazione/installazione dei plugin sul kernel Windows.

La CI Windows e macOS esegue anche le nuove regressioni API/media. Per l'accettazione sulla macchina Windows: installare la build aggiornata, aprire il catalogo VST3, installare un plugin scelto con licenza accettata, poi importare un contenuto YouTube autorizzato, salvare e riaprire il progetto. Allegare il journal diagnostico se il toolchain o il provider remoto restituiscono un nuovo errore.

Le aree AI Vocal Studio, hardware e modelli ancora aperte sono elencate in [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md).
