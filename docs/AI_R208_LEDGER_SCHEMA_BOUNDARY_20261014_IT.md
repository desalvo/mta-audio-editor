# MTA Audio Editor 0.3.0-r208 — Ledger identity contract

Il collegamento verificato tra un job AI e un job contabile richiede per i payload versionati:
- `schema_version` intero uguale a 1;
- `actor_user_id` intero positivo e coincidente con l'utente autenticato;
- `adapter` uguale all'operazione persistente `arranger` o `remix`;
- identità, tipologia e stato del job nel ledger compatibili con l'ammissione.

I payload versionati incompleti, alterati o inconsistenti non possono creare intenzioni di addebito. Gli identificativi legacy realmente non versionati rimangono riconosciuti per compatibilità, ma devono essere migrati prima di poter reclamare le stesse garanzie dei job versionati.

## Verifiche

488 test della suite `tests/test_r208*` superati localmente, compresi 23 casi parametrizzati di payload malformati/incompatibili e un caso positivo.

## Limiti

Non è ancora implementata né certificata l'attribuzione GPU per singolo job remoto, l'acquisizione autenticata delle evidenze dei worker remoti, né la certificazione end-to-end su Rocky EL10/ROCm. Questo controllo non li sostituisce.
