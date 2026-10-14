# MTA 0.3.0-r208 — supervisione worker AI legacy

- `run_external_worker` supporta ora `cancel_event`, verificato prima e durante l'esecuzione.
- Timeout e cancellazione terminano il worker; su POSIX viene isolata e ripulita l'intera sessione di processi, inclusi figli ancora attivi dopo l'uscita del processo principale.
- Il worker viene atteso e il WAV viene letto solo dopo un completamento riuscito; i byte restano quelli dello snapshot validato.
- L'esecutore legacy non produce automaticamente metering affidabile o addebiti; non è equiparato alla coda AI fatturabile.
- Test nuovi: pre-cancel, cancel in corsa, timeout, exit nonzero. Regressione selezionata: 30 superati, 8 warning di deprecazione.

## Limitazioni aperte

L'integrazione universale con lo scheduler AI, la metrica GPU, tutti i generatori nativi, e la prova su modelli/hardware reali non sono certificate. La terminazione ad albero garantita su Windows richiede un Job Object o processo di supervisione dedicato; qui la pulizia dei discendenti è garantita sul solo POSIX.
