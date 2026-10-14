# MTA Audio Editor 0.3.0-r208 — registro persistente dei file stem preservati

## Ambito e risultato

La riconciliazione di una transazione stem incompleta elimina soltanto i file
attribuiti alla transazione con identità invariata. Un file estraneo o sostituito
è preservato. Il precedente riepilogo numerico era presente soltanto nell'esito
del recovery; il journal veniva quindi rimosso senza lasciare la lista dei file
conservati. Adesso viene salvato nel progetto un registro persistente
`.recovered-stems-preserved.json` con formato versione 1 e voci
`receipt`, `file` (relativo al progetto), `reason` (`unowned` o
`identity_changed`).

Il registro viene aggiornato in modalità atomica e sincronizzato su disco
**prima** della rimozione del journal. Eventuali recovery successivi accumulano
le voci senza duplicare le stesse informazioni. Un registro simbolico oppure
illeggibile/non valido blocca la conclusione del journal; nessun file estraneo
viene eliminato per correggere l'incongruenza. I file preservati non vengono
cancellati automaticamente: la decisione deve essere dell'operatore dopo
ispezione del progetto e delle dipendenze.

## Verifica

`PYTHONPATH=. pytest -q tests/test_r208_recovered_stem* tests/test_r208_stem_* tests/test_r208_stem_durable_orphan_audit.py --disable-warnings --maxfail=1`

Risultato in questo ambiente: **40 passed, 8 warnings**.

La verifica copre registro persistente, aggregazione tra recovery, symlink
malevoli, rollback dei file con inode registrato e compatibilità con i test
di recovery già esistenti. Non certifica hardware, sistema operativo di
destinazione né l'intera suite globale del progetto.
