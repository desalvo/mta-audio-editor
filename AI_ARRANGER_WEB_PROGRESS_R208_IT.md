# AI Arranger — stato esecuzione visibile (0.3.0-r208)

La generazione avviata da **Generate + Add track** mostra una barra indeterminata, il tempo trascorso e disabilita il pulsante finché la richiesta termina. Il completamento o l'errore viene riportato nella finestra se ancora aperta. Non viene mostrata una percentuale non supportata dall'API.

## Limiti del collaudo e indagini ancora aperte

Il log EL10 conferma ROCm e il caricamento del modello, ma `starlette.requests.ClientDisconnect` riguarda una richiesta HTTP multipart interrotta e **non dimostra** l'esito del job di generazione. Le richieste MTA→ACE-Step e browser→MTA sono ancora sincrone e possono risentire di reverse proxy, gateway e timeout del client. Occorre ispezionare contestualmente `journalctl -u mta-server`, `journalctl -u mta-ace-step`, i timeout del proxy e gli eventuali job ACE-Step completati. Un API/job asincrono con job ID, poll dello stato persistente e progresso modello è un intervento successivo necessario per un progresso reale e la disconnessione sicura del browser.

Per il prossimo collaudo, usare una sorgente WAV di pochi secondi (non una traccia da 252 s), osservare gli errori HTTP sul browser e verificare la nuova traccia dopo completamento.
