# r208 — Serializzazione dei commit asincroni della separazione stem

Il worker `_stem_split_worker` ora serializza la pubblicazione del batch stem attraverso `project_publication_lock(project_id)`. Il caricamento del progetto avviene soltanto dopo aver acquisito il lock; copia/conversione e singolo `save_project` avvengono nella sezione critica, così da evitare snapshot obsoleti e perdite di tracce per pubblicazioni concorrenti. Le inferenze rimangono fuori dal lock.

Anche il commit della stima BPM acquisisce il lock dopo aver calcolato i valori, ricarica il progetto e aggiorna BPM/metrica. Gli arricchimenti Lyrics e Chords acquisiscono il lock prima di caricare e modificare il progetto. Attenzione: gli arricchimenti, in questa versione, conservano il lock durante l'analisi; ciò garantisce la serializzazione ma può ritardare altre scritture sullo stesso progetto.

Sono stati aggiornati tre test di regressione precedentemente legati all'indentazione sorgente e aggiunti due controlli che verificano lo scope dei lock. Suite eseguita: 925 passed, 9 warnings. Non sono stati eseguiti test hardware, GPU o di server remoto reale. Non è una transazione cross-filesystem e non copre automaticamente tutti gli altri writer asincroni.
