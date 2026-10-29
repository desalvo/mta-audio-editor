## Checkpoint corrente — accounting dei figli FFmpeg — 29 ottobre 2026

Leggere **FFMPEG_TREE_ACCOUNTING_R210.md** e `validation/r210/ffmpeg-ci-result.json`. Baseline confermata **8ed30091686bbb48722b8b73faf2927472d01d50**,tutti4176blob tracciati identici all’input. La CI standard40866015704 risolve gli8fallimenti precedenti ma fallisce1caso FFmpeg:7132passati,50skip,copertura76,71%;SAST e SDK VST3 passano. Il difetto reale è riprodotto:un figlio breve sfugge ai campioni/proc.

I percorsi del worker interno che avviano figli ora richiedono accounting dell’albero anche se wait4 appare isolato:Demucs,SAM,singer-separation,DSP FFmpeg e DrumSep/SAM. Completamento e cancellazione conservano job/claim originali incerti prima di output/addebito,senza CPU inventata. Percorso cgroup conservato;serve la delega effettiva per completare questi lavori locali. **248test locali distinti passati,13nuovi,zero failure/error/skip correnti**,compreso vero FFmpeg con osservatore vuoto. Il caso positivo cgroup è sintetico,non prova kernel.

Bandit304sorgenti/165finding(0HIGH/21MED/144LOW),C2 170confini,runtime551sorgenti/782punti,HTTP30siti/21file;gate e Ruff passano. Nessun checker,soglia,workflow o dipendenza modificato. Apple32controlli/build già acquisiti e13hash invariati:non ripetere iOS. Dopo il commit dell’utente verificare CI standard Quality/SAST;nessun verde remoto del nuovo delta ancora disponibile.

**28/42(66,7%),E completa1/7,RC aperta;nessun criterio promosso.** Residui originali invariati,non tutti esterni. Cumulativo unico:**MTA-0.3.0-r210-pre-RC-ffmpeg-tree-cumulative.zip**,con tutti4825percorsi e log di ingresso conservati. Nessun commit o modifica GitHub/server/provider. Commit suggerito:`Require tree accounting for known subprocess workers`.

---

Cronologia precedente,superata dove incompatibile con il checkpoint corrente:

## Checkpoint corrente — CI corretta e prova Apple acquisita — 29 ottobre 2026

Leggere **CI_40858_REPAIR_R210.md** e `validation/r210/ci-40858-result.json`. Baseline ora confermata **96c27c37e508564edc1cd4aee978896b1612e5a5**: tutti4164blob tracciati corrispondono al precedente cumulativo. La CI standard40858442206 fallisce8test obsoleti(7122passati,50skip,copertura76,67%);SAST e SDK VST3 Linux passano. Le fixture corrette conservano account/coda attivi,diritti espliciti per byte sintetici e default Whisper condiviso. Nessun codice di produzione,workflow,soglia o opt-in modificato. **26test mirati passati,3nuovi,zero failure/error/skip**;tutti8i fallimenti coperti.

**Apple40858613243 acquisito:32controlli SDK reali passati,zero skip,vero Keychain isolato e compilazione unsigned dell’app riuscita.** Artefatto verificato con digest remoto e13hash sorgenti correnti,conservato in `validation/r210/ci-40858613243-ios/`. Supera il precedente blocco locale Xcode,senza riscriverlo. Non è inferenza neurale,device fisico o intero F4/F5/F6;il registro CoreML reale resta vuoto. Non ripetere il workflow Apple invariato.

**28/42(66,7%),E completa1/7,RC aperta;nessuna promozione di criterio.** Dopo il commit dell’utente verificare il prossimo Quality standard. La fullCI storica su4c3 non certifica il nuovo delta. Riusare le prove delle sorgenti di produzione identiche;restano14criteri originali,con lavoro economico/legacy/esecutori non tutto esterno. Cumulativo unico:**MTA-0.3.0-r210-pre-RC-ci-40858-cumulative.zip**,con tutti4805percorsi e log di ingresso conservati. Nessun commit o modifica remota eseguito. Commit suggerito:`Align CI fixtures with execution and model rights guards`.

---

Cronologia precedente,superata dove incompatibile con il checkpoint corrente:

## Checkpoint corrente — contratto Core ML iOS e build — 29 ottobre 2026

Leggere **IOS_LOCAL_MODEL_RIGHTS_R210.md** e `validation/r210/ios-rights-result.json`. **28/42(66,7%),E completa1/7,PRE-RC;nessun criterio promosso,l’aumento numerico richiesto non è raggiunto.** Contratto iOS integrato tra revisione nel bundle,byte sorgenti,compilazione,ricevuta Keychain,inventario compilato,cache,revoca per chunk e consegna. Registro di produzione vuoto:zero checkpoint reali approvati;modelli legacy conservati ma senza grant automatico. Build/refresh non scaricano asset privi di revisione corrispondente.

**90 casi locali distinti passati,41 nuovi,zero failure/error/skip correnti.** Tutti304 sorgenti server identici:finanza/web/Chromium/Bandit/C2/HTTP/F3 invariati riusati. Inventario corrente551sorgenti/782punti,checker invariato. Swift/Xcode assenti:target **blocked,accepted:false,passed:0**. Pronto il workflow manuale default-off **Optional iOS model rights**,input **ios_model_rights=true**,con32 controlli SDK reali più compilazione dell’app iOS senza firma. Eseguirlo dopo il commit dell’utente;non dichiararlo già passato. F4 completo,F5/F6 e gli altri14criteri restano aperti;non tutti i residui sono esterni.

Cumulativo:**MTA-0.3.0-r210-pre-RC-ios-rights-cumulative.zip**. Baseline4c3 conservata;nessun commit o azione GitHub/server/provider. Non ripetere questa implementazione o i blocchi precedenti. Commit cumulativo suggerito:`Complete execution safeguards, settlement recovery and native model rights`.

---

Cronologia precedente,non prevale sul checkpoint corrente:

## Checkpoint corrente — Demucs/backing legacy e DSP condivisa — 29 ottobre 2026

Leggere **LEGACY_SEPARATOR_ACCEPTANCE_R210.md** e `validation/r210/legacy-separator-result.json`. **28/42(66,7%),E completa1/7,PRE-RC;nessuna promozione,l’aumento numerico richiesto non è raggiunto.** Chiusi il bypass della policy nel Demucs desktop/diretto,il repository/selector estraneo,la revoca prima/dopo la consegna,il caricatore backing con filename arbitrario e l’uso di un modello già caricato dopo revoca. Il comando opaco lead/backing è rifiutato prima di effetti/API/ledger;non riceve un grant DSP. DSP server/desktop condivisa con vero FFmpeg/PCM;accounting dei discendenti non provato conserva job/claim originali.

**286 casi distinti passati,47 nuovi,zero failure/error/skip correnti.** Nessun nuovo modello neurale;7 prove F3 precedenti riusate solo sui loader identici,7vecchi skip opzionali ancora aperti. Ruff/compile/61gate passano:304sorgenti/165finding(0HIGH/21MED/144LOW),170confiniC2,30sitiHTTP/21file,548sorgenti/781punti runtime;checker/soppressioni invariati. F4 completo,F5/F6 e gli altri14criteri restano aperti;CoreML e runtime opachi richiedono ancora codice/accettazione,non soltanto target. Non ripetere questo sottoblocco,i selector o la finanza già validata.

