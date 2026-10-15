# MTA Audio Editor 0.3.0-r208 — chiusura riconciliazione stem con proprietà inode

## Scopo
La riconciliazione dei job stem interrotti deve cancellare esclusivamente i file prodotti dalla transazione e mai file di altri flussi comparsi dopo lo snapshot. Il progetto già salvato resta autoritativo per individuare le transazioni committed.

## Modifica
I nuovi journal `.recovered-stems-pending.json` contengono la mappa `identities`, inizialmente vuota. Il salvataggio upload registra dispositivo e inode di ogni file della transazione mediante `ai_media_identity.record_upload`. La riconciliazione elimina soltanto i file nuovi con identità registrata e invariata; i media non posseduti e gli inode sostituiti vengono preservati. I journal storici senza campo `identities` mantengono il comportamento precedente per retrocompatibilità.

## Copertura eseguita
36 test del gruppo stem superati, 8 warning. Scenari: rollback dei file registrati, preservazione dei file non registrati, sostituzione inode, preservazione committed, startup reconciliation e legacy journal. La suite r208 completa è stata avviata ma non ha terminato nel limite operativo, quindi nessuna certificazione globale è attribuita a questo rapporto.

## Limiti
La registrazione inode e l'effettivo trasferimento dei file non sono stati collaudati su un server o filesystem remoto reale; le prove sono software locali. L'eventuale crash nel brevissimo intervallo prima della registrazione dell'inode preserva il file non attribuito, anziché cancellarlo senza prova di proprietà, e può richiedere manutenzione manuale.
