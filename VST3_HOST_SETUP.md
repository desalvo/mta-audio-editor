## r33 variable-length stereo offline rendering
The opt-in isolated native adapter accepts 1–1,048,576 mono or stereo frames, 48 kHz interleaved float32, retaining VST3 processor state across all 512-sample blocks and processing the final partial block. Each insert executes in a separate subprocess. This is not a realtime playback interface; MIDI and automation routing, plugin latency alignment and extended format negotiation are not yet integrated with this chain.

## r32: experimental native PCM serial-insert rendering

The separately built C++20 probe can render precisely 65536 mono 32-bit floating-point samples at 48 kHz through a Steinberg-SDK-backed plugin. The Python `native/vst3_probe/native_chain.py` adapter serializes each insert to a separate bounded subprocess and passes its output PCM to the next. Plugin modules must be installed under an allow-listed `MTA_VST3_PATHS` directory; the SDK itself is not bundled.

This is a restricted **offline diagnostic** path only, with no stereo, MIDI scheduling across insert boundaries, parameter automation from projects, plugin latency compensation, or realtime support. Do not use it for regular project exports yet. Any plugin timeout, failure, invalid PCM or NaN/Inf fails the entire chain. Plugin processes execute arbitrary third-party code with the user's privileges: timeout and memory limits do **not** amount to a security sandbox.

## 0.3.0-r21 (2026-10-10)

- Add explicit isolated VST3 `--configure` diagnostic: test processor setup at 48 kHz / 512 samples using a supported 32/64-bit format, without activation or processing.
- Return validated processing setup metadata to the Python probe; keep `native_host_ready=false` and production playback unchanged.
- Add tests for CLI safety, opt-in configuration, and mobile version consistency.
- The SDK-specific code path still requires compile/runtime validation against the Steinberg VST3 SDK and real plugins.

# VST3 insert hosting / Hosting insert VST3

## English

This initial experimental integration supports **offline VST3 effects on individual audio tracks** on desktop builds where the optional Python dependency `pedalboard` is installed. Install it into the Python environment used by MTA Audio Editor: `pip install -r requirements-vst3.txt`. It is not included in native installers by default. Plugins are discovered from OS-standard VST3 directories or paths listed in `MTA_VST3_PATHS` (separated by the OS path separator). Rescan by reopening the Add VST3 dialog.

In the mixer choose **Insert → VST3 (desktop)**, select a discovered plugin and add it. MTA stores its local path, not the plugin binary. The installed effect is applied during track rendering/export, after built-in inserts; built-in inserts placed after an active VST3 will cause an explicit error rather than silently changing the effect order. External VST3 software must be installed separately and supported by the current CPU architecture. Missing or incompatible plugins produce explicit errors. Plugins are loaded in an isolated Python subprocess for export. **Not yet supported:** native plugin editor windows, interactive parameter automation, live monitoring or VST3 on Master. Use the bypass toggle to compare with the dry signal.

## Italiano

Questa prima integrazione sperimentale supporta **effetti VST3 offline sulle singole tracce audio** nelle app desktop dove è installata la dipendenza opzionale Python `pedalboard`. Installa con `pip install -r requirements-vst3.txt` nell'ambiente Python utilizzato da MTA. La dipendenza non è ancora inclusa automaticamente negli installer nativi. I plugin sono rilevati nelle cartelle VST3 standard del sistema o nei percorsi elencati in `MTA_VST3_PATHS`. Per aggiornare la lista, riapri il dialogo Aggiungi VST3.

Nel mixer scegli **Insert → VST3 (desktop)**, seleziona un plugin rilevato e aggiungilo. Nel progetto viene memorizzato il percorso locale, non il binario. Il plugin viene applicato durante il rendering/esportazione della traccia, dopo gli insert integrati. Insert integrati posizionati dopo un VST3 attivo provocano un errore esplicito per non alterare silenziosamente l'ordine. Plugin mancanti/incompatibili producono un errore esplicito. Durante l'esportazione il VST3 gira in un processo Python separato. **Non ancora supportati:** finestre native di setup dei plugin, automazioni dei parametri, monitoraggio in tempo reale e VST3 sul Master.


## r298 parameters / parametri
The Insert VST3 setup scans exposed normalized parameters (0–1), lets you adjust them, and passes them to the isolated renderer. This is not the native VST3 graphical interface and does not enable real-time hosting.

Il setup VST3 legge i parametri normalizzati (0–1), consente di modificarli e li passa al renderer isolato. Non è l’interfaccia grafica originale del plugin e non abilita il processamento live.

## 0.3.0-r4: isolated native binary factory probe

`native/vst3_probe` builds a C++20 CLI with CMake. It checks whether a
native VST3 module exports Steinberg's `GetPluginFactory` symbol. Run it only
through `native.vst3_probe.probe.probe_plugin` (a separate process with a
bounded timeout). **This does not instantiate a VST3 plugin**, process sound,
open an editor or implement a working real-time VST3 host. The existing
Pedalboard offline fallback remains unchanged. VST3 bundles execute untrusted
native code during loading: test unknown plugins only in a restricted environment.

`native/vst3_probe` compila un tool C++20 che verifica l'esportazione
`GetPluginFactory` nel binario del plugin. Eseguirlo tramite `probe_plugin`,
in processo separato e con timeout. Non è ancora un host VST3 completo:
non istanzia plugin e non elabora audio live. L'host Pedalboard offline resta
invariato. Il caricamento di binari esterni esegue codice di terze parti.

### r22: SDK checkout validation
GitHub-generated VST3 SDK ZIP archives omit Git submodule sources. Use `git clone --recursive https://github.com/steinbergmedia/vst3sdk.git` and `git submodule update --init --recursive` before configuring `-DMTA_VST3_SDK_ROOT=...`. The CMake configuration now rejects incomplete SDK trees.

### r27 transport context
The isolated offline diagnostic now supplies deterministic musical transport (120 BPM, 4/4), with sample position and musical time advancing each block. This is diagnostic-only; it does not activate the VST3 host for realtime playback.

### Offline WAV export (r35)

Python API `native.vst3_probe.native_chain.render_native_wav(source, destination, plugins, executable)` supports 48 kHz mono/stereo PCM16 files up to 1,048,576 frames. Requires an SDK-enabled probe and VST3 plug-in(s). This is an opt-in test/export path, not the realtime engine. Output replaces the destination only after success.

### High-resolution WAV export (r36)

`render_native_wav()` accepts 48 kHz signed integer PCM16, PCM24 and PCM32 mono/stereo WAV input. It preserves the input bit depth and frame count, clamps overshoots safely, rejects non-finite plugin output, and atomically publishes the final file only on success. IEEE floating-point WAV and realtime processing are not enabled.

### Experimental batch render (r38)
Create a JSON manifest with `{ "schema": 1, "jobs": [{"source":"input.wav", "destination":"output.wav", "plugins":[["/path/plugin.vst3", "32hexCID"]]}] }`, and run `python -m native.vst3_probe.batch_wav_cli batch.json --probe /path/mta_vst3_probe`. Output JSON summarizes successes and failures. Relative WAV paths resolve from manifest directory. Outputs are independently atomic, not a multi-output transaction.