Cumulativo:**MTA-0.3.0-r210-pre-RC-legacy-separators-cumulative.zip**;baseline4c3 conservata,nessun commit o azione GitHub/server/provider. Migrazione delle sole configurazioni legacy descritta nel handoff. Commit cumulativo suggerito:`Complete execution safeguards, settlement recovery and legacy separator rights`.

---

Cronologia precedente,non prevale sul checkpoint corrente:

## Checkpoint corrente — selezione checkpoint prima dell’ammissione — 29 ottobre 2026

Leggere **MODEL_SELECTOR_BOUNDARIES_R210.md** e `validation/r210/selector-boundaries-result.json`. **28/42(66,7%),E completa1/7,PRE-RC;nessuna promozione,l’aumento numerico richiesto non è raggiunto.** Chiusi i bypass del selettore per Whisper/SAM/Demucs nei parent,default,ingressi diretti e wrapper profilato;API token JSON/WAV rifiutano i selettori estranei prima di processo e ledger. Nessuna sostituzione automatica di modello. Registro Demucs condiviso e default Whisper allineato.

**274 casi distinti passati,44 nuovi,zero failure/error/skip correnti.** Fixture di worker e model-loader,non nuova inferenza neurale.7 prove ONNX precedenti riusate solo per i3 loader identici e decisioneBasicPitch invariata;7 vecchi skip opzionali restano aperti. Ruff/compile/61gate passano:304sorgenti app/166finding invariati,171confiniC2,30sitiHTTP/21file,548sorgenti/783punti runtime. Checker/soglie/soppressioni invariati. Restano14 criteri originali,F4/F6 non completi,RC falsa. Non ripetere questo blocco o i precedenti helper/collector/settlement.

Cumulativo:**MTA-0.3.0-r210-pre-RC-model-selectors-cumulative.zip**;baseline confermata4c3c73afe6d3829aad155c23f5f1bbb6d375433a. Nessun commit o azione GitHub/server/provider. Suggerimento cumulativo:`Complete execution safeguards, administration, settlement recovery and checkpoint admission`.

---

Cronologia precedente,non prevale sul checkpoint corrente:

## Checkpoint corrente — diritti diretti e wrapper di componente — 29 ottobre 2026

Leggere **DIRECT_EXECUTOR_RIGHTS_R210.md** e `validation/r210/direct-rights-result.json`. **28/42(66,7%),E completa1/7,PRE-RC;nessuna promozione,l'aumento numerico richiesto non è raggiunto.** Completati18 ingressi diretti con verifica della policy corrente,revoca Whisper/fallback MPS->CPU e controlli indipendenti sui componenti canto. Wrapper offline vincolati a ruolo,componente installato,permessi,script e cwd originali;non sono più esecutori generici. Il criterio F4 completo,F5/F6,checkpoint/runtime opachi e target non sono accettati da queste fixture.

**507 casi distinti passati,99 nuovi,zero failure/error correnti,7 skip opzionali espliciti.** Comprende7 prove ONNX reali,di cui5F3/HTTPS e2coda/progetto,sui nuovi hash adapter;nessun downgrade di F3. Ruff/compile/61gate passano.303sorgenti/166finding invariati,171confiniC2,30sitiHTTP/21file,547sorgenti/783punti runtime;checker/soppressioni invariati. Finanza/UI/fullCI invariate riusate;non ripeterle senza modifiche rilevanti. Restano14 criteri originali,non tutti bloccati soltanto dall'ambiente;RC falsa.

Cumulativo:**MTA-0.3.0-r210-pre-RC-executor-rights-cumulative.zip**. Baseline confermata4c3c73afe6d3829aad155c23f5f1bbb6d375433a;nessun commit o azione GitHub/server/provider. Non rifare gli ingressi già chiusi o il settlement precedente. Suggerimento cumulativo:`Complete guarded execution, administration, settlement recovery and component rights enforcement`.

---

Cronologia precedente,non prevale sul checkpoint corrente:

## Checkpoint corrente — allocazioni parziali e replay originale — 28 ottobre 2026

Leggere **PAYPAL_PARTIAL_SETTLEMENT_R210.md** e `validation/r210/partial-report-result.json`. **28/42(66,7%),E completa1/7,PRE-RC;nessuna promozione,aumento numerico richiesto non raggiunto.** Completato recupero operativo di dispute parziali multicapture prive di importi articolo tramite allocazioni esatte ACM/STL autenticate,con rimborsi/debito abbonamento,rollback e replay ordinario vincolato a ricevuta/claim/hold/documento originali,ricontrollati nella transazione monetaria. Nessuna proporzione dei lordi o sostituzione di prove contraddittorie.

**357 casi distinti passati,40 nuovi,zero failure/error/skip correnti.** Provider/SFTP sintetici;ledger e transazioni reali isolati. Ruff/compilazione e61 gate passano:303 sorgenti app/166 finding invariati,171 confiniC2,30sitiHTTP/21file,547sorgenti/783punti runtime. Checker/soglie/soppressioni invariati. FullCI/Chromium/F3 invariate riusate. A4/A5/C3/C5/D6 restano aperti;14 criteri originali residui,RC falsa. Non ripetere questo percorso,collector o audit;proseguire su storico generale e basi legacy originali senza inventare denaro. Accesso report reale assente e non autorizzato,ma residui non tutti esterni.

Cumulativo completo:**MTA-0.3.0-r210-pre-RC-partial-settlement-cumulative.zip**;baseline confermata4c3c73afe6d3829aad155c23f5f1bbb6d375433a. Commit differito all'utente;nessuna azione GitHub/server/provider. Suggerimento cumulativo:`Complete guarded execution, administration and exact PayPal settlement recovery`.

---

Cronologia precedente,non prevale sul checkpoint corrente:

## Checkpoint corrente — recupero settlement autenticato — 28 ottobre 2026

Leggere **PAYPAL_SETTLEMENT_RECOVERY_R210.md** e `validation/r210/settlement-recovery-result.json`. **28/42 criteri (66,7%),E completa1/7,PRE-RC;nessun criterio promosso,aumento numerico richiesto non raggiunto.** Nuovo percorso operativo CLI: report ACM S6 e STL con credito completato T1202/T1205,conto/caso/apertura/aggiornamento/capture/importo esatti e fonte SFTP fissa autenticata -> claim immutabile del movimento e ledger originale. Nessun file browser o flag “pronto” autorizza denaro. Solo sottoinsieme CSV singolo/EUR/intervallo comune/case ID esatto;altri formati e casi restano bloccati.

