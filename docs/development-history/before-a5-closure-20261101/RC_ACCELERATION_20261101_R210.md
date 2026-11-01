# Piano accelerato verso la RC — MTA 0.3.0-r210

Baseline: commit ee4e37fd30c39a72638b303b01ca0cd5b090f272, full CI 41156985339 verde. I due interventi checkout successivi sono cumulativi e non ancora dichiarati committati. Misura invariata: **32/42 = 76,2%** dei criteri RC revisione precommercial-20261030; 2/7 macroaree accettate. Non è una percentuale dell'intero prodotto.

## Ordine di esecuzione

1. **Finanza A4/A5, percorso critico software.** Lavorare per esiti completi di un ordine nato in questa release: creazione, approvazione, acquisizione, rimborsi/dispute, esito incerto e recupero autenticato. Per ogni esito includere retry, concorrenza e conservazione della quota originale. Chiudere ogni percorso end-to-end prima di avviarne altri. Non importare storici commerciali pre-release inesistenti. Il controllo sulla quota di questo ciclo è parziale, non chiude A5.
2. **F4/F6, lavoro indipendente da finanza.** Completare identità del runtime e dei checkpoint per ciascun esecutore ancora scoperto, quindi revisione indipendente dei pesi realmente installati e delle relative licenze. Priorità agli esecutori effettivamente abilitati; registrare per quelli opzionali il relativo stato senza simularne l'accettazione. F4 e F6 restano aperti finché soddisfatti i rispettivi criteri originali.
3. **C6 insieme a B6.** Completare il lavoro di integrazione del cambio concorrente e preparare una singola campagna su host indipendenti che copra perdita worker, partizione, drain e ripristino. Conservare prove separate per B6 e C6: un solo scenario non certifica automaticamente entrambi.
4. **Collaudi esterni preparabili in parallelo:** A6 sandbox Stripe/PayPal; F5 sistemi nativi NC; G5 container e orchestrazione; G6 sistemi installati, GPU, modelli e VST. Preparare prove e prerequisiti mentre procede il codice, poi raccogliere gli esiti sugli ambienti effettivi. I due test esistenti in tests/test_r210_real_provider_sandbox.py sono letture e riconciliazione su copia isolata: non coprono da soli l'intero ciclo A6.

## Regole per ridurre i tempi

- Una coda per criterio con esito, prova mancante e prossimo test; evitare di ripetere suite già validate se il delta non le tocca. Eseguire regressioni mirate per ogni percorso e le verifiche di sicurezza e inventario interessate.
- Raggruppare i cambi locali compatibili in un cumulativo; mantenere il messaggio di commit cumulativo dall'ultimo commit confermato. Full CI prima del consolidamento RC e ogni volta che una modifica interessa i gate o i target estesi.
- Registrare blocchi reali specifici per ambiente, credenziali sandbox o asset autorizzati; nel frattempo continuare i blocchi indipendenti. Niente modifiche ai dati/server effettivi o alle risorse remote.
- Promuovere un criterio soltanto quando la sua prova richiesta è completa; non ripesare la matrice né trasformare build, mock o skip in accettazione su target reale.

## Delta corrente

Un checkout PayPal di abbonamento già creato verificava solo i centesimi arrotondati prima di riaprire il link. Ora controlla la quota immutabile anche al retry: un cambiamento sub-centesimo o una quota originale mancante blocca il link senza nuova richiesta provider. Restano inalterati il recupero e la verifica degli esiti già conclusi. Suite mirata finale 82 passati; Ruff e inventari di sicurezza passati; nessun provider reale o nuova CI eseguiti.

Commit suggerito: Harden checkout recovery and prioritize RC acceptance
