# MTA r208 — Windows Chordino CI rate-limit fix

Il job Windows falliva nel provisioning di Sonic Annotator con HTTP 403 `API rate limit exceeded` durante una chiamata anonima a `api.github.com`.

Il workflow passa ora il token a breve durata `github.token` alla sola fase di provisioning. Lo script PowerShell usa l'header `Authorization: Bearer` per interrogare i metadati della release, non stampa il token e mantiene i controlli sul plugin `nnls-chroma.dll` e sull'eseguibile Sonic Annotator. In caso di errore remoto restituisce una diagnostica esplicita.

Il token è quello automatico di GitHub Actions e non richiede secrets personali. La verifica effettiva deve essere eseguita su `windows-latest` in GitHub Actions. Versione `0.3.0-r208` invariata.
