## Checkpoint corrente — riscossione legacy e prove originali — 30 ottobre 2026

**RC69,0% (29/42),invariata:nessun criterio promosso;l'aumento richiesto non è ottenuto.** Leggere **LEGACY_SUBSCRIPTION_COLLECTION_R210.md** e `validation/r210/legacy-collection-result.json`. Rimborsi senza base originale registrati senza debiti ipotetici;riscossioni legacy preesistenti non verificate sospese prima del provider e dell'allocazione;account IT/EN e aggregati mostrano importi da verificare,revisione privata per proprietario. **779 casi distinti correnti passati,24 nuovi,10 skip Playwright;nessun nuovo collaudo Chromium/provider reale.** Ruff/sintassi/compilazione e quattro gate passano,senza nuovi finding o checker modificati.

A5/C3 restano aperti per prove originali quota/surplus mancanti e migrazione completa non certificata;A4 mantiene anche software/storia/movimenti da completare.Coda operativa in RC_DELIVERY_PLAN_R210.md,senza ripetere i blocchi già verificati. Cumulativo completo:**MTA-0.3.0-r210-pre-RC-legacy-collection-cumulative.zip**,include ACE e la riorganizzazione;non riapplicare il vecchio patch. Tutti i delta da4014a1f restano non committati. Nessuna azione remota.

---

Cronologia precedente,superata dove incompatibile:

# Percorso operativo verso RC — MTA 0.3.0-r210

Stato al 30 ottobre 2026: **29/42 criteri originali verificati, 69,0% verso la RC; 13 aperti; 1/7 macroaree completa (E). PRE-RC.** Questa riorganizzazione non promuove criteri. La percentuale misura l'accettazione RC, non tutte le funzionalità del prodotto.

La coda precedente ha prodotto correzioni utili senza chiudere F4: mancavano ancora runtime/dipendenze/backend ACE e prove effettive. Il nuovo ordine segue la dipendenza **A4/A5 → C3 → C5/D6**. Si lavora su un solo blocco funzionale; un impedimento concreto consente di passare a uno scenario indipendente. Le verifiche già accettate restano riutilizzabili sui confini invariati.

## Ordine di esecuzione

| Ordine | Blocco e criteri | Lavoro da completare | Condizione di uscita |
| --- | --- | --- | --- |
| 1 | Finanza generale: A4, A5, C3 | Basi originali legacy, esiti checkout non coperti, storia PayPal completa e movimenti payout/protection univoci; integrare tutte le obbligazioni con la riconciliazione | Criteri originali completi oppure impedimento preciso per lo scenario; un audit o una finestra acquisita non chiude il blocco |
| 2 | Cambio di regime: C5, D6 | Riutilizzare drain/API/UI/ripresa esistenti; collegare la clearance finanziaria generale e conservare saldi/periodi | Entrambe le direzioni attraverso API amministrativa reale, con storico provider/legacy, crash, perdita risposta e ripresa; dipende da C3 |
| 3 | Esecutori e diritti: F4, F6 | Contratti residui di interpreti/dipendenze/native/ACE, checkpoint effettivo e revisione indipendente dei diritti | Tutti gli esecutori e checkpoint del criterio originale; separare codice mancante, asset assente e prova target |
| 4 | Campagna target: A6, B6, C6, F5, G5, G6 | Sandbox, host indipendenti, cambio distribuito, applicazioni installate, container e hardware/modelli reali | Evidenze sul target con identità di sorgenti/configurazioni/artefatti; build o skip non costituiscono accettazione |

Il blocco 3 può proseguire quando uno scenario finanziario richiede prove esterne assenti. Non occorre attendere il completamento di tutti i target per sviluppare il codice indipendente. C6 ha ancora codice/integrazione da completare oltre al requisito di host indipendenti: non viene riclassificato come solo esterno. F6 richiede prove indipendenti dei diritti e non si risolve con un flag dell'operatore.

## Primo blocco concreto

Riprendere le basi originali legacy e gli esiti finanziari ancora non supportati. Prima di introdurre una migrazione, distinguere: contratto software mancante; prova originale disponibile; prova originale assente. `app/subscription_basis_audit.py` rileva già basi mancanti/conflittuali sull'intero insieme: non riscrivere l'audit. Il recupero deve vincolare ordine, proprietario, periodo, lordo, quota e surplus a prove storiche indipendenti e immutabili. Prezzi attuali, lordo PayPal e rimborsi modificabili non provano la ripartizione originale.

Per i casi con prove sufficienti, completare il recupero verificabile attraverso servizio/API e verificare ripetizione, concorrenza, inversione, cancellazione e conservazione degli obblighi originali. Per gli altri, registrare esattamente il documento o legame canonico mancante e proseguire un esito non coperto di A4/A5. Non introdurre stime di debito o scritture dirette su tabelle immutabili. La mancanza di prove originali non va presentata come solo codice da scrivere.

