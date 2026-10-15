# Checkpoint writer MTA 0.3.0-r208 — 14 ottobre 2026

## Modifiche verificate
- La normalizzazione Matroska usa un file temporaneo esclusivo nella cartella di destinazione, fsync e rename atomico.
- Il file precedente rimane intatto se normalizzazione, scrittura o rename falliscono prima del commit.
- Il writer rifiuta sorgenti/destinazioni symlink o non regolari e impedisce di sovrascrivere la sorgente.
- L'esportazione MTA valida il trasporto XOR sul file temporaneo prima di pubblicarlo.
- L'output finale viene copiato su staging nella stessa directory di destinazione, sincronizzato e pubblicato con os.replace.
- Cleanup dei temporanei limitato ai file di staging di questa operazione.

## Vincoli e limiti
- Versione e revisione 0.3.0-r208 invariate; nessuna operazione Git o server reale.
- La pubblicazione atomica non rappresenta una transazione distribuita con ledger, coda e progetto.
- Non eseguiti test Windows/macOS nativi e GPU reale; possibili rischi TOCTOU restano.
- I sottosistemi generatori locali, job lifecycle, billing e native/server non sono dichiarati chiusi.
