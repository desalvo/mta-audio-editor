# MTA 0.3.0-r208 — Rotazione chiavi evidenze di consumo remoto

Implementato protocollo v2 di attestazione delle evidenze CPU/I/O con `key_id` autenticato dalla firma HMAC-SHA256.

- `sign_rotating`: firma consumi CPU e I/O con una chiave e il suo identificativo.
- `verify_rotating`: verifica la chiave esplicita dal registro di fiducia; non tenta chiavi alternative.
- Revoca: rimuovere `key_id` dal registro impedisce ulteriori accettazioni con quella chiave.
- `capture_rotating_remote`: punto di acquisizione delle misure autenticate nel registro persistente.
- Le v1 restano supportate con API precedente, senza downgrade automatico dalla v2.
- Non è implementato un endpoint pubblico di provisioning del registro chiavi: l'operatore deve configurarlo e custodirlo in modo sicuro.
- Questa attestazione prova il possesso della chiave del worker, **non** il consumo GPU misurato dall'hardware.
- Non è ancora completo il wiring automatico dagli endpoint di inferenza remota alla contabilità di tutti gli adapter.

Verifica: 54 nuovi test di rotazione e manomissione, 618 regressioni r208 complessive, compilazione e integrità ZIP.
