# Recupero WAV remoto: idempotenza dopo rinomina (r208)

L'importazione manuale di un WAV riscoperto usa ora una ricevuta persistente `wav:<kind>:<request_id>` nel campo `recovered_ai_imports` del progetto. La ricevuta viene scritta nella stessa operazione `save_project` che registra la traccia, sotto il lock di pubblicazione del progetto. Un import ripetuto viene rifiutato anche se nel frattempo l'operatore ha rinominato la traccia.

Rimane anche il controllo precedente sul nome per proteggere i progetti creati prima dell'introduzione delle ricevute. Worker distinti con lo stesso request_id continuano a essere indipendenti. Il recupero non invia nuove richieste di inferenza o contabilizzazione.

Verifiche software: suite r208 (1167 test superati, 12 warning); test dedicati WAV/JSON/stem (12 test superati). Restano separati i collaudi hardware e la regressione globale di tutte le famiglie di test.