**348 casi interessati distinti passati,46 nuovi,zero failure/error/skip correnti.** Database,ledger e drain C2 reali/isolati;provider e processo SFTP in fixture. Non è una verifica su PayPal reale. Actor originale in ricevuta,nessun riuso del movimento per altri casi,rollback/replay e documento cambiato verificati. Errori finiti raccolti chiudono l'ammissione;quiescenza sconosciuta conserva il ticket. Ruff/compilazione e gate sorgenti passano:303 sorgenti app,166 finding revisionati(164 precedenti+2LOW,0HIGH/21MED/145LOW),171confiniC2,30sitiHTTP/21file e nuovo processoSSH esplicitamente revisionato,547sorgenti/783punti runtime. Checker,soglie e soppressioni invariati.

Blocco esterno:accesso report/credenziali SFTP/hostkey approvate e coppie reali ACM/STL non disponibili;nessuna azione su provider/server autorizzata. Restano anche implementazioni/prove generali di storico,payout/allocazioni e quota/surplus legacy. Non chiudere A4/C3 da questo profilo. Restano14 criteri originali;RC falsa. Non ripetere collector,coverage,bridge,UI/F3/Chromium/fullCI invariate. Baseline confermata4c3c73afe6d3829aad155c23f5f1bbb6d375433a/fullCI40584085026 conservate;delta cumulativo non committato.

Cumulativo unico:**MTA-0.3.0-r210-pre-RC-settlement-recovery-cumulative.zip**. Commit suggerito,non eseguito:`Complete guarded execution, administration and authenticated settlement recovery`.

---

Le sezioni seguenti sono cronologia e non prevalgono su questo checkpoint.

## Checkpoint corrente — acquisizione merchant riprendibile

Leggere MERCHANT_RANGE_ACQUISITION_R210.md e validation/r210/merchant-range-result.json. 106 passati,9 nuovi. Nuovo collector operativo su vuoti temporali,conferma/merchant originali,una finestra per passo e ripresa senza cancellare prove. 28/42(66,7%) invariato;nessun criterio promosso,RC aperta,commit differito. Non è quietanza economica o storico completo del conto. Cumulativo MTA-0.3.0-r210-pre-RC-merchant-range-cumulative.zip.

---

Cronologia precedente:

## Checkpoint corrente — copertura temporale merchant

Leggere MERCHANT_WINDOW_COVERAGE_R210.md e validation/r210/merchant-window-result.json. 28 casi mirati passati,13 nuovi. 28/42 (66,7%) invariato,nessuna RC o promozione. Nuovo audit offline read-only delle finestre;nessuna certificazione di storico completo o settlement. Commit differito;baseline confermata4c3,CI e prove precedenti conservate. Cumulativo MTA-0.3.0-r210-pre-RC-merchant-coverage-cumulative.zip.

---

Cronologia precedente:

## Checkpoint corrente — recupero merchant nel ledger originale — 28 ottobre 2026

Leggere **MERCHANT_LEDGER_RECOVERY_R210.md** e `validation/r210/merchant-ledger-result.json`. **28/42 criteri originali verificati (66,7%), E completa (1/7), PRE-RC. Nessun criterio promosso in questo blocco; aumento numerico richiesto non ancora conseguito.** Percorso completo da riga merchant immutabile a ordine locale originale e ledger: discovery canonica della capture, rilettura completa di rimborsi/dispute, conferma amministrativa e binding immutabile atomico. Nessun ordine adottato tramite note del pagatore, nessuna nuova capture o refund sul provider. Rifiutati anche riferimenti tra capture diverse dello stesso ordine.

**368 casi interessati distinti passati, 40 nuovi, zero failure/error/skip correnti; 12 Chromium reali IT/EN 390/1280, di cui 8 nuovi.** Replay/concorrenza/rollback, revoca o cambio di contesto e recupero del checkout pendente durante drain C2 verificati. Timeout privati mantengono obblighi; revisione completa oltre la pagina. Ruff completo, compilazione, sintassi JS e 61 gate sorgenti passano. Bandit 301 sorgenti/164 finding invariati (0 HIGH,21 MEDIUM,143 LOW),170 confini C2,30 siti trasporto,542 sorgenti runtime/782 punti; due handler nuovi revisionati,nessuna soglia/checker/soppressione allentata.

Restano 14 criteri: storico merchant completo,riferimenti locali mancanti,payout/protection con prova univoca e basi originali legacy non sono risolti. A4/A5/C3/C5/D6 e tutti gli altri stati originali rimangono invariati; non dichiarare questo blocco equivalente a quella accettazione. Prossima priorità: copertura/continuità merchant e prove originali dei movimenti;riusare il bridge consegnato.

Baseline confermata **4c3c73afe6d3829aad155c23f5f1bbb6d375433a** e full CI40584085026 conservate; F3 modello/HTTPS ed E4 non interessati non ripetuti. Ripristino cumulativo F3 SHA5ab4eaeb894c739920bed0d334d947beab0154b203ab92f727b029a43ce4d4a2,4635 file verificati. Cumulativo unico:**MTA-0.3.0-r210-pre-RC-merchant-ledger-cumulative.zip**. Delta B5+drain+E4+F3+merchant non committato;nessuna nuova CI GitHub o azione su server/provider reali.

Commit cumulativo inglese suggerito,non eseguito: `Complete guarded execution, administration and merchant-ledger recovery`.

---

Le sezioni seguenti sono cronologia e non prevalgono su questo checkpoint.

## Checkpoint corrente — F3 chiuso — 28 ottobre2026

Leggere **F3_REVIEWED_CHECKPOINT_ACCEPTANCE_R210.md** e `validation/r210/reviewed-checkpoint-acceptance.json`. **28/42 criteri originali verificati(66,7%),E completa(1/7),PRE-RC.** +F3 rispetto a27/42(64,3%);testo/peso originali invariati. Profilo esplicito `verified-pull-v1`:modello/grant/LICENSE/NOTICE/loader/runtime revisionati,controllo indipendente prima dell’inferenza,ricevuta legata a epoch/piano/sorgente/nonce/PID/risultato e credenziale HTTPS originale. Solo BasicPitch0.4.0 ONNX fissato è supportato;altri motori e trasporti generici sono rifiutati nel profilo,anche inNC.Off/compatibilità non certificati,F4/F5/F6 restano aperti. Nessuna attestation hardware/host ostile.

**246 casi distinti passati,55 nuovi,zero failure/error/skip correnti(185 test funzionali e 61 gate).**5 prove del modello reale,incluse4 su worker indipendente HTTPS,in entrambi i regimi,con/senza risposta persa;nota69 e replay originale verificati. Rifiutata anche la perdita del contratto originale senza downgrade legacy. Corretti limite interno16MiB vs minimo pubblico64 e decoder che sondava GCC/FFmpeg sui WAV;limiti pubblici e misura/quiescenza non allentati. Runtime ONNX-only testato;metadata upstream TensorFlow suPy3.12 non soddisfatti:nessuna pretesa di pip-check/packaging opzionale completo. Nessun modello/runtime incluso nella consegna,nessuna dipendenza di produzione cambiata.

Ruff/compilazione/gate passano;300fileapp/164finding revisionati(0HIGH/21MED/143LOW),170confiniC2,30siti/21filetrasporto,541sorgentiruntime/780punti. Checker/soglie/soppressioni invariati. E4/Chromium,fullCI40584085026 e codice non interessato conservati senza riesecuzioni generali. Commit confermato **4c3c73afe6d3829aad155c23f5f1bbb6d375433a**;delta B5+drain+E4+F3 ancora non committato. Nuova CI GitHub cumulativa non dichiarata.

