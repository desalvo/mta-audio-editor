# r210 accelerated finalization / Finalizzazione accelerata

## Italiano
Correzione: il benchmark Audio-to-MIDI verifica stabilità di dimensione, mtime e ctime dell’inode e l’esatta lunghezza della lettura, rifiutando file alterati durante la lettura.
Test eseguiti localmente su nove moduli: 96 superati, 0 falliti, 5 saltati. Non è una regressione generale. Nessuna inferenza neurale reale o prova di riproduzione GM eseguita.
**Ancora aperto:** collaudo inferenze con checkpoint autorizzati e relativa conformità licenze, benchmark musicali reali 10–16 strumenti, test browser/native/hardware e regressione integrale senza richieste di rete non autorizzate. Nuovi difetti software potrebbero emergere. Server reali e Git non modificati.

## English
Correction: Audio-to-MIDI benchmark verifies inode size, mtime, ctime and exact read length; rejects inputs changed during reads.
Local nine-module test selection: 96 passed, 0 failed, 5 skipped. Not a full repository regression. No real neural inference or GM audition.
**Open:** independently licensed checkpoint inference and rights review, 10–16-instrument real music benchmarks, browser/native/hardware acceptance, and full offline-safe regression. Additional software changes may be required. No server or Git actions.
