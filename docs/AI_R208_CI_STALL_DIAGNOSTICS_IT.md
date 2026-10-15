# Diagnostica degli stalli pytest — 0.3.0-r208

Il workflow quality imposta ora `faulthandler_timeout=240`: se un singolo test resta bloccato per quattro minuti, pytest stampa i traceback dei thread sul log del job, senza interrompere prematuramente la suite. Il timeout complessivo rimane 140 minuti per pytest e 150 per il job CI. JUnit XML e coverage sono caricati anche in caso di errori secondo le condizioni del workflow.

Verifica in ambiente software: suite `tests/test_r208_*` completata con 1166 test superati e 12 warning. La regressione globale e i test di installazione/GPU su hardware reale restano certificazioni separate.
