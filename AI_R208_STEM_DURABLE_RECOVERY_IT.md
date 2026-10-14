# MTA Audio Editor 0.3.0-r208 — Recupero durevole separazione audio

## Ambito implementato

- Gli endpoint di separazione per file e tracce persistono una richiesta versione 1 nel registro SQLite condiviso prima dell'esecuzione.
- Un restorer `stem-separation` ricostruisce i parametri Demucs, DrumSep, SAM Audio, singer/backing vocals e relative opzioni da payload JSON senza copiare oggetti Python volatili.
- Le sorgenti vengono referenziate esclusivamente all'interno della cartella del progetto (`audio`/`original`), e controllate prima del ripristino per presenza, symlink e hardlink.
- La cancellazione della route stem passa ora dal runtime condiviso: i job accodati vengono contrassegnati `cancelled` durabilmente; i job in esecuzione vengono segnalati all'evento di cancellazione del processo locale.
- La policy evita il replay automatico dei job già iniziati al crash, poiché le modifiche multitraccia non hanno ancora un protocollo di pubblicazione atomica.

## Test

Test di restorer, progetto errato, payload incoerente, sorgente mancante e cancellazione; controlli di regressione r208 e workflow stem esistenti.

## Vincoli ancora aperti

- Riconciliazione delle tracce parzialmente pubblicate dopo arresto brusco durante la separazione; non è consentito il replay automatico di lavoro già iniziato.
- Billing e misurazione GPU attendibile per i worker remoti e legacy.
- Verifiche hardware sulle dipendenze dei modelli Demucs/DrumSep/SAM e ROCm EL10.

Non è una certificazione complessiva del software. Nessun commit, push o modifica a host esterni eseguita.
