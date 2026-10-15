# MTA 0.3.0-r208 — Riserva namespace manifest stem

Il produttore di artifact AI ora rifiuta `manifest.json` in qualsiasi variante di maiuscole/minuscole tra i file dichiarati dal worker. Il nome è riservato al manifest di archivio generato, impedendo che un payload JSON arbitrario crei membri ZIP duplicati o ambigui. Il controllo avviene prima della lettura/pubblicazione degli artifact.

Test mirati: 13 superati, 8 warning. La suite r208 completa è stata avviata ma non conclusa nel limite operativo. Nessuna modifica a VERSION/REVISION o ai sistemi reali.
