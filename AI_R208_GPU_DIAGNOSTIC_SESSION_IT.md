# r208 — Sessione diagnostica GPU multipunto

Modulo: `app.ai_gpu_diagnostic_session`.

`collect_session()` raccoglie da 1 a 100 snapshot verificati AMD SMI, associa PID host ai cgroup dei job e rileva qualsiasi attività esterna in una finestra diagnostica. Non utilizza i contatori diagnostici come consumo GPU fatturabile. Richiede `host_pid_namespace_verified=True` **esclusivamente** quando eseguito da un operatore/agente affidabile sull'host con visibilità del `/proc` host. Non impostare questa opzione automaticamente in LXC.

`write_session_report()` crea un file JSON con permessi 0600, scrittura atomica e sync, e rifiuta dati contrassegnati come fatturabili. Non usare questi report come documenti contabili. La sessione non fornisce un misuratore hardware di tempo GPU, non completa il billing GPU e non effettua connessioni al nodo Rocky/ROCm.

Test: `PYTHONPATH=. pytest -q tests/test_r208_gpu_diagnostic_session.py tests/test_r208_gpu_attribution_report.py`.
