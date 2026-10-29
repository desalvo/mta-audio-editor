# MTA r210 — Acquisizione merchant riprendibile

28 ottobre 2026, Europe/Rome. PRE-RC: 28/42 (66,7%), E completa 1/7. Nessun criterio originale promosso; aumento numerico richiesto non conseguito. Nessuna modifica a Git/GitHub/server/provider reali, commit differito. Baseline committata confermata4c3c73afe6d3829aad155c23f5f1bbb6d375433a;full CI40584085026 conservata per quella revisione. Cumulativo precedente merchant-coverage SHA114459ac67958a88ba914ec5f99c131efd2e6091ee6504a71247c4d55e2b3fc3 conservato integralmente.

È ora disponibile un percorso operativo di acquisizione, oltre all'audit offline: `scripts/acquire_merchant_range.py` legge un solo vuoto temporale per invocazione, massimo31 giorni, fino a un intervallo esplicito massimo1096 giorni già concluso. Le finestre esistenti vengono verificate e riutilizzate. Nessun rimpiazzo automatico degli snapshot discordanti. Ripetere lo stesso comando riparte dal primo vuoto; se tutto è già coperto non viene eseguita alcuna richiesta al provider. Due riletture stabili e commit originale dello snapshot restano il protocollo di acquisizione esistente.

La conferma è obbligatoria, come l'amministratore attivo e merchant/ambiente espliciti. L'identità merchant attesa è verificata anche dentro l'acquisizione, prima dei GET, per impedire il cambio del conto tra pianificazione e lettura. La configurazione viene ricontrollata nel normale commit dello snapshot e dopo l'acquisizione. Una modifica o un errore interrompe il passo; le prove già salvate rimangono disponibili e non vengono riclassificate come vuote. Non esistono nuovi POST di capture/refund, accrediti, assegnazioni di ordini o deroghe al ledger. Durante drain attivo l'acquisizione nuova rimane soggetta ai controlli esistenti; il recupero di ordini originali usa il bridge separato precedente.

Eseguire sul nodo autorità configurato, con servizio aperto e il suo ambiente MTA:

```bash
python scripts/acquire_merchant_range.py --actor ID_ADMIN --start 2026-07-01T00:00:00Z --end 2026-09-15T00:00:00Z --environment sandbox --fingerprint SHA256_CLIENT_ID --confirm
```

Il fingerprint è quello merchant già presente negli snapshot; non passare segreti o client ID in chiaro. Codici uscita:0 intervallo richiesto coperto;2 passo salvato,restano vuoti e occorre ripetere lo stesso comando;1 errore/blocco da verificare. Ogni invocazione esegue al massimo un'acquisizione e rimane soggetta ai limiti preesistenti di20 pagine/2000 righe/timeout e120 snapshot/32MiB. Un limite raggiunto non viene aggirato. Prima di riprendere dopo un errore controllare configurazione e prove originali. Gli errori CLI non stampano credenziali o documenti provider.

Copertura richiesta non equivale all'intera vita del conto, freschezza o quietanza economica. Tutti i flag complete_account_history,ledger_reconciled,transition_authorized,release_candidate rimangono falsi. L'origine e la completezza dello storico più vecchio, i payout/protection senza allocazione univoca e la quota/surplus legacy restano problemi aperti. Questo percorso non abilita il cambio di regime. Non promuovere A4/C3 dalla sola acquisizione di finestre vuote.

Verifica:106 casi interessati passati (45 funzionali e61 gate),9 nuovi. Le prove simulano il trasporto GET del provider,usano il database applicativo reale e verificano tre finestre adiacenti,riuso di una finestra intermedia,ripetizione senza rete,ripresa dopo errore,attore/conferma/merchant/range invalidi e verifica interna del merchant prima della rete. Nessun sandbox/provider reale contattato. Ruff completo app/native/tests/scripts e compilazione passano. Bandit301 sorgenti/164 finding revisionati invariati(0HIGH/21MEDIUM/143LOW),170 confini C2,30 trasporti in21file,544 sorgenti runtime/782 punti. Nessuna disposizione nuova,soppressione,soglia o checker indebolito. UI,F3modello/HTTPS,Chromium e fullCI invariate non ripetute. Report esatti in validation/r210/merchant-range-result.json.

Restano14 criteri originali: A4,A5,B2,C3,C5,C6,D6,F4,F6 e5 target A6,B6,F5,G5,G6. Kernel cgroup locale non scrivibile; Docker/Podman/Kubernetes non installati: non dichiarare accettazione di questi target. Restano anche vere dipendenze di codice/prova finanziaria; non classificarle tutte come esterne. Prossimo intervento: completare prove univoche dei movimenti payout/protection e riferimenti originali mancanti,poi basi legacy e clearance generale C3;riusare collector,coverage e bridge già consegnati.

Unico cumulativo: MTA-0.3.0-r210-pre-RC-merchant-range-cumulative.zip. Conserva tutti i percorsi di ingresso,log originali,asset,manuali,licenze,modalità e metadati ZIP. Nessun modello/runtime/browser aggiunto. Commit cumulativo suggerito,non eseguito:

`Complete guarded execution, administration and resumable merchant recovery`
