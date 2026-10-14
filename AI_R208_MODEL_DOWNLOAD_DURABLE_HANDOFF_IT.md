# MTA Audio Editor 0.3.0-r208 — recovery durevole download modelli AI

## Implementato
- Download dei modelli Whisper/Lyrics e Chords ammessi allo scheduler SQLite con payload versionato.
- Ripristino delle sole richieste ancora accodate tramite restorer registrati.
- Convalida della famiglia di modello, ID e catalogo prima di rilanciare un download accodato.
- Consultazione dello stato persistente dopo riavvio; download di sistema autorizzati dall'attore autenticato, non da un progetto fittizio.
- Annullamento di richieste accodate anche dopo riavvio; rifiuto per richieste già partite che il processo attuale non può annullare in modo attendibile.
- Test di payload invalidi, recupero, ammissione e annullamento.

## Limiti espliciti
- Non vengono rieseguiti automaticamente download già in esecuzione prima di un crash.
- Il trasferimento già avviato non viene fermato necessariamente in modo cooperativo; l'annullamento copre l'attesa in coda.
- Gli adapter di separazione, billing remoto e metering GPU restano da completare/certificare; 225 test locali r208 non attestano la certificazione hardware.
- Versione invariata r208. Nessun commit o push.
