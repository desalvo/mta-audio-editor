# MTA 0.3.0-r208 — cancellazione effettiva del worker remoto

## Perimetro concluso
Il gateway remoto `/api/ai-jobs/execute` e l'endpoint di trasporto audio autenticato usano l'ID idempotente persistito per controllare la cancellazione durante l'esecuzione del worker amministrato. Il controllo viene propagato all'esecutore `wait4` oppure `cgroup v2`, che termina il gruppo di processi e non restituisce output fatturabile quando il job è cancellato. L'API risponde 409 per i job effettivamente cancellati.

## Verifiche
- Test con subprocess che dorme 20 secondi: interrotto prima del timeout al segnale di cancellazione.
- Test di successo senza cancellazione.
- Test di cancellazione immediata.
- Regressioni r208 + processo: 821 test superati nel container di sviluppo.

## Limiti
Questo completa l'arresto cooperativo dei **worker subprocess avviati tramite execute_registered_worker**; non garantisce l'interruzione immediata delle chiamate HTTP bloccate né dei provider esterni che non eseguono i modelli tramite l'esecutore amministrato. In ambienti cgroup, la delega e il contenimento effettivo richiedono collaudo su EL10. Nessuna GPU certificata è stata provata e non vengono fatturati consumi GPU dedotti dai tempi. Nessun commit o push eseguito.
