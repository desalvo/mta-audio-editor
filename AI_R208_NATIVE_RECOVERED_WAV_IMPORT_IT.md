# r208 — Importazione WAV recuperati nel progetto

Nella gestione delle richieste AI native pendenti è disponibile **Import recovered WAV / Importa WAV**. Il browser recupera la risposta remota con GET, rifiuta i payload diversi da `audio/wav`, controlla l'esistenza di un progetto attivo e importa il risultato come nuova traccia mediante il normale endpoint `POST /api/projects/{pid}/tracks`.

Il comando previene i doppi click concorrenti nella stessa schermata, verifica che il progetto non sia cambiato durante il recupero, controlla l'esistenza di una traccia col nome deterministico associato alla richiesta e non elimina il journal remoto dopo l'importazione.

**Limiti:** il blocco duplicati basato sul nome non è una garanzia transazionale tra finestre/processi diversi; il formato WAV viene validato dal normale importatore server. Gli output JSON e ZIP richiedono workflow specifici per adapter e rimangono scaricabili con il comando precedente. Questa chiusura riguarda l'importazione dei WAV recuperati, non l'applicazione generica di ogni tipo di risultato AI.
