# AI Arranger/Remix: primo collaudo con intervallo corto (r208)

**Versione applicativa invariata: 0.3.0, revisione 208.**

Nella finestra AI Arranger/Remix, impostare **Processing scope / Intervallo** su **Time range / Intervallo temporale**, poi **Start 0** e **End 10** (secondi). Selezionare la sorgente master oppure una singola traccia, verificare con **Plan / Pianifica**, quindi avviare **Generate + Add track** solo dopo aver salvato il progetto. L'audio PCM inviato al worker è ritagliato al solo intervallo scelto. L'output generato continua a essere aggiunto come **nuova traccia** secondo il comportamento già esistente; questa correzione non implementa ancora l'inserimento sulla timeline all'offset originale.

Confermare che il job termina entro il timeout e verificare la presenza e la riproducibilità del risultato. Se fallisce, esportare la diagnostica e i log dell'unità ACE-Step, senza ripetere più generazioni lunghe. Non considerare i campi `CPU: N/A` e `GPU: N/A` come consumo zero: accounting LXC/ROCm e cancellazione delle attività ACE-Step dopo il timeout rimangono **non certificati**. Non modificare i criteri di addebito e non dedurre GPU seconds dal wall time.

Questa patch corregge il limite della selezione di input, **non** certifica il metering, il timeout interno di 600 secondi ACE-Step o la cancellazione remota dell'inferenza. Il sistema deve essere sottoposto a test hardware prima della certificazione.
