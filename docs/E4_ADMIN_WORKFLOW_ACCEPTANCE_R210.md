# MTA 0.3.0-r210 — E4: flusso amministrativo completo

**28 ottobre 2026, Europe/Rome. PRE-RC. E4 verificato:27/42 criteri originali,64,3%,prima macroarea completa E(1/7).** Prima:26/42,61,9%,0/7. La formulazione originale **“Complete sensitive regime-switch operator workflow”**,il suo peso1 e gli altri41 criteri sono invariati. La transizione finanziaria generale C3/C5/D6 non è dichiarata pronta e la RC non è raggiunta.

Il cumulativo riprende `MTA-0.3.0-r210-pre-RC-service-drain-cutover-cumulative.zip`,SHA256 `635cf713aaf3fc149b5cc180b3ac51babd1e5736a0d8f66155122f8786c97d50`,98.085.856 byte,4580 file. Il workspace era tornato al vecchio23/42:è stato ripristinato il cumulativo giusto verificando SHA,CRC,manifest e modalità,senza ripetere le analisi già accettate. Baseline committata confermata dall’utente **4c3c73afe6d3829aad155c23f5f1bbb6d375433a**; B5,drain e questo blocco sono nello stesso delta non committato. Nessun commit,staging,push,dispatch,tag,release o intervento GitHub/server/provider da parte dell’agente.

## Comportamento implementato

Il flusso delle impostazioni consegnate mostra ora la revisione prima della conferma:13 famiglie indipendenti di pagamenti,contestazioni e recuperi;checkout incerti;eventi autenticati;osservazioni finanziarie;quota/surplus originali; rimborsi;proprietà worker;esecuzioni assegnate;quiescenza;perdite del gestore;contributi NC;schemi;storico provider. Ogni famiglia distingue verificato,in attesa,non verificabile e non utilizzato con prova di assenza. I totali comprendono tutte le registrazioni;la paginazione riguarda soltanto la visualizzazione dei casi.125 sottoscrizioni legacy senza prova sono tutte rilevate anche leggendo soltanto l’ultimo caso. Importi monetari esposti come stringhe intere e resi con BigInt,senza arrotondamento numerico JavaScript.

`GET /api/admin/service-regime/cutovers/preflight` richiede un amministratore attivo e restituisce una risposta non memorizzabile. Le famiglie vengono lette indipendentemente in una transazione `query_only`;un errore non diventa zero e non cancella le altre diagnosi. Credenziali,eccezioni private e payload provider non vengono restituiti. I journal opzionali sono “non utilizzati” soltanto quando assenti e quando gli originali libri finanziari e tipi di fence dimostrano assenza di attività. Un journal parziale,presente o con registrazioni orfane non riceve questa classificazione. Il digest diagnostico non è un permesso di scrittura: una richiesta che lo usa al posto dell’anteprima viene rifiutata.

Prima di confermare l’operatore deve leggere la revisione e selezionare la presa visione,inizialmente deselezionata. Segue la conferma esplicita di destinazione/revisione. Cambiare destinazione,riaprire o rinnovare il drain,oppure ricevere una lettura indisponibile invalida la presa visione precedente. Nessun POST viene ripetuto automaticamente. Il server continua a ricomputare la propria anteprima e conservare saldi/periodi attraverso la ricevuta originale;il client non può dichiarare pronta la finanza.

Il flusso comprende sospensione delle ammissioni,attesa delle attività originali,verifica,cambio nelle due direzioni,audit,annullamento precommit,recupero in avanti del commit già registrato,risposta persa/rilettura della stessa identità,passaggio esplicito al build e riapertura esplicita. Restano disponibili durante C2 le sole diagnosi private e i controlli precisamente elencati di riconciliazione del checkout originale,verifica riferimento e recupero worker originale. Autenticazione,CSRF e prove originali rimangono obbligatori. Non esiste un’esenzione per tutto il prefisso admin;nuovi checkout,dispatch di rimborso,letture merchant via POST e creazione di periodi restano bloccati durante il drain.

