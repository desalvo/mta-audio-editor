# Storage, prova gratuita e permessi di billing · 0.3.0-r210

## Italiano

### Quote storage e prezzo

Ogni abbonamento include la capienza configurata nel catalogo amministrativo. Un'estensione a pagamento aumenta la **quota assegnata**, non la misura dei file effettivamente presenti. La formula è:

`costo = GiB extra a pagamento × ore di assegnazione × tariffa ordinaria EUR/GiB·h`

Si usa la tariffa storage già configurata in Billing (`disk_gb_hours`, milionesimi di EUR per GiB-ora; 1 GiB = 1024³ byte). L'integrazione usa i secondi effettivi e divide gli intervalli a variazioni di quota, tariffa, giorno UTC e abbonamento. Non si addebitano ore future. Esempio: quota inclusa 5 GiB, quota assegnata 8 GiB, tariffa EUR 0,01/GiB·h: 3 GiB per due ore costano EUR 0,06 anche se i file occupano meno della capienza assegnata. Ridurre la quota a 5 GiB ferma i costi successivi senza annullare i precedenti.

L'admin ha un comando dedicato **Assegnazione storage (contratto corrente)**: imposta la quota totale e può selezionare **Concedi gratuitamente tutto lo storage extra**, con motivazione. La modifica non riavvia il periodo CPU/GPU. Le estensioni gratuite sono visibili nei report con costo zero. Il prezzo base di un piano promo gratuito non rende automaticamente gratuite le estensioni a pagamento.

L'utente può aumentare o ridurre la capienza extra dal profilo; l'aumento richiede crediti disponibili e una tariffa positiva e mostra il costo orario prima della conferma. La riduzione non può sottrarre la capienza inclusa o gratuita. I file non vengono cancellati al superamento della quota: viene impedita ulteriore crescita. I costi della capienza extra maturano fino alla riduzione o alla fine dell'abbonamento, anche se i crediti si esauriscono; il saldo può diventare negativo. L'amministratore può concedere gratuitamente l'estensione oppure ridurla.

Le estensioni seguono il totale di quota assegnato anche al rinnovo: se il nuovo piano include più spazio, diminuisce l'extra a pagamento; se ne include meno, l'extra aumenta. I precedenti acquisti prepagati del vecchio package conservano la copertura fino alla fine del periodo originale e non vengono addebitati di nuovo. Nessuna migrazione cancella file o restituisce retroattivamente gli acquisti già effettuati.

### Riepiloghi

Il profilo mostra extra a pagamento e gratuito, GiB-ora, intervalli, durata, tariffa e costo nel periodo corrente. Un selettore inizio/fine permette report personalizzati con ora locale, convertita in UTC. La pagina Billing mostra gli stessi intervalli per il periodo selezionato, anche personalizzato, filtrabile per utente. L'occupazione reale dei file rimane separata dalla capienza fatturata. Gli addebiti storage sono contabilizzati una sola volta nel saldo crediti; la consultazione ripetuta di un report non aggiunge nuovi addebiti. La consultazione di un periodo passato non restituisce i crediti già consumati.

### Prova gratuita

La prova è gratuita per **7 × 24 ore**, con le quote CPU/GPU/storage del settimanale al momento dell'attivazione. Si può usare una sola volta per account; annullare, riattivare o cambiare piano non ripristina l'idoneità. La scelta iniziale presenta schede con prezzo e risorse di tutti i piani e consente di scegliere subito il piano successivo, predefinito settimanale.

Durante la prova si può cambiare il prossimo piano o interrompere il rinnovo. Il piano scelto prende effetto alla scadenza, senza azzerare prima le quote della prova. Il primo rinnovo conserva prezzo e risorse mostrati alla scelta; i rinnovi successivi seguono il catalogo. Il rinnovo addebita crediti una sola volta; se il saldo non basta, il piano resta in attesa e nuovi job/crescita storage sono bloccati fino alla ricarica. Non è presente un gateway di pagamento.

### Permessi per utente

- `subscriptions_allowed`: attivo per default per i nuovi utenti; può essere disabilitato dall'admin. Consente di sottoscrivere e cambiare il piano successivo quando anche le opzioni globali abbonamenti/attivazione autonoma sono abilitate. Non iscrive automaticamente a un piano e non interrompe un contratto già attivo.
- `credit_billing`: disattivo per default; solo l'admin può abilitarlo. Senza abbonamento, addebita l'intero consumo CPU/GPU valido e lo storage occupato misurato alle tariffe ordinarie. I job catturano la modalità all'ammissione; cambiare il flag non modifica il contratto di un job già partito.
- Senza abbonamento e senza billing a crediti: valgono le quote manuali, con consumi registrati ed esposti ma senza addebiti. La disdetta torna a questa modalità alla scadenza. Le quote manuali restano limiti effettivi anche se si abilita il billing a consumo.

