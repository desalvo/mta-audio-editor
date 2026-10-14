# MTA Audio Editor 0.3.0-r208 — Recupero degli originali degli import asincroni

- Journal per job retrocompatibile con le ricevute versione 1; versione 2 registra il nome della copia originale prima di iniziarne la scrittura.
- La copia usa apertura esclusiva e `fsync` del file e della directory; il journal viene sostituito atomicamente e sincronizzato prima della copia.
- In fase di riconciliazione, l'originale viene rimosso solo se nessuna delle varianti audio dichiarate è presente nelle tracce o nella clip library del progetto.
- Gli originali preesistenti o individuati come duplicati non sono reclamati dal journal e non vengono cancellati.
- I percorsi non validi e i journal corrotti arrestano la riconciliazione senza eliminare i file.
- Percorso coperto: `/api/projects/{pid}/track-import-jobs`; i test locali non sostituiscono prove con kill -9 e storage di produzione.
