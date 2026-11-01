# Recupero rimborsi Stripe e PayPal — r210

Baseline: commit ee4e37fd30c39a72638b303b01ca0cd5b090f272, full CI 41156985339 verde. Cumulativo di tutti i delta successivi non dichiarati committati.

Il percorso di verifica senza ID ora funziona per Stripe e PayPal. Stripe interroga la lista autenticata filtrata per PaymentIntent. PayPal usa l'ordine originale, l'identità e la lista rimborsi e rilegge ciascuna ricevuta esatta con il merchant originale. Le letture sono limitate e ripetute; una sola ricevuta con identità, importo, valuta, cattura e token originali può essere verificata. Una lista vuota non prova che il provider non abbia creato il rimborso: l'operazione rimane incerta. Anche risultati discordanti, cambi di merchant o amministratore e ambiguità bloccano la chiusura. Nessun secondo POST. L'esito definitivo viene applicato solo dopo la normale riconciliazione autenticata.

Il modulo amministrativo consente il riferimento vuoto per entrambi i provider, con testo IT/EN e versione delle risorse aggiornata. Rimborsi di crediti, abbonamenti e rate di recupero sono coperti, inclusi perdita della risposta e terminazione reale del processo con provider simulato.

La concorrenza Stripe può modificare il registro durante la lettura. Un nuovo tipo di errore permette un solo nuovo tentativo della riconciliazione per questa condizione specifica; se persiste la pratica rimane in attesa. Non ripete il rimborso. Test forzati per race temporaneo e persistente, e sei esecuzioni della regressione concorrente: passati. Una precedente suite aveva rilevato un'attesa intermittente; non si dichiara dimostrata la risoluzione universale di ogni race.

## Verifiche e limiti

Suite finanziaria: 358 passati, 16 browser saltati perché Playwright/Chromium non disponibili. Altri 4 casi sul rimborso di abbonamento e rata passati, compresi 2 nuovi scenari; nessun provider reale né nuova CI. Ruff, sintassi JS, Bandit 309 sorgenti/168 finding invariati/0 HIGH e inventari AI/admission/remote superati. XML in docs/validation/r210/payment-refund-batch/.

Completato localmente il recupero delle referenze perse di entrambi i provider; A5 resta aperto per gli altri esiti e prove richieste. A4 richiede movimenti e contestazioni parziali con prova finanziaria completa; B6/C6 richiedono host indipendenti; A6, F5, G5 e G6 richiedono ambienti reali; F4/F6 comprendono identità degli esecutori e revisione indipendente dei checkpoint effettivi. Non promuovere mock, build o test saltati a collaudo di target. RC invariata 32/42 = 76,2%, perimetro precommercial-20261030. Batch di almeno 20 cicli non completato.

Commit suggerito: Recover uncertain refunds across providers and harden checkout
