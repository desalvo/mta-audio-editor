# MTA Audio Editor 0.3.0-r208 — verifica del refinement della coda AI

## Correzione aggiuntiva
- I dati di progresso live esposti agli amministratori dall'elenco job sono gli stessi visibili nel dettaglio del progetto.
- I valori percentuali e i secondi CPU/GPU sono accettati solo quando effettivamente riportati dal backend e numericamente validi. I valori mancanti rimangono N/A.
- Il test `tests/test_r208_queue_live_admin_progress.py` verifica coerenza fra elenco amministrativo, dettaglio job e dettaglio progetto e scarta valori non validi.

## Limiti NON risolti
- I callback esecutivi non sono persistiti: dopo riavvio i lavori interrotti richiedono nuovo invio esplicito, non riavvio automatico.
- Le cancellazioni di inferenze GPU in esecuzione non terminano in modo forzato il processo ACE-Step; il codice rifiuta la cancellazione non sicura.
- I percorsi non AI (per esempio esportazione di progetti e import YouTube) non sono parte della coda AI.
- I client e adapter esterni/nativi non sono certificati sotto l'unico scheduler. Verificare ogni protocollo AI remoto e legacy.
- La misura GPU per singolo job rimane N/A in assenza di misurazione affidabile fornita dal backend.
- Mancano i test end-to-end su host EL10 e GPU Radeon 8060S e la suite Quality completa.

## Condizioni per approvazione produzione
1. Testare tutti gli ingressi AI, anche remoti, sotto limite di concorrenza 1 e 2.
2. Dimostrare annullamento effettivo sul processo o job remoto prima di abilitarne il comando all'utente.
3. Realizzare payload durevoli e idempotenza prima di introdurre la ripresa automatica dopo riavvio.
4. Eseguire Quality CI, build firmate, test su EL10 e verifica degli archivi diagnostici senza segreti.

Nessun incremento della versione applicativa: 0.3.0-r208.