Il billing storage occupato senza abbonamento richiede misure adiacenti valide (gap massimo 26 ore), usa date di abilitazione/disabilitazione e tariffe storicizzate e non si sovrappone alla copertura di un abbonamento. Dati assenti o non validi non vengono trasformati in consumi fatturabili. Le funzionalità precedenti di fatturazione ordinaria/amministrativa restano disponibili; l'opzione a crediti senza abbonamento è esplicita e distinta.

### API e aggiornamento

Permessi admin: `PATCH /api/admin/subscriptions/users/{uid}/policy`. Quota admin: `PUT /api/admin/subscriptions/users/{uid}/storage` (`quota_bytes`, `free`, `reason`). Quota personale: `PUT /api/account/subscription/storage` (`quota_bytes`, `request_id`, `max_rate_micro`). Report: `GET /api/account/subscription/storage-report?start=...&end=...` o variante admin per utente. Rinnovo: `POST /api/account/subscription/renewal`. L'attivazione della prova accetta `plan: trial`, prezzo zero e facoltativamente `next_plan`/`next_price_micro`. Le API conservano autenticazione, ruolo e CSRF.

Le nuove tabelle hanno chiavi esterne agli utenti/job e sono incluse dai meccanismi generici di dump/restore e cancellazione privacy. Gli eventi quota e gli addebiti costituiscono dati contabili. Aggiornare con il normale flusso RPM/DEB r210 e riavviare il servizio; nessuna reinstallazione dei modelli AI richiesta. Non sono stati eseguiti commit, pubblicazioni o interventi sul server reale.

## English

Each plan includes its configured storage allowance. Paid storage is **assigned quota above the included allowance**, charged for its actual allocation interval at the configured historical EUR/GiB-hour rate. It is independent of occupied file bytes. For example, 3 extra GiB for two hours at EUR 0.01/GiB-hour costs EUR 0.06. Reductions stop future accrual without reversing previous hours; future hours are not prepaid. UTC-day, tariff, quota and subscription boundaries split the report.

Administrators can update total capacity on the current contract and explicitly grant all extra storage free of charge, with a reason, without resetting CPU/GPU periods. Users can increase or reduce paid capacity, but cannot remove included or free capacity. Extensions retain their total assigned target across renewals; the new plan's included capacity determines the remaining paid excess. Old prepaid purchases retain their original coverage until expiry. Quota or credit exhaustion never automatically deletes files. Assigned extra capacity continues accruing costs until reduced or the subscription ends, and the balance may become negative.

Profile reports show paid/free GiB, duration, GiB-hours, historical rates and costs for the current period or custom date/time ranges. Billing shows the same intervals for its selected user and billing/custom period. Occupied storage remains a separate statistic. Storage debits are reflected once in the credit balance; repeated or historical report reads do not duplicate or refund them.

The one-time free trial lasts **7 × 24 hours**, inheriting weekly allowances at activation. Plan cards disclose resources and price. The default next plan is weekly; users may select another at trial activation, change it during the trial or cancel renewal. The first renewal honors the selected quote; subsequent renewals use the catalog. Insufficient credit pauses access to the renewed plan until funded. No payment gateway is implemented.

Per-user `subscriptions_allowed` defaults to enabled, subject to the global subscription/self-service switches; no automatic enrollment occurs. Administrators may disable it without cancelling an existing contract. `credit_billing` defaults to disabled and only administrators may enable it. Without an active subscription, this explicitly charges valid CPU/GPU usage and observed occupied storage at ordinary rates. Otherwise configured manual quotas apply, usage is recorded and displayed without charges. Cancellation returns the user to that manual mode at expiry. Manual limits remain effective even with pay-as-you-go credit billing.

CPU/GPU jobs freeze their charging mode at admission. Occupied-storage credit billing uses effective-dated policy changes and adjacent valid measurements no more than 26 hours apart, without overlapping subscription coverage. Missing/invalid measurements do not become charges. Existing ordinary administrative billing remains available as a distinct feature.

Owner/admin APIs are listed above; existing role, authentication and CSRF protections apply. New tables participate in generic dump/restore and privacy erasure via user/job foreign keys. Quota events and debit records are accounting data. Deploy through the normal r210 package flow and restart; AI models need no reinstallation. Real-server, real-SMTP, native GUI and ROCm validation remain operator checks.
