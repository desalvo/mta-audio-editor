# Supporto VST3 — Guida utente

Funzioni disponibili, limiti e licenze

**MTA Audio Editor 0.3.0-r11 — Early release**

## Panoramica

MTA Audio Editor 0.3.0 supporta in via sperimentale effetti VST3 come insert offline sulle tracce delle applicazioni desktop. Il sistema attuale usa Pedalboard come backend opzionale e un probe C++ separato per l’ispezione della factory VST3. Non è ancora un host realtime VST3 completo.

## Piattaforme

Windows, macOS e Linux desktop. Il plugin deve essere disponibile nella stessa architettura CPU dell’applicazione (x86_64 oppure ARM64). Il supporto VST3 desktop non è previsto nella web app e nelle applicazioni mobile.

## Installazione e licenze

Installa ogni VST3 separatamente seguendo la licenza del produttore. MTA non distribuisce plugin commerciali né li copia nei progetti. Per usare il backend offline installa nel runtime Python effettivamente utilizzato dall’app: pip install -r requirements-vst3.txt. Il pacchetto nativo potrebbe non includere questa dipendenza: controlla l’ambiente della build.

## Cartelle e rilevamento

I plugin sono cercati nelle directory VST3 standard di ciascun sistema. Per aggiungere percorsi usa MTA_VST3_PATHS, con separatore dei percorsi del sistema operativo. Riapri la finestra di aggiunta VST3 per aggiornare la lista. In caso di mancato rilevamento controlla percorso, bitness/architettura e dipendenze del plugin.

## Inserimento nel mixer

Apri un progetto, individua il canale desiderato, clicca Insert e scegli Aggiungi VST3 (desktop). Seleziona un plugin rilevato, aggiungilo e utilizza il pannello parametri. I valori esposti sono normalizzati da 0 a 1. Il progetto conserva percorso e impostazioni, non i binari del plugin. L’host offline applica il VST3 al rendering della singola traccia.

## Ordine degli effetti

Il backend offline elabora gli insert integrati prima dei VST3 attivi. Se un insert interno viene posto dopo un VST3, viene restituito un errore invece di modificare silenziosamente l’ordine desiderato. Attiva il bypass per confrontare audio processato e originale.

## Probe nativo e sicurezza

Il probe C++20 controlla l’esportazione GetPluginFactory e, quando è compilato con lo Steinberg SDK, può leggere nomi, classi e categorie. L’operazione viene eseguita in processo separato con timeout. Un VST3 è codice nativo di terze parti: installa soltanto plugin attendibili. Il probe NON attiva una catena realtime.

## Limiti della versione 0.3.0-r11

Non sono ancora implementati GUI originale VST3, elaborazione low-latency realtime con SDK Steinberg, eventi MIDI, automazioni VST3, compensazione di latenza e VST3 sul Master. Per le funzioni non ancora disponibili utilizza gli insert integrati. Non interpretare il semplice rilevamento di un plugin come garanzia di compatibilità.

## Risoluzione dei problemi

Plugin assente: controlla directory e architettura. Errore durante il rendering: verifica dipendenze del VST3 e runtime Pedalboard. Il plugin non si apre: la GUI originale non è ancora supportata. Progetto trasferito: reinstalla il VST3 sulla destinazione; il file progetto non lo contiene.

## Licenze e distribuzione

Lo SDK Steinberg VST3 recente è sotto MIT, ma la licenza dei singoli plugin è indipendente. Pedalboard può comportare obblighi GPLv3 per i bundle redistribuiti. Consultare THIRD_PARTY_NOTICES.md e gli avvisi delle dipendenze; evitare di incorporare plugin di terze parti senza autorizzazione. I controlli automatici non sostituiscono un audit legale.



### r10: creazione isolata delle istanze
Con VST3 SDK installato separatamente, eseguire `mta_vst3_probe /percorso/modulo --instantiate <CID-esadecimale-32-caratteri>` nel processo diagnostico. Il componente viene rilasciato immediatamente; non vengono inizializzati plugin o elaborato audio.

### r11: diagnostica isolata del ciclo di vita
`mta_vst3_probe /path/to/module --lifecycle <CID-esadecimale-32-caratteri>` tenta l’inizializzazione con contesto host nullo e la terminazione solo se l’inizializzazione riesce. Alcuni plugin possono rifiutare il contesto. Non attiva audio, GUI, MIDI o playback realtime.
