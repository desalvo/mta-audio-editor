# r208 – Worker legacy, cancellazione e avanzamento cgroup

Questo ciclo corregge il trasferimento dell'ambiente del job nel percorso cgroup v2: `run_worker_with_project_audio` trasmette adesso `env` a `run_cgroup_process`, che lo inoltra al processo supervisore. `MTA_AI_PROGRESS_FILE` rimane disponibile anche quando il worker è sottoposto a misurazione cgroup, come già nei percorsi non-cgroup.

La cancellazione viene controllata prima della preparazione delle tracce, durante l'iterazione delle sorgenti, immediatamente dopo la risoluzione di un file e prima della serializzazione della richiesta. Una richiesta annullata non avvia l'inferenza dopo la fase di preparazione. Ciò non rende interrompibile un singolo rendering sincrono già in corso: la cancellazione viene osservata al successivo checkpoint.

Test: `tests/test_r208_worker_preflight_and_cgroup_environment.py` (3 casi) e regressioni worker/AI. Le misurazioni GPU restano non certificabili tramite diagnostica a campionamento; non sono stati eseguiti modelli o test cgroup su hardware reale.