La prova finanziaria completa nel browser attraversa l’API e il servizio reali:un checkout originale aperto viene riconciliato con GET provider autenticati;5EUR pagati e2EUR rimborsati producono3EUR netti sul wallet originale e chiudono la relativa attività. Il drain diventa verificato,ma lo storico provider generale continua correttamente a impedire la transizione. Il trasporto del provider è simulato;non sono stati mossi fondi o contattati conti reali.

## Difetti riprodotti e corretti

- Il precedente opt-in da12 casi non era stato eseguibile localmente. Chromium reale ha riprodotto6 fallimenti:aprire le impostazioni crea `ai_mail_config`,erroneamente classificato come obbligazione economica. La configurazione neutra è ora distinta dalle attività/invii e dallo storico worker,che mantengono i propri controlli. Nessuna riga finanziaria è stata ignorata.
- Un claim worker coerente ma ancora in esecuzione deve apparire pendente:il report combina integrità e conteggio dei claim attivi.
- Il pannello finanziario non poteva essere aggiornato sotto C2. Le letture private e i completamenti originali elencati ora attraversano il controllo;CSRF mancante viene ancora rifiutato prima di qualsiasi GET provider.
- L’analisi axe dell’intero pannello di regime rilevava due regioni diagnostiche con lo stesso nome. Ora hanno nomi IT/EN distinti. Nessuna regola è stata esclusa.

Gli XML iniziali conservano questi esiti. Altri tentativi iniziali contenevano errori della fixture(tipo header sovrascritto dal middleware,proxy di test,riassegnazione del medesimo contratto nello stesso secondo) o della raccolta test;sono stati corretti nei test,senza rilassare le protezioni del prodotto. Non sommare gli esiti ripetuti.

## Accettazione e distinzione dai criteri backend

E4 è chiuso per il **contratto completo dell’operatore**,con nuove funzioni e prova su tutte le fasi e gli stati osservabili:revisione finanziaria completa per famiglie,casi legacy,assenze e prove mancanti,conferma consapevole,controlli del drain,autorizzazione,riconciliazione,errore,risposta persa e recupero. Non è una promozione del solo precedente roundtrip del profilo ristretto. I casi bloccati fanno parte dell’accettazione:il flusso deve mantenerli bloccati e spiegare il lavoro residuo,senza offrire cancellazioni dello storico o finte quietanze.

L’anteprima eseguibile rimane quella del **profilo locale ristretto** verificato dal server. Configurazione/storico provider e obblighi non coperti impediscono il cambio;la revisione indica sempre che la finanza generale non è certificata. Non è stata implementata o abilitata per deduzione la transizione finanziaria generale. C3,C5,D6 restano `implementation_pending`,così come gli altri criteri originali aperti. Il requisito UI/operatorio E4 è distinto da questi requisiti backend:le prove coprono sia il percorso eseguibile sia la gestione corretta delle sue condizioni di rifiuto.

La macroarea E ora ha tutti i propri criteri verificati:

| Criterio originale | Prova di accettazione |
| --- | --- |
| E1 Financial positions use actual database API in Chromium IT/EN | Prove precedenti conservate;letture reali private anche nel flusso attuale |
| E2 Diagnostics remain readable during a reserved drain | Prove precedenti conservate;estensione verificata al drain C2 con route esatte |
| E3 Explicit confirmed reconciliation button traverses API/service and changes actual wallet in browser tests | Prove precedenti conservate;4 nuovi casi su pagina completa,durante C2,con CSRF e wallet originale |
| E4 Complete sensitive regime-switch operator workflow | Nuova revisione13 famiglie,presa visione,flusso completo e gate Chromium59/59 |
| E5 Complete transition progress,audit and forward recovery controls | Accettazione precedente conservata;regressioni backend e browser sulle parti interessate |
| E6 Full accessibility and responsive acceptance for the entire administration | Accettazione precedente conservata;8 nuove scansioni axe dell’intero pannello di regime,IT/EN390/1280,zero violazioni/esclusioni |

Questa è accettazione software dell’amministrazione nel browser supportato,non certificazione di OS nativi,modelli,hardware,diritti indipendenti o tecnologie assistive manuali. Questi requisiti conservano i propri criteri separati.

## Prove attuali e loro riuso

