# File del progetto: tracce, conversione e backup

In **File del progetto** la colonna **Tracce** indica dove un file audio è usato; le tracce conservate inattive sono contrassegnate. La stessa sorgente può essere usata da più tracce e viene sostituita per tutte le relative associazioni e clip della libreria.

Per i file WAV PCM interi a 8/16/24 bit e FLAC è possibile convertire rispettivamente verso FLAC o WAV. La conversione verifica frequenza, canali e hash dei campioni decodificati prima della sostituzione. Formati diversi, PCM floating-point e profondità superiori a 24 bit non vengono convertiti da questa funzione, per evitare perdita silenziosa. Per passare a WAV, il progetto esce dalla modalità di conversione automatica in FLAC; gli altri file già FLAC non sono riscritti.

Prima di sostituire una sorgente viene conservata una copia originale nell'area **originali**, identificata come backup nella stessa finestra. **Ripristina** consente di scegliere il file audio da sostituire, riassegna il backup a tutte le tracce che lo usano e conserva a sua volta una copia del file sostituito. I backup rimangono anche durante la pulizia dei media inutilizzati e si possono eliminare manualmente quando non servono.

Fermare la riproduzione prima dell'operazione. La conversione o il ripristino attendono la conclusione dei job attivi del progetto; in presenza di job attivi l'operazione viene rifiutata e può essere ripetuta successivamente. I progetti portabili includono i backup, che aumentano lo spazio occupato. Le operazioni sono verificate localmente con FFmpeg; la verifica nelle app native e sul dispositivo resta necessaria.
