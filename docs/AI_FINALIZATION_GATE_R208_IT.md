# AI finalization gate - MTA 0.3.0-r208

## Implementato in questo incremento

- `app/ai_finalization.py`: verifica ricevuta di pubblicazione audio e, quando presente, consegna billing esplicita; tenta il retry idempotente prima del recovery dello scheduler.
- L'avvio del server invoca il coordinatore per ogni ricevuta audio pubblicata, isolando i fallimenti per job senza bloccare la ripresa degli altri.
- `reconcile_published_audio` rifiuta transizioni `interrupted -> completed` quando una consegna billing associata esiste ma non è ancora `delivered`.
- Test `tests/test_r208_finalization_gate.py`: assenza audio, consegna pendente, consegna confermata, failure ledger.

## Limiti non risolti (NON CERTIFICATI)

- Non si crea in automatico un job di billing per ogni richiesta Arranger/Remix: occorrono identità utente, autorizzazione e regole tariffarie verificabili.
- L'esecutore dei job può ancora scrivere `completed` dopo il ritorno dell'adapter; il gate aggiunto vincola il *recovery* e non tutte le possibili transizioni in tempo reale.
- Nessuna transazione ACID può comprendere SQLite separati e filesystem. Il protocollo deve essere completato con stati `finalizing` durevoli, controllo del commit del billing sull'intero percorso e crash injection negli ingressi live.
- La verifica di compatibilità degli adapter su Rocky EL10/ROCm 7.2.4 e Radeon 8060S richiede inferenze reali su `ollama-02`.

## Verifiche locali

`PYTHONPATH=. pytest -q tests/test_r208_*.py` -> 145 passed.

Non eseguire crash injection distruttiva su produzione. Effettuare test end-to-end su una copia isolata del database e dello storage, con backup e credenziali di test.
