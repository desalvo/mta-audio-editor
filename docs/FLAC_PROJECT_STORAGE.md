# Project audio storage: WAV and FLAC / Archiviazione WAV e FLAC

## Italiano

- **Impostazioni → Use FLAC for new projects**: predefinita disabilitata. L'opzione viene memorizzata nelle preferenze locali dell'applicazione; nuovi progetti sono creati in modalità `flac` quando abilitata, altrimenti `wav`.
- Ogni progetto mantiene `audio_storage_mode` nel proprio `project.json`. I progetti precedenti senza questo campo rimangono WAV.
- In apertura di un progetto WAV, se FLAC è abilitato globalmente, viene chiesto il consenso prima della migrazione. Rifiutando, i file restano WAV.
- Solo WAV PCM interi a 8/16/24 bit vengono convertiti losslessly. WAV floating point, WAV PCM a 32 bit e formati non supportati vengono conservati senza forzarne la conversione.
- La conversione crea e controlla i nuovi FLAC prima di aggiornare `project.json`; i WAV esistenti sono cancellati soltanto dopo aver salvato i nuovi riferimenti. Su errore di conversione i vecchi WAV non vengono rimossi.
- Nuovi WAV PCM interi creati da un progetto in modalità FLAC vengono convertiti al salvataggio. La compressione è FLAC livello 1, per privilegiare la velocità.
- La cache derivata di anteprima e rendering PCM **non è inserita nel progetto**: il rendering usa directory temporanee del sistema e la cache preview esistente è specifica della sessione.
- Gli archivi portatili `.maeprojz` conservano gli stem FLAC referenziati dal progetto. Il formato `.mta` per M-Live non contiene tracce FLAC: l'export decodifica le sorgenti in WAV PCM temporanei con le modifiche/timing della timeline e codifica gli slot audio come MP3.
- La sincronizzazione di clip, marker, testi e accordi è definita dai timestamp del progetto, non dal codec sorgente.

## English

- **Settings → Use FLAC for new projects** is off by default and stored in local app preferences. Each project persists its own `audio_storage_mode`; existing projects default to WAV.
- Opening a WAV project while FLAC is globally enabled requests consent; declining leaves the project unchanged.
- Only 8/16/24-bit integer-PCM WAV is converted without loss. Float PCM and 32-bit integer WAV are retained, to avoid silent precision loss.
- Files are encoded and validated before references are committed; source WAVs are removed only after project metadata has been persisted. New WAV integer PCM created in FLAC projects is converted when saving.
- Transient PCM rendering and previews remain **outside the portable project archive**, using OS temporary files and session preview storage.
- `.maeprojz` includes project FLAC assets; `.mta` is a different, device-oriented format. The MTA exporter renders either source format on the same timeline and encodes MP3 streams inside the MTA container, preserving clip/event timestamps.
