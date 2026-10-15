# MTA Audio Editor 0.3.0-r209 — verifica server

La revisione applicativa sale da 208 a 209. Il pacchetto server RPM e DEB
include ora `VERSION`, `REVISION`, `BUILD_INFO` e `RELEASE_CHANNEL` nello
staging. La pagina About espone modalità d'installazione e disponibilità GPU;
quest'ultima è una verifica di visibilità del runtime, **non** di consumo
attribuito al singolo job.

## Dopo installazione

```bash
rpm -q mta-audio-editor-server
rpm -ql mta-audio-editor-server | grep -E '/(VERSION|REVISION|BUILD_INFO|RELEASE_CHANNEL)$'
sudo systemctl restart mta-server.service
curl -fsS http://127.0.0.1:8081/api/health
```

Usare la porta HTTP configurata, se diversa da 8081. L'API health deve riportare
`"version":"0.3.0"`, `"revision":"209"` e il build ID numerico. In About
verificare che i tre campi corrispondano; su RPM è attesa la dicitura
`Native Linux package (RPM/DEB)` e con ROCm visibile `AMD ROCm available`.

Se la UI sembra invariata, ricaricare forzatamente la pagina. L'HTML della
r209 richiede `app.js?v=0.3.0-r209` per invalidare la cache precedente.
Nel pannello AI Arranger/Remix **Time range** è preselezionato, con inizio 0 e fine 10 secondi visibili; modificare
**Start (seconds)** e **End (seconds)**. Il server elabora esclusivamente
l'intervallo selezionato.

## Limiti del collaudo

La revisione r209 non certifica automaticamente il metering dei job ROCm/LXC
né risolve per sé il timeout interno 600 s di ACE-Step: utilizzare un
intervallo breve (es. 0-10 s), batch 1, e verificare il risultato.
Non interrompere o reinstallare worker attivi durante i test.
