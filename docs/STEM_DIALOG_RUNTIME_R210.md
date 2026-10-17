# Separazione tracce: controlli e runtime server — 0.3.0-r210

I pulsanti Download DrumSep e Add singer si trovano nel contenuto della finestra e non nel footer utility-actions. Lo stile leggibile ora è applicato a tutti i pulsanti utility-btn del workflow stem, con sfondo scuro, testo chiaro, text-fill esplicito e focus da tastiera. La correzione copre sia il menu contestuale delle tracce sia il workflow di importazione/separazione.

Il catalogo lead/backing prima cercava audio_separator solo nel processo web. Il download tentava inoltre di importarlo nel venv web, anche quando l'installer aveva predisposto un ambiente AI isolato. Ora sul server il catalogo verifica il pacchetto nell'interprete operatore configurato per backing-vocals; il download viene delegato allo stesso interprete mediante il bridge interno ai_model_download.py. Non si installano librerie ML nel venv web. Percorso dell'interprete e directory dei modelli provengono dalla configurazione operatore, mai da input API. Il modello resta vincolato al catalogo consentito.

Web e worker usano la stessa cache: MTA_LEAD_BACKING_MODEL_DIR esplicita ha precedenza; altrimenti usano MTA_AI_VOCAL_MODELS_DIR, impostata dall'installer. Il download controlla la presenza finale del file prima di dichiararsi completato. Errori dell'interprete non diventano disponibilità fittizia; vengono gestiti come errore del download e registrati nel log.

La separazione server lead/backing continua nel worker globale registrato e misurato. Il download dei pesi non esegue inferenza. Nessuna variazione ai controlli di billing, autenticazione e accounting. Nessuna scansione automatica di ambienti non configurati: se l'installazione AI non è conclusa occorre prima completarla e riavviare il servizio.

## Validazione

Test mirati: catalogo nell'interprete AI corretto, pacchetto assente/interprete guasto/timeout, download delegato e cache condivisa, modello non consentito, comportamento nativo, permanenza dell'inferenza nella coda globale, regole CSS. Prova effettiva del bridge in un sottoprocesso con pacchetto separatore simulato, senza modelli o rete. Non è un'inferenza audio-separator reale.

La verifica visiva in browser non è stata eseguita: il download del browser di test ha restituito un archivio incompleto. Restano da verificare sul server il rendering dei due pulsanti e una separazione lead/backing reale, oltre alle prove SAM/ROCm già pendenti. I risultati della regressione completa sono in validation/r210-stem-dialog-*.
