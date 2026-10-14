# Regressione globale Python r208 — suddivisione riproducibile

La suite globale include anche test precedenti alla r208; non coincide con `tests/test_r208_*`.

`python scripts/run_global_regression_shard.py --shards 8 --shard 0 --list-only` mostra i moduli inclusi nel gruppo 0. Il criterio SHA-256 sul percorso è stabile e non dipende dall'ordine del filesystem. Ciascun gruppo esegue moduli completi e produce un JUnit XML più un riepilogo JSON. Timeout, assenza di report e fallimenti producono codici d'uscita non nulli.

Il workflow `.github/workflows/global-regression-shards.yml`, avviabile manualmente, esegue gli otto gruppi con `fail-fast: false`, così conserva gli esiti di tutti i gruppi indipendentemente da un singolo errore. I report vengono caricati anche quando pytest fallisce.

**Limiti**: l'esecuzione dei singoli gruppi non è la prova che la suite globale monolitica passi; eventuali dipendenze tra moduli/test e difetti di isolamento devono essere analizzati separatamente. I benchmark GPU, i server reali e gli installer multipiattaforma non sono coperti. Solo il completamento con successo di tutti gli otto gruppi costituisce evidenza della regressione Python suddivisa.