Restano14criteri(9implementazione/diritti,5target).Priorità C3→C5/D6;finanza globale/legacy,payout/protection,diritti/esecutori e target rimangono aperti. Nessuna RC,Git/GitHub/server/provider mutation o commit dell’agente. Cumulativo:**MTA-0.3.0-r210-pre-RC-reviewed-checkpoint-cumulative.zip**.

Commit inglese suggerito,non eseguito: `Complete execution ownership, guarded administration and reviewed remote checkpoints`.

---

Le sezioni seguenti sono cronologia e non prevalgono su questo checkpoint.

## Checkpoint corrente — E4 e macroarea E chiusi — 28 ottobre 2026

Leggere **E4_ADMIN_WORKFLOW_ACCEPTANCE_R210.md** e `validation/r210/sensitive-operator-acceptance.json`. **27/42 criteri originali verificati(64,3%),prima macroarea completa E(1/7),PRE-RC.** +1 criterio E4 rispetto a26/42(61,9%);formulazione e peso originali invariati. Nuovo flusso completo dell’operatore:revisione13 famiglie finanziarie/worker,prove originali e casi legacy oltre pagina,assenza distinta da sconosciuto,conferma con presa visione fresca,diagnosi/completamenti originali sotto drain,riconciliazione reale del ledger via GET provider,entrambi i cambi di regime ammessi,audit,esito incerto/recupero,build e riapertura esplicita. E4 chiuso per il contratto completo valido/bloccato/errore dell’operatore;non per promozione del solo vecchio roundtrip ristretto.

**243 casi interessati distinti passati,zero failure/error/skip correnti;73 nuovi.59 veri casi Chromium e8 scansioni axe del pannello regime completo in impostazioni IT/EN390/1280,zero violazioni/esclusioni.** I12 casi browser prima saltati ora passano:origine ufficiale Google alternativa funzionante,Chrome145.0.7632.6/Playwright1.58.0. Non chiedere o ripetere il solo vecchio opt-in12. Nuovo workflow manuale opzionale **Optional sensitive operator Chromium**,input `sensitive_operator_chromium=true`,gate esatto59pass/0skip,già riuscito localmente. Nessun dispatch GitHub.

Corretti il falso obbligo sulla configurazione email creata dalle impostazioni,la distinzione di claim coerente ma attivo,le diagnosi bloccate sotto C2 e due landmark con lo stesso nome. Query-only/ruoli/CSRF/prove originali restano obbligatori;il digest diagnostico non autorizza scritture.300fileapp/164finding revisionati(0HIGH/21MED/143LOW),170confiniC2,30sititrasporto,541sorgentiruntime/780punti;Ruff,compilazione,sintassiJS e gate sorgenti passano. Checker e soglie invariati.

**C3,C5,D6 restano aperti**:finanza globale/legacy e transizione backend generale non certificate;nessuna abilitazione per deduzione,nessuna RC. C6,B2,F3/F4/F6 e5 target/ambienti restano nei15 criteri residui. E1/E2/E3/E5/E6 già accettati sono conservati e verificati nelle parti interessate;B5/full CI invariati non ripetuti. Baseline committata **4c3c73afe6d3829aad155c23f5f1bbb6d375433a**;full CI40584085026 conservata. Delta B5+drain+E4 non committato,nuova CI cumulativa non ancora confermata. Nessuna mutazione Git/GitHub/server/provider.

Cumulativo completo:**MTA-0.3.0-r210-pre-RC-admin-workflow-cumulative.zip**. Commit inglese suggerito,non eseguito: `Close execution ownership and complete guarded regime-switch administration`.

---

Le sezioni seguenti sono cronologia;percentuali,blocchi browser e stati E4/E superati non prevalgono su questo checkpoint.

## Checkpoint corrente — cutover e drain persistente — 28 ottobre 2026

Leggere **CUTOVER_SERVICE_DRAIN_R210.md** e `validation/r210/cutover-service-drain-result.json`. **26/42 criteri originali verificati (61,9%),0/7 macroaree,PRE-RC;nessuna promozione in questo blocco.** Completato il collegamento del drain C2 con il cutover amministrativo ristretto:journal bloccato attraverso commit/mirror/finalizzazione,anteprima vincolata al drain originale,riapertura negata su riserva/commit incompleti,recupero originale dopo SIGKILL reale e ripetizione esatta del risultato dopo riapertura. Pannello IT/EN con sospensione,rilettura,riapertura e passaggio esplicito al build corrente;nessun POST automatico dopo esito incerto.

**149 test interessati distinti passati,23 nuovi(17 funzionali/6 gate);12 nuovi casi Chromium saltati per browser assente e non accettati.** Workflow opt-in nuovo **Optional service drain cutover Chromium**,input `service_drain_cutover_chromium=true`,solo12 casi nuovi,richiesti12pass/0skip dopo commit dell’utente. Il download locale restituisce HTML e il gate rigoroso produce correttamente `accepted:false`. Non ripetere i9 casi browser già confermati o la full CI invariata. Ruff,compilazione,sintassi JS e gate sorgenti passano;299fileapp/164finding revisionati,170confiniC2,30sititrasporto,540sorgentiruntime/779punti. Nessuna soglia/checker allentata.

C3 resta lavoro finanziario incompleto:storico PayPal globale,payout/protection e prova originale quota/surplus legacy. C5/D6/E4 non vengono promossi dal profilo locale ristretto;C6 cross-host e F3/F4/F6 restano aperti. Questo non è soltanto un blocco CI. Baseline committata **4c3c73afe6d3829aad155c23f5f1bbb6d375433a** e full CI40584085026 conservate. Delta cumulativo include B5 precedente e questo blocco,non committato. Nessun intervento Git/GitHub/server/provider. Cumulativo completo:**MTA-0.3.0-r210-pre-RC-service-drain-cutover-cumulative.zip**.

Commit cumulativo inglese suggerito,non eseguito: `Close execution ownership and bind administrative cutover to durable service drain`.

---

Le sezioni seguenti sono cronologia e restano valide soltanto dove coerenti con questo checkpoint.

## Checkpoint corrente — B5 chiuso — 28 ottobre 2026

Leggere **EXECUTION_ENTRY_ACCEPTANCE_R210.md** e `validation/r210/execution-entry-result.json`. **26/42 criteri originali verificati (61,9%), +1 criterio B5 rispetto a25/42(59,5%);0/7 macroaree,PRE-RC.** Proprietà e metering degli ingressi server/legacy/native censiti sono ora verificati:539 sorgenti runtime vincolati,779 punti classificati(18 tipi di worker incorporati;il conteggio dei punti include handler senza inferenza),271 test interessati distinti passati(unione degli esiti più recenti),59 nuovi,zero fallimenti/errori/skip. Identità account/token ricontrollata dopo FIFO e prima del risultato;CPU su cancellazione conservata;figlio raccolto anche su errore del sensore;incertezza conserva claim/fence/riserva e restituisce409 privato senza riesecuzione o falsa misura.

