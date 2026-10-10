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
