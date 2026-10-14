# MTA 0.3.0-r208 — Replay remoto sicuro e recovery

## Interventi

- La cache degli output remoti serializza per chiave le scritture e le letture tramite blocco `flock` condiviso fra processi Linux.
- Lettura di manifest e payload mediante file descriptor con `O_NOFOLLOW`, verifica che siano file regolari, con singolo hardlink e dimensioni limitate.
- Il digest SHA-256 viene verificato sui byte effettivamente letti e l'identità del job deve coincidere con quella persistita.
- Scrittura del risultato e dei metadati con `fsync` dei file e della directory. In caso di crash intermedio, il consumer rifiuta qualsiasi coppia incongruente.
- Test di manomissione via symlink, hardlink, metadati malformati e scrittura parallela.

## Limiti e blocchi residui

- Queste protezioni non provano atomicità di billing, file system e ledger attraverso tutte le istanze.
- L'attribuzione GPU per job e la certificazione su ROCm devono ancora essere completate con hardware reale e worker remoti attendibili.
- Non è attestata la centralizzazione completa di tutti gli adapter legacy.
