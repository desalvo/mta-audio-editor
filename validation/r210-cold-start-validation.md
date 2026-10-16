# Validazione r210 — recupero avvio ACE lento

Data: 2026-10-17, Europe/Rome. Versione 0.3.0-r210 invariata.
Base: MTA-r210-ace-timeout-cancel.zip, 1432 file;
SHA-256 41cf55c9909e819758b32aef3b5f6cfce45ee82e0e82ebd2254be40ccbe4c1d6.
Ultimo commit effettivo utente verificato tramite GitHub:
1c7f9724b06bdd77ecf4c2de11392646380a4ddf
(Add live GPU diagnostics and unified AI profiling, fix ACE long-job timeouts and support Arranger cancellation).
Nessun commit, push, tag, release o intervento sul server effettuato dall'assistente.

## Evidenza e riproduzione

Analizzati ZIP mta-diagnostics-2f03ce5338d84ff3a219c6a0736229ff.zip,
screenshot e journal del tentativo e65dbf78074846c59de9b0442958785a.
Il journal mostra modelli caricati al primo task, poi TaskStopped durante il
ricampionamento; ACE presenta la conseguenza come Invalid source audio.
La richiesta di controllo con timeout HTTP di 3 s poteva scadere mentre ACE
caricava i modelli, provocando il cleanup e il comando cancel=true.

È stato eseguito il sorgente esatto dell'adapter precedente contro un server
HTTP con risposta al controllo ritardata di 3,25 s. Risultato: TimeoutError
in 3,01 s e POST cancel=false seguito da cancel=true. Evidenza sintetica nel
file r210-cold-start-reproduction.log. Il codice corretto supera la medesima
attesa sia come modulo sia come subprocess: un solo upload, WAV ricevuto e
nessuna richiesta di annullamento. Nessuna GPU/modello è simulato come reale.

## Modifiche

Richieste idempotenti di controllo/polling con timeout fino a 30 s, ridotto al
budget residuo; errori temporanei di trasporto e HTTP 429/502/503/504 ritentati
senza duplicare il task o estenderne il tempo totale. HTTP di autenticazione
ed errori di validazione restano bloccanti. Nessun retry dell'upload ambiguo.
Scadenza reale e cancellazione esplicita mantengono i percorsi di arresto.
Il sidecar comunica soltanto messaggi fissi, senza dettagli remoti o segreti.
Nessuna modifica a cgroup, ledger, GPU verified o ammissibilità al billing.
Tutte le funzionalità del precedente archivio sono conservate.

## Risultati finali

- Controlli mirati: 104 passed, 1 warning in 19.00s.
- Primo passaggio generale: 1 failed, 3331 passed, 4 skipped, 10 deselected, 4 warnings in 203.07s (0:03:23).
- L'unico fallimento era FileNotFoundError per cmake assente nel runner, nel test
  VST3 preesistente test_sdk_cmake_rejects_incomplete_checkout. Installato CMake
  4.4.4 nel runner e rieseguito lo stesso test senza modificarlo: 1 passed.
  Evidenza in r210-cold-start-environment-rerun.log/XML.
- Esito finale complessivo sullo stesso codice: **3332 test superati**;
  i 4 skip e 10 casi esclusi restano dichiarati. Il primo log generale viene
  conservato integralmente, compreso il fallimento ambientale poi risolto.
- Copertura app: 74.62% (soglia 70%).
- Ruff app/native/tests/scripts/k8s-wizard.py: superato.
- node --check app/static/app.js: superato; JavaScript invariato.
- ZIP: verifica CRC e conservazione dell'intero manifest di base;
  checksum SHA-256 consegnato separatamente.

I quattro skip richiedono SDK Steinberg/ADelay opzionali. I dieci test esclusi
sono integrazioni AF_UNIX non eseguibili nel runner. I warning sono nei log.
Casi specifici: risposta HTTP reale >3 s, CLI standalone, retry di socket,
connessione, 429 e 503 in entrambe le fasi, budget ridotto rispettato con
richiesta cancel solo alla scadenza, 401/403/422 bloccanti. Sono inclusi i
precedenti test di task control, sicurezza API, annullo, GPU live e accounting.

## Limiti e prova sul server

La causa di rete e la sua correzione sono riprodotte su HTTP reale CPU.
Non è disponibile ROCm nel runner. Restano da verificare la prima generazione
a freddo sul server con profiler attivo, i campioni GPU live, annullo volontario,
il brano lungo oltre dieci minuti e playback/persistenza del risultato.
Nessuna certificazione completa o abilitazione del billing GPU viene dichiarata.
Istruzioni: ACE_COLD_START_R210.md e ACE_LONG_JOBS_AND_CANCELLATION_R210.md.
