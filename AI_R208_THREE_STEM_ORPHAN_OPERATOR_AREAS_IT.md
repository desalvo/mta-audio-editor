# MTA Audio Editor 0.3.0-r208 — tre chiusure software orfani stem

## 1. Revisione amministrativa
GET `/api/projects/{pid}/recovered-stem-orphans` restituisce il registro persistente con stato di presenza per ogni file; richiede accesso al progetto e il lock di pubblicazione. Percorsi e motivi sono validati, i symlink non sono seguiti.

## 2. Quarantena amministrativa non distruttiva
POST `/api/projects/{pid}/recovered-stem-orphans/quarantine` con JSON `{"receipt":"...","file":"audio/nome.wav"}` sposta il file referenziato dall'audit in `.recovered-stems-quarantine` con nome unico; non effettua cancellazione definitiva. Sono bloccati journal pendenti, file attualmente referenziati dal progetto e voci mancanti. L'API richiede accesso al progetto e lock.

## 3. Audit durevole e riesame dopo riavvio
Il registro originale non viene rimosso: dopo la quarantena la consultazione indica `present=false` per la posizione precedente, mantenendo ricevuta, percorso e motivo per i successivi avvii. I contenuti in quarantena restano fisicamente presenti.

## Test
Suite stem/orfani mirata: 43 passed, 8 warnings. Non è una certificazione della suite globale, di filesystem Windows/macOS o di un servizio GPU reale.

## Restrizioni note
Non implementa cancellazione definitiva, restore automatico o interfaccia grafica dedicata. La serializzazione richiede lock sul progetto: le API lo applicano, mentre le funzioni interne richiedono che sia già detenuto. La procedura di quarantena è intenzionalmente non distruttiva.
