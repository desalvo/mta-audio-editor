# MTA 0.3.0-r208 – Remote metering attestation batch

## Implementazione effettiva

- Nuovo modulo `app/ai_remote_metering_attestation.py` con firma HMAC-SHA256 dell'envelope di consumo CPU/I/O.
- Firma vincolata a schema v1, job, richiesta idempotente e identificativo del worker.
- Canonicalizzazione JSON deterministica, firma verificata con confronto costante nel tempo, chiave di almeno 32 byte.
- Rifiuto di identità mancanti, tipi non validi, formati fuori contratto, nomi eccessivi, signature alterate, versioni sconosciute, campi aggiunti, contatori non finiti/negativi, GPU non certificata, byte I/O frazionari e interi non rappresentabili esattamente.
- `ai_metering_bridge.capture_authenticated_remote(...)` verifica l'envelope prima di inoltrare l'evidenza CPU alla persistenza durevole con fonte `remote-worker`.
- Idempotenza e immutabilità continuano a essere garantite dallo storage esistente della bridge.

## Limiti da rispettare

Questo modulo è un *building block* del protocollo: **non è ancora automaticamente collegato agli endpoint del remote AI gateway**. Non inserire chiavi HMAC negli output, nei log o nella configurazione lato client. Una chiave condivisa autenticata attesta l'origine della dichiarazione CPU, non dimostra che il worker abbia effettivamente misurato correttamente né certifica la GPU. Una soluzione di GPU accounting per-job richiede isolamento, sensori/driver e collaudo ROCm reale. Per questo il percorso rifiuta qualsiasi campo GPU nell'envelope.

## Test

- 76 nuovi test e scenari parametrizzati (62 contratto e 14 bridge).
- 564 test r208 superati nella copia di sviluppo in questo ciclo.
- Da completare: integrazione autenticata nel server remoto, deployment/rotazione delle chiavi, binding al worker registry, crash injection di produzione, misurazione GPU certificata e collaudo ollama-02.
