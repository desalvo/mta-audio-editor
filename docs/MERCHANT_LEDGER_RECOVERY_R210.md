# MTA 0.3.0-r210 — Recupero merchant PayPal nel ledger originale

28 ottobre 2026, Europe/Rome. **PRE-RC, 28/42 criteri (66,7%), E completa (1/7).** Nessun criterio originale promosso in questo blocco. L'aumento numerico richiesto non è ancora conseguito: A4 e C3 richiedono anche copertura completa dello storico e prove dei movimenti ancora non allocati. Non confondere la chiusura funzionale di questo percorso con la chiusura di quei criteri.

Baseline committata confermata: `4c3c73afe6d3829aad155c23f5f1bbb6d375433a`; full CI confermata 40584085026 conservata per quella revisione. Ripristinato il cumulativo F3 da 98.249.286 byte e 4.635 file, SHA256 `5ab4eaeb894c739920bed0d334d947beab0154b203ab92f727b029a43ce4d4a2`, con controllo SHA, CRC, manifest e modalità. Non partire dalla copia obsoleta a 23/42. Il delta cumulativo B5 + drain + E4 + F3 + recupero merchant resta non committato. Nessun commit, staging, push, dispatch CI, pubblicazione o modifica a server/provider reali.

## Percorso completato

Il pannello amministrativo collega ora una riga dello storico merchant a un ordine originale e alla riconciliazione completa del ledger. Prima lo storico era soltanto una lettura diagnostica, senza un'azione per recuperare l'ordine dalla capture canonica. Il nuovo percorso supporta il principale Express Checkout T0006 positivo e il rimborso T1107 negativo, riusciti e in EUR; altri movimenti restano esplicitamente da verificare.

1. L'operatore legge e conserva il normale snapshot autenticato, con due passaggi stabili sull'intervallo UTC massimo di 31 giorni.
2. «Carica osservazioni» mostra anche i candidati e gli ordini originali già collegati. La revisione è locale, senza richieste al provider o mutazioni finanziarie; i totali comprendono tutti i casi, anche oltre la pagina visualizzata.
3. «Riconcilia ordine originale» richiede una conferma distinta. Il browser invia soltanto SHA della riga originale e conferma: non può fornire importo, utente, ordine o prova alternativa.
4. Se il collegamento locale manca, un GET fisso della capture usa il suo `supplementary_data.related_ids.order_id` per cercare l'ordine locale già esistente, dello stesso merchant e ambiente. Note, custom label, URL e account dichiarati dal pagatore non creano né assegnano ordini.
5. Si riusa il servizio canonico completo: ordine, capture, rimborsi cumulativi e dispute vengono verificati e riletti. Nella transazione economica si ricontrollano amministratore attivo, configurazione originale, snapshot e riga immutabili, proprietario, tipo, periodo, importo, riferimenti ed epoch originale.
6. Importo e identità della riga devono coincidere con il principale canonico. Per un rimborso il riferimento TXN deve essere proprio la sua capture verificata, non un'altra capture dello stesso ordine. Il timestamp deve appartenere alla finestra originale.
7. L'evento immutabile `merchant_discovery_binding` lega snapshot, SHA della riga e ordine. Binding, finanziamento, rimborsi, rischio e ledger condividono la transazione: un errore intermedio annulla anche il primo DDL. Replay e richieste concorrenti rileggono il provider e non duplicano accrediti, rimborsi o binding.

L'esito può riconciliare il ledger mantenendo dispute o altri obblighi pendenti. Non dichiara mai `complete_account_history` o `transition_authorized`. Nessun POST di capture o rimborso viene inviato al provider da questo percorso. Le credenziali non entrano nel DTO, nel binding persistito o nel browser.

Il recupero resta disponibile durante il drain C2 attraverso tre pattern esatti: lettura dettaglio, lettura revisione e POST della riconciliazione. Non viene aperto un prefisso amministrativo generico. La prova reale lascia il checkout originale pendente, avvia il drain, recupera il saldo originale e soltanto dopo verifica la quiescenza effettiva. Le altre richieste ordinarie restano bloccate durante il drain.

## API e uso

- GET `/api/admin/paypal/merchant-history/{snapshot}/review?offset=0&limit=50`: revisione privata, amministratore attivo, massimo 100 righe visualizzate; totali completi sullo snapshot.
- POST `/api/admin/paypal/merchant-history/{snapshot}/reconcile`: body esatto `{"observation_sha256":"SHA256 della riga","confirm":true}`, sessione amministrativa e header `X-MTA-Request: 1` obbligatori.

Il percorso è nel pannello impostazioni già esistente, in italiano e inglese, con conferma, stato accessibile, errore e retry. Una risposta persa si recupera ripetendo la stessa azione originale; non creare un secondo checkout. Timeout e errori HTTP del provider mantengono gli obblighi e producono una risposta privata senza dati del provider. Le risposte di revisione/riconciliazione hanno `Cache-Control: no-store`.

