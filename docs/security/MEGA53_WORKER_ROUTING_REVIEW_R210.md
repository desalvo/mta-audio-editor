# Revisione instradamento Mega 53 — r210

La separazione usa il percorso worker esistente `drumsep`, selezionato dal server o dalla configurazione nativa. Il client non sceglie eseguibili o percorsi; il modello esplicito continua a passare dalla policy di licenza, dall'identità del worker registrato e dalla contabilizzazione già esistenti. Un errore remoto non attiva un fallback locale. La pre-verifica riguarda solo l'ambiente nativo locale o il worker unificato sul medesimo host: non assume informazioni su worker pull o remoti separati e non concede autorizzazioni di esecuzione.

Il risultato accetta soltanto l'insieme esatto di nomi previsti, dati WAV validi e un insieme limitato di target; non utilizza nomi di file provenienti dal worker per costruire destinazioni arbitrarie. Il controllo di cancellazione è eseguito prima e dopo il trasferimento. Le categorie di errore cgroup sono marcatori fissi e le informazioni diagnostiche non riportano percorsi o stderr arbitrari. Sono state preservate le politiche sui checkpoint: hash v1.0.21 verificato al caricamento e nessun download automatico.

La nuova scansione Bandit ha 181 finding: 0 HIGH, 21 MEDIUM e 160 LOW, senza soppressioni. Quattro finding preesistenti cambiano numero di riga senza modifiche al relativo codice e mantengono le rispettive motivazioni; non sono emersi nuovi finding. Le revisioni degli inventari mantengono 817 confini di esecuzione, 179 siti admission e 32 di trasporto con forme AST invariate. Queste verifiche non certificano i pesi, la qualità di separazione o il codice presente su un worker esterno.

Evidenza: `tests/test_r210_mega53_worker_routing.py`, `validation/r210-mega53-worker-routing.xml`, `validation/r210-mega53-security-gates.xml` e `docs/validation/r210/mega53-worker-routing/`.
