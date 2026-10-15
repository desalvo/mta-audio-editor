# MTA r208 – Recupero sicuro di annotazioni JSON

Per i risultati Whisper e Chords recuperati dal journal o dalla discovery remota, gli archivi ZIP vengono ora verificati interamente prima di applicare le annotazioni. Voci duplicate, percorsi assoluti o traversali, directory, symlink, cifratura, file estranei e limiti dimensionali non validi provocano un rifiuto 422 senza modificare il progetto. I soli membri ammessi sono il file di annotazioni specifico e l'eventuale manifest.json.

Questa chiusura riguarda **la validazione e applicazione sicura degli archivi JSON recuperati**. I collaudi GPU reali, la certificazione globale e il lifecycle/billing end-to-end non sono inclusi nella certificazione.

Test locali: 46 passed, 9 warnings; suite di recupero e importazione r208, 9 moduli selezionati.
