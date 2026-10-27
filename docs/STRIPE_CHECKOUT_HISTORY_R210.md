# MTA r210 — riconciliazione Stripe degli ordini conosciuti — 27 ottobre 2026

Baseline committata: `772fbe7508cc08266466a3746bb51f0fe5d0179b`.
Cumulativo completo: `MTA-0.3.0-r210-pre-RC-stripe-checkout-history-cumulative.zip`.

## Risultato funzionale

Le azioni esistenti di riconciliazione dell'amministratore e di verifica del pagamento dell'utente ora leggono una storia finanziaria completa e concorde del PaymentIntent originale prima di modificare saldo,ordini e registri locali. Sono coperti sia l'incasso riuscito sia la chiusura senza incasso con intent cancellato,conservando le ricevute e l'identità della richiesta originale.

Il difetto corretto era concreto: la precedente lettura poteva unire un incasso precedente a una collezione di rimborsi/dispute cambiata durante la richiesta. Inoltre,il solo `latest_charge` non descriveva i tentativi falliti precedenti;la collezione vuota di un intent cancellato usciva dalla verifica prima della rilettura finale.

## Percorso implementato

1. L'ordine e le credenziali provengono dal database;il controllo del proprietario precede qualsiasi richiesta esterna.
2. Per un pagamento riuscito si verificano Checkout in modalità payment,PaymentIntent e Charge,con importi interi esatti,valuta EUR,ambiente coerente,incasso completo e assenza di importo ancora catturabile. La lista paginata dei Charge deve contenere quello riuscito. Ogni altro tentativo deve avere una rilettura canonica che provi il fallimento senza incassi,rimborsi,dispute,autorizzazioni o movimenti di saldo irrisolti.
3. Ogni rimborso e disputa viene riletto singolarmente;identità,stato,importo e riferimenti devono concordare con le liste. I rimborsi riusciti devono sommare al totale rimborsato del Charge;il flag disputed deve concordare con la collezione. Stati inattesi e prove incomplete mantengono il blocco.
4. L'intera raccolta è ripetuta e confrontata sui soli campi finanziari normalizzati. Cambiamenti nei dati cliente irrilevanti non invalidano il confronto e non entrano nella ricevuta.
5. Prima delle letture viene acquisita un'impronta dei record Stripe del journal,compresi gli eventi ancora senza ordine. Dopo le letture,la transazione `BEGIN IMMEDIATE` ricontrolla ordine,credenziali e journal. Un webhook intervenuto richiede un nuovo aggiornamento;una vecchia osservazione favorevole non può scavalcare il nuovo rischio registrato.
6. La stessa transazione conserva la prova finanziaria normalizzata,il relativo digest e le modifiche a saldo/inbox/ordini. Una failure locale annulla tutto;la ripetizione conserva una sola attribuzione del credito.
7. Anche la collezione vuota di un intent cancellato richiede la seconda lista e la rilettura dell'intent,con ambiente verificato. Una chiusura terminale concorrente già registrata può essere ripetuta solo superando nuovamente la verifica della ricevuta originale e delle obbligazioni. Un evento finanziario contraddittorio resta da esaminare.

Tutto il traffico del flusso è GET. Nessuna cattura,richiesta di rimborso o mutazione del provider viene inviata. La transazione contabile non resta aperta durante le letture esterne. Le API e i controlli UI esistenti restano il punto d'ingresso;non sono aggiunti controlli da attivare.

## Limiti operativi espliciti

Massimo100 tentativi di Charge e1000 oggetti per collezione rimborsi/dispute,entro il limite complessivo più restrittivo di256 GET e60 secondi per tentativo. Il timeout di ogni richiesta è limitato al tempo residuo. La ricevuta usa il limite esistente di64KiB del journal:una storia eccedente richiede revisione invece di una prova troncata. Una variazione concorrente di un altro evento Stripe può richiedere un retry conservativo;non viene riletto il provider sotto lock contabile.

La concordanza di due letture è un'osservazione stabile in quel momento,non una transazione distribuita con Stripe né una garanzia contro eventi futuri. La ricevuta conserva riferimenti ai movimenti di saldo,ma non dimostra una liquidazione payout o l'attribuzione delle commissioni. Il blocco globale sul cambio di regime rimane attivo.

## Verifica

Risultato aggregato: **220 test funzionali distinti +43 controlli di gate =263 passati**,inclusi50 nuovi casi. XML originali,fallimenti corretti,identità dei casi e hash sono registrati in `validation/r210/stripe-stable-history-result.json`. Il conteggio usa l'ultimo esito di ciascun caso;non somma le ripetizioni. Le correzioni alle fixture includono i veri campi finanziari richiesti dal contratto Stripe;nessuna policy di produzione è disabilitata nei test.

Le prove usano FastAPI,SQLite,journal,saldo e transazioni reali con trasporto HTTP Stripe isolato. Coprono entrambe le API,paginazione,tentativi falliti,rimborsi/dispute,riletture discordanti,webhook durante l'I/O,rollback dopo attribuzione del credito,limiti e recupero. Il trasporto simula il provider:non costituisce esecuzione sandbox esterna. Ruff completo e compilazione dei file modificati passano. Bandit294 file/165 finding invariati,0HIGH;gate source-bound e inventario30 siti/21file aggiornati senza nuove soppressioni.

Riutilizzate la CI standard40480180716 e l'accettazione Chromium40505295056 sulla baseline per le parti invariate. Nessuna modifica JavaScript/template;nessuna nuova esecuzione Chromium richiesta per questo delta backend. I9casi del cambio locale già validati non sono stati ripetuti. La CI standard sul futuro commit verificherà l'integrazione del nuovo delta;la full non è stata eseguita qui.

## Stato RC e prossimi passi

Questo chiude il percorso di lettura stabile/ancestry/concorrenza degli ordini Stripe noti nel perimetro sopra descritto. Non chiude una delle7macroaree originali: **23/42,54.8%,0/7;PRE-RC**.
Restano A4/A5/C3: storia globale del merchant,associazione univoca payout/protezione/caso PayPal,obbligazioni legacy e prove originali fee/surplus mancanti. Per queste ultime serve prova storica indipendente;importi o commissioni non sono ricostruiti per ipotesi. Restano inoltre copertura di tutti gli executor/drain distribuito,cambio generale C2/C3/C5/C6/D6,diritti e target esterni. La modalità locale di cambio regime resta default-off e non viene ampliata da questa modifica.

Nessun commit,staging,push,dispatch CI o modifica di GitHub/server/provider reali eseguito.
Commit cumulativo suggerito dopo772fbe7:
`Harden Stripe checkout history, webhook concurrency and terminal reconciliation`

## Fonti tecniche primarie consultate

- Stripe, elenco Charge e filtro payment_intent: https://docs.stripe.com/api/charges/list
- Stripe, oggetto Charge e campi di incasso/rimborso/rischio: https://docs.stripe.com/api/charges/object
- Stripe, PaymentIntent e storia dei tentativi: https://docs.stripe.com/api/payment_intents
- PayPal, Disputes API: https://developer.paypal.com/api/customer-disputes/v1/disputes-list
- PayPal, codici evento e direzione dei movimenti: https://developer.paypal.com/reports/reference/t-codes/
Queste fonti descrivono i contratti;le prove eseguite qui sono quelle locali sopra indicate.
