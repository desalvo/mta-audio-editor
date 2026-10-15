# Recupero diretto per richiesta AI remota (r208)

Il download dalla cronologia nativa non scansiona più le prime 10.000 richieste completate. Interroga `GET /api/ai-jobs/request-status/{request_key}` con il bearer token configurato, ricevendo uno stato limitato al proprietario dal server, e permette il download soltanto per lo stato `completed`. Il download effettivo resta demandato al percorso attestato `recover_after_lost_response`, senza nuova inferenza e senza abilitare importazioni senza journal locale. Le richieste non completate o non appartenenti al token non sono scaricabili. I test coprono il recupero di richieste non presenti nelle pagine iniziali, oltre al mancato download di richieste non completate.

Non sostituisce i collaudi GPU, il recovery end-to-end delle singole famiglie di modelli e le prove native multipiattaforma.
