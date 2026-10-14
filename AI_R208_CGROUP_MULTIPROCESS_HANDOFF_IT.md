# r208 — Misurazione multiprocesso tramite cgroup v2

- Se `MTA_AI_CGROUP_PARENT` è configurata su Linux, Arranger/Remix esegue il worker in una cgroup v2 dedicata, con misure CPU e I/O comprensive dei processi figli. In caso di mancata delega, errori di lettura o processi residui il job fallisce in modo conservativo; non viene usato `wait4` come fallback silenzioso.
- L'evento di cancellazione del job viene rispettato anche nel loop cgroup. L'annullamento invalida le misure; nessun consumo CPU/GPU viene inventato.
- La telemetria GPU tramite DRM fdinfo rimane diagnostica campionata e non è fatturabile come secondi GPU attestati.
- **Non certificato senza hardware:** permessi systemd per la delega cgroup su Rocky EL10, processi figlio ACE-Step, GPU per-job e compatibilità reale di tutti gli adapter. Servono test su un'installazione isolata su ollama-02 prima della produzione.

## Verifiche consigliate in staging

```bash
cat /sys/fs/cgroup/cgroup.controllers
systemctl show mta-server.service -p Delegate -p ControlGroup
systemctl show mta-ace-step.service -p Delegate -p ControlGroup
python -m pytest -q tests/test_r208_cgroup_worker_handoff.py tests/test_r208_real_worker_cancellation.py
python scripts/crash_inject_ai_outbox_r208.py
python scripts/certify_ai_r208.py --hardware --output ai-hardware-probe.json
```

Usare una subtree cgroup **effettivamente delegata e scrivibile dall'utente del servizio**, assegnata a `MTA_AI_CGROUP_PARENT`. Non configurare un percorso fittizio per aggirare l'errore. Il collaudo su EL10 deve verificare i controller `cpu` e `io` e una prova con worker che genera processi figli. Non riavviare servizi di produzione per questi test; usare un'istanza staging.
