# Archivio e installer eseguibili — r208

La regressione globale ha isolato un fallimento nel test dell'installer ACE-Step:
lo script era stato incluso in alcuni ZIP cumulativi senza i bit Unix di esecuzione.
Il packaging ora ripristina i bit di esecuzione per gli entry-point shell nella
cartella scripts, anche quando l'archivio sorgente è stato estratto da un tool che
ha perso i permessi. Lo ZIP registra i permessi mediante external_attr.
Non sono stati eseguiti installer né modificati host o GPU reali.
