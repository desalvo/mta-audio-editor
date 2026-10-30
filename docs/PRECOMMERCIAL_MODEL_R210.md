# MTA0.3.0-r210 — modello pre-commerciale semplificato

**RC attuale:76,2% (32/42),perimetro v2 autorizzato dall'utente.** Il vecchio perimetro resta29/42=69,0%:non sono7,2punti di implementazione comparabili sulla vecchia migrazione generale. C3/C5/D6 sono stati riscritti per la prima attivazione e accettati dopo verifiche reali. Macroaree complete nel perimetro attuale:D ed E(2/7). PRE-RC;10criteri ancora aperti.

## Decisione e comportamento

L'utente conferma che billing commerciale e rimborsi non sono mai stati attivati e autorizza la semplificazione. Non serve importare una storia commerciale pre-release inesistente. Nessun dato economico viene eliminato o ricostruito per ottenere idoneità.

Il profilo **precommercial-no-payment-history-1** consente la configurazione anticipata di Stripe/PayPal e dei prezzi futuri:configurazione e credenziali non equivalgono a un incasso. Qualsiasi ordine,refund,eventi finanziari,intenti incerti,obbligo monetario esistente o schema sconosciuto impedisce invece l'attivazione. Consumi NC,saldi,periodi e rendiconti sono conservati esattamente.

La transizione usa l'API amministrativa esistente con modalità locale dell'autorità esplicitamente abilitata,preview esatta,controlli del servizio,conferma e recupero in avanti. I flag e i server reali non sono modificati. Le due direzioni sono supportate **prima dell'avvio dei checkout**. Dopo l'avvio dei checkout,anche se la risposta è persa,il cambio automatico con storia monetaria non è supportato da questo profilo:richiede un percorso finanziario separato,escluso dalla RC semplificata. Questo limite è indicato nel pannello IT/EN.

Un marcatore immutabile e privo di dati personali registra l'avvio nella stessa transazione di ammissione checkout,prima del dispatch. Non scade,non viene cancellato dall'erasure di un account e non può essere modificato/cancellato da SQL ordinario. Un'origine parziale o alterata blocca il profilo.

## Nuovi pagamenti e rimborsi

Gli abbonamenti salvano quota,lordo e surplus prima di contattare PayPal,riusando la base immutabile già esistente:nessuna nuova tabella di preventivi e nessun backfill storico. Prezzi di listino successivi non riscrivono l'ordine. Anche una variazione inferiore a un centesimo del debito originale impedisce una nuova capture. Un preventivo non pagato resta distinto da una base finanziata;VOID/annullamento non crea un falso debito o un falso problema legacy.

Il recupero merchant introdotto nel cumulativo precedente è esteso ai nuovi abbonamenti con quota originale e alle repayment con target originale verificato. Restano incasso netto,rimborsi,dispute,replay e recupero senza nuovo dispatch. Un documento già completato ma incoerente con il debito originale viene trattenuto per revisione,mai adattato al prezzo corrente.

## Cambio di perimetro RC

42pesi uguali e42ID conservati. La definizione precedente completa è archiviata in `docs/development-history/precommercial-scope-20261030/`;il confronto machine-readable è `validation/r210/precommercial-model/scope-comparison.json`. Nessuna chiusura del criterio v1 sulla migrazione finanziaria generale viene dichiarata.

|ID|Stato v1|Definizione v2|Stato v2|
|---|---|---|---|
|A4|implementation_pending|Canonical history for payments created by this release, refunded initial captures, exact multicapture attribution and unresolved ambiguous PayPal dispute/payout movements; no import of pre-release merchant history|implementation_pending|
|A5|implementation_pending|New checkout/refund/reversal lifecycle with immutable original quotes, terminal and uncertain response recovery and subscription repayment; no adoption of pre-release financial obligations|implementation_pending|
|C3|implementation_pending|Transactional absence of monetary checkout/refund/history and unknown financial schemas before pre-commercial activation; no legacy financial migration|verified|
|C5|implementation_pending|Enabled local-authority administrator API activation and two-way mode changes before commercial checkout starts, with exact preview, drain, replay and forward crash recovery; post-checkout migration unsupported|verified|
|D6|implementation_pending|Preserve balances, periods and measured non-commercial statements across pre-commercial administrator activation and recovery|verified|

I37criteri non elencati mantengono testo,stato e peso. A4/A5 restano da completare per gli esiti dei nuovi pagamenti,non per importare conti commerciali precedenti.

## Verifica

- **894test finanziari/regime passati nell'ultima esecuzione completa,0fallimenti/0skip. 938casi distinti correnti** includendo accettazione e inventari pertinenti senza doppio conteggio.
-23casi nei due nuovi file,più un parametro aggiuntivo con provider/prezzi preparati nel collaudo che esegue davvero un worker NC misurato e ne conserva il rendiconto.
-API reale:preparazione provider,attivazione,ritorno pre-checkout,staleness preview,origine immutabile,storia inattesa,crash mirror/recupero,idempotenza e conservazione byte-per-byte dei record finanziari.
-Confronto di9casi sui sorgenti precedenti:7fallimenti e2pass,documentati. Il primo run esteso conservava una vecchia attesa di rifiuto per sole credenziali:il caso ora usa un evento economico vero,che resta bloccante. L'intera esecuzione finale passa.
-Ruff app/tests,compilazione Python e sintassi JS passano. Bandit168finding invariati(0HIGH/21MEDIUM/147LOW),309sorgenti. Inventari556sorgenti/780confini,309sorgenti/173siti e21sorgenti/30trasporti. Checker,soglie,soppressioni e classificazioni non modificati;solo hash sorgenti e una riga inventario spostata da200a202.
-Nessun nuovo collaudo browser,sandbox reale,multihost,container/installazione OS,GPU o hardware. Nessuna nuova CI remota. Il precedente blocco Chromium resta documentato e i test browser restano nel pacchetto.

## Consegna e ripresa

Cumulativo:**MTA-0.3.0-r210-pre-RC-precommercial-model-cumulative.zip**. Include anche il precedente recupero PayPal ancora non committato;baseline Git verde sempre`da300396a8dc9f7b84703565959b4df36dd7c15e`(CI41129584447). Sorgenti,asset,licenze e log originali conservati con metadati ZIP e CRC verificati.

Commit cumulativo suggerito: `Simplify commercial launch, freeze quotes and recover PayPal checkouts`

Nessun commit/staging/push/tag/rilascio/dispatchCI,configurazione di server o operazione reale su provider eseguita. Restano A4,A5,A6,B6,C6,F4,F5,F6,G5,G6. Dati monetari inattesi bloccano il modello:non vengono cancellati per rendere il database apparentemente nuovo.
