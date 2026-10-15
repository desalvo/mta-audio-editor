# Console operatore per file stem orfani — 0.3.0-r208

L'interfaccia web della configurazione AI nativa ora rende possibile consultare gli elenchi server-side dei file stem preservati dopo il recupero e degli artifact in quarantena per il progetto attualmente aperto. Le azioni disponibili sono: visualizzare gli elenchi, spostare un file preservato in quarantena e ripristinare un elemento dalla quarantena. Nessuna cancellazione definitiva automatica.

Ogni richiesta è associata all'ID del progetto selezionato; dopo ogni operazione si aggiorna l'inventario. Una variazione del progetto durante l'operazione impedisce l'aggiornamento della vista con dati di un progetto diverso. Le operazioni mutative richiedono conferma, sono serializzate lato interfaccia e sfruttano l'autorizzazione e il lock server-side già implementati. Il testo proveniente dalle API viene aggiunto al DOM con textContent, non interpolato come markup HTML.

Certificazione: test operator-console e regressione di quarantena/ripristino. Non sono stati condotti test interattivi su browser reali; non si considerano completate le macroaree indipendenti di billing, worker lifecycle o regressione globale.
