# Coda AI — contesa transitoria della barriera SQLite

29 ottobre 2026 · MTA 0.3.0-r210 PRE-RC · checkpoint autosufficiente.

**Corretto il polling della coda in presenza di una barriera SQLite temporaneamente occupata; isolate anche le fixture recenti. 145 test locali distinti passati, 9 nuovi, zero failure/error/skip correnti.** Nessuna promozione dei criteri originali: **28/42 (66,7%), E completa, RC aperta**. Il commit spetta all’utente.

## Baseline verificata e CI osservata

[Run 40912981261, job Quality 123585628451](https://github.com/desalvo/mta-audio-editor/actions/runs/40912981261/job/123585628451) esegue il commit **`dafdff6a1d5a8fc5670e9125297406c5df470231`**, messaggio `Require tree accounting for known subprocess workers`. Quality: **7145 passati, 1 fallito, 50 skip**, 1089,52 secondi, copertura **76,71%**, soglia 70% raggiunta. SAST/dependency audit e SDK VST3 Linux passano; i job dipendenti da Quality sono saltati. La correzione FFmpeg precedente è conservata. Il nuovo delta non dispone ancora di una CI remota verde.

Il confronto in sola lettura dell’intero albero Git, non troncato, conferma tutti i **4193 blob tracciati** identici all’archivio in ingresso. Dopo il reset locale è stato ripristinato **MTA-0.3.0-r210-pre-RC-ffmpeg-tree-cumulative.zip**, SHA256 `4f184c5f4cb2915cc824334d3abb128f9147edeb11c34eaa7b128bd83abf4817`, 99.306.612 byte / 4853 file. SHA, CRC, manifest e modi verificati; nessun lavoro precedente ricostruito.

## Causa e comportamento corretto

Il fallimento avveniva prima di ricevere `WorkerUncertain`, durante `ai_global_execution.execute → queue.get → _db → _Connection → fence_held`. La lettura di `sqlite_master` incontrava un lock e produceva correttamente `BarrierUnavailable(retryable=True)`. Il polling trattava però questa osservazione transitoriamente indisponibile come un errore definitivo. Il log non prova quale connessione concorrente detenesse il lock.

È stata riprodotta la stessa indisponibilità con **SQLite reale in WAL e `locking_mode=EXCLUSIVE`**. Anche rilasciando il lock subito dopo la prima lettura fallita, il vecchio `get` propagava l’errore e non osservava il risultato originale.

`app/ai_arranger_runtime.py:get` ora esegue fino a **3 tentativi**, con pausa di 50 ms tra i tentativi, soltanto per `BarrierUnavailable` esplicitamente marcato retryable da `SQLITE_BUSY/SQLITE_LOCKED`. Ogni tentativo apre di nuovo la connessione e verifica la barriera corrente: nessun permesso o risultato è memorizzato come sostituto della verifica. La guardia conserva il proprio budget breve; non sono stati aumentati i timeout SQLite generali. Le altre query conservano i timeout precedenti, quindi non si promette un limite globale di durata per tutte le operazioni della coda.

La ripetizione riguarda **l’osservazione dello stesso job**, compreso il recupero idempotente già presente nel getter. Non ripete `start`, `_claim`, il callback del worker, pubblicazione, fatturazione o pagamenti. Il recupero esistente aggiorna soltanto gli stati ancora eleggibili e conserva le ricevute terminali uniche; non rigioca il lavoro. Stato mancante resta mancante.

Se la contesa persiste, il terzo tentativo propaga l’indisponibilità. Una barriera sconosciuta, manutenzione effettiva, corruzione o altro errore SQL continua a fallire immediatamente. Non si interpreta mai una lettura fallita come assenza della barriera. La gestione successiva degli errori esauriti resta quella precedente; questa correzione non introduce una nuova politica di cancellazione o recupero dei worker.

## Isolamento delle fixture

I 13 casi di `test_r210_known_worker_tree_accounting.py` usavano la coda globale ereditata dal processo di test. Ora ogni caso usa una directory temporanea propria. La fixture conserva la vera factory dei thread, registra quelli creati e ne attende la terminazione prima di ripristinare i percorsi. Restano verificati claim originali, ledger `running/unmetered`, uso vuoto, rifiuto della misura incompleta e percorso cgroup sintetico. Nessun test è rimosso o spostato in opt-in e nessuna barriera è disabilitata.

Questo elimina una fonte di interferenza tra casi; non viene presentato come prova che quella specifica interferenza fosse l’unico detentore del lock della CI.

## Prove correnti e riuso

**145 esiti correnti distinti passati, 9 nuovi**, calcolati dall’ultimo esito per identità, senza sommare le riesecuzioni delle fixture. I nuovi casi verificano: lock reale rilasciato dopo la prima lettura, lock persistente con tre soli tentativi, quattro errori non ritentabili, job assente e due esecuzioni reali della coda che conservano risultato o errore/identità originali con un solo callback. Il test positivo e quello negativo attraversano il lock reale; non usano un falso successo della barriera.

Il gruppo comprende account/coda/token e API, cancellazione, accounting degli alberi noti e contesa durante export. I 13 casi con la fixture finale sono passati dopo il join dei thread. La diagnosi iniziale include anche un doppio close della nuova fixture di test, corretto prima della riproduzione valida. Tutti i rapporti storici restano conservati; gli esiti correnti sono in `validation/r210/queue-busy-result.json`.

Ruff app/test modificati e i quattro gate sui sorgenti passano. Bandit: **304 sorgenti / 165 finding**, **0 HIGH / 21 MEDIUM / 144 LOW**; tutte le identità dei finding sono invariate, zero errori o soppressioni. C2 conserva **170 confini**, runtime **551 sorgenti / 782 punti**, HTTP **30 siti / 21 file**. Review aggiornate sul solo delta runtime; nessun checker, soglia, workflow o dipendenza modificato.

Il solo sorgente di produzione modificato è `ai_arranger_runtime.py`. Gli altri 303 sorgenti app, il controllo FFmpeg/worker, i loader F3, native/mobile, workflow e dipendenze sono byte-identici. Si riusano le prove delle parti invariate di finanza, web/Chromium, diritti e ONNX/HTTPS. I **13 hash** della prova Apple `40858613243` coincidono ancora: 32 controlli SDK e build unsigned già passati, nessun nuovo run iOS necessario. Non è stata ripetuta la full suite e non è stata ricalcolata qui la copertura globale.

## Stato RC e prossima azione

Restano aperti **A4,A5,A6,B2,B6,C3,C5,C6,D6,F4,F5,F6,G5,G6**. Parole, pesi e stati originali dei 42 criteri restano invariati. Finanza globale/legacy, tutti gli esecutori e revisioni indipendenti richiedono ancora lavoro; i residui non sono tutti esterni. Registro Core ML reale vuoto, RC e transizione finanziaria generale disabilitate. La correzione non certifica un kernel cgroup effettivo, più host, hardware o modelli neurali.

Dopo il commit dell’utente verificare **Quality e SAST della CI standard**. Riusare iOS già validato; nessuna necessità di ripetere prima la full CI. Nessun dispatch CI, commit/staging/push/tag/release o intervento su GitHub/server/provider reali è stato effettuato.

Consegna: **MTA-0.3.0-r210-pre-RC-queue-busy-cumulative.zip**, con SHA256 adiacente. Conserva tutti i **4853 percorsi e 660 log di ingresso** byte per byte, asset/licenze/manuali e modi/metadati ZIP originali. Nessun runtime, modello, database o credenziale aggiunto.

Commit inglese suggerito, cumulativo dopo `dafdff6`:

`Retry busy queue observations and isolate worker tests`

## English handoff

Run 40912981261 binds commit `dafdff6a1d5a8fc5670e9125297406c5df470231`; all 4193 tracked blobs match the previous delivery. Quality has 7145 passes, one retryable SQLite barrier failure, 50 skips and 76.71% coverage. SAST/VST3 succeed. Actual exclusive SQLite contention reproduces the failure; the log does not identify the original competing lock holder.

The original job getter now retries only typed BUSY/LOCKED barrier observations, at most three attempts, with fresh validation. Persistent or nonretryable barriers still fail; workers, admission, publication and billing are never replayed. Existing non-barrier SQL timeouts and final error handling are unchanged. Known-tree fixtures now own a separate queue and join their actual threads before restoring paths.

Current local proof:145 distinct passes,9new, including real exclusive locks, original result/error identity and single callback execution. Only one runtime source changed; security finding identities and checker logic are unchanged. Reuse Apple/finance/web/loader evidence for identical boundaries. After the user commits, inspect ordinary Quality/SAST. Original score remains28/42,66.7%,E complete,RCfalse;no remote mutation or new full/kernel/model acceptance claimed.
