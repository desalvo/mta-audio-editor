# A4 — cronologia canonica e cassa dei nuovi pagamenti PayPal

1 novembre 2026, Europe/Rome. **RC: 34/42 = 81,0%, PRE-RC. A4 chiuso nel perimetro autorizzato `precommercial-20261030`; A5 resta chiuso.** Testo, peso e denominatore dei criteri invariati; nessun target provider reale accettato. D/E complete: 2/7.

Cumulativo: `MTA-0.3.0-r210-pre-RC-paypal-cash-history-cumulative.zip`. Parent A5 verificato SHA-256 `a6f9809c8a53c23196e5ee6255d919e7b39771d73f8d015fe00758162ef7f651`. Baseline Git confermata `ee4e37fd30c39a72638b303b01ca0cd5b090f272`, full CI `41156985339` verde. Il commit resta all'utente; tutti i delta precedenti sono inclusi.

## Percorso completato

L'azione owner/admin di verifica risolve ora gli esiti finali PayPal con payout/protection attraverso letture finanziarie autenticate, prima della prima contabilizzazione. La cronologia canonica completa di capture e rimborsi viene confrontata con due acquisizioni stabili di movimenti che incidono sul saldo del merchant originale, dallo start originale al limite di copertura del reporting. I casi sono raccolti e riletti completamente per le capture dell'ordine, inclusi i casi senza importi per articolo. Senza prove sufficienti rimangono bloccati: nessun debito, credito o esito finale viene ricavato dalla sola etichetta della disputa o dai suoi orari di avvio.

La cassa attribuisce esattamente il principale a ogni capture attraverso i soli riferimenti provider; non divide proporzionalmente un importo di disputa e non inventa un rimborso per ogni caso. Nei casi multipli sullo stesso originale, il netto del pagamento è provato dal set completo di casi finali e dai suoi movimenti, mentre i campi descrittivi conservano gli importi canonici dei singoli casi senza una ripartizione stimata dei payout. I campi di dettaglio payout e le commissioni non sono autorità monetaria. Valute, stati e movimenti non supportati o temporanei non risolti mantengono il blocco.

Ogni movimento e caso ha un claim immutabile legato al solo pagamento originale. Quote, proprietario, merchant, ammissione originale del checkout, oggetti canonici e versione del journal vengono ricontrollati nella transazione finale. La stessa transazione registra prima contabilizzazione, rimborsi, prova, correzione del wallet o della rata e chiusura finanziaria delle osservazioni coperte. Nessun importo lordo diventa spendibile durante una prima acquisizione incompleta. I documenti/esiti finali contraddittori non sono riscritti; la prova di cassa chiude soltanto la conseguenza finanziaria. Un caso già osservato/provato non può sparire da un readback successivo.

Per le rate si corregge la copertura del debito originale, senza creare un debito ricorsivo o un credito wallet. Per l'abbonamento si riusa la conservazione A5 di quota e surplus. Reintegri successivi, notifiche nuove, rimborsi ed evidenze cambiate richiedono una nuova prova: una notifica più recente della copertura temporale impedisce la riconciliazione anticipata. Il rimborso operatore conserva una sola POST; con risposta persa o cassa non ancora aggiornata rimane pending/uncertain e si chiude tramite verifica, dopo la copertura del reporting.

## Matrice del criterio A4 invariato

| Obbligo | Implementazione e prova |
|---|---|
| Cronologia canonica dei pagamenti creati dalla release | Provider readback, capture/refund collection e oggetti riletti; `test_r210_stripe_paid_history.py`, `test_r210_paypal_history_reconciliation.py`, `test_r210_paypal_dispute_history.py` |
| Capture iniziali già rimborsate | Riconciliazione prima del primo accredito e atomicità con eventi anticipati; `test_r210_paypal_reconciliation_e2e.py`, suite operator/refund e primo funding |
| Attribuzione esatta su più capture | Importi item/report quando disponibili e, nel nuovo percorso, movimenti del principale con riferimenti univoci per capture; `test_r210_paypal_cash_history.py`, `test_r210_paypal_settlement_reports.py` |
| Dispute/payout ambigui | Casi finali + cassa completa quando provabili; altrimenti pending/error senza moneta stimata. Coperti payout parziale, protezione integrale, sola perdita, reintegro e più casi sullo stesso originale |
| Nessuna importazione di storia commerciale pre-release | Solo ordine originale, merchant e checkout ammesso; nessun importatore o ricostruzione di quote legacy. Restano i controlli precommerciali e le prove di creazione persa A5 |

## Prova finale

**927 casi distinti passati, 48 nuovi; zero fallimenti/errori, 20 skip browser espliciti.** XML unico della selezione finale in `validation/r210/paypal-cash-history/financial-final.xml`; casi e hash nel `result.json`. Il sorgente non è cambiato durante l'esecuzione finale. Inclusi i precedenti 879 casi passati di A5, i 48 nuovi casi di A4 e i 20 skip esistenti per assenza di Playwright/Chromium. Le prime regressioni avevano individuato la corretta distinzione pending/uncertain per il rimborso con ricevuta nota e il ritardo dopo una nuova notifica: le fixture sono state corrette prima del run finale completo. Nessun xfail aggiunto.

SQLite, API HTTP locale, concorrenza, cancellazione account e SIGKILL Linux sono reali e isolati; le API provider sono simulate. Nessun nuovo collaudo Chromium, sandbox, server o host indipendente è dichiarato. Ruff completo, compilazione, Bandit e quattro gate di sicurezza/inventario passano: 311 sorgenti app, 558 runtime, 168 finding invariati (0 HIGH/21 MEDIUM/147 LOW), 780 siti esecuzione, 173 ammissione e 32 trasporto. Classificazioni, checker, soglie e soppressioni restano invariati.

Restano **A6,B6,C6,F4,F5,F6,G5,G6**. A6 richiede il ciclo effettivo sul sandbox; il rapporto sui prerequisiti è ora incluso in `A6_SANDBOX_PREREQUISITES_R210.md`. C6 mantiene integrazione e prova fra host. Il prossimo blocco software F4 richiede contratti indipendenti per interpreti/dipendenze e modello ACE effettivamente eseguito: non può essere chiuso dai soli hash del client o da dichiarazioni del runtime. F6 mantiene la revisione indipendente dei checkpoint installati. Nessun indice ripesato e nessuna dichiarazione RC. Nessun commit, push, tag, CI remota o operazione su denaro/server reali.

Contratti primari consultati: https://developer.paypal.com/platforms/disputes/handle-disputes/use-disputes-api/ ; https://developer.paypal.com/api/customer-disputes/v1/definitions/dispute_outcome_code ; https://developer.paypal.com/api/transaction-search/v1/search-get . La documentazione non è collaudo del conto effettivo.

Commit cumulativo suggerito: `Complete canonical payment recovery and cash-proven payout reconciliation`
