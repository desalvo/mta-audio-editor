# Accounting dei worker con figli — correzione CI

29 ottobre 2026 · MTA 0.3.0-r210 PRE-RC · checkpoint autosufficiente.

**Corretto il difetto reale emerso nella CI: l’assenza di figli nei campioni `/proc` non certifica l’accounting completo dei percorsi interni che avviano altri processi. 248 test locali distinti passati, 13 nuovi, nessun failure/error/skip corrente.** Stato originale invariato: **28/42 (66,7%), E completa, RC aperta**. Il commit resta all’utente.

## Baseline e risultato remoto

[Run 40866015704, job Quality 123420863146](https://github.com/desalvo/mta-audio-editor/actions/runs/40866015704/job/123420863146), commit **`8ed30091686bbb48722b8b73faf2927472d01d50`**, messaggio `Fix CI`: **7132 passati, 1 fallito, 50 skip**, 719,49 secondi. Copertura **76,71%**, soglia 70% superata. SAST/dependency audit e SDK VST3 Linux passano; i job dipendenti dal Quality fallito sono saltati. Gli otto fallimenti del run precedente risultano risolti. Questa CI complessiva resta fallita: non esiste ancora un verde remoto della nuova correzione.

Il confronto in sola lettura dell’albero Git completo, non troncato, conferma tutti i **4176 blob tracciati** identici all’input consegnato. Il workspace era tornato al checkpoint admin-cutover: è stato ripristinato **MTA-0.3.0-r210-pre-RC-ci-40858-cumulative.zip**, SHA256 `a24735415f1fcfe233e81f0929549b784e98f4d5abc7b8b93ee79494828ae774`, 99.085.551 byte / 4825 file, verificando SHA, CRC, manifest e modi. Nessuna implementazione già validata è stata ricostruita.

## Difetto riprodotto e correzione

Il test fallito non era soltanto una fixture obsoleta. Il worker DSP registrato esegue FFmpeg come figlio; il file audio sintetico è brevissimo e il figlio può nascere e terminare tra due osservazioni del supervisore. In quel caso `wait4` del worker poteva essere dichiarato isolato senza avere dimostrato la misura dell’intero albero. La riproduzione deterministica esegue ancora FFmpeg reale e forza soltanto l’osservatore dei figli a restituire campioni vuoti. Prima della correzione riproduce lo stesso `DID NOT RAISE WorkerUncertain`.

`app/ai_metering_agent.py` ora riconosce la topologia dei percorsi del **worker interno esatto** `ai_unified_adapter.py`:

- Demucs, SAM Audio e singer-separation;
- backing-vocals con DSP FFmpeg, compreso il default effettivo selezionato dalla policy;
- DrumSep quando usa il percorso SAM Audio.

Per questi percorsi, una misura di sola fonte `worker`/`wait4` non consente pubblicazione o finalizzazione fatturabile, anche quando il campionamento dichiara `isolated:true`. La condizione viene verificata sia al completamento sia nel trattamento di `WorkerInterrupted`: una cancellazione non trasforma la misura incompleta in un addebito parziale. Restano l’errore `WorkerUncertain`, l’identità del job originale, il ledger `running/unmetered`, l’uso non addebitato e il claim originale `running`.

La misura cgroup isolata conserva il proprio percorso. Il controllo riguarda il worker interno risolto dal registro e la decisione effettiva del modello; non cambia per semplice nome fornito dalla richiesta e non impone la topologia del worker interno agli eseguibili esterni dell’operatore. I controlli precedenti su figli osservati, account/token, cancellazione e quiescenza restano attivi. Nessun comando opaco riceve un’autorizzazione.

**Conseguenza operativa:** per completare e contabilizzare questi percorsi locali con figli serve la delega cgroup v2 già prevista da MTA. Senza una misura completa il servizio conserva lo stato incerto e richiede la riconciliazione originale; non inventa CPU o prova di arresto. Il percorso standalone/native della DSP resta quello precedente. Questa correzione non certifica worker ostili, figli sconosciuti, contenitori, kernel remoti o recupero multi-host: B2/B6/F4 e i target effettivi restano distinti.

## Verifica corrente

**248 esiti correnti distinti passati, 13 nuovi**, ricavati dall’unione degli esiti più recenti per identità del caso, senza sommare sovrapposizioni. Include il caso reale FFmpeg, diritti dei separatori legacy, account/coda/token e API, worker esterni reali, cancellazione e claim originali, quiescenza e tutti i gate sui sorgenti modificati.

I dodici nuovi casi negativi esercitano sei selezioni/default in completamento e cancellazione, con misura sintetica apparentemente isolata e divieto di pubblicare. Un caso positivo aggiuntivo conserva instradamento/ricevuta/settlement del runner cgroup con **risultato sintetico**. Le fixture cgroup verificano il contratto software; non sono una prova del kernel reale. Nessuna nuova prova cgroup fisica, GPU o modello neurale è dichiarata.

Sono conservati i rapporti diagnostici: il difetto di produzione riprodotto prima della correzione e una prima aspettativa errata delle nuove fixture (`usage_json` vuoto è `{}`, non SQL NULL). La successiva verifica richiede l’oggetto d’uso vuoto e passa. Gli esiti correnti e gli hash sono in `validation/r210/ffmpeg-ci-result.json`; i vecchi fallimenti non sono cancellati né conteggiati come pass.

Ruff app/test modificati passa. Bandit completo aggiornato: **304 sorgenti, 165 finding, 0 HIGH / 21 MEDIUM / 144 LOW**, nessun errore, soppressione o finding nuovo; tutte le identità dei finding coincidono con la scansione precedente. La revisione manuale lega il solo delta di `ai_metering_agent.py`; C2 conserva **170 confini**, il censimento runtime **551 sorgenti / 782 punti** e HTTP **30 siti / 21 file**. Nessun checker, soglia, workflow o esclusione modificato. Non è stata ripetuta la full suite né ricalcolata qui la copertura globale.

## Riuso, residui e prossima azione

Tutti gli altri 303 sorgenti app, native/mobile, loader F3, workflow, dipendenze e trasporti sono identici all’input. Si riusano le prove corrispondenti di finanza, Chromium, diritti/loader e i sette casi ONNX/HTTPS precedenti. La prova Apple `40858613243` resta valida: i suoi **13 hash** sono invariati, 32 controlli SDK e build unsigned già passati. Nessun bisogno di ripetere iOS per questo delta server.

Restano aperti i criteri originali **A4,A5,A6,B2,B6,C3,C5,C6,D6,F4,F5,F6,G5,G6**. Nessuno promosso da questa correzione; parole, pesi e stati dei 42 criteri sono conservati. Finanza legacy/globale, accettazione completa degli esecutori e revisioni indipendenti richiedono ancora lavoro, oltre ai target effettivi. Registro Core ML reale vuoto; RC e transizione finanziaria generale restano disabilitate.

Dopo il commit dell’utente verificare la **CI standard Quality e SAST**. Non è necessario ripetere prima iOS o la full CI invariata. Nessun dispatch automatico, commit/staging/push/tag/release, modifica GitHub o intervento su server/provider reali è stato effettuato.

Consegna: **MTA-0.3.0-r210-pre-RC-ffmpeg-tree-cumulative.zip**, con SHA256 adiacente, tutti i 4825 percorsi e i 649 log di ingresso byte-identici, asset/licenze/manuali e modi/metadati ZIP originali. Nessun runtime, modello, database o credenziale aggiunto.

Commit inglese suggerito, cumulativo dopo `8ed3009`:

`Require tree accounting for known subprocess workers`

## English handoff

Run 40866015704 binds commit `8ed30091686bbb48722b8b73faf2927472d01d50`; all 4176 tracked blobs match the previous delivery. Quality has 7132 passes, one failure, 50 skips and 76.71% coverage; SAST and VST3 SDK succeed. The remaining failure exposes a real short-child sampling gap. It is reproduced deterministically with actual FFmpeg and an observer returning empty samples.

Known child-spawning routes of the exact internal unified adapter now require tree accounting even if direct-child wait4 appears isolated. Completion and interruption both preserve the original uncertain job/claim without publication or guessed billing. Cgroup results retain their existing path; external operator workers keep their own topology. Local proof has 248 distinct current passes, 13 new, including real FFmpeg and explicitly synthetic cgroup contract cases. Only one production source changed; security reviews were refreshed without new findings or weaker checkers. Real cgroup/kernel/multi-host and whole-F4 acceptance remain open.

Original score stays 28/42, 66.7%, E complete, RC false. Reuse unchanged Apple/finance/web/loader proofs. After the user commits, inspect ordinary Quality/SAST; no automatic GitHub/server/provider action is authorized.
