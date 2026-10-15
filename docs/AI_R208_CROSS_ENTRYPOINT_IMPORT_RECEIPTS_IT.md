# r208 — Identità durevole per importazione WAV remota

Entrambi i percorsi di recupero WAV, con journal locale e tramite discovery dello storico server, memorizzano ora `wav:<worker-kind>:<request-id>` in `recovered_ai_imports`. La verifica e la pubblicazione sono serializzate dal lock del progetto. Le ricevute precedenti (`wav:pending:<request-id>`) restano riconosciute in entrambi i percorsi, senza migrazione distruttiva. Importare lo stesso risultato da un percorso alternativo dopo aver rinominato la traccia produce HTTP 409, senza avviare una nuova inferenza o addebito.

Sono stati eseguiti 29 test mirati di importazione WAV, JSON/stem, compatibilità ed identità: 29 superati, 8 warning. La regressione r208 completa non si è conclusa entro il limite operativo e non è certificata da questo intervento. Rimangono separati i collaudi multipiattaforma e sui server/GPU reali.
