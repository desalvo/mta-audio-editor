# CPU/GPU nella Coda AI — r210

La lista utente e la lista amministrativa ora recuperano i consumi dei worker dal registro di accounting, attraverso il collegamento `queue_job_id` e lo stesso proprietario. La soluzione si applica a tutti gli adapter registrati, presenti e futuri, senza introdurre percorsi separati per lyrics, chords, markers e separazione in stem. Anche i job storici collegati al registro mostrano le misure già disponibili; i dati mancanti non possono essere ricostruiti retroattivamente.

I componenti di uno stesso job vengono sommati. La CPU finale richiede una fonte di misura riconosciuta; la GPU richiede una fonte GPU verificata e, per la profilazione certificata, la corrispondente evidenza persistita. L'assenza di una misura GPU non viene presentata come zero. Le misure di un altro utente e i record non collegati non sono usati.

Durante l'esecuzione, il supervisore pubblica campioni CPU al massimo una volta al secondo: dal cgroup dedicato quando configurato, oppure dal processo worker diretto. Questi valori sono parziali, diagnostici e non fatturabili. Il checkpoint della coda li espone con frequenza massima di circa due secondi, oltre al polling dell'interfaccia. La misura finale continua a usare i controlli esistenti di isolamento, accounting e process tree. Il percorso ACE-Step mantiene i propri contatori backend.

Le stime GPU del profiler restano esplicitamente diagnostiche. CPU e GPU diagnostiche vengono salvate insieme, evitando che l'aggiornamento di un contatore cancelli l'altro. Il tempo GPU durante l'esecuzione compare soltanto se il motore pubblica campioni: un report disponibile solo alla chiusura del profiler non consente un contatore GPU continuo.

La proiezione è in sola lettura e non cambia prezzi, fatture, esclusioni, saldo o consumi contabilizzati. Non trasforma una stima in un addebito. La verifica su hardware ROCm/LXC e sui modelli reali resta da eseguire dopo l'aggiornamento del server.
