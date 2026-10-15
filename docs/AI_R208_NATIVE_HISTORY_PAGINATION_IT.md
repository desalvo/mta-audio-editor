# Storico AI remoto: paginazione nativa (r208)

Lo storico dei job AI persistenti nell’interfaccia nativa visualizza ora più di 50 richieste per worker tramite paginazione incrementale. Ogni worker mantiene la propria posizione; una nuova discovery invalida le risposte tardive della precedente. La funzione rimane di sola lettura, non lancia inferenza e non concede importazione senza una ricevuta locale verificata.

I risultati già completati rimangono scaricabili attraverso il percorso autenticato introdotto in precedenza.
