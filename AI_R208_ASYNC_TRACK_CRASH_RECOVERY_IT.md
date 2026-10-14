# MTA 0.3.0-r208 — Recovery upload tracce asincrone

I caricamenti `/api/projects/{pid}/track-import-jobs` registrano ora, **prima di copiare i byte**, una ricevuta persistente per job in `.async-track-{job_id}.pending.json` nella cartella del progetto. L'identificativo permette l'esistenza di job concorrenti indipendenti. La ricevuta contiene soltanto quattro nomi di destinazione prestabiliti (audio caricato e conversioni a 44.1/48/96 kHz) e viene sincronizzata su disco con `fsync`.

All'avvio il server analizza le ricevute sotto il lock cross-process del progetto: conserva qualunque traccia o sorgente di libreria già referenziata e rimuove **solo** i file esplicitamente nominati nella ricevuta e non presenti nel progetto persistente. La riconciliazione non esegue sweep dei file prodotti da altri writer. Ricevute invalide o symlink interrompono l'eliminazione in modalità fail-closed. Il worker tenta la riconciliazione finale dopo il salvataggio o l'errore.

Limiti: questa chiusura riguarda i file `audio/` dell'importazione asincrona, non eventuali copie degli originali né tutti gli altri writer. Un errore persistente nel journal richiede risoluzione manuale. L'avvio su più processi deve essere verificato operativamente; ROCm e billing GPU non sono interessati.

Verifiche locali: 971 test r208/r207 superati, 9 warning, inclusi 5 casi mirati su cleanup, commit, non-interferenza e journal fail-closed.
