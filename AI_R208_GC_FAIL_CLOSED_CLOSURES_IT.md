# MTA Audio Editor 0.3.0-r208 — Refinement GC fail-closed

Checkpoint: MTA-r208-durable-media-recovery-cumulative.zip (SHA256 f8cefd84aed8a6e304c7c8c8b771655580808bc7475e9e4dbabb48f6b47ddd7c). Il checkpoint non contiene le dieci chiusure della successiva sessione disconnessa.

Chiusure verificate su questo checkpoint:
1. I journal della GC malformati, di schema errato o duplicati vengono rifiutati (non più interpretati come vuoti), conservando le informazioni di recovery.
2. GC limitata a file regolari, senza seguire symlink di file o directory; vengono mantenuti i candidati sospetti per successive verifiche.
3. Journal GC symlink rifiutato anche sul percorso di scrittura/cancellazione, evitando di sostituire collegamenti non affidabili.

Regressioni focalizzate: 17 passed (suite GC + normalizzazione + recovery FLAC), 8 warning di deprecazione; suite globale avviata, non conclusa entro il tempo disponibile. Non dichiarare le precedenti dieci chiusure come recuperate. Non sono stati effettuati commit, push, tag, release né accessi ai server.

Limiti residui: nessuna transazione globale ACID filesystem/progetto/queue/ledger; protezione GC ancora senza blocco cross-process globale; possibili race avversariali TOCTOU; metering GPU non fatturabile; accettazione Windows/macOS e real GPU non completate. I sistemi di import media e gli adapter legacy necessitano ulteriori chiusure.
