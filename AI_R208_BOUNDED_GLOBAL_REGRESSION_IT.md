# Regressione globale r208: concorrenza controllata

La pipeline globale mantiene otto shard deterministici con report individuali e certificazione fail-closed, ma esegue al massimo due shard simultaneamente (`max-parallel: 2`). Questo limita la contesa su CPU/RAM durante i test con compilazioni native C++ senza ridurre la copertura della matrice. La verifica finale richiede ancora gli otto report validi.

Convalida locale di questo ciclo: 24 test mirati passati, 8 warning. Tentativo degli otto shard locali avviato, ma interrotto senza riepilogo globale: non costituisce una certificazione. Restano necessari i test su runner CI e su hardware reale. Timeout esistenti invariati: 150 minuti job principale e 140 minuti per pytest.
