> Stato aggiornato / Updated state: [SUBSCRIPTION_ONLY_CREDITS_DEVICE_R210.md](SUBSCRIPTION_ONLY_CREDITS_DEVICE_R210.md). Le descrizioni precedenti sono storiche.

> Aggiornamento / Update: per le regole correnti di accesso, crediti nominali, tetti di spesa CPU/GPU e tariffe iniziali vedere [CREDIT_ACCESS_NATIVE_TIMELINE_R210.md](CREDIT_ACCESS_NATIVE_TIMELINE_R210.md). Le indicazioni precedenti di arresto per crediti esauriti e saldo CPU/GPU negativo sono superate. / Previous credit-exhaustion cancellation and negative compute-balance rules are superseded.

# Quote, abbonamenti, crediti e documenti legali / Quotas, subscriptions, credits and legal documents

Release: **0.3.0-r210**. Nessun commit, push, tag, release o aggiornamento dei server reali eseguito da questo intervento.

## Italiano

### Attivazione e valori iniziali

La sezione amministrativa **Abbonamenti e crediti** consente di abilitare gli abbonamenti e, separatamente, l'attivazione autonoma da parte degli utenti. Entrambe le opzioni sono inizialmente disattivate. Le quote CPU/GPU individuali possono essere assegnate anche senza abbonamenti: in quel caso sono giornaliere e i consumi restano gratuiti salvo abilitazione amministrativa esplicita del billing a crediti senza abbonamento. Nessun utente viene iscritto automaticamente a un piano. I nuovi utenti mantengono la quota storage ordinaria di 5 GiB.

Gli amministratori sono senza quote per default. I nuovi admin hanno quota storage zero nel modello storico, dove zero significa illimitato; nei nuovi contratti zero significa invece nessuna risorsa disponibile e null significa illimitato. La migrazione conserva gli eventuali limiti admin preesistenti diversi dal precedente default automatico di 5 GiB. Un limite admin può essere assegnato esplicitamente. Gli admin restano protetti da disabilitazione ed eliminazione.

| Piano | CPU per periodo | GPU per periodo | Capienza storage | Fattore rispetto alla base giornaliera |
| --- | ---: | ---: | ---: | ---: |
| Giornaliero | 4 h | 4 h | 5 GiB | 100% |
| Settimanale | 35 h | 35 h | 6,25 GiB | 125% |
| Mensile | 180 h | 180 h | 7,5 GiB | 150% |
| Trimestrale | 630 h | 630 h | 8,75 GiB | 175% |
| Annuale | 2.920 h | 2.920 h | 10 GiB | 200% |

CPU e GPU sono quantità complessive del periodo, non quantità rinnovate ogni giorno nei piani più lunghi. I valori nominali usano 7/30/90/365 giorni e fattori crescenti fino al 200% annuale. Lo storage è una capienza, non un consumo cumulativo in byte. Sono tutte impostazioni modificabili, comprese le tariffe ordinarie per categoria già presenti in Billing.

I periodi iniziano all'assegnazione: giorno e settimana durano 24 ore e 7 giorni; mese, trimestre e anno seguono il calendario UTC conservando l'ancora originale, anche dopo mesi più corti e anni bisestili. L'interfaccia visualizza gli estremi locali. Le modifiche al catalogo valgono dal periodo seguente; quello in corso conserva quote e prezzo. Un'assegnazione amministrativa esplicita avvia un nuovo contratto e chiude il precedente. Le risorse non utilizzate non si accumulano. La fine del periodo non cancella i file.

### Crediti e billing

I crediti sono un saldo prepagato in EUR, registrato in milionesimi di euro con causale, operatore, data e identificatore idempotente. Solo un admin può aggiungerli manualmente. Non è stato introdotto un gateway di pagamento o un checkout. I prezzi dei piani partono da zero; un admin può modificarli. Un motivo promo/gratuito rende gratuito il prezzo base del piano assegnato, senza eliminare le sue quote.

