# MTA Audio Editor 0.3.0-r208 — Remote settlement handoff

Nuovo punto di integrazione `ai_metering_bridge.infer_and_register_remote_settlement`:

1. Usa l'identità deterministica del job remoto già disponibile in `infer_durable_remote`.
2. Richiede attestazione HMAC v2 validata dalla configurazione dell'operatore.
3. Usa il sink durevole per registrare in modo immutabile l'evidenza CPU e il binding locale/remoto.
4. Verifica tipo e struttura del risultato prima dell'intenzione contabile.
5. Registra o riutilizza l'intenzione contabile tramite la Billing Outbox.
6. Non restituisce l'audio se l'intenzione contabile richiesta fallisce.
7. Non crea misure GPU presunte e non marca come pubblicato l'audio: il chiamante deve usare la Audio Publish Outbox.

## Verifica locale

768 test r208 superati, inclusi 8 test nuovi sul contratto di handoff. Compilazione Python e validazione ZIP da eseguire nel packaging.

## Limiti aperti

Il punto di integrazione non è ancora cablato a tutti i chiamanti reali; il contratto di pubblicazione audio rimane separato. Il metering GPU hardware per singolo job e il test end-to-end su Rocky EL10/ROCm non sono certificati. Il ciclo non contiene oltre 100 interventi funzionali indipendenti.
