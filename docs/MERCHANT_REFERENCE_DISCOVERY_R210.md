# MTA 0.3.0-r210 — recupero PayPal da risposta di creazione persa

**RC:69,0% (29/42),invariata. L'incremento percentuale richiesto non è stato ottenuto;nessun criterio originale completo è stato chiuso.** Il flusso concreto descritto sotto è invece implementato e verificato fino al ledger.

## Baseline confermata

Commit utente `da300396a8dc9f7b84703565959b4df36dd7c15e`,tree `4bca9324a11d00df7212011af2feff0eca1d85b9`. Tutti i4328blob tracciati coincidono con il cumulativo CI41125 recuperato prima del lavoro. CI41129584447 verde:Quality7689passati/50skip,copertura76,58%;SAST,SDK,container e build desktop/mobile riusciti,pubblicazioni saltate. Questi risultati appartengono alla baseline,non al nuovo codice.

## Prima e dopo

Prima,un incasso presente nello storico PayPal ma con risposta di creazione persa lasciava `provider_order` vuoto e l'outbox `uncertain`:anche se l'ordine locale originale esisteva,il pannello dello storico chiedeva di recuperarne manualmente il riferimento remoto.

Ora l'azione già esistente **Riconcilia ordine originale / Reconcile original order** segue l'osservazione immutabile fino al refund/capture canonico e al suo ordine autenticato. Soltanto i due identificatori dell'unità canonica,insieme a importo,merchant,ambiente,ordine locale e tentativo di creazione originale,permettono di recuperare il riferimento. Note,subject e identificatori del report non diventano autorità sul proprietario o sul denaro.

Il servizio rilegge la storia completa dei rimborsi e verifica stabilità del documento prima dell'associazione;ricontrolla amministratore,snapshot,configurazione,ordine e documento canonico nella transazione che conferma il riferimento. L'associazione non concede credito né chiude il fence. La riconciliazione originale rilegge poi rimborsi e dispute e applica atomicamente il saldo netto. Il caso verificato incassa5€,ha4€di rimborsi e accredita1€,anche partendo da capture già REFUNDED/PARTIALLY_REFUNDED.

Una perdita di risposta dopo l'associazione si recupera dalla stessa azione;errori nel binding o nel regolamento annullano soltanto la relativa transazione completa. Concorrenza e replay non ricreano il checkout,non inviano capture/refund e non raddoppiano il credito. L'acquisizione token OAuth del trasporto esistente resta distinta dalle operazioni monetarie. Il pannello IT/EN e l'API amministrativa già presenti usano il nuovo percorso senza introdurre nuove autorizzazioni o parametri client.

## Limite finanziario mantenuto

Il nuovo recupero automatico riguarda **ordini credits**. Gli abbonamenti e le repayment con riferimento perso non vengono adottati senza prova originale della quota/surplus o del target:prezzo corrente e importo lordo non bastano. L'ordine locale originale mancante non viene creato da etichette o importi del report. Non è certificata la copertura dell'intero conto né autorizzato il cambio generale di regime.

Questi sono blocchi reali di A4/A5/C3,non criteri ridotti per far salire il conteggio. A4 richiede ancora storia generale e movimenti payout/protection;A5/C3 richiedono prove originali e recupero completo delle obbligazioni/esiti residui. C5/D6 restano dipendenti dalla clearance generale. I criteri target e diritti restano quelli della coda originale.

## Verifiche

- **232test passati,0fallimenti,8skip Chromium;34nuovi casi non browser**. Inclusi merchant/refunds/capture multipli,legacy collection,reference recovery,report di settlement,range e copertura.
- Prima del fix:30casi della nuova suite contro i sorgenti originali,12fallimenti riprodotti e18rifiuti già corretti. Quattro ulteriori casi su risposte malformate sono verificati sul codice finale.
- API amministrativa reale:autenticazione,ruoli,CSRF,body esatto,no-store,associazione e credito reale del ledger. Ripresa,concorrenza e rollback controllati.
- Ruff su app/tests,compilazione Python,Bandit e tre inventari passano. Bandit168finding invariati:0HIGH/21MEDIUM/147LOW;nessun ID nuovo/rimosso. Inventari555sorgenti/780confini,308sorgenti/173siti,21sorgenti/30trasporti. Checker,soglie,disposizioni e soppressioni invariati.
- Otto casi aggiuntivi del pannello reale IT/EN,mobile/desktop,capture/refund sono predisposti riusando il collaudo applicativo esistente. **Non eseguiti**:downloadChromium negato con HTTP403 `Domain not in allowlist`. Non sono sostituiti da un simulatore DOM e non vengono contati come passati.
- Nessuna nuova CI remota,nuova full-suite,operazione su provider/server o accettazione hardware/multihost dichiarata.

Prove in `docs/validation/r210/merchant-reference-discovery/`. Cumulativo completo:**MTA-0.3.0-r210-pre-RC-merchant-reference-discovery-cumulative.zip**. Versione,asset,licenze,sorgenti e log precedenti conservati con i metadati ZIP originali.

Commit cumulativo suggerito dal commitda300396: `Recover lost PayPal credit checkout references from merchant history`

Nessun commit/staging/push/tag/dispatchCI/rilascio eseguito. Il nuovo codice è non committato;il precedente fix drain è già nel commit verde da300396.
