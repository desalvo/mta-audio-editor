# Recupero dei pagamenti già acquisiti — r210

Baseline confermata: commit `ee4e37fd30c39a72638b303b01ca0cd5b090f272`, full CI `41156985339` verde. La base di questo batch è `MTA-0.3.0-r210-pre-RC-payment-refund-batch-cumulative.zip`, SHA-256 `ae1588f556ecb47a94f81e58bb203f85af840a2cd199c38eddc77aafba8361e1`. I delta successivi al commit rimangono cumulativi e non committati.

## Comportamento

Un ordine PayPal acquisito dal provider prima della perdita della risposta può essere recuperato dal proprietario anche se successivamente i crediti sono stati disabilitati o il debito per abbonamento è cambiato. Prima dell'accredito viene riconciliato lo storico autenticato dei rimborsi e delle contestazioni: l'importo viene contabilizzato al netto delle perdite accertate e una storia incompleta blocca l'accredito. Una segnalazione preesistente o arrivata durante la lettura non può essere cancellata dalla normale chiamata del proprietario: occorre una riconciliazione esplicita. Se la rata già acquisita risulta eccedente rispetto al debito attuale, l'eccedenza viene registrata come rimborso dovuto, senza nuova acquisizione.

Un ordine soltanto approvato, invece, viene rivalutato sulle condizioni correnti e sulla quota originale prima di inviare una nuova acquisizione. Le ripetizioni terminali di checkout Stripe e PayPal restituiscono la ricevuta originale anche dopo la disabilitazione del servizio, mentre richieste con importo contrastante sono rifiutate. I controlli di titolarità e le restrizioni sul regime restano applicati.

## Verifica e limiti

Suite locale di 15 file su checkout, rimborsi, contestazioni, riconciliazione e rate: **461 passati, zero fallimenti e zero skip**; XML `validation/r210/payment-completed-recovery/financial-closure-v2.xml`. Test supplementare sulla segnalazione concorrente: **5 passati**, XML `validation/r210/payment-completed-recovery/owner-history-race.xml`. Le API provider sono simulate; database, transazioni e ledger applicativi sono reali e isolati. In una suite intermedia erano passati 459 casi e uno era fallito: la normale chiamata del proprietario poteva tentare di rimuovere un precedente blocco per storia incompleta. Il controllo è stato ripristinato anche nella transazione e la suite finale è stata rieseguita interamente.

Ruff, Bandit e i controlli degli inventari sicurezza/AI/ammissione/trasporti superati: 309 sorgenti, 168 finding invariati, nessun HIGH. Questi risultati non sono un collaudo su provider reale; non sono state eseguite una nuova CI remota o prove browser per questo batch. Nel batch precedente 16 prove browser erano state saltate per assenza di Playwright/Chromium.

A4 resta aperto per copertura dei movimenti/contestazioni parziali e ambigui e verifica dei report reali; A5 resta aperto per ulteriori esiti del ciclo di vita e relativa prova. Non tutti i residui sono esterni: restano implementazione e verifiche da completare. La RC mantiene il perimetro `precommercial-20261030`: **32/42, 76,2%**; nessun criterio è stato promosso e il batch richiesto di almeno 20 cicli non è completato. Nessun commit o modifica remota è stata effettuata.

Commit cumulativo suggerito: `Recover uncertain payments and refunds across providers`