Baseline committata **4c3c73afe6d3829aad155c23f5f1bbb6d375433a**,full CI40584085026 verde conservata per il codice invariato. Questo delta funzionale è **non committato** e non ha ancora una nuova conferma CI GitHub. Ruff,compilazione,Bandit299file/164finding(0HIGH/21MED/143LOW),trasporto30siti e ammissioneC2 170confini passano;nessun gate/soglia/checker di sicurezza allentato. Nessuna UI Chromium invariata o full CI ripetuta,nessuna mutazione Git/GitHub/server/provider.

B2 e F3/F4/F5/F6 e gli altri criteri originali restano separati:questo non certifica quiescenza kernel esterna,checkpoint/diritti indipendenti,OS installati,modelli o hardware. Restano11 criteri funzionali/diritti e5 target/ambiente. Proseguire **C3+C5+D6+E4**,riutilizzando C2/E5/B5 accettati. I gate globali di transizione finanziaria e RC restano bloccati. Cumulativo completo:**MTA-0.3.0-r210-pre-RC-execution-ownership-cumulative.zip**;nessun commit da parte dell'agente.

---

Le sezioni seguenti sono cronologia:baseline,percentuali,commit suggeriti e attività già chiuse sono superati dove discordano dal checkpoint corrente.

## Checkpoint corrente — full CI confermata — 28 ottobre 2026