Riutilizzare `paypal_merchant_history.py`, `paypal_merchant_reconcile.py` e `paypal_settlement_reports.py`: collector, copertura intervalli, bridge al ledger e allocazione parziale già esistono. Restano da completare la copertura generale, i riferimenti originali e gli esiti non coperti. La sola presenza di un report o di un dispute outcome non autorizza accredito, quietanza o clearance C3.

## Evidenze indispensabili, oggi non dimostrate

| Criteri | Prerequisito preciso | Quanto esiste già e va conservato |
| --- | --- | --- |
| A4/A5/C3 | Prove storiche della ripartizione originale quota/surplus; origine/storia completa del conto; legami canonici dei movimenti; per report reali, accesso SFTP e host key approvate | Audit basi, acquisizione per intervalli, ledger bridge, recovery payout parziale; non equivalgono a clearance generale |
| F4 | Runtime/dipendenze e checkpoint autorizzato effettivo, identità del backend ACE e accettazione dei confini residui | Contratti MT3, rifiuti pre-ledger, policy e prova Apple; non equivalgono all'intero criterio |
| F6 | Asset realmente installati con licenze/provenienza/revisioni indipendenti per ogni checkpoint | Cataloghi e pin identificano byte; non concedono diritti ulteriori |
| A6 | Ambienti Stripe test e PayPal sandbox isolati, storie canoniche complete e autorizzazione alle operazioni necessarie | Due readback esistenti coprono solo parte del lifecycle |
| B6/C6 | Autorità e worker su host indipendenti, controllo di perdita/partizione/drain; per C6, transizione generale completata | SIGKILL/TLS/processi locali e B2 accettato; nessuna nuova certificazione multi-host |
| F5/G6 | App installate sui sistemi supportati, modelli autorizzati, GPU, plugin VST reali e hardware audio | Build e regressioni native pregresse conservate |
| G5 | Docker, Podman e Kubernetes effettivi con persistenza/restart/ingress/worker | Gate di build container storico; esecuzione completa ancora aperta |

Questa pianificazione non autorizza operazioni su provider/server o nuovi dispatch CI. I prerequisiti target vanno registrati senza ripetere sonde sugli stessi strumenti assenti.

## Regola di completamento e resoconto

Ogni blocco parte da uno scenario di accettazione originale e termina con criterio completo o impedimento concreto, indicante scenario, tipo di mancanza, artefatto/ambiente richiesto, evidenze conservate e prossima azione indipendente. Un nuovo helper, una variante di test o un fix UI non definiscono una consegna funzionale.

Eseguire le regressioni dei confini modificati e i gate pertinenti; conservare le evidenze fallite e gli skip. Riutilizzare prove accettate con sorgenti e confini invariati. Non ripetere B2, loader MT3, rifiuti API o la race ACE per aumentare conteggi. Dopo il commit dell'utente controllare Quality/SAST ordinari; non avviare CI remota automaticamente.

Ogni aggiornamento e consegna riporta **percentuale RC, criteri verificati/42, nuovi criteri accettati e impedimento principale**. Nessuna previsione numerica di avanzamento, data RC o numero di cicli sostituisce l'accettazione. Stato di questa consegna: **69,0% (29/42), nessun nuovo criterio**.

## Ripresa e consegna

La fonte autorevole dei 42 criteri resta `DEVELOPMENT_COMPONENTS_R210.json`; la coda eseguibile è `RC_EXECUTION_STRATEGY_R210.json`. I testi, pesi e stati originali sono invariati. Otto criteri restano implementation/review pending e cinque environment_blocked; il piano descrive i prerequisiti aggiuntivi senza cambiare queste classificazioni.

Base completa più recente: `MTA-0.3.0-r210-pre-RC-ace-observer-isolation-cumulative.zip`, SHA256 `ff08b5549904981ffb1950c87987feabb6bfa6fd1d6490e3e2af73614cf860f0`. Contiene tutti i delta da `4014a1fd5bfccc4e7f65c32345cb4c52f98f3d8d`. Applicare a questa base il solo delta documentale della riorganizzazione; nessun ZIP intermedio aggiuntivo. Alla prossima chiusura funzionale sostanziale produrre un unico cumulativo completo. Le versioni precedenti di coda/strategia sono conservate in `development-history`.

Nessun sorgente applicativo, test, dipendenza, gate di sicurezza, criterio, versione o flag di abilitazione modificato in questa riorganizzazione. Nessuna nuova regressione applicativa o prova target dichiarata. Commit/staging/push/tag/release restano differiti; il cambio generale resta disabilitato.
