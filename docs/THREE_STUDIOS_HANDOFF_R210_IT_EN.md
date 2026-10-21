> Historical cycle record / Resoconto del ciclo precedente. Per lo stato attuale, i limiti aggiornati e le attività ora implementate consultare [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md) e [guida asset IT/EN](STUDIO_MANAGED_ASSETS_R210_IT_EN.md).

# MTA 0.3.0-r210 — Three studio areas / Tre macroaree

## Italiano

**Sintesi:** questo ciclo non certifica il completamento delle tre macroaree. I sorgenti preservano Vocal Studio (OddVoices, bridge DiffSinger), Audio-to-MIDI (YourMT3, Basic Pitch, riconciliazione e benchmark) e il GM renderer (FluidSynth/TinySoundFont). È stata aggiunta a entrambi i backend GM una validazione comune dei messaggi MIDI e del loro scheduling, per evitare eventi malformati o fuori blocco. Un nuovo audit opzionale prova tutte le 128 patch GM e alcune percussioni *quando* il banco con hash verificato e la libreria di sintesi sono installati.

Esecuzione sul server di **test**, non di produzione:

```sh
python scripts/check_diffsinger_ready.py --json
python scripts/check_gm_soundfont.py --output gm-audit.json
python scripts/check_audio_midi_quality.py riferimento.json predizione.json --min-instruments 10 > midi-quality.json
```

La presenza del backend DiffSinger **non** prova una voicebank o un vocoder realmente funzionante; servono modelli acustici/vocoder con diritti verificati e test con audio generato. La fonemizzazione italiana/francese, la conversione timbrica e gli strumenti espressivi avanzati non sono stati completati in questo ciclo. Il numero di strumenti MIDI riconosciuti **non** equivale alla qualità della trascrizione; servono mix stereo e MIDI multitraccia di riferimento, confronto e verifica nell'editor. L'audit GM misura soltanto la produzione di campioni finiti e non nulli: non sostituisce ascolto, qualità, performance o compatibilità hardware.

**Richiesta all'utente dopo installazione**: esiti JSON dei tre comandi, licenze e SHA-256 di voicebank/vocoder, mix e MIDI di riferimento, osservazioni d'ascolto e test di salvataggio/riapertura dei progetti. Non installare pesi non autorizzati. Nessun commit/push/tag/release è stato effettuato.

## English

**Status:** All three areas remain open pending missing features and end-to-end verification. This cycle shares strict MIDI packet/timing validation between both GM engines and adds a 128-program plus percussion offline smoke audit for a separately installed, licensed SoundFont. Neural singing, ten-to-sixteen-instrument real-mix transcription, and complete GM fidelity are **not certified** by unit tests. Use the same three commands above on a staging server with reviewed assets and report their JSON outputs. Keep individual checkpoint and vocoder rights documented; synthetic benchmarks are not model inference. No Git actions performed.
