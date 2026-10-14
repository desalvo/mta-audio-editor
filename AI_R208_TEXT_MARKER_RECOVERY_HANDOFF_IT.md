# MTA 0.3.0-r208 — Recovery unificato Lyrics/Chords/Markers

- Registrato l'adapter persistente `extract-markers`, insieme a `extract-lyrics` e `extract-chords`.
- Validazione payload prima del ripristino dei job accodati; non si riavviano automaticamente esecuzioni interrotte.
- Endpoint di stato dei media job: fallback in sola lettura sulla coda persistente per i job testuali/marker, senza esecuzione di side effect; mantiene autorizzazione sul progetto.
- Regressioni locali r208: 214 test superati.

## Limiti e collaudo

La proiezione di stato recupera lo stato del job, non necessariamente i risultati analitici preesistenti in memoria. Rimangono da verificare o integrare il billing degli adapter legacy/remoti, l'attribuzione GPU a singoli job con telemetria affidabile, e i test end-to-end EL10/ROCm con interruzioni reali. Queste parti NON sono certificate da questa modifica.
