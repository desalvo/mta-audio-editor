# MTA 0.3.0-r208 — controllo integrità PCM della generazione locale

Nel percorso comune di pubblicazione Arranger/Remix la validazione non si limita più all'header WAV: legge tutti i frame PCM dichiarati e ne controlla la lunghezza rispetto a numero di canali e sample width. Un risultato troncato viene rifiutato prima di creare file di progetto o modificare tracce.

Verifica eseguita: 41 test mirati superati, 8 warning di deprecazione. La regressione globale è stata avviata ma non terminata entro il limite di esecuzione; non è certificata. Restano aperti i test di inferenza ACE-Step/GPU reale e la verifica end-to-end completa dell'area generazione locale e legacy.
