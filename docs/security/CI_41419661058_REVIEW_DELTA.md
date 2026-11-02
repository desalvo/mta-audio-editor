# CI 41419661058 — delta da sottoporre a revisione

Questo elenco è un inventario automatico, non una revisione o approvazione di sicurezza. Non modificare i registri degli hash senza riesaminare codice, confini e prove.

Bandit 1.9.4: 171 risultati, 11 identità nuove rispetto al registro. Il confronto usa il codice di questo pacchetto; zero HIGH e nessuna soppressione.

## Sorgenti differenti nel registro execution

- `app/ai_adapter_identity.py`
- `app/ai_models.py`
- `app/ai_server_execution.py`
- `app/ai_worker_registry.py`
- `app/codec.py`
- `app/main.py`
- `app/merish_mta16.py`
- `app/models.py`
- `app/mta_writer.py`
- `app/paypal_cash_history.py`
- `app/static/app.js`
- `app/static/owner_payments.js`
- `app/static/regime_admin_panel.js`
- `native/mta_audio_editor_native.py`

## Nuove identità Bandit non revisionate

| File | Riga | Check | Severità |
| --- | ---: | --- | --- |
| `app/ai_models.py` | 190 | B404 | LOW |
| `app/ai_models.py` | 192 | B603 | LOW |
| `app/codec.py` | 107 | B603 | LOW |
| `app/main.py` | 3478 | B607 | LOW |
| `app/main.py` | 3478 | B603 | LOW |
| `app/main.py` | 4924 | B404 | LOW |
| `app/main.py` | 4936 | B603 | LOW |
| `app/main.py` | 5766 | B603 | LOW |
| `app/main.py` | 7274 | B603 | LOW |
| `app/main.py` | 7486 | B603 | LOW |
| `app/merish_mta16.py` | 11 | B405 | LOW |

## Nuovi punti di ingresso nel censimento

| Registro | File | Funzione | Tipo |
| --- | --- | --- | --- |
| Execution | `app/ai_models.py` | `chord_engine_available` | `process_boundary` |
| Execution | `app/main.py` | `_text_music_worker` | `inference_call` |
| Execution | `app/main.py` | `import_merish_metadata` | `http_entry` |
| Admission | `app/ai_models.py` | `chord_engine_available` | `process_boundary` |

Il censimento remote transport non rileva nuove forme di chiamata; il registro è comunque obsoleto rispetto a `app/main.py`. Le differenze nei sorgenti completi e le variazioni di righe richiedono verifica contestuale.
