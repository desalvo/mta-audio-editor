# MTA Audio Editor 0.3.0-r208 — Verifica attestazioni lato client

## Intervento
- `infer_audio` e `recover_audio` ricevono parametri facoltativi `metering_sink` e `metering_keyring`.
- Il risultato viene verificato per dimensione, tipo, richiesta e hash SHA-256 prima di consegnare misure.
- Se il sink è richiesto, l'header `X-MTA-AI-Metering-V2` è obbligatorio e viene validato contro le chiavi consentite con `verify_rotating`.
- La firma vincola `job_id`, `request_id`, `worker_id`, tipo di contatore, valore e chiave firmataria.
- I fallimenti dell'attestazione bloccano l'accettazione e non richiamano il sink.
- La compatibilità delle invocazioni prive di sink è preservata.

## Contratto di integrazione
Il sink riceve `(envelope, usage)` **solo dopo le verifiche**. Il chiamante deve autorizzare il job locale e identificare la relazione tra `job_id` remoto e job locale prima di usare `capture_operator_authenticated_remote()` e `register_settlement()`; non è sicuro equipararli automaticamente. Non viene introdotta attribuzione GPU fittizia.

## Verifiche
- 746 test r208 superati, di cui 11 nuovi casi sul sink remoto.
- Test hardware EL10/ROCm NON eseguiti; nessuna certificazione dell'attribuzione GPU.
- Non sono stati raggiunti 100 interventi funzionali indipendenti: il ciclo completa un'integrazione e la sua matrice di regressione.
