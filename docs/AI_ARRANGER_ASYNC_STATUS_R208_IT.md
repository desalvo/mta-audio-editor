# Generazione ACE-Step asincrona, stato e progresso — r208

- La web UI avvia un job tramite `POST /api/projects/{pid}/ai-arranger/start-generation` oppure `/remix/start-generation` (HTTP 202), ricevendo immediatamente un `job_id`.
- Interroga `GET /api/projects/{pid}/ai-arranger/active-generation` ogni 2 secondi. Il controllo di autorizzazione è eseguito sul progetto prima di restituire lo stato.
- Esiste un unico slot di generazione web attivo per istanza host: file lock POSIX condiviso fra processi; una nuova richiesta riceve HTTP 409, **non** viene accodata.
- Stati: `idle`, `running`, `busy` (altro progetto), `completed`, `failed`, `interrupted` (riavvio del processo). Le informazioni non espongono job di altri progetti.
- Per ACE-Step l'adapter scrive le fasi `uploading`, `queued`, `inference`, `downloading`. Se `/query_result` fornisce un valore `progress` numerico 0–100, la barra mostra quel dato. In assenza di progresso documentato, resta indeterminata: il tempo trascorso e la fase rimangono visibili.
- La generazione continua dopo chiusura della finestra browser, finché il processo server rimane attivo. Non esiste ripresa automatica del calcolo dopo riavvio; lo stato viene marcato `interrupted`.
- Il sistema non implementa una coda, né annullamento del calcolo in esecuzione, né persistenza durevole di più job. Il vecchio endpoint sincrono rimane per compatibilità e andrà migrato o ritirato dopo verifica degli altri client.
- La validazione dell'audio generato e l'aggiunta non distruttiva della nuova traccia restano quelle del flusso r208 già esistente.
- Nessun test GPU/EL10 reale è stato effettuato qui.
