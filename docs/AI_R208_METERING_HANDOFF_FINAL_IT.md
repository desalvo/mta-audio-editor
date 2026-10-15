# MTA 0.3.0-r208 — Collegamento metering Arranger/Remix

## Implementato
- Il worker locale Arranger/Remix su POSIX/Linux viene atteso con `wait4` sul PID esatto, conservando CPU user+system process time come `cpu_seconds` soltanto quando la misurazione resta attribuibile al processo diretto.
- La presenza osservata di processi discendenti impedisce di qualificare la misura diretta come CPU complessiva del job.
- La misurazione viene scritta nell'evidence store immutabile prima di pubblicare il risultato audio, usando l'identita' durevole del job.
- Nessun valore GPU viene ricavato dalla durata o dall'utilizzazione media host.
- La coda, l'Outbox e il billing mantengono il gate fail-closed gia' presente quando mancano evidenze sufficienti.

## Non certificato
- La rilevazione dei figli tramite polling non garantisce la cattura di processi discendenti molto brevi. Per fatturazione accurata di process tree e GPU serve isolamento cgroup e attestazione GPU autenticata.
- L'implementazione resta specifica al worker locale usato da Arranger/Remix: Whisper, Demucs, DrumSep, SAM Audio, separazione vocale, analisi accordi, remoto e legacy vanno verificati e uniformati uno a uno.
- Il protocollo scheduler/Outbox audio/billing e' una saga recuperabile, non una transazione ACID distribuita; servono prove reali di crash e verifica contabile in staging prima di dichiarare certificazione end-to-end.
- Mancano prove reali su Rocky EL10 / ROCm 7.2.4 / gfx1151.

## Collaudo sicuro su ollama-02 (NON sulla produzione)
1. Eseguire il backup di database, ledger e progetti, poi creare un'istanza di staging isolata con porte, servizi e path distinti.
2. Nell'ambiente Python dell'istanza staging: `python scripts/certify_ai_r208.py --hardware --output ai-hardware-probe.json`.
3. Eseguire offline `python scripts/crash_inject_ai_outbox_r208.py`.
4. Provare una richiesta reale per ciascun adapter in staging, con cancellazione e riavvio; verificare log, ledger, checksum audio e Outbox senza doppio addebito.
5. Controllare che la rilevazione CPU delle inferenze multi-processo sia considerata non attestata, finche' non si usa un cgroup dedicato; per GPU confrontare i dati con l'agente autenticato.
6. Restituire report JSON, diagnostica sanitizzata, matrice adapter e risultati dei test: saranno necessari per la certificazione finale.

Non eseguire crash injection sul servizio di produzione.
