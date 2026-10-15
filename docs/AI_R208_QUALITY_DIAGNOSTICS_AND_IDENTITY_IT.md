# r208 — Identità degli import remoti e diagnostica CI

- Le tracce WAV recuperate dal server includono **tipo di worker** e **ID completo della richiesta** nel nome: `Recovered AI <kind> <request_id>`.
- Il controllo duplicati distingue worker diversi che hanno emesso lo stesso request ID, mantenendo il blocco per una seconda importazione del medesimo risultato.
- Il workflow `quality` produce `pytest-results.xml`, indica i 30 test più lenti e registra gli esiti non superati. Il report JUnit e l'eventuale report coverage sono caricati anche se la fase test fallisce.
- Il timeout del job rimane 150 minuti, mentre pytest ha 140 minuti per completarsi.
- La suite completa precedente è incompleta: i fallimenti osservati non equivalgono a errori risolti. La certificazione globale rimane aperta.

## Limiti
La scelta del progetto per un recupero senza journal rimane esplicita. Nessun collaudo su GPU o infrastruttura reale è stato eseguito.
