# r208 — Importazione WAV da journal locale: ricevuta persistente

L'importazione delle richieste WAV in sospeso ora registra una ricevuta `wav:pending:<request_id>` insieme alla pubblicazione della traccia, tramite il writer già esistente e sotto lock di progetto. Il controllo precedente sul nome della traccia rimane per i progetti storici. Rinominare la traccia non rende la stessa richiesta nuovamente importabile. Le importazioni da discovery remota mantengono le ricevute distinte `wav:<worker>:<request_id>`. Non viene ripetuta alcuna inferenza né addebitata una richiesta nuova.

Test mirati: `tests/test_r208_pending_wav_durable_receipt.py`, `tests/test_r208_recovered_import_atomic.py`, `tests/test_r208_discovered_wav_project_import.py`. La regressione r208 estesa è stata avviata ma non conclusa entro i limiti operativi di questa esecuzione; non costituisce certificazione globale.
