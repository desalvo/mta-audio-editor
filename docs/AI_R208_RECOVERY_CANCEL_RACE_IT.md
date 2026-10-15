# MTA 0.3.0-r208 — Race tra riconciliazione e cancellazione

Intervento sul recupero delle richieste remote già pubblicate: la verifica della cache può sovrapporsi a una cancellazione o a una finalizzazione fallita. In questa condizione la finalizzazione SQL resta condizionale sullo stato `admitted`, ma l'API di riconciliazione ora rilegge lo stato terminale concorrente e lo restituisce senza trasformare una race legittima in un errore HTTP 500. Uno stato `cancelled` o `failed` non viene mai sovrascritto.

Aggiunta validazione robusta del tipo dell'identificativo per `request_status`; input diversi da stringa generano ValueError anziché TypeError.

Verifiche: 809 test r208/r207 idempotency superati; compilazione e sintassi installer da verificare in packaging. Non sono 100 interventi funzionali indipendenti. Restano aperti arresto fisico cooperativo del worker remoto, attribuzione GPU per singolo job, integrazione contabile completa degli adapter e certificazione su EL10/ROCm.
