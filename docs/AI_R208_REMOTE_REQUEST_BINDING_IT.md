# R208 — Vincolo di identità della richiesta remota

Le risposte POST e GET possono riportare `X-MTA-AI-Request-ID`, derivato dalla chiave di idempotenza autenticata. Il client confronta l'header con l'ID originario, prima di accettare il contenuto. Il controllo si aggiunge alla verifica SHA-256, tipo MIME, identificativo job e lunghezza.

In assenza dell'header è mantenuta la compatibilità con i server precedenti; tale compatibilità non costituisce una garanzia di associazione crittografica. Per gli endpoint nuovi il server restituisce sempre l'header quando è presente una chiave, e sul GET restituisce la chiave autenticata del percorso.

Il lavoro NON completa da solo la misurazione GPU per job e NON certifica il billing e tutti gli adapter su hardware ROCm.
