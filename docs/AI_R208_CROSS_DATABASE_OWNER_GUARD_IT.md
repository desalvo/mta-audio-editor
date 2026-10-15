# MTA Audio Editor r208 — associazione sicura scheduler/ledger

La registrazione di una finalizzazione billing ora esegue controlli su **entrambi** i database: (1) il job AI durevole contiene `schema_version=1` e `actor_user_id` autenticato; (2) lo stesso utente coincide con quello indicato nella richiesta di settlement; (3) il record nel ledger appartiene al medesimo utente; (4) l'operazione dell'inferenza corrisponde al tipo nel ledger. Un payload JSON corrotto è rifiutato.

Questi vincoli evitano che il solo possesso di un job contabile dello stesso tipo sia sufficiente per associare un'altra inferenza appartenente a un utente differente. I vecchi fixture/test con payload privi di `schema_version=1` mantengono la precedente compatibilità: tali percorsi legacy **non sono equivalenti a una attestazione autenticata** e richiedono ulteriore migrazione.

Verifica locale: `PYTHONPATH=. pytest -q tests/test_r208*` → 288 test superati. Restano da completare il metering GPU attestato per job, la copertura billing remota e i test di crash reali. Nessuna certificazione ROCm implicita.
