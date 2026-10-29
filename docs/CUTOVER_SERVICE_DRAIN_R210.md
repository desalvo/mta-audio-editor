# MTA 0.3.0-r210 — cutover e drain persistente

Checkpoint: **28 ottobre 2026, Europe/Rome. PRE-RC. 26/42 criteri originali (61,9%),0/7 macroaree; nessun nuovo criterio promosso.** Questo blocco chiude il collegamento funzionale fra il drain C2 già accettato e il profilo amministrativo locale ristretto. Non completa la riconciliazione finanziaria generale. La richiesta di aumentare la percentuale non è ancora soddisfatta: nessun requisito originale è stato ridotto o sostituito.

Baseline committata confermata dall’utente: **4c3c73afe6d3829aad155c23f5f1bbb6d375433a**. Cumulativo di ingresso: `MTA-0.3.0-r210-pre-RC-execution-ownership-cumulative.zip`, SHA256 `03ab20ada81b9aa7976e11fa19676f65b84d5195b9471878e942f061e7dadef9`,98.017.071 byte,4559 file. B5 resta accettato e il relativo delta non committato è incluso. Full CI40584085026 verde sul commit4c3 conservata; nessuna nuova CI GitHub confermata per B5 e questo blocco. Nessun commit,staging,push,dispatch,tag,release o intervento su GitHub/server/provider da parte dell’agente.

## Comportamento consegnato

Con il protocollo C2 attivo, un anteprima/cambio/recupero acquisisce nell’ordine il journal originale delle ammissioni e la lease esclusiva del servizio. Richiede fase `draining`, build e istanza originali, evento coerente con la revisione e nessuna ammissione aperta. Ricontrolla il lavoro pendente reale prima di procedere. Il journal resta bloccato attraverso commit SQLite, sostituzione durevole del mirror e finalizzazione: una lettura precedente con `drained:true` non autorizza un cambio successivo.

L’anteprima incorpora identità,revisione,build e istanza del drain nella propria impronta. Riapertura,nuovo drain o cambio del build invalidano la vecchia conferma anche quando saldi e periodi sono identici. Il cambio finalizzato conserva il drain: riaprire il servizio è un’azione amministrativa esplicita distinta.

Una riserva di regime ancora attiva o un commit non finalizzato impediscono la riapertura delle ammissioni. Prima del commit si può annullare soltanto la riserva originale; dopo il commit si può completare soltanto il recupero in avanti, con identità/revisione e ricevuta finanziaria originali. L’audit del drain può escludere esattamente il proprio commit già registrato e il relativo epoch bloccato; non può ignorare altri worker,pubblicazioni,checkout o transizioni. La conservazione dei saldi resta obbligatoria. SIGKILL libera i lock del processo,ma non cancella questi obblighi persistenti.

La ripetizione esatta di una richiesta già finalizzata restituisce la ricevuta originale anche dopo la riapertura. Ricontrolla amministratore,identità,destinazione,revisione e impronta; non avvia un secondo passaggio. Una richiesta differente con la stessa identità viene rifiutata.

Il pannello impostazioni IT/EN espone stato,rilettura,sospensione,riapertura con identità originale e passaggio esplicito al nuovo build. Conferma da tastiera,stati non disponibili e perdita della risposta conservano l’incertezza; non viene ripetuto automaticamente alcun POST. Timeout15s su lettura e corpo della risposta. Un cambiamento del drain invalida l’anteprima visualizzata. Queste nuove interazioni richiedono ancora la prova Chromium descritta sotto.

## Configurazione e procedura operativa

Il codice non modifica configurazioni o installazioni reali. Il protocollo supportato resta una sola autorità Linux/POSIX con database e journal locali,processi API/timer sul medesimo build e worker HTTPS con credenziali originali. Non usare SQLite su NFS o questo lock come elezione HA.

1. Configurare coerentemente tutti i processi con `MTA_SERVICE_ADMISSION=authority-v1`. Per il solo profilo di cutover ristretto resta necessario `MTA_REGIME_CUTOVER=local-authority-v1`; entrambi sono opt-in. Non eliminare journal o file `.instance`: togliere la variabile non disattiva un journal già presente.
2. Dal pannello amministrativo leggere lo stato e confermare **Sospendi nuove ammissioni**. Attendere zero ammissioni e zero attività pendenti verificate. Uno stato non disponibile,un worker incerto o un errore di integrità non equivale a zero.
3. Verificare separatamente gli obblighi finanziari. Il drain restituisce sempre che non certifica la solvibilità. Il profilo locale continua a rifiutare provider configurati,storici provider/legacy non riconciliati e piani a pagamento; non cancellarli per far passare il gate.
4. Ottenere una nuova anteprima e confermare destinazione e revisione. In caso di risposta persa rileggere il registro e riprendere la stessa identità. Non costruire una seconda richiesta per aggirare l’incertezza.
5. Con commit incompleto completare il recupero originale. Una pubblicazione o altra attività pendente indipendente continua a bloccarlo. Dopo finalizzazione verificare lo stato e confermare **Riapri ammissioni** usando il drain originale.
6. Per aggiornare il codice di un’autorità già attiva: drenare e completare tutto il lavoro con il build originale prima del cambio; poi utilizzare il controllo esplicito **Conferma passaggio al build corrente**,vincolato a vecchio build e revisione. Un crash con commit ancora incompleto richiede prima il recupero con il build originale. Nessun timeout o cancellazione dei file autorizza il cambio di build.

