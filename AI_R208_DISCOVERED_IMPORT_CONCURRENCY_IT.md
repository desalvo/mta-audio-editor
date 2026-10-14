# r208 — importazione esplicita degli artifact remoti: concorrenza UI

Le importazioni WAV recuperate senza journal locale ora usano una chiave di operazione composta da tipo di worker, identificativo remoto e formato WAV. Un download rimane un'operazione non mutante; un'importazione richiede la conferma dell'operatore, un progetto aperto, la verifica della richiesta posseduta e i controlli server-side di pubblicazione. Le importazioni di JSON e stem mantengono chiavi indipendenti per worker, richiesta e formato.

Il test `tests/test_r208_discovered_import_ui_inflight.py` impedisce la regressione verso una chiave basata sul solo identificativo remoto. I test software non costituiscono benchmark GPU o collaudi di installer multipiattaforma.
