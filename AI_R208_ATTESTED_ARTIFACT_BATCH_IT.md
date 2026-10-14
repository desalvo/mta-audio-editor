# MTA 0.3.0-r208 — Verifica contenuto risultati remoti (batch)

Questo ciclo aggiunge il controllo del formato dei byte ricevuti con `require_attestation=True`, sia POST sia GET di recovery.

## Controlli implementati

- WAV: magic RIFF, lunghezza del buffer, tipo WAVE e coerenza della lunghezza dichiarata.
- JSON: UTF-8 valido, JSON completo, oggetto/array, nessuna chiave duplicata (anche annidata), NaN/Infinity rifiutati.
- ZIP: struttura leggibile e CRC dei file, archivio non vuoto, massimo 512 voci, niente nomi duplicati, niente symlink, percorsi assoluti, backslash o traversal; limite cumulativo 32 MiB dei file decompressi.
- La modalità compatibile continua ad accettare gli artefatti legacy senza questa ulteriore verifica del formato; digest e binding quando dichiarati restano comunque obbligatoriamente verificati.

Sono stati aggiunti 30 casi parametrizzati per formato valido/malformato e corrette due fixture WAV precedentemente non valide.

## Limiti

L'integrità di trasporto e la verifica dei formati non attestano il consumo CPU/GPU. Mancano ancora l'attribuzione GPU attendibile per job, il billing uniforme degli adapter remoti e i test integrati su ROCm/EL10. Non dichiarare il software completamente certificato.
