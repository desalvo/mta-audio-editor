# Diagnostica unattended delle installazioni — MTA 0.3.0-r208

Questi script controllano **l'app già installata**, non la suite pytest del sorgente. Eseguono soltanto controlli non distruttivi, senza aprire o alterare progetti, avviare inferenze o generare addebiti. Richiedono **Python 3** (solo standard library), oltre all'applicazione o al server da verificare. Lo script per Windows richiede PowerShell; gli script macOS/Linux/server richiedono Bash. Non occorrono i requisiti Python del server né pytest. I controlli codesign, spctl, rpm/dpkg e GPU sono opzionali secondo la piattaforma.

Eseguire i comandi **dalla root del pacchetto sorgente estratto**, non dall'interno del bundle `.app`. Gli script non sono garantiti presenti negli installer precedenti. Se il percorso o il nome dell'eseguibile varia, passare `--app`.

## macOS

```bash
bash scripts/diagnose_macos_r208.sh --app '/Applications/MTA Audio Editor.app' --output "$HOME/mta-diagnostics"
```

Verifica Info.plist, presenza dell'eseguibile, firma `codesign` e valutazione `spctl` (il rifiuto Gatekeeper viene segnalato come avvertimento). Non apre la GUI.

## Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\diagnose_windows_r208.ps1 --app 'C:\Program Files\MTA Audio Editor\MTA Audio Editor.exe' --output "$env:USERPROFILE\mta-diagnostics"
```

In alternativa usare `pwsh -File ...`. Python 3 deve essere accessibile tramite `py` o `python`. Verifica l'eseguibile e, se PowerShell lo consente, lo stato della firma Authenticode. Non modifica installazione, registro o configurazione.

## Linux

```bash
bash scripts/diagnose_linux_r208.sh --app /usr/bin/mta-audio-editor --output "$HOME/mta-diagnostics"
```

Si può passare un percorso AppImage o una directory dell'installazione. I metadati DEB/RPM sono informativi e opzionali.

## Server

```bash
bash scripts/diagnose_server_r208.sh --url 'http://127.0.0.1:8080' --output "$HOME/mta-server-diagnostics"
```

Se è pubblicato in HTTPS usare l'URL HTTPS corretto. Il controllo richiama **solo endpoint HTTP GET**, senza autenticazione e senza token; non avvia job o modifica database. L'URL remoto HTTP non cifrato produce un avvertimento. Sondaggi non invasivi della disponibilità degli strumenti Docker, ROCm e NVIDIA sono opzionali: la loro presenza **non certifica** inferenza o contabilizzazione GPU.

## Output e codici

Ogni script produce `report.json`, `report.md` e `mta-r208-<piattaforma>-diagnostics.zip` nella directory `--output`; se omessa, viene creata una directory temporanea, indicata su stdout. `0` = verifiche obbligatorie superate; `1` = una o più fallite. Le verifiche facoltative non bloccanti sono etichettate `WARN` o `SKIP`.

L'archivio contiene **solo i due report sintetici**: non include audio, progetti, file di configurazione, log applicativi, variabili d'ambiente, credenziali o token. Controllare comunque il report prima di condividerlo, perché include informazioni sulla macchina e percorsi degli eseguibili.

## Limiti della certificazione

Non vengono testati automaticamente apertura GUI, riproduzione, VST3, periferiche audio, inferenza reale ACE-Step, Remix/Arranger end-to-end, billing, crash/recovery, upgrade migratorio o integrità dei progetti utente. Il runner `scripts/unattended_certification_r208.py` è invece per **test del codice sorgente** e non sostituisce questi script.
