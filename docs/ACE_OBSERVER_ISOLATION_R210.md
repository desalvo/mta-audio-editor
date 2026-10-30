# ACE-Step: isolamento degli osservatori — 30 ottobre 2026

Corretta una race reale nei callback asincroni della UI: una risposta di stato o errore dopo il cambio di progetto poteva aggiornare il dialogo del progetto nuovo. Inoltre, dopo await reconcileAiProject, il completamento di un vecchio osservatore poteva chiudere una nuova finestra aperta nello stesso progetto. Ora sono verificati progetto ed epoch sia dopo la risposta API sia dopo la riconciliazione, e anche nel percorso di errore. Timer, risorse CPU/GPU e chiusura conservano i comportamenti precedenti per l'osservatore corrente.

Prove:57 test passati,2 saltati per WeasyPrint assente;1 nuovo caso esegue3 race deterministiche sul JavaScript di produzione con Node. Include risposte tardive, errori tardivi e osservatore sostituito durante riconciliazione. Non è un collaudo browser/native o GPU reale. Sintassi JavaScript e Ruff completo passano. Due vecchie fixture GPU usavano worker sintetici senza la dichiarazione test-only già prevista: corretta la fixture con synthetic_worker_resolution, nessun bypass di produzione. Log diagnostici iniziali conservati.

Avanzamento PRE-RC invariato:29/42=69,0%. Il criterio F4 non viene chiuso da questo intervento UI. L'incremento percentuale richiesto non è raggiunto; rimangono runtime/dipendenze esterne, identità del backend ACE e gli altri criteri finanziari/target originali. Nessun criterio, peso o denominatore modificato. L'interfaccia ha un difetto corretto e verificato, ma non viene dichiarata una nuova accettazione della macroarea intera.

Input: MTA-0.3.0-r210-pre-RC-pinned-transcription-loaders-cumulative.zip, SHA256 d1f2a97db8cc0a7e0243b8935dfa4a0886b38d7672ab17d33c01a4dff345b254. Tutti i delta successivi a4014a1f rimangono cumulativi e non committati. Stato/checkpoint aggiornati nel pacchetto. Backend Python, modelli, policy, contatori e API non modificati; inventario runtime aggiornato per l'hash del JS, checker invariato. Nessun commit/push/tag, CI remota o intervento di produzione.

Commit cumulativo suggerito:

`Enforce model rights, pin transcription loaders and isolate AI job observers`
