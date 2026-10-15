# MTA 0.3.0-r208 – Correzione quality CI

- Il test `tests/test_sample_editor_136.py::test_sample_editor_endpoints_copy_delete_paste_preview_apply` si bloccava per acquisizione ricorsiva di `flock` nello stesso thread, dopo il lock gia acquisito dal decoratore di route.
- `app/ai_project_lock.py`: lock rientrante per thread e percorso, mantenendo flock e isolamento tra thread/processi; rilascio solamente al termine della sezione esterna.
- `requirements-dev.txt`: dipendenza `pytest-timeout==2.4.0`.
- `.github/workflows/ci-cd.yml`: ogni singolo test puo essere interrotto dopo 180 secondi, mentre faulthandler conserva diagnostica.
- Test aggiunti: nested same-thread e non rilascio anticipato verso altri thread.
- Verifica locale: 9 passed, 8 warnings in 5.45s per sample-editor e lock.
- Test suite completa su GitHub ancora da verificare.