`validation/r210/sensitive-operator-acceptance.json` contiene l’unione esatta dei risultati più recenti: **243 casi distinti passati,zero fallimenti/errori/skip correnti**.73 casi nuovi(29 backend,38 browser,6 gate). I12 casi browser prima saltati sono ora passati realmente e non costituiscono più un prerequisito mancante.

- `operator-backend-final.xml`:123 passati,compresi API/privatezza/CSRF,verifica read-only,casi oltre pagina,journal parziali,digest non autorizzante e regressioni cutover/C2/lifecycle.
- `sensitive-operator-browser-final/pytest.xml`:59 passati,zero skip;`acceptance.json` accettato dal gate rigoroso. Include9 casi precedenti aggiornati perché la conferma è cambiata,12 drain finalmente eseguiti,34 revisione/errori/accessibilità e4 riconciliazione finanziaria sotto drain.
- `operator-source-gates-final.xml`:61 passati. Ruff app/native/tests/scripts,compilazione app/scripts e sintassi dei3 JavaScript cambiati passano.

Browser reale **Chrome for Testing145.0.7632.6**,Playwright1.58.0,axe-core4.14.0 test-only verificato con SHA512 della distribuzione ufficiale. Il vecchio CDN restituiva HTML;il download dall’origine ufficiale Google funziona. Hash/versioni in `sensitive-operator-runtime-provenance.json`. Otto scansioni axe,nessuna esclusione;nessun modello reale scaricato o eseguito. Browser/tool temporanei non sono inclusi nel prodotto.

Bandit1.9.4:300 sorgenti app,164 finding revisionati invariati(0HIGH/21MEDIUM/143LOW),nessuna soppressione.170 confini C2;trasporto30 siti/21 file;541 sorgenti runtime/780 punti classificati. Un endpoint diagnostico non inferenziale è stato aggiunto e revisionato;nessuna nuova inferenza o deroga ai diritti. Checker/soglie/configurazioni di sicurezza invariati;le nuove continuazioni del prodotto sono descritte e provate esplicitamente.

Scansione Gitleaks8.24.3 delle nuove righe:zero segreti rilevati,configurazione invariata.

B5 invariato(271 casi precedenti),vecchia accettazione E5 e full CI40584085026 verde su4c3 sono conservati senza riesecuzione generale. La nuova revisione della conferma giustifica la regressione browser interessata;non è stata ripetuta la full suite da6887 casi o la copertura globale. Il codice cumulativo non ha ancora una nuova conferma CI GitHub.

## Ripresa,consegna e commit differito

Restano **15 criteri originali**:10 di implementazione/diritti(A4,A5,B2,C3,C5,C6,D6,F3,F4,F6) e5 target/ambiente(A6,B6,F5,G5,G6). Priorità C3:storico globale PayPal e attribuzione payout/protection,obblighi legacy e prova originale quota/surplus;una finestra richiesta o un prezzo corrente non costituiscono quella prova. Quindi C5+D6 sulla transizione finanziaria generale,riutilizzando C2 ed E ora completati. C6 richiede ancora prove tra host;F3/F4/F6 richiedono protocollo/copertura/revisione diritti;gli ambienti fisici non vengono simulati come accettati. Non riclassificare questo lavoro di codice come semplice attesa della CI.

Il nuovo workflow opt-in **Optional sensitive operator Chromium**,input `sensitive_operator_chromium=true`,usa `python scripts/run_admin_cutover_chromium.py --operator-workflow --output sensitive-operator-ci` e richiede esattamente59 casi passati,zero skip,con axe installato. È pronto per una futura verifica sul commit dell’utente;non è necessario rilanciare separatamente il vecchio opt-in12 per ottenere la prova già riuscita qui. Nessun workflow è stato avviato dall’agente.

Consegna unica:**MTA-0.3.0-r210-pre-RC-admin-workflow-cumulative.zip**,checksum adiacente e questo handoff autonomo. Include tutti4580 percorsi del cumulativo precedente,attributi/modalità,asset,licenze,manuali e tutti i log originali byte-identici. Manifest e prova di conservazione aggiornati;nessuno ZIP intermedio pubblicato. Il commit resta differito.

Commit cumulativo inglese suggerito,non eseguito,comprensivo di B5,drain ed E4 dopo4c3:

`Close execution ownership and complete guarded regime-switch administration`
