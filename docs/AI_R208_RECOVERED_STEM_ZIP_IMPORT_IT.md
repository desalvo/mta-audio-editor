# Importazione risultati recuperati ZIP multitraccia — r208

- Nuovo endpoint nativo `POST /api/native/ai-workers/pending/{request_id}/import-stems/{pid}`.
- Recupero HTTP esclusivamente read-only: non avvia una nuova inferenza.
- Supporta archivi con `manifest.json` versione 1 e WAV da adapter demucs, drumsep, sam-audio, singer-separation e backing-vocals.
- Verifica membri e manifest con limiti di dimensione, numero file, nomi sicuri, digest WAV e struttura audio.
- Importa gli stem nel progetto in un'unica chiamata applicativa sotto lock cross-process, registra un receipt persistente e mantiene il journal remoto.
- UI nativa: comando `Import recovered stems / Importa stem` per adapter compatibili.

Limite: l'importazione salva il progetto una sola volta, ma i file audio attraversano il normale percorso di caricamento; in caso di terminazione forzata tra scrittura file e salvataggio sono possibili file orfani. Non si dichiara transazione filesystem+database strettamente atomica, né certificazione sul server remoto reale.
