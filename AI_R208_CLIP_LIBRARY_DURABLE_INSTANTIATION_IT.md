# MTA Audio Editor 0.3.0-r208 — Clip library: istanziazione recuperabile

## Interventi completati

- Istanziazione clip da asset riutilizzabile senza modificare l'audio originale.
- Validazione inode regolare e rifiuto dei collegamenti simbolici e delle sorgenti non sicure.
- Per sample rate differente: copia esclusiva su nome casuale, fsync prima della conversione e conversione in file distinto.
- Cleanup dei file temporanei e prodotti soltanto dall'operazione corrente mediante identità inode.
- In caso di errore prima del salvataggio: rollback dei file non referenziati nel progetto persistito.
- In caso di eccezione dopo commit: conservazione dei file già referenziati nel progetto persistito.
- Compatibilità con le clip legacy che non possono essere interrogate da FFprobe quando non occorre conversione.
- Conversione rifiutata se non si può verificare il formato effettivo necessario.

## Verifiche

`pytest -q tests/test_r208_clip_instantiation_durable.py tests/test_project_clip_library_119.py tests/test_project_clip_details_121.py tests/test_project_clip_browser_120.py tests/test_import_split_regressions_108.py tests/test_mta_advanced.py tests/test_production.py --disable-warnings --maxfail=1`

Risultato: **44 passed, 8 warnings**. Compresi test con FFmpeg reale, errore pre-commit, errore post-commit e symlink.

## Limiti

Non è un protocollo ACID tra filesystem e project.json. Se il processo termina brutalmente prima della registrazione di un nuovo file, la pulizia continua a dipendere dalla riconciliazione dello storage. Il lifecycle degli altri job, il billing/metering GPU e i collaudi Windows/macOS e hardware reale non sono certificati in questo ciclo. Versione invariata `0.3.0-r208`. Nessuna attività su server reali o Git.
