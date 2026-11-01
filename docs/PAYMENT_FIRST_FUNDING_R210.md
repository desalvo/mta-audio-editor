# Prima contabilizzazione Stripe e PayPal — r210

Baseline Git confermata: `ee4e37fd30c39a72638b303b01ca0cd5b090f272`, full CI `41156985339` verde. L'archivio precedente è `MTA-0.3.0-r210-pre-RC-completed-payment-recovery-cumulative.zip`, SHA-256 `0ccc665e1474c2803ef41024f51d24121e0a0e8b9d6c4327cf24d33d32802920`. Tutti i delta successivi al commit restano cumulativi e non dichiarati committati.

## Modifica

La prima acquisizione PayPal e il webhook `PAYMENT.CAPTURE.COMPLETED` passano dalla riconciliazione autenticata dei rimborsi e delle contestazioni prima di rendere disponibili i crediti. Un pagamento di 5 euro con contestazione da 2 viene contabilizzato per 3; dati incompleti impediscono l'accredito e richiedono la riconciliazione esplicita, senza una seconda acquisizione. Un evento webhook e la contabilizzazione restano nella stessa transazione. L'evento di completamento non viene confermato se l'ordine canonico non è ancora completato. La verifica dell'epoca commerciale avviene prima della lettura per non interpretare un blocco di regime come storia incompleta; la verifica nella transazione resta attiva.

Il primo webhook Stripe pagato usa due riletture complete della sessione originale, del PaymentIntent, dei tentativi, dei rimborsi e delle dispute. La posizione iniziale e l'evento firmato vengono registrati nella stessa transazione; se il provider riporta 5 euro pagati e 2 già rimborsati, il saldo disponibile iniziale è 3 euro. Se la risposta di creazione era stata persa, il webhook lega prima la sessione con il protocollo di recupero autenticato già esistente, verificando ordine originale e outbox. Eventi ripetuti sono confrontati con digest e contenuto registrati. Un cambiamento concorrente del registro provoca al massimo una rilettura supplementare; se il risultato rimane incerto non viene confermato. Le notifiche incompatibili con una chiusura terminale restano in revisione, senza riaprire il pagamento.

I due endpoint webhook eseguono l'I/O sincrono in un thread del server, evitando di bloccare l'event loop. L'operazione dipende dalla disponibilità e dai permessi delle API provider: uno storico non verificabile impedisce l'accredito automatico e può richiedere intervento amministrativo. Le API restano limitate e i timeout possono comunque incidere sui tempi di risposta e sull'uso dei thread.

## Verifica e residui

La suite finanziaria integrata di 17 file ha dato **577 passati e nessuno skip**, prima dell'ultimo aggiustamento al controllo di regime. Dopo il primo controllo di regime: **238 passati e 22 browser saltati**; dopo la precisazione sugli ordini terminali: **26 passati e gli stessi 22 browser saltati**. I 22 skip derivano dall'assenza di Playwright e non sono prove browser; le suite si sovrappongono e non vanno sommate. La verifica finale Stripe mirata include **10 passati**, endpoint HTTP, rimborso/disputa, riferimento perso, dati incompleti e concorrenza. Tutti usano provider simulati e database/ledger locali isolati. XML in `validation/r210/payment-first-funding/`.

La regressione Stripe era stata riprodotta prima della correzione: la prova esplicita `stripe-baseline-repro-failed.xml` registrava 5 euro accreditati anziché i 3 al netto del rimborso; lo stesso caso passa nella verifica finale. Una precedente esecuzione di accettazione aveva segnalato il falso blocco PayPal dopo cambio regime; è stato corretto e il caso è passato nella verifica terminale finale. Ruff, compilazione, Bandit e inventari AI/ammissione/trasporti passano; Bandit analizza 309 sorgenti con 168 finding invariati, nessun HIGH. I 32 punti di trasporto comprendono il nuovo client di lettura Stripe. Non sono state eseguite una nuova CI remota o prove provider effettive.

Non è dimostrata la copertura completa di tutti i casi A4/A5: restano la contabilizzazione dei movimenti e delle contestazioni PayPal parziali/ambigue non supportate, gli ulteriori esiti e le corse del ciclo di vita finanziario, e il collaudo sulle API e sui report del conto abilitato. I test locali non costituiscono certificazione sandbox o produzione. A4 e A5 rimangono aperti: **32/42 = 76,2% verso la RC**, perimetro `precommercial-20261030`. Batch di almeno 20 cicli non dichiarato completato. Nessun commit, push o modifica di server/provider reali.

Riferimenti provider: https://developer.paypal.com/api/rest/webhooks e https://developer.paypal.com/platforms/disputes/handle-disputes/use-disputes-api/.

Commit cumulativo suggerito: `Reconcile initial payments and uncertain refunds across providers`
