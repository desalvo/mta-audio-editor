# Lyrics server: dispositivo e notifiche — 0.3.0-r210

Lo screenshot del 17 ottobre mostra un worker uscito con codice 1, categoria worker_exit, prima della produzione di un risultato valido. La scritta metering invalid è una conseguenza dell'uscita fallita: non dimostra un difetto del contatore. Senza il dettaglio del journal non si può attribuire con certezza quella specifica esecuzione a una singola eccezione.

## Correzione dispositivo

Il wizard accetta e salva MTA_AI_DEVICE=auto/cpu/cuda/rocm. native_ai_device restituiva direttamente anche auto e rocm, che non sono nomi di dispositivo PyTorch utilizzabili per caricare Whisper. Ora auto esegue il rilevamento effettivo; rocm richiede un runtime HIP disponibile e restituisce cuda, l'API PyTorch utilizzata anche dalle GPU AMD. Nessun fallback CPU silenzioso quando è richiesto esplicitamente ROCm. cpu e i dispositivi espliciti preesistenti restano supportati.

Anche l'indicatore del catalogo non presenta più auto come un dispositivo hardware effettivo. Aggiunte categorie diagnostiche limitate per runtime ROCm non disponibile, dispositivo PyTorch non valido e torch.OutOfMemoryError. Non vengono esposti al client stderr arbitrari, prompt o credenziali. Controlli cgroup, accounting e condizioni di fatturabilità non sono stati ridotti: un worker fallito resta non fatturabile.

## Correzione notifiche

Il popup richiede una chiusura esplicita della finestra registrata come origine del job. Una semplice sostituzione del contenuto durante il polling non significa chiusura. I job senza origine nota, inclusa la cronologia recuperata dopo un reload, restano visibili nella lista ma non producono popup di completamento. Lo stato resta disponibile nel centro job; le email non sono modificate.

Il polling dei download modelli usa ora il polling media che rispetta la chiusura della finestra, aggiorna sempre il riferimento al contenuto corrente e non riapre il progresso dopo una chiusura. Il completamento osservato dalla finestra viene registrato prima dei callback: chiudere il risultato al 100% non abilita una nuova notifica. Se disponibile, anche completed_at impedisce notifiche per chiusure successive alla fine del job.

Le notifiche di download parlano di modello disponibile sul server e non di tracce aggiunte al progetto; non mostrano Apri progetto. I download non avviano una riconciliazione di progetto superflua. Per i risultati AI di progetto resta l'attesa della riconciliazione/persistenza prima del popup e dell'acknowledgement.

## Verifica e limiti

Test di dispositivo con runtime PyTorch simulato e percorso Whisper completo fino alla trascrizione simulata; test JavaScript Node sul monitor effettivo: finestra aperta, ridisegnata, sconosciuta, chiusa prima della fine e chiusa dopo il completamento. Test preesistenti di attesa riconciliazione aggiornati per rappresentare una chiusura esplicita.

Non eseguita inferenza Whisper reale sulla GPU del server. Dopo aggiornamento RPM e riavvio verificare lyrics con auto o rocm; se fallisce ancora raccogliere la diagnostica ZIP o la riga del journal AI metered worker exited nonzero. L'immagine da sola non contiene lo stderr originale. La certificazione funzionale rimane aperta.
