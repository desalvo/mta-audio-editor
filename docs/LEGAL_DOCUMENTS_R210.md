# Documenti privacy e termini del server — r210

Sono inclusi quattro documenti HTML IT/EN, pubblici e stampabili, con logo, indice, data di efficacia e versione. Le route non richiedono login. Il login e l’auto-registrazione mostrano i quattro collegamenti; le stesse risorse sono incluse nei payload Docker, RPM/DEB e app native attraverso le directory `app/docs`, `app/templates` e `app/static`.

| Documento | URL prevista dopo l’aggiornamento del server |
| --- | --- |
| Privacy IT | https://mta.apps.desalvo.eu/privacy/it |
| Privacy EN | https://mta.apps.desalvo.eu/privacy/en |
| Termini IT | https://mta.apps.desalvo.eu/terms/it |
| Terms EN | https://mta.apps.desalvo.eu/terms/en |

`/privacy` e `/terms` selezionano la lingua dal parametro `lang=it` o `lang=en`, oppure dalla lingua iniziale dell’header Accept-Language, con inglese come fallback. I link espliciti di lingua sono sempre disponibili. Il pulsante Stampa / Salva PDF usa la stampa del browser: non è richiesta una dipendenza PDF aggiuntiva sul server.

## Dati dell’istanza e revisione

Aprire **Impostazioni → Privacy e termini** come amministratore. Inserire titolare/prestatore effettivo, sede, Paese, email privacy e assistenza, identificativi fiscali/registro ove applicabili, DPO e rappresentanti ove richiesti. Dichiarare in entrambe le lingue:

- hosting, Paesi di conservazione e accesso;
- fornitori effettivi di infrastruttura, SMTP, SSO, assistenza e AI esterna, categorie di dati e ruoli;
- eventuali trasferimenti fuori SEE, destinazioni, strumenti giuridici, misure e accesso alle garanzie;
- periodi o criteri di conservazione e basi per dati operativi, contabilità, log, email/outbox, account pendenti, backup, digest di identità e quarantena; gestione concreta delle richieste privacy e delle cancellazioni.

Le informazioni pubblicate sono testi, mai HTML fornito dall’admin. Non inserire password, token, chiavi, percorsi interni riservati o credenziali. La conferma di revisione è consentita solo quando tutti i dati richiesti sono presenti. Prima di allora i documenti restano consultabili con un avviso di incompletezza. Una casella di revisione esprime una dichiarazione del gestore: non certifica la conformità normativa.

Ogni modifica salva una revisione con autore e data nella cronologia amministrativa persistente; una modifica parziale senza nuova conferma revoca lo stato verificato. I giorni di conservazione nei documenti riflettono `account_retention_config`. Una variazione di questi valori invalida la revisione dei documenti finché il gestore non la rinnova. I testi e le dichiarazioni amministrative precedenti vanno conservati secondo la politica del gestore; questa funzionalità registra le configurazioni, non costituisce un sistema di firma né una prova di accettazione individuale dei termini.

Le API `GET/PUT /api/admin/legal-settings` richiedono una sessione admin; le mutazioni richiedono inoltre l’header d’integrità same-origin. Le pagine pubbliche non espongono la cronologia e non creano o migrano il database durante il rendering.

## Ambito dei testi e condizioni da verificare

L’informativa riflette funzioni effettive: registrazione con approvazione e MFA email/TOTP, SSO facoltativo, inferenze remote associate a token, accounting distinto dalle stime, progetti e voci, email transazionali, cookie tecnici e preferenze locali, diagnostica, disattivazione, archivi e quarantena. Un account chiuso normalmente conserva accounting e riserve di identità. I digest HMAC sono pseudonimi: non si promette che siano anonimi o eliminati automaticamente.

I valori di default di 60 giorni per i progetti e 365 per la quarantena sono opzioni tecniche già presenti, non scadenze legali universali. Il diritto alla cancellazione e i termini per rispondere alle richieste devono essere valutati autonomamente. Se una conservazione non ha più base giuridica, il gestore deve cancellare o anonimizzare, adeguando anche la procedura operativa e i backup; il semplice documento non implementa una nuova gestione automatica di ogni richiesta GDPR. La riserva persistente di username/email richiede una giustificazione e un riesame concreto.

I termini riguardano il servizio, senza sostituire la licenza EUPL 1.2 del codice. Tutelano diritti inderogabili, contestazioni, conformità dei servizi digitali e recesso ove applicabile. Non introducono un checkout, nuovi prezzi, una rinuncia automatica al recesso o un consenso privacy generale. Prima di nuove vendite occorrono informazioni economiche, eventuale modulo di recesso, registrazione dell’accettazione e conferme richieste. Un DPA e l’eventuale accordo commerciale sono separati. Non sono state implementate nuove notifiche automatiche di modifica delle policy: il gestore deve gestirle prima delle modifiche sostanziali.

I riferimenti internazionali si applicano solo quando ricorrono i relativi presupposti; nessun testo standard garantisce da solo conformità in ogni Paese. Occorre una verifica professionale sull’istanza reale, sui contratti con i fornitori e sulle attività offerte, prima di dichiarare completata la documentazione. Non sono stati modificati il server pubblico o la revisione dell’app, che resta **0.3.0-r210**.

## Fonti ufficiali verificate il 18 ottobre 2026

- GDPR: https://eur-lex.europa.eu/eli/reg/2016/679/oj/?locale=it
- EDPB, basi giuridiche: https://www.edpb.europa.eu/sme/be-compliant/process-personal-data-lawfully_en
- EDPB, diritti e termini delle richieste: https://www.edpb.europa.eu/sme/find-practical-info/faq_en
- EDPB, ruoli: https://www.edpb.europa.eu/sme/learn-the-basics/data-controller-or-data-processor_en
- EDPB, trasferimenti internazionali: https://www.edpb.europa.eu/sme/be-compliant/international-data-transfers_en
- Garante, esercizio dei diritti: https://www.garanteprivacy.it/home/diritti/come-agire-per-tutelare-i-tuoi-dati-personali
- Cookie: https://europa.eu/youreurope/business/growing/digitalising/online-privacy/index_en.htm
- Clausole abusive: https://commission.europa.eu/law/law-topic/consumer-protection-law/consumer-contract-law/unfair-contract-terms-directive_en
- Servizi digitali: https://eur-lex.europa.eu/eli/dir/2019/770/oj/eng
- Diritti dei consumatori: https://eur-lex.europa.eu/eli/dir/2011/83/oj/eng (consultare versione consolidata vigente)
- Commercio elettronico: https://eur-lex.europa.eu/eli/dir/2000/31/oj/eng
- AI Act, trasparenza: https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50
- UK: https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/
- Svizzera: https://www.edoeb.admin.ch/en/privacy-statements-on-the-internet
- California: https://oag.ca.gov/privacy/ccpa

- Dismissione ODR: https://eur-lex.europa.eu/eli/reg/2024/3228/oj/eng
