# MTA 0.3.0-r208 — Finalizzazione con metering verificato

## Implementato e provato localmente

Il modulo `app/ai_metering_bridge.py` conserva nel database SQLite della coda un'evidenza immutabile per job: campi di consumo e provenienza. Il replay identico è idempotente; quello discordante fallisce. Il modulo non inventa misure a partire dal tempo trascorso. `register_settlement` rifiuta i job fatturabili privi di evidenze e collega i dati al ledger tramite l'Outbox esistente e la verifica dell'utente.

Nel worker dei job durevoli Arranger/Remix il gate contabile viene invocato prima di confermare la chiusura; in presenza di un errore la finalizzazione rimane recuperabile. I job legacy privi dell'identità utente persistente mantengono il comportamento esistente.

## Limiti: non certificato per produzione

**ATTENZIONE**: `capture()` è un'interfaccia interna che deve essere chiamata solo dopo autenticazione della fonte. Non è ancora collegata a una sorgente di misurazione affidabile per tutti gli adapter. Una prova locale del bridge non è una prova che CPU/GPU siano misurate correttamente: quando manca tale evidenza, i job fatturabili restano in sospeso. I valori GPU devono essere acquisiti da un GPU agent autenticato; non usare wall-time o progress bar come misure GPU. La copertura degli ingressi legacy e degli adapter non è completa. Non dichiarare certificazione end-to-end né deploy di produzione completati.

## Collaudo hardware futuro

1. Eseguire `python scripts/certify_ai_r208.py --hardware --output ai-hardware-probe.json` con l'interprete del server EL10, senza credenziali nel report.
2. Eseguire un job reale per adapter su ambiente isolato, generando evidenze affidabili CPU/GPU, validando un solo file pubblicato e un solo addebito.
3. Ripetere le crash injection fra stadio audio, Outbox, ledger e completamento, verificando il recovery e i job pendenti.
4. Eseguire Quality CI completa e prove di concorrenza prima di una dichiarazione di certificazione.

Non sono stati effettuati commit, push o interventi sul CT Proxmox 130.
