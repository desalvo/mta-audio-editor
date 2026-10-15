# R208 — Consolidamento end-to-end della quarantena degli stem

Versione invariata: 0.3.0-r208.

## Tre chiusure software

1. **Integrità del registro amministrativo:** validazione fail-closed delle origini audio/originals, dei percorsi e dei nomi in quarantena; identità di quarantena univoche.
2. **Ripristino coerente con lo stato del progetto:** prima di ripristinare un file stem, verifica delle tracce e della clip library nello stato corrente del progetto; nessun ripristino in una destinazione ora referenziata.
3. **Regressione combinata:** test integrati su consultazione, quarantena, ripristino, registro persistente e percorsi stem: 54 passed, 8 warnings; regressione r208: 1206 passed, 13 warnings.

La macroarea dell'amministrazione server-side degli orfani stem è validata in software. Rimangono da realizzare o collaudare UI amministrativa dedicata, piattaforme fisiche e regressione generale non-r208. Il ripristino non cancella la cronologia di audit; non sono previste cancellazioni definitive automatiche.
