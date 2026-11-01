# Isolamento dell’avvio worker — MTA 0.3.0-r210 PRE-RC

**RC: 34/42 = 81,0%; F4 rimane aperto.** Questo checkpoint completa una correzione finita di avvio, senza modificare il testo o il peso dei criteri.

## Problema e soluzione

Due test con processi reali hanno dimostrato, prima della correzione, che un `sitecustomize.py` introdotto tramite `PYTHONPATH` poteva eseguirsi all’avvio del guardian o del worker ACE, prima dei normali controlli. L’avvio Python dei worker registrati, pull, Studio, ACE e dei bootstrap guardian/cgroup usa ora `-I`. Una copia dell’ambiente filtra le variabili di avvio Python e i principali punti di preload del linker; conserva policy ammessa, impostazioni GPU e le altre variabili operative. Anche il probe ACE, i test Studio, il probe e la separazione legacy Demucs sono coperti dagli specifici percorsi modificati. L’adattatore unificato aggiunge `-I` ai processi Python Demucs e SAM. I processi binari non diventano attestati con queste modifiche.

Una prova Linux compila una libreria con costruttore e verifica che `LD_PRELOAD` la esegua in un processo di controllo; l’avvio del guardian filtrato non la esegue. Altre prove controllano il passaggio della policy, l’assenza di esecuzione del `sitecustomize`, il probe ACE reale e l’esecuzione FFmpeg reale con contabilità/recupero. Le prove di sostituzione processo e quelle senza modello sono indicate come tali nei test: non attestano inferenza reale. La suite finale selezionata contiene **764 passati, 11 saltati, nessun errore o fallimento**; i prerequisiti mancanti sono riportati nell’XML. Ruff, compilazione e quattro gate di revisione passano; Bandit 168 finding già riesaminati, 0 HIGH. Gli esiti precedenti del primo tentativo (permesso eseguibile perso dall’estrazione, revisione sorgente temporaneamente non aggiornata e dipendenza `mido` assente) sono stati risolti prima della selezione finale; non rappresentano una CI remota.

## Compatibilità e limiti

Gli operatori che fornivano moduli ai processi Python mediante `PYTHONPATH` devono installarli nell’ambiente dell’interprete selezionato. `LD_LIBRARY_PATH` e `PATH` restano disponibili per GPU e runtime, perciò non sono autenticati da questa correzione. `-I` non è una sandbox: non verifica interpreti esterni, pacchetti o file `.pth` delle site-packages, librerie native o codice di amministratori. Non sana un processo padre già compromesso.

**F4 non è completo:** `MTA_DEMUCS_PYTHON`, gli interpreti e le dipendenze esterne richiedono un contratto indipendente; Mega53 consente ancora una checkout e uno script upstream scelti dall’operatore; il backend ACE remoto non dimostra quale checkpoint effettivo abbia eseguito. Non sostituire tali prove con nomi, digest autoriferiti o test simulati. Rimangono aperti A6, B6, C6, F4, F5, F6, G5, G6; C6 comprende anche integrazione software oltre alla prova tra host. I dettagli A6 sono in `A6_SANDBOX_PREREQUISITES_R210.md`.

## Ripresa

Archivio `MTA-0.3.0-r210-pre-RC-worker-startup-isolation-cumulative.zip`, prova `docs/validation/r210/worker-startup-isolation/result.json`; il contenuto finanziario A4/A5 è conservato. Baseline Git confermata `ee4e37fd30c39a72638b303b01ca0cd5b090f272`; ultima full CI nota `41156985339`. Nessun commit, push, tag o CI remota effettuati qui. Commit cumulativo suggerito: `Recover canonical payments and isolate AI worker startup`.
