# MTA Audio Editor 0.3.0-r208 — serializzazione delle importazioni tracce

## Problema
Le importazioni WAV, JSON e ZIP di risultati AI recuperati utilizzavano già `project_publication_lock`, mentre l'endpoint generale `POST /api/projects/{pid}/tracks` leggeva e salvava il progetto senza quel lock. Due scritture concorrenti potevano salvare snapshot diversi e perdere una traccia.

## Modifica
La route pubblica `add_track` acquisisce adesso il lock cross-process del progetto *prima* di caricare il progetto. La routine `_add_track_under_project_lock` gestisce il lavoro effettivo ed è utilizzata dalla route di recupero WAV che detiene già il medesimo lock, evitando un deadlock da doppia acquisizione.

I test verificano l'acquisizione, il rilascio in caso di errore e la compatibilità delle importazioni recuperate. Tutte le 899 verifiche della suite r208 e delle rotte native r207 selezionate passano localmente. Non sono inclusi test reali multi-processo o su hardware.

## Limiti
Gli altri endpoint che modificano direttamente un progetto (es. sostituzioni, editing, cancellazioni) non sono ancora stati uniformati: questo intervento impedisce le collisioni fra importazione ordinaria, pubblicazione AI e importazioni recuperate, ma non garantisce isolamento globale di ogni mutazione del progetto.