Se manca l'ordine locale originale, ripristinare la sua prova originale: non assegnare a un account la transazione attraverso una nota. Snapshot di un altro merchant, prove corrotte, valute/stati/codici non supportati, importi incoerenti o revoche restano bloccati. Nessuna configurazione reale è stata modificata.

## Verifica corrente

`validation/r210/merchant-ledger-result.json` aggrega **368 casi distinti passati, 40 nuovi**, senza sommare le riesecuzioni. Dodici prove usano Chromium reale: otto nuovi percorsi capture/rimborso, IT/EN e viewport 390/1280, più quattro regressioni della lettura merchant nello stesso pannello modificato. Il ledger viene verificato contro l'API e il database effettivi, con netto di 1.000.000 micro dopo 400 centesimi di rimborsi su 500 centesimi di incasso.

I report correnti coprono anche autorizzazione/CSRF, conferma annullata, input estranei, errori HTTP privati, revoche e cambi di contesto durante i GET, riferimento errato tra capture dello stesso ordine, ordine locale mancante, rollback dopo rimborso parziale, concorrenza, paginazione oltre 100 casi e recupero sotto drain. I primi tentativi falliti restano conservati: le aspettative delle fixture sono state corrette per DDL transazionale, checkout ancora pendente e letture soggette al drain; i controlli di produzione non sono stati allentati.

Ruff completo app/native/tests/scripts, compilazione Python e sintassi JS passano. Bandit: 301 sorgenti, 164 finding revisionati invariati (0 HIGH, 21 MEDIUM, 143 LOW). Inventari: 170 confini di ammissione, 30 trasporti in 21 file, 542 sorgenti runtime e 782 punti. Due nuovi handler sono revisionati come ingressi amministrativi senza inferenza. Nessun checker, soglia, soppressione o disposizione di finding nuova. Sessantuno gate sorgenti passano.

Chrome 145.0.7632.6 / Playwright 1.58.0: il CDN predefinito restituiva ZIP non validi; gli archivi ufficiali Google Chrome-for-Testing della stessa versione sono stati scaricati e verificati con CRC. Non occorre una CI browser per supplire a uno skip locale: tutte le 12 prove interessate sono passate. Le prove F3 ONNX/HTTPS, E4/axe non interessate e la full CI invariata non sono state ripetute. Nessuna nuova full CI cumulativa dichiarata.

Riesecuzione mirata, solo se cambia il percorso:

```bash
MTA_TEST_OFFLINE=1 python -m pytest -q tests/test_r210_merchant_ledger_bridge.py tests/test_r210_merchant_ledger_browser.py tests/test_r210_paypal_merchant_history_browser.py
```

Le prove browser richiedono Playwright e Chromium installati. Le prove non muovono denaro reale: il trasporto provider è simulato e limitato ai GET; API applicativa, transazioni, ledger e browser sono reali e isolati.

Fonti primarie confrontate il 28 ottobre 2026: [Transaction Search](https://developer.paypal.com/api/transaction-search/v1/search-get), [reference ID](https://developer.paypal.com/api/transaction-search/v1/definitions/transaction_detail_list/), [T-code](https://developer.paypal.com/reports/reference/t-codes/), [Disputes API](https://developer.paypal.com/api/customer-disputes/v1/disputes-list). Una finestra stabile non prova la copertura dell'intera vita del conto; uno stato di reporting o l'inizio di un movimento non prova da solo il completamento economico e l'allocazione di payout/protection.

## Residui e ripresa

Restano tutti i 14 criteri già aperti: nove di implementazione/diritti (A4, A5, B2, C3, C5, C6, D6, F4, F6), cinque di target/ambiente (A6, B6, F5, G5, G6). Il prossimo intervento finanziario deve completare copertura e continuità delle finestre merchant, gestione durevole dei riferimenti mancanti e prove univoche di completamento/allocazione dei movimenti, poi basi originali legacy di quota/surplus. Non sostituire queste prove con prezzi correnti, semplici osservazioni o quietanze prodotte dal browser. C5/D6 generali dipendono ancora da C3; nessuna transizione finanziaria generale o RC autorizzata.

Questo blocco consegna un percorso utilizzabile completo e 40 nuove prove, ma non soddisfa ancora l'aumento della percentuale richiesto. Non riaprire i percorsi già chiusi né ricreare questo bridge nel prossimo turno.

Consegna unica: `MTA-0.3.0-r210-pre-RC-merchant-ledger-cumulative.zip`, checksum adiacente e questo handoff. Conservare tutti i 4.635 percorsi di ingresso e tutti i log originali byte-identici, asset, manuali, licenze e metadati ZIP. Runtime di test e browser non sono inclusi. Commit ancora differito.

Commit cumulativo inglese suggerito, non eseguito:

`Complete guarded execution, administration and merchant-ledger recovery`
