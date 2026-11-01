# SAM Audio: caricamento e diagnosi — 0.3.0-r210 PRE-RC

**RC 34/42 = 81,0%; F4 aperto.** La diagnostica inviata dall'utente registra due fallimenti `sam_model_load_failed` alle 15:42 e 15:51 UTC del 1 novembre 2026; contiene soltanto `CalledProcessError`, non l'eccezione originale. Il tempo CPU e lo stato della GPU non dimostrano la causa. Non è possibile concludere da questi dati se il problema sia accesso, rete, modello, memoria o altro.

## Correzioni

- Nel cumulativo immediatamente precedente il worker SAM lanciato con `python -I` poteva cercare `sam_audio_compat` come modulo di primo livello e fallire: ora importa `app.sam_audio_compat`. La regressione è stata riprodotta prima della modifica ed è coperta dall'avvio reale di uno script Python isolato da una directory temporanea. Librerie torch/SAM e output WAV di quel test sono sintetici; non prova inferenza con pesi reali.
- Gli errori di caricamento classificabili riportano codici fissi per accesso negato, identificativo/modello non trovato o non accessibile, limite del servizio, rete/cache, formato checkpoint e memoria insufficiente. La classificazione non registra il testo arbitrario dell'eccezione. Il trasferimento del modello al dispositivo è segnalato come fase distinta; gli errori sconosciuti restano tali. Non viene modificata la policy o aggirato l'accesso ai checkpoint.
- Le indicazioni nel messaggio utente rimandano al controllo pertinente. Le misurazioni invalide rimangono invalide.

## Prove e passo sul sistema reale

Selezione finale: **338 passati, 0 saltati, 0 fallimenti/errori**; vedi `validation/r210/sam-model-load-diagnostics/tests-final.xml`. Ruff, inventari di esecuzione/ammissione/trasporto e revisione Bandit passano (168 finding riesaminati, zero HIGH). Nessuna prova su checkpoint SAM reale, credenziali Hugging Face o GPU ROCm del sistema utente; nessuna CI remota eseguita.

Per comprendere l'errore già avvenuto, il journal può ancora contenere la descrizione filtrata, a differenza del bundle strutturato. Sul server, il seguente comando usa l'ora UTC degli eventi e seleziona solo la riga di uscita del worker:

```bash
sudo journalctl -u mta-server.service --since '2026-11-01 15:40:00 UTC' --until '2026-11-01 15:54:00 UTC' --no-pager | grep -F 'AI metered worker exited nonzero'
```

Prima di condividere l'output, eliminare eventuali credenziali e dati personali. Se la riga non è più disponibile, installare il cumulativo e ripetere la separazione: il nuovo codice diagnostico può distinguere le classi di errore previste; per quelle sconosciute servono ancora dettagli dal journal. La disponibilità del modello e i diritti di accesso dipendono dal servizio effettivo.

## Ripresa

Archivio `MTA-0.3.0-r210-pre-RC-sam-model-load-diagnostics-cumulative.zip`. Baseline Git confermata `ee4e37fd30c39a72638b303b01ca0cd5b090f272`; ultimo commit differito e nessuna nuova CI remota. Restano A6,B6,C6,F4,F5,F6,G5,G6. Non dichiarare risolto il problema originario senza prova sul servizio reale. Commit cumulativo suggerito: `Recover canonical payments and harden AI worker startup and SAM diagnostics`.
