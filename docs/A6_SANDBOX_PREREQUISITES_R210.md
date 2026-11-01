# A6 — prerequisiti mancanti per il collaudo reale

1 novembre 2026, Europe/Rome. **RC confermata: 33/42 = 78,6%, PRE-RC. A6 resta environment_blocked.** Nessun criterio, peso o denominatore modificato. A5 resta chiuso. Il commit è differito all'utente.

Base recuperata e verificata: `MTA-0.3.0-r210-pre-RC-a5-lifecycle-cumulative.zip`, SHA-256 `a6f9809c8a53c23196e5ee6255d919e7b39771d73f8d015fe00758162ef7f651`. Nessun nuovo cumulativo software è necessario: questa verifica non modifica il codice.

## Verifica effettuata

- Letto il criterio invariato A6: `Actual Stripe and PayPal sandbox readback and lifecycle verification`.
- Nessuna variabile di configurazione Stripe, PayPal o MTA sandbox presente nell'ambiente di esecuzione. Nessuna copia di database sandbox indicata.
- Richieste HEAD prive di credenziali: Stripe `/v1/account` risponde HTTP 401; PayPal sandbox `/v1/oauth2/token` risponde HTTP 404. Sono prove di raggiungibilità HTTP, non di autenticazione, permessi o disponibilità del ciclo finanziario.
- Eseguito `tests/test_r210_real_provider_sandbox.py`: **0 passati, 2 saltati**, entrambi per assenza di opt-in e copia sandbox isolata. Nessuna accettazione provider ricavata da questi skip.
- Nessun checkout, capture, rimborso, webhook o intervento su server/GitHub effettuato.

## Input necessari per proseguire

Occorre un ambiente MTA di collaudo isolato con accesso a entrambi i provider e con dati esclusivamente di test:

| Input | Requisito |
|---|---|
| Stripe | Credenziali test, configurate come segreti locali; chiave test, webhook di test e relativo segreto. Nessuna chiave live. |
| PayPal | App e merchant sandbox, credenziali sandbox e webhook sandbox; account acquirente sandbox per l'approvazione. Permessi reporting per il readback di cassa introdotto in A5. |
| Stato MTA | Copia coerente e privata di `auth.sqlite3` sandbox e della corrispondente `.auth-secret`, con riferimenti agli ordini MTA effettivamente associati agli oggetti provider di prova. Non usare la directory dati di un servizio in esecuzione. |
| Scenari provider | Ordini/sessioni di prova, rimborsi e casi di disputa/reversal/payout creati e controllabili nel sandbox. Non usare la storia di clienti reali. |
| Esecuzione | Indicare il percorso dell'ambiente isolato accessibile al runner oppure eseguire la campagna su quell'ambiente e conservare i risultati. Le credenziali non devono essere incollate nella chat o incluse nei rapporti. |

Le variabili già riconosciute dai due test di sola lettura sono `MTA_TEST_PROVIDER_SANDBOX=1`, `MTA_SANDBOX_DATA_DIR`, `MTA_TEST_STRIPE_SANDBOX_ORDER`, `MTA_TEST_PAYPAL_SANDBOX_ORDER`; `MTA_TEST_OFFLINE` deve essere assente o diverso da `1`. I riferimenti devono appartenere alla copia sandbox e alla configurazione originale corretta.

Comando per la sola verifica iniziale di readback, dalla radice del cumulativo A5:

```bash
python -m pytest -q -rs tests/test_r210_real_provider_sandbox.py --junitxml=provider-sandbox-readback.xml
```

Il comando da solo non chiude A6: i due test leggono ordini già creati e riconciliano la copia locale; non eseguono l'intero ciclo. Non presentare due pass come accettazione completa.

## Evidenza richiesta per chiudere A6

La campagna deve collegare la versione esatta di MTA, il conto di test, gli oggetti canonici provider e i risultati effettivi del ledger isolato. Devono essere eseguiti e registrati i flussi supportati di checkout/approvazione/capture, rimborsi e risposte incerte con recupero, notifiche autenticate/replay, revoche/dispute e relativi esiti, abbonamento/rata/eccedenza, più capture e attribuzioni di payout/protection previste dal criterio. Per la cassa PayPal occorre attendere la copertura effettiva del reporting; un esito o un timestamp non sostituisce il denaro completato.

Conservare rapporti privi di segreti e dati personali, identificatori dei casi, esiti del readback canonico e del ledger, importi prima/dopo, assenza di duplicazioni ed eventuali casi non eseguibili. Un mock, uno skip, una build o una lettura HTTP non autenticata non soddisfano A6. Gli eventuali residui software di A4 non vengono convertiti in soli problemi ambientali.

Fino alla raccolta delle prove richieste A6 non è promosso. Una sua futura accettazione completa porterebbe la misura a 34/42 = 81,0%; questa percentuale non è raggiunta in questa verifica.

Commit cumulativo suggerito invariato dalla consegna A5: `Complete payment recovery and cash-proven subscription loss repayment`.