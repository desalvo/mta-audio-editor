# Windows: diagnostica dell'avvio nativo (0.3.0-r209)

Se il pacchetto PyInstaller mostra `Native server did not become ready`,
la causa non è necessariamente la porta o la connessione Internet. Il programma
crea un server HTTP *locale* sulla loopback `127.0.0.1` e attende il suo endpoint
`/api/health` prima di visualizzare la finestra.

Il launcher registra gli errori in:

`%LOCALAPPDATA%\\MTA Audio Editor\\logs\\native-startup.log`

Il file è limitato a 2 MiB, con due rotazioni. Se il processo server termina,
l'errore viene mostrato immediatamente con il riferimento al log. Il tempo di
attesa iniziale è 90 secondi, per evitare falsi negativi nelle prime esecuzioni
su Windows; può essere configurato tramite `MTA_NATIVE_STARTUP_TIMEOUT` (20–180s).

**Diagnostica Windows**: chiudere MTA, aprire PowerShell ed eseguire:

```powershell
Get-Content "$env:LOCALAPPDATA\\MTA Audio Editor\\logs\\native-startup.log" -Tail 100
```

Non cancellare la cartella dei progetti e non reinstallare i modelli AI prima
di avere verificato il log. I test locali senza Windows non costituiscono una
certificazione di avvio dell'eseguibile PyInstaller sul sistema operativo reale.