Il prezzo del piano, se presente, viene prelevato dai crediti una sola volta per periodo. In mancanza di fondi il rinnovo resta in attesa: non vengono consentiti nuovi job o crescita dello storage finché non viene finanziato. L'attivazione autonoma richiede l'opzione amministrativa dedicata, mostra il prezzo e impedisce di riattivare il piano per azzerare il periodo corrente. È possibile interrompere il rinnovo a fine periodo. Al termine di un contratto interrotto si torna alle quote manuali del profilo; i consumi continuano a essere registrati e non sono addebitati, salvo il billing a crediti esplicitamente abilitato dall’admin.

L'utente può abilitare l'extra quota CPU/GPU tramite crediti. I consumi extra vengono valorizzati alle tariffe ordinarie delle categorie CPU second e GPU second, con decorrenza al momento di avvio del job. La quota e il consumo sono condivisi fra web e tutti i token dell'utente. I job soggetti a quota vengono serializzati per utente per evitare ammissioni concorrenti sulla stessa disponibilità. Le misure verificate hanno precedenza; le stime diagnostiche accettate restano distinguibili.

Il calcolo incluso nel contratto e l'extra quota finanziato tramite crediti non vengono addebitati una seconda volta nel billing ordinario. Le quantità fisiche rimangono registrate; i movimenti dei crediti e gli extra sono consultabili separatamente. I job di contratti precedenti non vengono rivalutati cambiando il catalogo. L'esclusione amministrativa di un job dai consumi rimuove anche il relativo addebito extra dal saldo corrente; le fatture già chiuse mantengono i controlli esistenti e richiedono rettifiche esplicite.

Lo storage extra è ora una variazione della quota assegnata, non una prenotazione prepagata fino a fine periodo. Si contabilizzano i GiB di capienza oltre la quota inclusa del piano, per la durata effettiva dell’assegnazione, usando la tariffa ordinaria GiB-ora storicizzata. Lo spazio occupato dai file resta una metrica distinta. Riduzioni, rinnovi e cambi tariffa suddividono gli intervalli; non vengono addebitate ore future. L’admin può concedere tutta l’estensione gratuitamente con motivazione, senza riavviare il contratto. I vecchi acquisti prepagati conservano la copertura originale fino a scadenza. L’utente può ridurre la propria estensione senza rimuovere la quota inclusa o gratuita. I file non sono eliminati automaticamente se la quota viene ridotta o i crediti si esauriscono. Si veda `STORAGE_QUOTAS_TRIALS_R210.md` per esempi, prova gratuita, permessi e API.

### Misure, limiti e avvisi

La CPU è tempo CPU, non tempo trascorso; la GPU segue il contatore per job disponibile. I controlli live usano i campioni del worker e richiedono la cancellazione quando quota o credito sono esauriti. Non possono arrestare il processo esattamente sul secondo finale: il ritardo di campionamento e arresto può produrre un piccolo superamento. Se è stato autorizzato l'extra, un saldo residuo insufficiente alla misura finale può diventare negativo e blocca i job successivi finché viene reintegrato. Con extra disattivato il solo ritardo di arresto non autorizza un prelievo di crediti.

I campioni diagnostici di job interrotti possono concorrere alle quote e allo storico, senza trasformarsi automaticamente in misure fatturabili o addebiti GPU validi nel ledger. I dati mancanti, non finiti o negativi non vengono inventati. Senza telemetria live non è possibile garantire un limite hardware puntuale: l'ammissione successiva usa i consumi disponibili. Non viene modificata la protezione sul metering invalido e non viene creata una misura GPU a partire dal carico anonimo dell'host.

Ogni job è attribuito al periodo in cui è iniziato, mantenendo lo stesso contratto durante l'esecuzione anche oltre il confine del periodo. È una regola di attribuzione contabile, non una ripartizione temporale dei kernel. L'energia GPU non è inclusa nelle ore GPU e non viene stimata.

Le soglie 80%, 90% e 95% generano al massimo un avviso per risorsa, utente e periodo. Gli avvisi contengono utilizzo, limite, periodo e link al profilo; con abbonamenti abilitati includono anche il link alla relativa gestione. L'outbox è persistente, con tentativi e Message-ID stabile. SMTP/SMTPS deve essere configurato; i destinatari devono avere un indirizzo verificato e un account attivo. La coda conserva gli avvisi in attesa di configurazione o recupero SMTP. Come ogni invio SMTP, un crash dopo l'accettazione remota può causare una ripetizione.

