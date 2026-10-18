# Cancellazione utenti, dump e Coda AI — 0.3.0-r210

Questo intervento parte dal pacchetto già committato `MTA-r210-sso-branding-admin-email-links-cumulative.zip`. Tutti i 1753 file di quel pacchetto rimangono presenti; le modifiche ai test precedenti aggiornano soltanto le aspettative alla nuova politica di cancellazione e di protezione admin.

## Modifiche

- In Archivi utenti cancellati: pulsante rosso per eliminare immediatamente account, token/sessioni, progetti posseduti, condivisioni, archivi, sandbox riconducibili all’account, dati contabili e righe/ricevute collegate ai job. Una sola conferma; nessuna nuova quarantena. Gestiti anche gli account già rimossi dalle vecchie versioni. Journal privato per riprendere un errore di filesystem, eliminato al completamento.
- Tutti gli admin sono protetti anche nel backend: non possono essere disabilitati, declassati o cancellati. Le verifiche vengono ripetute nelle transazioni di modifica per evitare aggiramenti concorrenti.
- Dump globale dalla Web App: utenti e progetti ricercabili e selezionabili, inclusione automatica di tutti i progetti degli utenti selezionati e degli admin necessari al ripristino. Snapshot SQLite selettivi: i dati degli utenti esclusi non vengono nascosti soltanto nel frontend, ma rimossi dalla copia esportata. Conservati chiavi, impostazioni centrali, stato diagnostica e catalogo/blacklist modelli, storico, accounting/billing, archivi pertinenti e risultati AI non scaduti identificabili. Modelli e ambienti installati esclusi perché reinstallabili.
- Ledger centrale mantenuto stabile durante la copia dell’outbox contabile: non si esporta un acknowledgement applicato insieme a un ledger precedente. Manutenzione temporanea del traffico applicativo durante il dump; gli health check rimangono disponibili.
- Restore verificato a servizio fermo, su directory vuote e separate, disponibile anche come `python -m app.restore_dump` nel pacchetto server. Anteprima di integrità dall’interfaccia. SHA-256 per file, percorsi controllati, rifiuto di link/duplicati, limiti, integrità DB, admin attivo e validazione dei progetti; rollback delle destinazioni pubblicate in caso di errore ordinario. Nessuna fusione o sovrascrittura di account esistenti. Vedere `APPLICATION_DUMP_RESTORE_R210.md` e `/docs/admin/application-dump`.
- Coda AI amministrativa: colonna Utente con username, nome e ID; ricerca anche per queste informazioni e, per gli admin, email. Identità esplicita persistita per stem, estrazioni e download modelli; recupero dei job storici solo da un collegamento contabile univoco, senza attribuire arbitrariamente il lavoro al proprietario del progetto.
- Consumi dei job: lettura dalle misure del ledger collegato; test del percorso reale di un subprocesso stem fino alla coda amministrativa e al record contabile. Nessuna conversione di stime, GPU mancanti o accounting non isolato in misure fatturabili.
- Privacy e termini IT/EN e guida account aggiornati alla nuova procedura. Le scadenze ordinarie e delle sandbox storiche non eliminate manualmente rimangono configurabili.

## Verifiche

- Regressione generale: 3808 passati, 5 saltati, 10 esclusi per i limiti AF_UNIX noti di questo ambiente, nessun errore.
- Verifica mirata finale dopo gli ultimi controlli di coerenza snapshot: 101 passati, nessun errore; inclusi restore selettivo, rifiuto di archivi alterati e percorsi non sicuri, rollback, preservazione degli altri utenti, cancellazione di vecchie sandbox, protezione multi-admin, lock contabile, stato diagnostica/catalogo, health durante manutenzione e CPU del worker stem.
- 40 test di integrazione aggiuntivi passati, inclusa la regressione dei download modelli; Ruff e sintassi Node dei quattro file JS modificati verificati.
- La verifica completa sui sorgenti definitivi supera anche i 18 controlli di lock/pubblicazione/import. I precedenti errori di ispezione dovuti a una modifica del file durante una prima esecuzione sono stati eliminati ripetendo la suite a sorgenti fermi.
- Anteprima statica interna della nuova UI; nessuna prova dichiarata su browser o applicazioni native reali.

## Limiti e prova sul server

Non sono state effettuate inferenze ROCm/ACE-Step/Demucs sul server dell’utente, né operazioni di cancellazione sui suoi dati. Dopo l’aggiornamento avviare un nuovo job stem: controllare utente, secondi CPU, eventuale GPU verificata e corrispondenza nei consumi contabili. Un vecchio job senza misure valide non può essere ricostruito inventando secondi; GPU assente o solo diagnostica rimane non fatturabile. Il test di subprocesso usa un backend controllato per produrre artefatti stem e consumare CPU reale, non carica i pesi Demucs e non certifica l’hardware ROCm.

I modelli/Python, configurazione OS/service/proxy e copie già esportate non sono un backup gestito dall’app. Il restore richiede configurazione dei percorsi e verifica dei runtime prima del riavvio. Copie scaricate, email già consegnate e log esterni devono essere gestiti separatamente. Gli alias che vecchie versioni avevano già scollegato irreversibilmente dall’identità non sono ricostruibili dal solo digest; vengono eliminate tutte le riserve ancora associate e quelle storiche riconoscibili.

La revisione resta 0.3.0-r210. Nessun commit, push, tag o release eseguito.

Commit suggerito:
`Add permanent user erasure, protected admins, selective backup restore, and AI job ownership and metering links`
