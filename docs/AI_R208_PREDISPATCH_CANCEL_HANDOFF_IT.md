# MTA Audio Editor 0.3.0-r208 — cancellazione remota pre-dispatch

- La route di esecuzione remota verifica la tombstone durevole dopo `admit()` e prima della chiamata al modello.
- Se la richiesta è stata annullata, risponde 409 senza eseguire il worker.
- Il controllo riduce la race di cancellazione tra ammissione e dispatch; non può garantire arresto fisico dopo l'avvio.
- Due test specifici verificano il caso annullato e quello ammesso; suite r208 795 superati.
- Restano da implementare cancellazione cooperativa durante l'inferenza, integrazione GPU per job e prove end-to-end su EL10/ROCm.
- Nessun commit o push; versione 0.3.0-r208 invariata.
