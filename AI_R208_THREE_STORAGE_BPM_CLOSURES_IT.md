# MTA Audio Editor 0.3.0-r208 — tre chiusure storage e BPM

## 1. Migrazione FLAC

La route `POST /api/projects/{pid}/migrate-flac` usa il lock cross-process condiviso prima di rileggere il progetto; la migrazione audio e i relativi salvataggi rimangono serializzati rispetto agli altri writer coordinati.

## 2. Endpoint compatibile di separazione stem

La route `POST /api/stems/split`, per i progetti esistenti, acquisisce il lock *prima* di caricare lo stato corrente e lo conserva durante separazione, conversione e pubblicazione. Per un progetto nuovo resta il normale percorso di creazione. Questa soluzione privilegia la consistenza: durante la separazione sincrona l'editing concorrente del progetto preesistente rimane in attesa. Non sostituisce una transazione filesystem/database.

## 3. Stima BPM non bloccante, con rilevazione dei conflitti

La route `POST /api/projects/{pid}/tracks/{track_id}/estimate-bpm` acquisisce il lock per acquisire l'identità della traccia (file, sample rate, durata) e il valore di riferimento del tempo. Rilascia il lock per l'analisi musicale e lo riacquisisce per ricaricare il progetto. Un cambio alla traccia o al tempo produce HTTP 409 e *nessun* salvataggio BPM: non vengono ripristinati snapshot obsoleti. Le modifiche indipendenti restano preservate al successivo salvataggio.

## Verifica locale

`PYTHONPATH=. pytest -q tests/test_r208* tests/test_r207_native_remote_routes.py`: **952 passed, 9 warnings**.

I test nuovi coprono lock FLAC, BPM non bloccante con conflitto di tempo, sostituzione della traccia durante inferenza e confine protetto dell'endpoint di compatibilità. La precedente prova BPM è stata aggiornata per verificare i due periodi di lock.

## Limiti residui

Le verifiche non includono collaudo ROCm/hardware reale né processi server concorrenti distribuiti. Le operazioni sui file non costituiscono una transazione atomicamente coordinata con il salvataggio di progetto. Nessuna modifica al mirroring PackSphere; versione invariata 0.3.0-r208.