Il profilo, nella sezione collassabile **Limiti e Quote**, mostra anche tabella e grafici degli ultimi 30 giorni UTC. Lo storico è disponibile senza quote. CPU/GPU sono attribuite al giorno di avvio del job; lo storage è il picco giornaliero osservato dei file appartenenti all'utente, contando gli inode condivisi una volta. Non viene ricostruito uno storage passato inesistente. I job senza una misura disponibile sono segnalati e non devono essere interpretati come consumo zero.

### Privacy e termini

Le URL rimangono `/privacy/it`, `/privacy/en`, `/terms/it`, `/terms/en`, con PDF dinamico aggiungendo `.pdf`. I documenti usano la terza persona, omettono i dati non compilati e non presentano il preambolo di documento da completare. Gli indicatori amministrativi di completezza e revisione restano disponibili. Il PDF privacy conserva ora anche le categorie della tabella HTML che il renderer precedente ometteva.

Un cambiamento effettivo dei dati dei documenti o dei tempi di conservazione accoda una notifica professionale HTML agli utenti registrati, con i campi modificati e link diretti ai documenti nella lingua del profilo. Salvare nuovamente gli stessi dati non genera un altro avviso. Nessuna email reale è stata inviata durante lo sviluppo. La notifica non sostituisce un eventuale consenso o un'accettazione contrattuale richiesti dalla disciplina applicabile.

### API, verifiche e installazione

Le API personali sono sotto `/api/account/subscription`; quelle amministrative sotto `/api/admin/subscriptions`. Autenticazione, ruoli e protezione CSRF riutilizzano il percorso dell'applicazione. Le nuove tabelle sono incluse nei meccanismi generici di dump, restore, conservazione e cancellazione dei dati utente. I crediti e i contratti contano come dati contabili per le protezioni del lifecycle.

I risultati esatti sono in `validation/r210-subscriptions-*.xml`, `.log` e nel report JSON. Sono inclusi test delle quote, concorrenza, crediti, rinnovi, calendari, SMTP simulato, autorizzazioni, storico, PDF e i due test della CI segnalata nel log del 18 ottobre. Non sono state eseguite prove GUI su Windows/macOS o inferenze sul server ROCm. L'aggiornamento richiede il normale RPM r210 prodotto da Matrix/Publish e il riavvio di MTA; non richiede reinstallazione dei modelli AI.

## English

### Defaults and periods

**Subscriptions and credits** is an administrator section with separate switches for subscriptions and self-service activation; both default to off. Manual CPU/GPU quotas work independently as daily limits. Usage is free unless an administrator explicitly enables pay-as-you-go credit billing without a subscription. Users are not automatically enrolled. New ordinary accounts retain 5 GiB storage; administrators are unlimited by default, with existing explicit custom limits preserved.

Default period allowances are: daily 4 CPU hours / 4 GPU hours / 5 GiB; weekly 35 / 35 / 6.25 GiB; monthly 180 / 180 / 7.5 GiB; quarterly 630 / 630 / 8.75 GiB; yearly 2,920 / 2,920 / 10 GiB. Compute uses nominal 1/7/30/90/365 days with 100/125/150/175/200% multipliers. Storage is capacity, not cumulative byte consumption. All values are editable.

Daily and weekly periods last 24 hours and seven days from assignment. Monthly, quarterly and yearly periods follow the UTC calendar, retaining the original anchor through short months and leap years. Current period allowances and price are frozen; catalog changes apply next period. An explicit admin reassignment starts a new contract and closes the old one. Unused allowances do not accumulate. Period expiration does not delete files.

### Credits and accounting

Credits are prepaid EUR millionths with operator, timestamp, reason and idempotency ID. Only administrators grant credits; no payment gateway is implemented. Plan prices initially equal zero and are editable. An administrator promotion reason waives the base plan fee while retaining quotas. The base fee is debited once per period; unfunded renewals block new inference and storage growth. Self-service activation requires explicit administrator enablement and cannot reset an active period. Renewal may be stopped at period end; the account then falls back to manual profile quotas and free recorded usage unless the administrator explicitly enabled pay-as-you-go credit billing.

