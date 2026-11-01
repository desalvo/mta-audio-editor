# A5 — accettazione completa del ciclo finanziario software r210

1 novembre 2026. **RC: 33/42 = 78,6%, PRE-RC**, perimetro autorizzato `precommercial-20261030`. **A5 chiuso**, testo e peso invariati; nessun altro criterio promosso. Macroaree complete D/E: 2/7. L'accettazione sandbox reale resta A6.

Riprendere da `MTA-0.3.0-r210-pre-RC-a5-lifecycle-cumulative.zip`, cumulativo dopo il commit confermato `ee4e37fd30c39a72638b303b01ca0cd5b090f272` (full CI `41156985339` verde). Parent verificato: `MTA-0.3.0-r210-pre-RC-paypal-lost-creation-cumulative.zip`, SHA-256 `42d81010709a30335a99ff2ec7e2fe3630103e4cf50654444d26153fcdd6ae82`. Tutti i delta precedenti sono conservati; il commit rimane all'utente.

## Esito

La verifica owner/admin di un pagamento PayPal di abbonamento con perdita permanente legge ora il denaro effettivo anche per le revoche integrali già provate. Copre perdita parziale, più capture, sovrapposizione con rimborsi, reintegro successivo del provider e restituzione dell'eccedenza della rata già pagata. La decisione della disputa non crea da sola un debito.

`subscription_cash_reconciliation.py` acquisisce due scansioni complete e stabili dei soli movimenti che incidono sul saldo del merchant originale. Verifica identità di account, ordine/capture, rimborsi canonici, casi finali, tempi, pagine, valuta, direzione e riferimenti provider. Finestre automatiche di massimo 31 giorni dalla creazione originale, copertura fino a tre ore prima della lettura; limiti espliciti di 36 finestre, 256 richieste, 90 secondi e 10.000 righe. Mancanza di permessi, ritardo, instabilità, ambiguità o superamento dei limiti mantengono il blocco e consentono il normale tentativo di verifica successivo, senza inviare denaro.

Il modello usa il principale lordo, esclude commissioni e restituzioni delle commissioni, accetta trattenute temporanee solo quando il saldo delle cancellazioni è esattamente nullo per capture. Un rimborso può essere già compreso in una revoca: la stessa perdita non viene sommata due volte. I soli riferimenti TXN/ODR appropriati collegano le righe; note, invoice e osservazioni di payout non sono autorità monetaria. I codici T classificano movimenti autenticati e completi, non sostituiscono tale prova.

Ogni movimento del principale ha un claim immutabile univoco sul pagamento originale. La ricevuta vincola quote originali, titolare, merchant e versione del journal. Nuove notifiche invalidano la vecchia prova; senza nuovo readback la raccolta è bloccata. La transazione finale ricontrolla tutto e aggiorna posizione, debito ed eccedenze insieme. Nessuna transazione di scrittura rimane aperta durante le letture provider. Le contraddizioni finali rimangono nel journal immutabile: la sola conseguenza finanziaria può essere chiusa con prova di cassa completa e casi canonici finali esattamente corrispondenti. Rischi ignoti o non corrispondenti non vengono cancellati.

La quota e il surplus originali restano immutabili e separati dal wallet. Una correzione riduce l'importo effettivo delle fonti di debito conservando le righe storiche, applica prima gli importi già pagati e rende rimborsabile l'eccesso. Il normale flusso operatore restituisce tale eccedenza; la risposta POST persa viene recuperata con sole GET, senza un secondo invio.

## Matrice di accettazione A5

| Obbligo del criterio invariato | Prova eseguita |
|---|---|
| Quote originali prima dell'invio; nessuna adozione pre-release | `test_r210_subscription_quote_origin.py`, `test_r210_precommercial_launch.py` |
| Creazione e risposte malformate/perse | `test_r210_checkout_provider_protocol.py`, `test_r210_checkout_malformed_response.py`, `test_r210_checkout_reference_recovery.py`, `test_r210_merchant_lost_creation.py` |
| Esiti terminali e tentativi falliti | `test_r210_terminal_checkout_e2e.py`, `test_r210_failed_charge_recovery.py` |
| Prima contabilizzazione con storico e rimborsi già esistenti | `test_r210_stripe_paid_history.py`, `test_r210_paypal_reconciliation_e2e.py`, `test_r210_paypal_history_reconciliation.py` |
| Rimborso operatore e risposta incerta | `test_r210_operator_refunds.py`, `test_r210_operator_refunds_recovery.py` |
| Revoche integrali/parziali, casi finali, overlap e reintegri | `test_r210_original_subscription_loss.py`, `test_r210_subscription_cash_lifecycle.py`, `test_r210_paypal_terminal_integrity.py` |
| Rata e rimborso dell'eccedenza; nessun credito wallet | `test_r210_subscription_repayment_e2e.py`, `test_r210_subscription_cash_lifecycle.py` |
| API reali locali, owner/CSRF/merchant/quote/journal, concorrenza, SIGKILL, erasure | `test_r210_subscription_cash_lifecycle.py` |

## Validazione e limiti della prova

**879 casi distinti passati, 61 nuovi, zero fallimenti/errori; 20 skip per browser non disponibile.** Il file nuovo contiene 61 casi passati; nessuno skip o xfail nuovo. Regressione finale unica sul sorgente finale senza modifiche durante l'esecuzione: `validation/r210/a5-lifecycle/financial-final.xml`; identità dei casi, SHA e inventario sorgenti nel `result.json`. Le tre aspettative precedenti sulla UI delle dispute permanenti sono state corrette per esporre la perdita ancora priva di prova, mantenendo i controlli sull'immutabilità dell'esito e sull'assenza di debito inventato. Le prove senza cassa restano negative; quelle positive ora chiudono gli stessi casi tramite il percorso di riconciliazione.

SQLite, ledger, HTTP locale, concorrenza, cancellazione account e SIGKILL Linux sono effettivi e isolati; API monetarie simulate. Gli skip esistenti `account_refund_acceptance` e `operator_refunds_ui` indicano Playwright/Chromium assenti: non sono pass o nuovo collaudo UI. Le UI IT/EN riusano le azioni esistenti; questa consegna non certifica browser o provider reale. Ruff, compilazione e i quattro gate sicurezza/inventario passano: 310 file app, 557 sorgenti runtime, 168 finding invariati (0 HIGH,21 MEDIUM,147 LOW), 780 siti esecuzione, 173 ammissione, 32 trasporto. Nessun checker, soglia, classificazione o soppressione modificato.

Restano **A4,A6,B6,C6,F4,F5,F6,G5,G6**. A4 conserva attribuzioni generali di payout/protection e movimenti ambigui non coperti; non viene promosso dal readback delle perdite originali qui provate. A6 richiede il ciclo effettivo su sandbox Stripe/PayPal. Nessuna storia commerciale pre-release da migrare, nessun commit/push/tag o esecuzione remota effettuato. Non dichiarare la RC raggiunta e non contare combinazioni di test come cicli di lavoro.

Riferimenti primari del contratto provider, consultati il 1 novembre 2026: https://developer.paypal.com/api/transaction-search/v1/search-get e https://developer.paypal.com/docs/transaction-search/transaction-event-codes/ . La documentazione non sostituisce la verifica sul conto effettivo.

Commit cumulativo suggerito: `Complete payment recovery and cash-proven subscription loss repayment`
