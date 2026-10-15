# r208 – cancellazione dei processi ACE-Step e limiti del coordinatore

Il percorso asincrono web AI Arranger/Remix passa un evento di cancellazione allo
specifico subprocess del worker AI. Il gestore manda SIGTERM al suo gruppo di
processi e, dopo 5 secondi, SIGKILL se ancora attivo. L'eventuale traccia
prodotta non viene pubblicata quando la cancellazione è stata richiesta.
La transizione al terminale `cancelled` avviene solo dopo l'uscita del worker.

La cancellazione è implementata per il subprocess locale e non per tutti i
worker legacy che eseguono funzioni Python nello stesso processo server.
Questi ultimi restituiscono un errore esplicito se ancora in esecuzione.

La coda SQLite conserva ordine, impostazioni, stati e metriche conosciute,
ma non serializza gli oggetti callable, le credenziali o il contenuto sorgente
dell'elaborazione. Dopo un crash, i job non possono essere riavviati
automaticamente in modo sicuro: vengono indicati come `interrupted` e
richiedono un nuovo avvio esplicito.

I vecchi endpoint sincroni e alcuni worker remoti possono ancora aggirare la
coda. Per una garanzia globale serve una migrazione con protocollo idempotente
ed esecuzione controllata per *ogni* adapter, inclusi i job non-web.

Questa modifica NON costituisce certificazione del coordinamento globale, della
ripresa automatica o dei benchmark ROCm.