Installazioni senza alcun protocollo C2 persistente conservano la compatibilità del vecchio profilo locale ristretto. Quel percorso non certifica un drain distribuito e non promuove C3/C5/D6/E4. Per il percorso integrato inizializzare C2 prima del cutover e mantenere identica configurazione tra processi.

## Verifica disponibile e Chromium opt-in

`validation/r210/cutover-service-drain-result.json` riporta **149 casi interessati distinti passati**,23 nuovi(17 funzionali e6 del gate rigoroso),0 fallimenti/errori correnti; **12 casi Chromium saltati per prerequisito assente e non accettati**. Unione degli ultimi risultati per identità,non somma delle riesecuzioni:

- `cutover-drain-final.xml`:85 passati,12 skip.
- `cutover-drain-process-final.xml`:17 passati;14 sovrapposti e3 ulteriori per annullamento,obbligo indipendente e SIGKILL reale.
- `cutover-drain-gates.xml`:61 passati.

Le14 iniziali anomalie erano nella fixture che ricreava una directory già esistente; XML iniziale conservato,correzione soltanto alla fixture. I report intermedi non sono nuovi test aggiuntivi. La regressione su cutover,C2 e lifecycle è stata rieseguita perché quei confini sono cambiati; B5,full CI e vecchie prove browser invariate non sono stati ripetuti.

Ruff app/native/tests/scripts,compilazione app/scripts,sintassi dei due JavaScript e gate sorgente passano. Bandit1.9.4:299 file,164 finding revisionati(0HIGH/21MEDIUM/143LOW),nessun finding aggiunto o soppresso. Inventario C2:170 confini;trasporto:30 siti/21 file;runtime B5:540 sorgenti/779 punti classificati. L’unico nuovo sorgente runtime è il pannello statico; nessuna nuova inferenza o permesso remoto. Inventari aggiornati dopo revisione esplicita,checker e soglie invariati.

Il browser non è installato nel workspace ripristinato. Il download ufficiale restituisce HTML invece dell’archivio. Il runner rigoroso è stato eseguito e ha prodotto `accepted:false` per i12 skip; non è una prova UI riuscita. Il workflow locale nuovo è `.github/workflows/service-drain-cutover-chromium.yml`,**Optional service drain cutover Chromium**. Dopo il commit dell’utente eseguire soltanto questo opt-in con `service_drain_cutover_chromium=true`. Comando equivalente: `python scripts/run_admin_cutover_chromium.py --service-drain --output service-drain-cutover-ci`. Richiedere `acceptance.json` con `accepted:true,passed:12,skipped:0`. Mancanze,casi duplicati,modulo sbagliato,skip o vecchio report da9 casi non soddisfano il gate. Non serve ripetere i9 casi già confermati soltanto per questo nuovo blocco. Nessun dispatch automatico.

## Blocchi reali e prosecuzione

**C3 resta implementazione incompleta**,non un semplice problema CI: manca una riconciliazione completa dello storico globale PayPal,con attribuzione di payout/protection e casi ambigui; per alcune sottoscrizioni legacy manca la prova originale della quota/surplus. Gli snapshot merchant su una finestra richiesta non certificano l’intero conto. Prezzo corrente,stato della rata o saldo rimborsabile mutabile non possono ricostruire la quota originale. Le prove locali accettate del ledger non autorizzano queste deduzioni.

Di conseguenza **C5,D6,E4 non vengono promossi** dal roundtrip del profilo ristretto,anche se ora integra il drain persistente. C6 richiede ancora accettazione crash/concorrenza tra host reali; questo SIGKILL è un processo locale. E5 e C2 restano accettati nei rispettivi contratti. Il browser nuovo è un blocco di ambiente verificabile in CI,distinto dal lavoro finanziario ancora da implementare. L’ispezione dell’alternativa F3 conferma soltanto il precedente pilot Basic Pitch: non è un’attestazione completa di tutti i checkpoint remoti e non cambia il suo stato.

Riprendere dal manifest degli obblighi finanziari completi: integrare scoperta e attribuzione canonica,far emergere ogni voce legacy priva di prova originale e dimostrare le risoluzioni tramite servizi di riconciliazione/rimborso/rimborso-ricevibile esistenti. Non saltare i gate,non sostituire i42 criteri con il profilo locale e non chiedere un’altra full CI per codice invariato. Conservare il collegamento C2 qui completato e riusarlo nella transizione finanziaria generale.

## Consegna e commit differito

Cumulativo completo: **MTA-0.3.0-r210-pre-RC-service-drain-cutover-cumulative.zip**,checksum adiacente,manifest aggiornato con baseline4c3. Tutti4559 percorsi di ingresso,asset,licenze,manuali,attributi ZIP e614 `.log` originali conservati; nessun archivio intermedio pubblicato. Il nuovo log del runner fallito resta come prova distinta. Esito di conservazione in `validation/r210/cutover-drain-preservation.json`.

English cumulative commit, **not executed**, including B5 plus this block since4c3:

`Close execution ownership and bind administrative cutover to durable service drain`
