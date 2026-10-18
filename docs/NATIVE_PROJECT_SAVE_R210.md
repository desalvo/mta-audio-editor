# r210 — Native project creation after Save / Creazione progetto dopo Salva

## Italiano

Versione e revisione mantenute: **0.3.0-r210**. Baseline:
`MTA-0.3.0-r210-native-first-start-dialogs-cumulative.zip`, SHA-256
`ffed211c2a0dcc9779e0bad025679c52c7117b9b00f43fb2167123811ef5d689`.
Tutti i file del precedente cumulativo sono conservati. Ripristinati inoltre
i bit eseguibili dei punti di ingresso con shebang: lo ZIP precedente li
riportava come non eseguibili. Il nuovo archivio conserva i permessi corretti.

### Difetto individuato e riprodotto

Dopo il ritorno del selettore, il progetto veniva creato nel workspace e
associato a un percorso. La creazione dello ZIP richiamava `os.fsync` su un
file riaperto come `rb`. Il requisito di accesso in scrittura della flush
Windows non era rispettato. Un test che applica questo vincolo al salvataggio
reale fallisce sul codice precedente e passa con la correzione.

L'errore finiva in un toast con z-index 200, sotto la finestra con z-index
5000: la finestra rimaneva aperta senza un errore visibile. Ogni nuovo clic
ripartiva dalla scelta del percorso e poteva creare un altro workspace.
Senza il log del PC non si certifica che questa fosse l'unica causa del caso
segnalato; il difetto e il messaggio nascosto sono verificabili nel codice.

Fonti primarie:
- Python, `os.fsync`, delega a `_commit` su Windows:
  <https://docs.python.org/3.13/library/os.html#os.fsync>.
- Microsoft, requisito `GENERIC_WRITE` di `FlushFileBuffers`:
  <https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers>.

### Correzioni condivise fra le app native

- Il temporaneo ZIP è aperto come `r+b` per la sincronizzazione: la verifica
  CRC, la validazione del progetto e la sostituzione atomica rimangono attive.
  Un errore di flush continua a impedire la pubblicazione del file.
- Corretto lo stesso schema nei salvataggi MTA, metronomo, aggiornamento
  regionale del metronomo, rigenerazione chords ed esportazione configurata.
- Il binding viene registrato soltanto dopo la scrittura del progetto.
  Registro dei percorsi scritto atomicamente; rollback del binding in memoria
  se il registro non può essere salvato. Un vecchio archivio valido rimane
  intatto quando la nuova scrittura fallisce.
- Creazione con stato visibile: scelta destinazione, creazione, salvataggio,
  apertura. Errori persistenti nella finestra, oltre al toast ora visibile
  sopra i dialoghi. Annullamento distinto da un ritorno erroneo del selettore.
- Un nuovo tentativo nella stessa finestra riutilizza percorso e ID già
  ottenuti. Se il file è già stato salvato, riprova soltanto il caricamento.
  Evita di riaprire il selettore e di creare progetti duplicati per i fallimenti
  di binding o caricamento. Una richiesta HTTP senza risposta certa non offre
  garanzia di idempotenza lato server.
- Le stringhe di stato sono IT/EN; aggiornate le chiavi di cache degli asset.
- Aggiunti test del salvataggio ai job CI nativi Windows e macOS, compresi
  i runner delle architetture macOS già previste. La CI Linux li include
  automaticamente nella suite generale. La CI non è stata avviata da qui.

### Verifiche e limiti

Regressioni reali di filesystem: archivio valido e completo, creazione via
HTTP, percorso con spazi e caratteri Unicode, binding, sync, riapertura,
conservazione della copia precedente in caso di flush fallita, mancata
registrazione di binding falliti, rollback dopo errore del registro.

Simulati i formati di ritorno dei selettori WinForms, Cocoa, GTK e Qt.
Test del JavaScript effettivo: successo web, annullamento, errore del selettore,
creazione HTTP fallita, binding fallito e caricamento fallito, con tentativi
successivi, stati IT/EN e assenza di creazioni duplicate dopo un ID confermato.
Inclusi test di esportazione nativa e generazione del metronomo con il vincolo
Windows sugli handle scrivibili.

Esito complessivo: **3916 passati, 5 saltati, 10 esclusi** per socket Unix
non disponibili. **92 test mirati passati**, 1 saltato perché richiede Win32.
La prima passata completa ha avuto 9 fallimenti: 8 per i bit eseguibili assenti
nel precedente ZIP, uno per CMake non installato nell'ambiente locale. Dopo
il ripristino dei permessi e l'installazione del tool, tutti e 9 sono passati
nella ripetizione mirata, senza modificare il codice fra le due passate.
I report originali completo/ripetizione e il riepilogo combinato sono inclusi.
Copertura complessiva **76,87%**; Ruff e sintassi JavaScript superati.
Report: `validation/r210-native-project-save-*`.
La verifica locale avviene su Linux; non è un'esecuzione delle GUI Windows o
macOS. Sul nuovo installer provare Crea progetto → Salva → editor aperto,
verificare il file `.maeprojz`, aggiungere una traccia, salvare, chiudere e
riaprire; ripetere con Annulla e con una destinazione non scrivibile. Non sono
state eseguite nuove prove GPU/ROCm sul server.

## English

Version remains **0.3.0-r210**, retaining the entire previous cumulative ZIP.

Native archive creation flushed a read-only file descriptor. This violates
the Windows flush write-access requirement. A regression exercising the real
archive writer under that constraint fails before the fix and passes after it.
The resulting error toast was also below the creation dialog.

Archive and generated-audio flushes now use writable handles, retaining
validation, atomic replacement and failure propagation. Destination bindings
are committed after the durable project write, with an atomic registry and
in-memory rollback on registry failure. The previous valid archive survives
a failed flush.

Creation reports its current stage and keeps errors visible. Retry within the
same dialog reuses the confirmed project ID and selected path; a completed
binding is reused if only the final load fails. Cancellation is explicit.
Successful web creation remains available. Unknown HTTP outcomes are not made
server-side idempotent by this change.

Tests cover real files and HTTP endpoints, Unicode paths, sync/reopen,
failure preservation and actual creation JavaScript with IT/EN status/retry
checks. Windows and macOS build jobs now run the native save regressions.
Local tests run on Linux; real native GUI validation remains required after
building the updated installer. No commit, push, tag or release was performed.

Overall validation: **3916 passed, 5 skipped, 10 deselected**. Initial full run:
3907 passed and 9 environment-related failures (missing executable bits and
CMake). All 9 passed in a focused rerun after repairing the environment, with
no source-code changes between runs. Original and combined reports included.
92 targeted tests passed, one Win32-only test skipped; coverage 76.87%, Ruff
and JavaScript syntax checks passed. Executable entry-point modes restored
and retained in the ZIP.
