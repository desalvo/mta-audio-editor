# PayPal: ordine creato con risposta persa — r210

1 novembre 2026, Europe/Rome. **RC: 32/42 = 76,2%, PRE-RC**, perimetro `precommercial-20261030`. Nessun criterio promosso. Baseline confermata `ee4e37fd30c39a72638b303b01ca0cd5b090f272`, full CI `41156985339` verde; tutti i delta successivi restano non dichiarati committati.

Riprendere dal cumulativo `MTA-0.3.0-r210-pre-RC-paypal-lost-creation-cumulative.zip`. La base di questa consegna è `MTA-0.3.0-r210-pre-RC-initial-payment-history-cumulative.zip`, SHA-256 `da746581bf65e514ed511c9a5fc53d0a62882b2d63a18e71866fb931e1dfdb62`. I punti di ripresa della strategia ora indicano questo checkpoint; non ripristinare il precedente archivio pre-commerciale citato nelle vecchie istruzioni.

## Percorso completato localmente

PayPal poteva aver creato e incassato un ordine mentre la risposta di creazione era andata persa. Il webhook, pur verificato, cercava soltanto il riferimento remoto non ancora salvato e rifiutava il pagamento come sconosciuto. Ora, dopo la verifica della firma, legge l'ordine dal provider, seleziona il candidato locale dai soli riferimenti canonici e richiama il protocollo esistente di recupero. Quel protocollo verifica importo, valuta, intent CAPTURE, merchant, identità originale, tentativo effettivo e ammissione commerciale; ora confronta anche la fattura originale `mta-<ordine>` e la configurazione usata per verificare il webhook.

Il riferimento viene legato con la normale transazione di recupero. La riconciliazione completa dei rimborsi e delle dispute precede poi la contabilizzazione; evento e saldo rimangono atomici. Il percorso copre crediti, abbonamento e rata del debito originale. Rimborsi e revoche già notificati vengono applicati nella stessa contabilizzazione, senza una finestra di credito lordo spendibile. Lo storico incompleto impedisce l'accredito e mantiene il normale requisito di riconciliazione esplicita. Anche con crediti/provider successivamente disabilitati, l'endpoint HTTP può registrare il denaro già incassato.

Una terminazione reale con SIGKILL dopo il legame del riferimento e durante la transazione finanziaria lascia il riferimento verificato e annulla l'accredito non confermato: la notifica successiva riprende senza una seconda creazione o capture. Prove concorrenti con otto consegne conservano un solo riferimento, una sola capture e un solo accredito. Le sole POST usate dall'applicazione nel recupero sono quelle di verifica della firma; non vengono ripetute le operazioni monetarie.

## Verifica

**723 casi distinti passati, 26 nuovi, zero fallimenti/errori/skip nelle selezioni correnti.** Suite finanziaria 675, suite merchant/protocollo 48, file distinti; `validation/r210/paypal-lost-creation/result.json` verifica identità e hash dei rapporti. Provider simulati; transazioni, ledger, concorrenza e terminazione Linux reali e isolati. I due nuovi casi base fallivano sul sorgente precedente con `Unknown PayPal order`; XML iniziale conservato. Un successivo errore SQL nella nuova asserzione del test è stato corretto prima della verifica finale. Nessun test atteso-fallito è stato introdotto.

Ruff, compilazione, Bandit e inventari sicurezza/AI/ammissione/trasporti passano. Bandit: 309 sorgenti, 168 finding invariati, zero HIGH; nessun nuovo sito di trasporto. Nessuna nuova CI remota o accettazione browser/provider reale: gli skip browser dei checkpoint precedenti non sono stati trasformati in pass.

## Residuo concreto e prossima area

Questo chiude il recupero dell'ordine PayPal con risposta di creazione persa, non l'intero A5. In `tests/test_r210_original_subscription_loss.py`, `test_partial_permanent_loss_stays_unallocated` e `test_gap_review_distinguishes_legacy_and_unproved_partial_loss` mantengono esplicitamente aperta l'attribuzione di perdite permanenti parziali dell'abbonamento. `test_buyer_favour_dispute_without_actual_reversal_never_collects_fee` mantiene il requisito di un movimento effettivo, anche quando il caso è risolto a favore dell'acquirente. Mancano ancora il percorso generale di prova e allocazione di questi movimenti e la sua verifica: non sono residui tutti esterni e non possono essere trasformati in un debito stimato.

A4 mantiene movimenti PayPal parziali/ambigui e relative prove di settlement. F4 mantiene i contratti indipendenti di interpreti/dipendenze e l'identità del backend ACE effettivo; F6 richiede le revisioni indipendenti dei checkpoint. A6/B6/C6/F5/G5/G6 conservano i requisiti effettivi riportati in `KNOWN_BLOCKERS_R210.md`. Nessun conto commerciale pre-release da migrare. Nessun commit, push, intervento su GitHub/server o denaro reale. Il batch richiesto di almeno 20 cicli non è dichiarato completato: combinazioni di test non sono cicli.

Riferimento primario sui campi di identità del purchase unit: https://developer.paypal.com/api/orders/v2/definitions/purchase_unit . La documentazione non sostituisce il collaudo del conto effettivo.

Commit cumulativo suggerito: `Recover uncertain payments and refunds with canonical provider history`
