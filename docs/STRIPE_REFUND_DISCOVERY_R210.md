# Recupero automatico rimborso Stripe incerto — r210

Base: commit ee4e37fd30c39a72638b303b01ca0cd5b090f272, full CI 41156985339 verde; tutti i delta successivi restano cumulativi e non dichiarati committati.

## Percorso completato

Un rimborso inviato una sola volta può essere creato da Stripe e perdere la risposta, lasciando l'operazione locale incerta senza ID. L'amministratore può ora lasciare vuoto il campo ID e premere verifica: il server elenca su Stripe i rimborsi dell'intento originale, con pagine e tempi limitati e due letture complete stabili. Individua una sola ricevuta con metadata immutabile della specifica operazione e verifica identità, valuta, importo e stato. Poi rilegge la risorsa esatta e usa la normale riconciliazione prima di chiudere l'operazione. Nessun nuovo POST, rimborso o accredito derivano dalla ricerca. Riferimento API: https://docs.stripe.com/api/refunds/list .

Nessuna corrispondenza, duplicati, ricevute contraddittorie, lista mutevole, limiti superati o provider indisponibile lasciano l'esito incerto. L'amministratore deve ancora essere attivo al momento di salvare la ricevuta e dell'eventuale chiusura. PayPal richiede ancora il riferimento esatto. I testi di interfaccia IT/EN e la versione delle risorse statiche sono aggiornati.

## Prove e limiti

166 test passati e 12 casi Chromium saltati: test reale API amministrativa e controlli di ruolo/CSRF, processo terminato dopo dispatch, risposta persa, duplicati, mutazione, errato importo/destinatario, revoca amministratore e rimborsi concorrenti. Provider simulato; nessuna sandbox, nuova CI o browser locale. Ruff e verifica sintassi JS passati. Scansione Bandit 309 sorgenti, 168 finding identici (0 HIGH), inventari AI 780 e ammissione 173; revisione esplicita di 31 punti trasporto, uno nuovo solo lettura.

Questo chiude il sottopercorso locale Stripe di ricerca del riferimento, non l'intera area A5. A4/A5 richiedono ancora la gestione delle contestazioni/movimenti parziali e le prove di provider; PayPal senza ID resta da risolvere. Altri blocchi: F4/F6 runtime e diritti, C6/B6 host indipendenti, A6/F5/G5/G6 ambienti reali. RC invariata 32/42=76,2% (precommercial-20261030). La richiesta del batch di almeno 20 cicli resta aperta, non considerare le combinazioni di test come cicli completati.

Commit cumulativo suggerito: Discover uncertain Stripe refunds and harden checkout recovery
