# r208 — Pubblicazione audio concorrente e stato della certificazione

## Correzione implementata
La pubblicazione audio asincrona Arranger/Remix acquisisce un lock POSIX per **progetto**, in aggiunta al lock Outbox per singolo job. Il progetto viene caricato soltanto dopo aver acquisito il lock, così due job differenti non sovrascrivono le rispettive modifiche al file di progetto. La chiave del lock usa SHA-256 dell'identificativo di progetto; il file è in storage persistente con permessi 0600 e apertura senza seguire symlink (quando supportato).

## Verifiche locali
- `PYTHONPATH=. pytest -q tests/test_r208*`: 141 superati.
- Due processi concorrenti sullo stesso identificativo: serializzazione verificata.
- Non è stata eseguita inferenza reale su Radeon 8060S/ROCm, né un test di stress con progetti di produzione.

## Requisiti ancora mancanti (non certificati)
- Legame automatico e autenticato dei job Arranger/Remix con identità billing e utente: oggi l'Outbox contabile è esplicitamente opt-in; non è corretto creare addebiti senza identità verificata.
- Chiusura `completed` subordinata alla conferma contabile per tutti i job fatturabili.
- Coordinamento del lock progetto con tutti gli altri endpoint di modifica progetto (non soltanto pubblicazione AI): in presenza di scritture web concorrenti resta una possibile lost update.
- Test di crash injection con un job billing realmente associato, incluse riconciliazioni dopo riavvio.
- Certificazione degli adapter su ollama-02 EL10/ROCm 7.2.4.

## Azioni dell'operatore
Nessuna azione necessaria per questo refinement. Evitare il commit di certificazione finale finché non siano completati i requisiti software e il collaudo hardware.
