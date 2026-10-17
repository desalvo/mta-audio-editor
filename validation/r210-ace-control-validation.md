# Validazione r210 — timeout ACE e cancellazione

Data locale: 2026-10-17 (Europe/Rome). Versione 0.3.0-r210 invariata.
Base cumulativa: MTA-r210-live-gpu.zip (1422 file), SHA-256
f5d2bf65adfd820459b920e246c8bfad6b9d5ac102f2a17ae127a66b12fe440e.
Ultimo commit utente noto: d3be8838dafadfb756b2a25d4adb16a5eb27af65.
Le modifiche precedenti non committate (GPU live e worker unificati) sono mantenute.
Nessun commit, push, tag, release o intervento sul server reale eseguito.

## Evidenza e correzioni

Allegato analizzato: mta-diagnostics-262bacf4c9884e53a08f99b83ae10365.zip;
screenshot di errore a 608 s con limite Arranger di 60 minuti.
Job: 5011abc47294421fb153577ba3d6cf76; categoria ace_adapter_failed.
Lo ZIP precedente non conserva il dettaglio dell'eccezione ACE.
Nel sorgente upstream v0.1.8 fissato dall'installer (dce621408bee8c31b4fcf4811682eb9359e1bc94)
è stato verificato il limite service-generate di 600 s con thread lasciato vivo.
È coerente con il guasto osservato, ma non prova retroattivamente l'eccezione
specifica di quel job né dimostra un problema di memoria GPU.

Il launcher MTA alza il tetto tecnico finito a 14520 s e applica il budget
immutabile per task (60–14400 s), con checkpoint cooperativi nei thread reali.
Il supervisore conserva il suo limite totale e i controlli cgroup/accounting.
La cancellazione viene inoltrata al servizio ACE anche dopo il kill dell'adapter,
tramite il sidecar privato; nessun kill globale o PID scelto dall'utente.
Il pulsante si trasforma in Annulla job, con stato di annullamento e protezione
contro doppi invii. Endpoint con ACL progetto, autenticazione e integrità richiesta.
Gli errori ACE sono classificati senza conservare messaggi remoti o segreti.
Il profiler è avviato nel vero thread service_generate per i campioni live;
la cattura non certifica tutte le fasi GPU del job. Il billing GPU resta escluso.

## Risultati finali

- Suite mirata: 94 passed, 1 warning in 8.69s.
- Regressione generale: 3318 passed, 4 skipped, 10 deselected, 4 warnings in 132.18s (0:02:12).
- Coverage app: 74.59%, superiore alla soglia richiesta del 70%.
- Ruff app/native/tests/scripts/k8s-wizard.py: superato.
- node --check app/static/app.js: superato.
- bash -n scripts/install_ace_step.sh: superato (installer invariato rispetto alla base).
- ZIP cumulativo: controllo CRC e conservazione integrale del manifest di base;
  checksum SHA-256 affiancato al pacchetto.

I quattro skip richiedono SDK Steinberg/ADelay opzionali. I dieci casi esclusi
sono le integrazioni AF_UNIX non eseguibili nel runner. I warning sono riportati
nei log. Test di nuove API e UI, clock oltre 600 s, annullamento pre-esecuzione,
timeout, veri thread figli, subprocess reale con cancellazione HTTP, retention
cancel dei task in attesa, pulizia hook, protezioni di accesso, redazione degli
errori e metering non valido sono inclusi nelle prove mirate.

## Prove ancora necessarie

Nessuna GPU ROCm nel runner; kernel/eventi simulati nei test. Il vecchio test
breve finale aveva prodotto audio persistente e 66.898005 s GPU diagnostici.
Non è accettazione del nuovo controllo task, della cattura nel thread GPU o della
prova lunga. Da eseguire sul server: breve inferenza con contatore live, annullo
senza pubblicazione, arresto GPU al checkpoint utile, nuovo brano lungo oltre
i dieci minuti e persistenza/riproduzione del risultato. Un kernel lungo o un
modello compilato può ritardare l'arresto cooperativo. Backend senza nuove API
non garantiscono l'arresto remoto. Windows e certificazione completa r210 restano
separatamente da concludere. Nessuna misura non valida diventa fatturabile.

Istruzioni complete: docs/ACE_LONG_JOBS_AND_CANCELLATION_R210.md.
