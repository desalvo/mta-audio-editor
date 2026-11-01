# MTA 0.3.0-r210 — stato corrente

**Verso la RC: 32/42 = 76,2%, perimetro `precommercial-20261030`; PRE-RC, 10 criteri aperti, D/E complete (2/7).** Il precedente perimetro v1 resta 29/42 = 69,0% e non è direttamente comparabile. Testi, pesi e denominatore dei criteri correnti non sono modificati da questo checkpoint.

## Ripresa e commit

Ultimo cumulativo: **MTA-0.3.0-r210-pre-RC-paypal-lost-creation-cumulative.zip**. Leggere `PAYPAL_LOST_CREATION_HANDOFF_R210.md` e `validation/r210/paypal-lost-creation/result.json`. `RC_EXECUTION_STRATEGY_R210.json` ora punta al checkpoint corrente. La copia temporanea era stata rimossa; il lavoro è ripreso dal precedente cumulativo verificato per SHA-256, senza ricostruire o perdere delta.

Baseline Git confermata: **ee4e37fd30c39a72638b303b01ca0cd5b090f272**, full CI **41156985339** verde. L'utente effettua il commit successivamente; nessuna operazione remota eseguita. I delta cumulativi successivi comprendono recupero dei checkout e delle quote, ricerca dei rimborsi incerti Stripe/PayPal, riconciliazione dello storico prima del primo accredito, webhook fuori dall'event loop e recupero automatico degli ordini PayPal con risposta di creazione persa.

Commit suggerito: `Recover uncertain payments and refunds with canonical provider history`.

## Ultimo percorso chiuso e prova

Un webhook PayPal verificato può recuperare il riferimento di un ordine creato con risposta persa, validando identità canonica, fattura originale, merchant, quota e outbox prima di riconciliare e contabilizzare. Coperti crediti, abbonamento e rata; rimborsi/revoche anticipati, disabilitazione successiva del servizio, concorrenza, rollback e vera terminazione SIGKILL, senza un secondo pagamento.

**723 casi distinti passati, 26 nuovi, nessun errore/fallimento/skip nelle selezioni correnti.** Ruff, compilazione, Bandit e inventari passano: 309 sorgenti, 168 finding invariati, zero HIGH. API provider simulate; nessuna nuova CI o prova browser/provider reale. Gli skip browser precedenti restano non accettati.

## Residui verso la RC

- **A4/A5:** i movimenti PayPal parziali e ambigui e l'attribuzione delle perdite permanenti parziali dell'abbonamento non hanno ancora un percorso generale completo di prova/allocazione. I test espliciti e i prossimi vincoli sono nel rapporto corrente e in `KNOWN_BLOCKERS_R210.md`. Non ipotizzare un debito da una sola decisione sulla disputa o da movimenti sovrapposti.
- **F4/F6:** contratti indipendenti degli interpreti e delle dipendenze, identità del backend ACE effettivo e revisione dei checkpoint installati.
- **A6/B6/C6/F5/G5/G6:** collaudi su provider, host indipendenti, sistemi nativi, container e hardware/modelli/VST effettivi; C6 conserva anche lavoro di integrazione.

Non serve importare una storia commerciale pre-release: billing e rimborsi non erano mai stati attivati. Restano i vincoli della prima attivazione e il divieto di migrazione automatica post-checkout descritti in `PRECOMMERCIAL_MODEL_R210.md`. Non ricostruire blocchi già accettati o promuovere test simulati a collaudo reale. Il batch di almeno 20 cicli non è dichiarato completato.

La cronologia precedente di questi documenti è conservata in `development-history/before-paypal-lost-creation-20261101/`; le istruzioni storiche incompatibili con il modello pre-commerciale sono superate.
