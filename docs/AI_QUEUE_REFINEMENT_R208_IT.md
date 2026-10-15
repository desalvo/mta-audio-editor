# MTA Audio Editor 0.3.0-r208 — refinement coda e diagnostica

Questo cumulativo preserva il lavoro precedente (coda condivisa web/alcuni job legacy, amministrazione, diagnostica e wizard) e corregge:

- Il comando di annullamento legacy ora autentica l'attore e autorizza il progetto PRIMA di modificare l'evento di cancellazione.
- Se un job AI legacy è ancora in coda, l'annullamento lo marca cancellato anche nella coda SQLite, evitando che parta successivamente.
- La coda su server usa per default `/var/lib/mta/ai-jobs`, persistente e scrivibile dal servizio, anziché `/tmp`; è configurabile tramite `MTA_AI_JOB_STATE_DIR`. Le installazioni desktop native conservano un default scrivibile temporaneo.
- Gli eventi diagnostici sono scritti in JSON Lines corretto, una riga per evento.
- Test aggiuntivi per due slot simultanei, attesa del terzo job, cancellazione e default persistente.

Test mirati eseguiti localmente: 18 passati. Tentata l'intera suite: non completata entro il timeout locale. Non effettuato collaudo EL10/ROCm né eseguite GitHub Actions.

## Limiti ancora aperti (non dichiarare il lavoro completato)

- Percorsi AI sincroni e client remoti possono ancora bypassare lo scheduler centralizzato.
- I callback di alcuni job legacy sono in memoria: la coda preserva lo stato ma non può riprendere automaticamente i calcoli dopo un crash.
- Annullamento effettivo di un'inferenza GPU già partita non disponibile: occorrono processi isolati e supporto di cancellazione lato ACE-Step.
- CPU/GPU secondi attribuiti individualmente e percentuali reali dipendono da metriche del backend; `N/A` resta il valore corretto in assenza di dati affidabili.
- Prima del commit sono necessari completamento di questi punti, suite Quality integrale e verifica dei repository RPM/DEB firmati.

Nessun commit o push. Nessuna modifica al CT Proxmox 130. Versione applicativa invariata 0.3.0-r208.