Users can opt into CPU/GPU overages using credits. Actual settled excess is priced at ordinary category tariffs effective at job start. Quotas aggregate all user tokens and web jobs. Quota-controlled jobs serialize per user to prevent concurrent admission against the same balance. Verified measurements take precedence; accepted diagnostic estimates remain labelled estimates.

Subscription compute and credit-funded excess are not invoiced again as ordinary compute. Physical quantities remain in accounting; credit movements and overages are shown separately. Catalog edits do not reprice previous contracts. Administrative accounting exclusion removes the corresponding excess charge from the current balance, subject to existing protections for closed invoices.

Additional storage now changes assigned capacity without prepaying future hours. GiB above the plan allowance are integrated over the actual allocation interval at historical GiB-hour tariffs. Actual occupied files remain a separate metric. Administrators may grant extensions free of charge without restarting the contract. Reductions, renewal boundaries and tariff changes split the intervals. Existing prepaid purchases retain their original coverage until expiry. Included and free capacity is not billed again; no files are automatically deleted when quota or credits run out. See `STORAGE_QUOTAS_TRIALS_R210.md` for examples, trials, permissions and APIs.

CPU hours are CPU time, not elapsed time. GPU hours use available job-scoped telemetry. Live samples request cancellation at exhaustion, but sampling and termination delays can overshoot the last allowance. With overages authorized, final excess can make the balance negative, blocking subsequent jobs until replenished. A termination delay alone does not authorize credit spending when overages are off. Missing telemetry cannot guarantee a precise hardware cutoff and is not invented.

Diagnostics from interrupted jobs can consume quotas and appear in history without becoming valid billable GPU evidence. Invalid metering protections remain. Each job belongs to its start period for its entire execution; this is accounting attribution rather than a temporal split of kernel capture. GPU energy is not inferred or included in GPU hours.

### Notices, history and legal documents

80%, 90% and 95% warnings are deduplicated per resource, user and period. They include usage, allowance, period and direct profile links, plus subscription management when enabled. A persistent SMTP outbox retries delivery with stable Message-IDs; active accounts and verified email are required. SMTP failures do not discard notices. As with any SMTP delivery, a crash after remote acceptance can cause duplication.

The collapsible **Limits and Quotas** profile section includes the last 30 UTC days as tables and charts even without quotas. Compute is attributed to job start date. Storage is the observed daily peak of user-owned files, with shared inodes counted once. Unavailable historical storage is not reconstructed; jobs with missing measurements are marked.

Privacy and terms remain at `/privacy/en`, `/privacy/it`, `/terms/en`, `/terms/it`, with `.pdf` dynamic variants. They use third-person language, omit unset data and no longer show an incomplete-instance preamble. Admin completeness/review indicators remain. Privacy PDFs now preserve all data categories previously omitted by the HTML-table renderer.

Actual legal disclosure or retention-setting changes enqueue localized professional HTML notices identifying changed fields and linking directly to the documents. No-op saves do not enqueue another notice. Notifications do not replace any legally required consent or acceptance. Development used simulated SMTP only.

Personal endpoints are under `/api/account/subscription`; administrator endpoints under `/api/admin/subscriptions`. Existing authentication, role and CSRF controls apply. Generic user dump/restore and erasure machinery includes the new tables; credits and contracts are treated as accounting records. Test results are in `validation/r210-subscriptions-*`. No live native GUI or ROCm validation was performed. Install through the normal r210 RPM Matrix/Publish flow and restart MTA; AI model reinstallation is unnecessary.

I crediti CPU/GPU addebitati sono distinti dagli importi ordinari nei report per token e nelle email. La cancellazione prima dell’esecuzione libera la prenotazione contabile solo quando la coda conferma che il job non è mai iniziato.

CPU/GPU credit debits are separate from ordinary invoice amounts in per-token reports and email. Pre-execution cancellation releases accounting reservations only when the queue confirms the job never started.