Leggere **FULL_CI_CONFIRMED_4C3C73A_R210.md** e `validation/r210/ci-4c3c73a-observation.json`. Baseline committata **4c3c73afe6d3829aad155c23f5f1bbb6d375433a**; full run [40584085026](https://github.com/desalvo/mta-audio-editor/actions/runs/40584085026): **6887 passati,114 skip,76,88% coverage,14 job riusciti,zero fallimenti,un job di pubblicazione su tag saltato**. SAST,SDK,gate container e build native/mobile verdi; pubblicazioni Docker Hub e rolling early-main riuscite. iOS è un archivio non firmato: IPA/TestFlight non provati.

La regressione della fixture Stripe è chiusa anche in GitHub: non riapplicare la patch e non ripetere i test invariati. Tutto il precedente delta funzionale e la correzione della fixture sono committati. Questo checkpoint aggiunge solo documentazione/prove/manifest. Riprendere C3+C5+D6+E4 riutilizzando C2/E5 accettati e proseguire gli altri filoni indipendenti. **25/42(59,5%),0/7 macroaree,PRE-RC;nessuna promozione da test/build e nessuna autorizzazione alla transizione finanziaria globale.** Restano12 criteri funzionali/diritti e5 target/ambiente. Nessun test o mutazione Git/GitHub/server/provider effettuato in questo aggiornamento.

Cumulativo completo: **MTA-0.3.0-r210-pre-RC-full-ci-confirmed-cumulative.zip**. Non serve rilanciare full CI per riconfermare questa riparazione.

---

Le sezioni sottostanti conservano la cronologia. Baseline, commit suggeriti, richieste di CI e conferme pendenti precedenti sono superati quando in conflitto con il checkpoint corrente.

## Current continuation — CI Stripe refund fixture repair — 2026-10-27

Read **CI_STRIPE_REFUND_FIX_5891082.md** first. User confirmed commit5891082820d3d69bd8bd3ea0be06117d5639c135;run40550957081 has60 Quality failures from the shared stale Stripe refund fixture,6818passes/114skips and76.78%coverage;SAST/SDK pass. Fixture now supplies canonical payment/test environment,intent/capture/charge history and exact paginated queries. **299 production Python sources unchanged;no financial guard/threshold/workflow/scanner relaxation.**

**156 distinct latest affected cases pass,including all60 CI failures,14 actual Chromium and9 new negative environment cases;0 unresolved failures/errors/skips.** Current proof:validation/r210/ci-5891082-result.json. Existing production source-bound security/transport/admission and unchanged CI proof reused;no full-suite rerun. The GitHub run remains failed until the user's next commit confirms the repair;no remote rerun or write performed.

Complete cumulative **MTA-0.3.0-r210-pre-RC-ci-stripe-refund-fixture-cumulative.zip** retains every earlier path/assets/licenses/logs/mode. Isolated test-only patch included:CI_STRIPE_REFUND_FIX_5891082.patch. Only tests/test_r210_operator_refunds.py changes executable behavior. **25/42(59.5%),0/7;PRE-RC;no criterion promoted.** Accepted C2/E5 remain;next functional work remains original financial/integrated cutover/rights/target exits. Next suggested commit covers only this fixture repair after5891082,not the already committed Stripe/C2/E5/legacy/export work. No commit/staging/GitHub/provider/real-server mutation.

## Current accepted milestone — C2 service admission and drain — 2026-10-27

Read **SERVICE_ADMISSION_DRAIN_R210.md** first. Original C2 “Distributed admission barrier and service-wide drain” is now verified for the accepted B4 supported deployment:one pinned local Linux authority with multiple current-build API/timer processes and independent authenticated HTTPS workers. Full ASGI lifetimes,finite/helper threads,long capture/VST3 sessions,actual periodic/CLI cycles and original pending journals are covered. Preaccepted TLS/local workers complete once under the held barrier;new work is refused. Unknown/lost work never expires into quiescence. Actual source-build handoff fences old replicas;backup/restore preserves original journal/instance and uncertain admissions with exact bundled immutable schema validation.

**25/42 original criteria(59.5%),up from24/42(57.1%);0/7whole macroareas;PRE-RC.** Only C2 promoted;original wording,weights and42 denominator unchanged. C3/C5/C6,D6,E4,kernel/rights/financial/external target exits remain open. No general financial transition is authorized;global switching/readiness flags remain false and authority-v1 is default-off. This is neither HA/NFS nor actual cross-host/kernel/hardware acceptance.

**321 distinct latest affected passes,71 new C2 cases;0 unresolved failures/errors/skips.** Final161 integration cases and37 security/transport cases pass;unchanged default-off boundaries reuse the earlier197-case run. Exact case/report/source provenance:validation/r210/service-admission-result.json. Source-bound inventory reviews170 explicit boundaries/all299app sources;Bandit164reviewed existing findings(0HIGH/21MEDIUM/143LOW),transport30sites/21files,unchanged checkers and no new scanner suppression. Actual TLS response loss,local registered worker/heartbeat/publication/single charge,PCM import,process SIGKILL,real changed-source build upgrade and original-journal backup/restore included. Controlled VST3 Session child tests certify lifetime accounting,not plugin/hardware behavior.

Complete cumulative **MTA-0.3.0-r210-pre-RC-service-admission-cumulative.zip** retains all uncommitted Stripe,E5,legacy and export SQLite recovery work after last confirmed772fbe7508cc08266466a3746bb51f0fe5d0179b. The earlier inactive C2 patch is now integrated and superseded;do not reapply it. Reuse accepted E5 Chromium/Stripe/unaffected native/full-CI evidence. No GitHub/real-server/provider/Git mutation or unchanged full CI rerun. User commit remains deferred. Next integrated work is C3+C5+D6+E4 with original financial/executor recovery dependencies;do not rebuild C2 or weaken unknown-work proof.

## Current continuation — export SQLite exclusive-read recovery — 2026-10-27

Read **EXPORT_SQLITE_EXCLUSIVE_RECOVERY_R210.md** first. Complete cumulative **MTA-0.3.0-r210-pre-RC-export-sqlite-recovery-cumulative.zip** includes all preceding uncommitted Stripe,E5 and legacy work after confirmed772fbe7508cc08266466a3746bb51f0fe5d0179b. The newly reported trace fails on barrier/auth schema reads under reader-blocking SQLite contention. Caller-connection reuse,private typed503,bounded GET-only retries and original-job/export-download resumption replace the unhandled500. Fresh authentication,session revocation,original ownership and cutover guards remain enforced;mutations/general completion callbacks are never replayed. Static asset version updated. Exact production writer is unknown from redacted diagnostics;permanent locks remain an operator diagnosis.

**143 distinct affected cases pass,22 new;0 unresolved failures/errors/skips.** Actual FFmpeg/ffprobe verifies project/track MP3/WAV/FLAC under reserved/exclusive contention. Shipped JS API/poll/download functions execute in Node;no new Chromium acceptance is claimed. Bandit296sources/164explicitly reviewed findings(0HIGH/21MEDIUM/143LOW);transport30sites/21files;checkers/activation flags unchanged. Source/report/case provenance:validation/r210/export-exclusive-result.json. Unchanged Stripe,accepted E5 browser and legacy proof reused;no full CI rerun or real-server/provider/GitHub/Git mutation.

**24/42(57.1%),0/7whole macroareas;PRE-RC.** No criterion promoted by this bug fix. The unfinished C2 implementation is preserved as an **inactive development patch**,not applied to application source:development-pending/README.md and C2_SERVICE_ADMISSION_WIP.patch. Its preliminary tests are not current acceptance;whole-source build/upgrade,lifetime/entry inventory and final proof remain incomplete. Continue from this exact checkpoint after the hotfix;do not lose or silently enable it. Install/restart/reload instructions and persistent-lock limits are in the new handoff. No deployment has occurred.

> Chromium follow-up: manual workflow **Optional merchant history Chromium**, input **merchant_history_chromium=true**;requires4 real passes/zero skips. See current handoff for exact dispatch/artifact procedure. No GitHub write or CI run was performed here.

## Current checkpoint — merchant-wide observations — 2026-10-25

Read **MERCHANT_HISTORY_HANDOFF_R210.md** first. New: bounded two-pass authenticated PayPal account-history acquisition,private immutable snapshots/admin API and IT/EN consultation panel. **70 current passes,32 new,4 actual Chromium cases blocked by missing engine.** Merchant observations never settle money or certify full history. A4/A5 legacy/partial/actual movement binding remain open. **23/42(54.8%),0/7 whole macroareas;RC false;switching disabled.** Current evidence: `validation/r210/merchant-history-test-summary.json`.

## Current checkpoint — 2026-10-25 — original subscription loss

Read **ORIGINAL_SUBSCRIPTION_LOSS_HANDOFF_R210.md** and the revised **RC_CLOSURE_PLAN_R210.md** first. New closure: immutable original fee/surplus basis, authenticated full-capture reversal to exact owner repayment, no duplicate refund principal, conservative legacy/partial/protection gaps. Current tests: `validation/r210/original-loss-test-summary.json`. **23/42(54.8%),0/7 whole macroareas;RC false;switching disabled.** Previous validated execution/publication work is retained.

## Current continuation — 2026-10-25

Read **TWENTY_CYCLE_RECOVERY_HANDOFF_R210.md** first. New closure: original-owner frozen Arranger/Remix publication after verified parent death, real WAV publication metadata, crash/ACK/concurrency recovery and administrator API. Only newly admitted immutable publication intents qualify. Prior statements that all successful frozen deferred output is unrecoverable are superseded for this exact scope; legacy/unknown work remains held. **23/42 (54.8%),0/7 whole macroareas; RC false, transition disabled.** Current evidence: `validation/r210/twenty-cycle-test-summary.json`.

## Current checkpoint — ten-cycle authoritative pull coordination — 2026-10-24 — PRE-RC

Read **PULL_COORDINATION_HANDOFF_R210.md**, **PULL_COORDINATION_IT_EN_R210.md** and **TEN_CYCLE_BATCH_R210.json**. Ten substantial internal cycles completed without intermediate packages or commits. The actual registered/token and deferred Arranger/Remix paths now use one pinned shared HTTPS authority for admission, owner/epoch, private input/result storage, frozen completion and original-client recovery. Node credentials are scoped; stale/revoked/uncertain workers cannot obtain takeover. Pause/drain/planned recovery, actual erasure, free-only no-charge and namespace-correct process identity/telemetry are integrated.

**B4 locally verified;23/42 (54.8%),0/7 whole macroareas;RC false,switching disabled.** This is a supported single-authority Linux backend, not multi-leader/HA or actual multi-host/kernel certification. **898 distinct affected cases passed,90 new,zero unresolved failures/errors/skips.** Real independent HTTPS worker processes, authority/worker SIGKILL, dropped replies, exact one-execution counters, original request replay and final account erasure are included. Source-bound review284 app files/168 unchanged unsuppressed findings(0 HIGH/21 MEDIUM/147 LOW);transport30 sites/21 files;checkers unchanged. Full Ruff/compileall passed. Historical unrelated Linux/native/coverage/dependency/E6 browser/axe evidence reused. B2/B5/B6,whole-service C2,global/legacy finance,executing-checkpoint rights,enabled cutover and target acceptance remain open. No GitHub/real-server/payment/model/SMTP changes or commit/push/tag/release. Exact case provenance:validation/r210/ten-cycle-test-summary.json.

## Historical checkpoint records (superseded for current progress)

## Current checkpoint — worker ownership and epoch integrity — 2026-10-24 — PRE-RC

Read **WORKER_EPOCH_HANDOFF_R210.md** and **WORKER_EPOCH_IT_EN_R210.md**. After environment recovery, the verified administration cumulative was restored; the interrupted unsaved pull prototype was lost and is not delivered or counted. Shared receipt checks now reject stale or inconsistent worker ownership across claim retry, heartbeat, release, actual billing, deferred publication and recovery. Exact closed historical acknowledgements remain idempotent after later epochs; read-only audit uses one snapshot and flags current epoch/barrier corruption.

**350 distinct affected cases passed, including 49 new; zero current failures/errors/skips.** Actual child death after accounting commit recovers without a second settlement; original uncertain worker holds and quiescence requirements remain enforced. Source-bound static review:279 app files,168 unchanged unsuppressed findings,0 HIGH/21 MEDIUM/147 LOW;transport29 sites/20 files;checkers unchanged. Full Ruff/compileall passed. Historical unrelated Linux/native/coverage/dependency/admin browser/axe evidence reused. **22/42 (52.4%),0/7 complete macroareas;RC false,switching disabled.** Shared coordinator/storage,all-executor quiescence,global/legacy finance,remote executing-checkpoint rights and enabled cutover still require implementation/acceptance. No GitHub/real-server/payment/model/SMTP changes or commit/push/tag/release. Per-case evidence:validation/r210/worker-epoch-test-summary.json.

## Historical checkpoint records (superseded for current progress)

## Current checkpoint — complete current web administration acceptance — 2026-10-24 — PRE-RC

Read **ADMIN_ACCEPTANCE_HANDOFF_R210.md**, **ADMIN_ACCEPTANCE_IT_EN_R210.md** and the restructured **RC_CLOSURE_PLAN_R210.md**. All nine settings tabs, Billing, Tokens, optional catalogue and the job monitor now pass actual local API/SQLite/Chromium acceptance in IT/EN, commercial/NC, 390/1280 px and light/dark themes. Repaired duplicate retention forms, unnamed fields, tab/focus semantics, contrast/reflow and read-error recovery; real retention/quota/permission/token workflows read back their actual effects.

**330 distinct affected cases passed, including 136 actual Chromium;44 new browser cases.328 administration axe reports have zero violations/unresolved supplemental items;no rule exclusions.** Exact latest-case/report provenance: validation/r210/admin-test-summary.json. Source-bound security:279 app Python files,168 reviewed unsuppressed findings(0 HIGH/21 MEDIUM/147 LOW);transport inventory29 sites/20 files,checkers unchanged. Historical unrelated full Linux/C++/coverage/dependency evidence reused. **E6 locally verified:22/42 (52.4%),0/7 whole macroareas;RC false,switching disabled.** Complete enabled-cutover E4/E5,D6,shared coordination/all-executor quiescence,global/legacy financial obligations,payout proof and remote rights/target acceptance remain open. Current web acceptance is not OS-native/manual-assistive-technology/whole-product certification. No GitHub/real-server/actual payment/inference/SMTP changes or commit/push/tag/release.

## Previous checkpoint records (historical)

## Current checkpoint — exact PayPal item allocation and private movement review — 2026-10-24 — PRE-RC

Read **PAYPAL_ITEM_MOVEMENT_HANDOFF_R210.md** and **PAYPAL_ITEM_MOVEMENT_IT_EN_R210.md**. Authenticated canonical item amounts now support exact partial multicapture disputes through atomic ledger settlement and actual IT/EN owner pages. Missing/ambiguous item evidence stays blocked; quantity never multiplies the monetary proof. The administrator has a bounded private movement-observation table with exact decimal display, keyboard scrolling, error recovery and no settlement action. Payout/protection completion still lacks authoritative unique case/capture/completed-transaction binding; these observations never release funds or pass processor fees to users.

**392 distinct affected cases passed, including 30 actual Chromium; 66 new cases (54 domain/12 browser), zero current failures/errors/skips.** Source review: 279 app files, 168 unsuppressed reviewed findings, 0 HIGH/21 MEDIUM/147 LOW; transport inventory 29 sites/20 files, checker unchanged. Prior Linux/C++/coverage/dependency/D4 accessibility evidence reused without rerun. **Formal progress remains 21/42 (50.0%), 0/7 whole macroareas; RC false and switching disabled.** A4/A5 global/ambiguous history, payout settlement, legacy obligations and original permanent fee loss remain open, along with shared coordination, remote attestation, enabled cutover and target acceptance. No actual merchant/real-server/GitHub changes or commit/push/tag/release. Exact evidence: validation/r210/paypal-item-movement-test-summary.json.

## Previous checkpoint records (historical)

## Current checkpoint — PayPal known-order dispute history — 2026-10-24 — PRE-RC

Read **PAYPAL_DISPUTE_HISTORY_HANDOFF_R210.md** and **PAYPAL_DISPUTE_HISTORY_IT_EN_R210.md**. Existing owner/admin GET-only verification now discovers paginated canonical disputes for every capture of the selected known PayPal order, applies exact supported holds/releases with funding/refunds atomically, and exposes private held amounts and unresolved status. Full-gross multicapture allocations are exact; partial/foreign/payout/protection ambiguities remain blocked. Durable history gaps retain previously observed dispute IDs, prevent ordinary unpaid fulfillment bypass and close only with verified complete settlement. No financial provider mutation is available through verification.

**428 distinct affected cases passed, including 47 actual Chromium; 93 new cases (77 domain/16 browser), zero current failures/errors/skips.** Current source-bound review: 278 app Python files, 168 unsuppressed reviewed findings, 0 HIGH/21 MEDIUM/147 LOW; transport inventory 29 sites/20 files. Prior full Linux/C++/coverage/dependency and D4 accessibility evidence reused without rerun. **Formal progress remains 21/42 (50.0%), 0/7 whole macroareas; RC false and switching disabled.** A4/A5 global history, actual payout/protection movements, partial multicapture allocations and legacy/original fee-loss obligations remain implementation pending. Shared coordination, remote rights, enabled cutover and full target acceptance remain open. No GitHub/real-server/actual payment changes or commit/push/tag/release. Exact evidence: validation/r210/paypal-discovery-test-summary.json.

## Previous checkpoint records (historical)

## Current checkpoint — complete local owner Account workflow — 2026-10-24 — PRE-RC

Start with **ACCOUNT_WORKFLOW_HANDOFF_R210.md** and **ACCOUNT_WORKFLOW_IT_EN_R210.md**. The actual Account and Credits pages now complete the local two-regime owner workflow: commercial plan/trial/renewal/cancellation/overage/storage/report controls, authenticated funding and existing-payment recovery, private repayment/refund histories, NC voluntary statements/reports/reviewed receipts and CSV. Locale changes and simultaneous refreshes cannot repeat in-flight mutations or replace newer results; verified payment notices survive the fresh readback. Owner tables have named keyboard scrolling, visible focus, truthful empty/error states and tested contrast.

**315 distinct affected cases have current passing evidence, including 160 Chromium cases; 104 new cases include 94 Chromium. No current failures/errors/skips.** Sixteen axe owner-page combinations passed WCAG2/2.1 A/AA automated checks with zero violations and zero unresolved supplemental contrast items; no whole-product/native accessibility certification is claimed. Provider I/O is simulated. Historical full Linux/C++/coverage/dependency evidence is preserved without rerun. Current source-bound security: 277 app Python files, 168 reviewed unsuppressed findings, 0 HIGH/21 MEDIUM/147 LOW; transport inventory 29 sites /20 files. **D4 locally verified: 21/42 milestones (50.0%),0/7 whole macroareas; RC false and switching disabled.** A4/A5,F3,I1/I4,D6,whole administration/native/target acceptance remain open. No actual merchant, GitHub or real-server mutation; no commit/push/tag/release. Exact per-case provenance and corrected earlier runs: validation/r210/account-workflow-test-summary.json.

## Historical checkpoint records (superseded for current progress)

**Current continuation: OPERATOR_REFUNDS_HANDOFF_R210.md. Preserve the historical evidence below; RC false and switching disabled.**

**Current continuation: REMOTE_RIGHTS_HANDOFF_R210.md. Older checkpoints below remain historical; RC false and switching disabled.**

**Current continuation: FINANCIAL_OUTCOME_HANDOFF_R210.md. Older checkpoints below are historical; RC false and switching disabled.**

**Current continuation: OWNER_PAYMENT_RECOVERY_HANDOFF_R210.md supersedes the historical checkpoints below. Formal acceptance remains 20/42, 0/7 complete macroareas; RC false and switching disabled.**

**Superseded for current progress and repayment code by SUBSCRIPTION_RECOVERY_HANDOFF_R210.md. The 18/42 figures below are the previous checkpoint.**

# MTA 0.3.0-r210 — continuation handoff, 2026-10-23

**PRE-RC.** This is the latest continuation of the ledger-workers checkpoint. Version, release channel and disabled administrative switching are unchanged. No GitHub writes, real servers, real payments or production credentials were used. No commit, tag or release was made. The acceptance checklist is now **18/42 locally verified milestones (42.9%), 0/7 complete macroareas**. This does not estimate whole-product completion.

## Resume provenance and validation reuse

Started from the already-present cumulative workspace corresponding to `MTA-0.3.0-r210-pre-RC-ledger-workers-cumulative.zip`, SHA-256 `6341ed9b86a45235177df9347d06e7508b4580f61ebb2d1c76d0af7462f0fbec`. The original archive remains `MTA-r210-provider-authenticated-journal-handoff-cumulative.zip`, SHA-256 `603c5a5e650178b912605d4203154ea310b2f387e35c9c4c9e719ee30c1d1817`. Exact baseline preservation is recorded in `validation/r210/work-git-comparison.json` and the source manifest.

The preceding full Linux result (5,228 passed, 73 skipped; 73.67749% combined coverage), C++ result and dependency audit were reused. They are not new final-code global results. New regression scopes and their overlap are explicit in TEST_MATRIX_R210.md. Do not rerun the full baseline unless further changes or failures justify it. Old logs are retained as historical evidence.

## Deferred execution ownership — B3 locally closed

`app/deferred_execution_owner.py` connects the durable scheduler to the authoritative billing claim. Before running authenticated, billed Arranger/Remix work it verifies the local scheduler PID/process identity, claims the existing stable ledger with a fresh secret token and starts a heartbeat. It never invents a ledger for legacy unbilled work. An old claim cannot be adopted to execute again.

The registered worker reuses those original credentials. Trusted metering persists a private owner receipt with immutable evidence. Publication stores it in a separate private `owner_json` column, outside user metadata. Billing freezes it in the intent and authenticates final ledger/claim/fence settlement with the same owner. Public stage/status/inspection responses and publication callbacks omit tokens. Existing ownerless legacy records remain supported; stripping an owner from a claimed job is rejected.

Recovery may deliver previously staged bytes and persisted final measurement outside the execution ContextVar. It validates the original claim/epoch/ledger binding and never calls inference. Repeated delivery after ledger commit but before acknowledgement is idempotent, including concurrent retries. Heartbeat failure sets cancellation, prevents new evidence/staging and leaves uncertain running claims durable. It does not assert that an external process has stopped.

Affected modules: `ai_arranger_runtime`, `ai_metering_agent`, `ai_metering_bridge`, `ai_publish_outbox`, `ai_billing_outbox`. Publication/billing databases remain a recovery-safe saga, not a distributed ACID transaction. This closes receipt propagation only. Real supervisor loss with independent worker quiescence, all legacy entrypoints and a shared multi-host coordinator are still unaccepted (B2/B4/B5/B6).

Evidence: final 23-case owner/publication regression (`continuation-deferred-final.log`, including both adapters); 76-case scheduler/recovery regression (`continuation-deferred-regression.log`). New tests include missing/forged/changed/removed receipts, heartbeat loss, publication crash boundaries and ledger-commit-before-ack retry. New crash-boundary tests simulate process interruption; they do not certify actual supervisor/worker loss.

## PayPal canonical refund history — partial A4 progress

The administrator reconciliation service now reads the order, each capture and each referenced refund through fixed authenticated GET endpoints. `app/paypal_reconciliation.py` verifies IDs, amounts, EUR currency, refund-to-capture links, optional related order identity, capture/refund statuses and cumulative refund totals. It rereads the order after discovery and rejects any changed document. Bounds are 100 captures and 1,000 refunds; overflow fails closed. Pending/unknown refunds, omitted refunded captures, repeated objects, cumulative mismatch and unsupported statuses block settlement.

Fulfillment rechecks immutable local order fields and the complete decrypted provider configuration under `BEGIN IMMEDIATE`. Known local refunds must be present in the snapshot. It journals discovered refunds, funds the capture and replays refunds in that same transaction. A gross wallet balance is never committed between those steps. An already-paid or duplicate capture still processes newly discovered refunds. Failed processing rolls back captures, credit, journal and refunds together. Subscription refunds create exact receivables without adding wallet credit. Amount parsing now accepts only exact, nonnegative EUR decimal strings with up to two fractional digits, converted using integers.

Initial `REFUNDED` and `PARTIALLY_REFUNDED` captures are supported only by this authenticated history path. Ordinary fulfillment rejects embedded refund history rather than silently granting gross credit. The operator can retry after a blocked/changed snapshot; no blind provider capture/refund action is performed.

Evidence: `test_r210_paypal_history_reconciliation.py`, existing PayPal and Stripe/checkout/browser regressions, 108 passed in `continuation-financial-regression.log`. Provider responses are fixtures; this is not sandbox certification. Canonical order refund references plus cumulative totals detect missing predecessor refunds, but do not certify provider-wide historical dispute/protection/payout completeness or absence of later changes. Missing optional cumulative data intentionally blocks this path until a complete observation is available. A4 remains implementation_pending.

Primary API references used for request/field contracts:

- https://developer.paypal.com/api/orders/v2/definitions/purchase_unit — purchase-unit captures/refunds collection and statuses.
- https://developer.paypal.com/api/payments/v2/captures-refund — canonical refund response, capture `up` link and `seller_payable_breakdown.total_refunded_amount`.

## Next concrete work, without redoing this checkpoint

1. Implement the shared coordinator and cross-host storage/fencing semantics (I1); independently prove external worker quiescence on supervisor death (B2). Do not release claims merely because a heartbeat or queue runner disappeared.
2. Finish PayPal dispute/protection/payout historical discovery, multi-capture allocation, legacy liabilities and definitive terminal/uncertain checkout handling (I5). Complete exact subscription reversal repayment; recording a receivable is not collection.
3. Bind authenticated remote checkpoint identity and reviewed rights to admission, then cover remaining legacy executor bypasses (I3). Commercial remote execution remains blocked in the meantime.
4. Complete financial migration, distributed admission/drain and the operator workflow before enabling administrative switching in either direction (I4). Keep current safe-switch gate disabled.
5. Complete NC voluntary contribution collection and full account/operator UX (I6/I7). Immutable allocation exports remain statements, not proof of collected contributions.
6. Review the retained Bandit baseline (I8), then perform actual configured sandbox lifecycle and target platform/container/GPU/audio/VST acceptance when those environments are available.

External limitations are listed separately in KNOWN_BLOCKERS_R210.md. They do not excuse the unfinished code above. The unchanged RC gate remains BLOCKED. No background continuation is scheduled; resume from this handoff and DEVELOPMENT_COMPONENTS_R210.json.
