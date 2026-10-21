# Gestione centralizzata dei modelli AI / Central AI model administration

Versione 0.3.0-r210 · 21 ottobre 2026.

## Italiano

Aprire **Impostazioni → Modelli AI** come amministratore. Il nuovo inventario è raggruppato per motore e ricerca ogni singolo file nei percorsi modello configurati: checkpoint, configurazioni, dizionari, vocoder, encoder e altre dipendenze. Sono inclusi anche i membri mancanti degli inventari gestiti: un file eliminato non scompare dal modello previsto. La tabella ha paginazione e conteggio totale; eventuali errori di accesso o metadati non validi sono espliciti. Oltre 200.000 file la scansione fallisce chiaramente, senza restituire un elenco parziale spacciato per completo.

### Azioni

- **Scarica dalla fonte:** recupera il file originale da una fonte fissata, verifica revisione, dimensione e digest prima della pubblicazione. Il catalogo distribuito contiene pin ufficiali per YourMT3 noPS/PS e sorgenti, RVC/HuBERT/RMVPE, Seed-VC/Whisper/BigVGAN/CAMPPlus, Demucs, Transkun e i pacchetti completi Qixuan/vocoder. Le aggiunte MR-MT3 sono gestite nello stesso inventario. Le istantanee HF già installate possono essere ripristinate dalla stessa revisione immutabile: prima viene verificato il digest originale della metadata API. Non si accettano URL o percorsi dal browser.
- **Ripristina file esatto:** carica soltanto byte che corrispondono allo SHA-256 già presente nel manifest/receipt. È utile per file convertiti localmente, come `model.safetensors`, per i quali non esiste un URL originale degli stessi byte. Non è un uploader libero di checkpoint arbitrari.
- **Elimina file:** rimuove esclusivamente il membro selezionato; i vicini non vengono cancellati. I pacchetti gestiti diventano disabilitati e i runtime YourMT3/MR-MT3 perdono lo stato `tested`; un successivo ripristino non li riabilita automaticamente.
- **Esporta file:** consente all'amministratore di ottenere il file già presente. La verifica dei diritti e l'obbligo di conservare pacchetti/notices completi restano applicabili; non è un endpoint pubblico di distribuzione.
- **Installazioni complete per motore:** espone anche le ricette già presenti per Whisper, accordi, UVR, DrumSep, Basic Pitch, OddVoices e GM. L'import ZIP completo gestito rimane disponibile direttamente nella stessa pagina. La sezione Demucs preesistente conserva aggiornamento e blacklist per i suoi cataloghi nativi.

Un download di **sorgenti o archivi** è staging verificato, non installazione di un ambiente Python o certificazione di inferenza. I runtime esterni vanno configurati con le ricette fissate del loro motore; i loro receipt rendono poi gestibili anche i singoli membri. I file senza fonte diretta verificata mostrano il ripristino SHA o la necessità del pacchetto completo, senza un falso pulsante di download. Gli interpreti MR-MT3 copiati e verificati sono distinti dalle dipendenze Python generiche.

### Dipendenze e cache condivise

RMVPE appare nei motori RVC e Seed-VC senza duplicare il file. Il config Seed-VC di canto 44k attivo usa un target mel, quindi la presenza di una sezione DAC nel YAML non richiede da sola un checkpoint codec. Le opzioni speech vengono etichettate separatamente e non vengono scaricate insieme al canto.

I link di file HF sono ammessi solo all'interno del cache configurato; link di directory e link che escono dalla radice non vengono seguiti. La cancellazione di un alias snapshot conserva il blob condiviso. Un blob ancora referenziato da altri membri non si può eliminare direttamente: prima vanno rimossi soltanto gli alias dei modelli desiderati. I blob orfani restano visibili per un'eventuale eliminazione esplicita.

Password, file token e directory estranee ai modelli non sono inventariati. I download hanno coda, progresso e annullamento; le azioni modificanti rispettano i lock Studio e non sono pubblicate durante job AI in esecuzione o inferenze in coda/bloccate; le sole manutenzioni accodate non impediscono il ripristino. L'ammissione in coda è serializzata durante la sostituzione/cancellazione per evitare l'avvio di un nuovo worker nel mezzo dell'operazione. Le modifiche alle licenze, ai consumi e al billing sono separate e non vengono simulate da questi controlli.

### Limiti intenzionali

Le cache su un server ACE remoto non sono modificabili da questo server; vanno amministrate dove risiedono. Un runtime Python non configurato non viene indovinato cercando nell'intero filesystem. Le normali librerie di un venv non sono presentate come checkpoint. I checkpoint gated, personali o non redistribuibili richiedono la sorgente/autorizzazione effettiva oppure un pacchetto completo revisionato, non l'aggiramento della licenza.

Le prove automatiche del gestore usano byte di test, senza inferenze: autenticazione amministratore, inventari mancanti, paginazione, ripristino SHA, rifiuto di file sovradimensionati, isolamento di link e blob condivisi, selettività delle cancellazioni e blocco durante job attivi. Log: `validation/r210-model-admin-focused.log`.

## English

Open **Settings → AI models** as an administrator. The central inventory groups configured model files by consuming engine, including missing members from reviewed manifests and runtime receipts. Pagination reports the full count; scan failures and inaccessible/unsafe locations are explicit. No API accepts a user-supplied server path or download URL.

Fixed-source downloads verify original revision, size and digest before publishing. Exact restore accepts only bytes matching the existing SHA-256 inventory; locally converted weights therefore use restore or their fixed installation recipe rather than a fabricated upstream URL. Individual deletion preserves neighboring files, disables managed bundles and invalidates relevant runtime test receipts. Restoring bytes never grants rights or automatically re-enables inference.

Shared HF snapshot aliases are handled separately from their blobs; referenced blobs cannot be deleted while still used by another model member. Source archives and runtime code remain staged until actually installed and tested. Existing per-engine installers, complete managed ZIP upload, and native Demucs management remain available. Remote servers and unconfigured Python environments are not searched or modified. Licensing, regime admission and accounting remain enforced separately.
