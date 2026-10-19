# Manuale VST3 - MTA Audio Editor 0.3.0-r210

## Motore DSP sul server

Il motore C++ e gli effetti audio VST3 sono disponibili anche sul server, per anteprime, bounce, export e riproduzione live nel browser. In Impostazioni > Web App un amministratore sceglie il motore C++. La scelta viene salvata separatamente da quella delle app native; le sessioni già avviate mantengono il proprio motore. RPM/DEB e Docker includono il runtime Pedalboard/PyAV e compilano il DSP durante la build, senza compilare all’avvio. Il motore corrente rimane disponibile per il rendering offline.

## Installazione e uso VST3 sul server

L’amministratore installa plugin Linux della stessa architettura del server in /opt/mta/vst3, /usr/lib/vst3 o /usr/local/lib/vst3. MTA_VST3_PATHS consente directory aggiuntive, separate da due punti. Le directory devono essere esterne ai dati dei progetti e non scrivibili da gruppo/altri utenti. In Docker montare la directory dei plugin in sola lettura su /opt/mta/vst3. Non sono inclusi plugin di terzi: il runtime e i plugin hanno licenze separate.

Nel mixer scegliere VST3 (server), selezionare un effetto e regolare i parametri dal pulsante di configurazione. Gli effetti di tracce e master vengono applicati in ordine; i controlli di gain, volume, pan, mute/solo e i fade del master restano attivi. I parametri vengono salvati nel progetto e riutilizzati negli export. Il pulsante Editor originale mostra l’interfaccia autentica del plugin nel browser, con mouse e tastiera. Il package server include un Xvfb privato compilato anche per EL10 e usa libXtst su un display privato autenticato e confinamento dei file Linux Landlock ABI 3 o superiore; se il kernel o il container lo impediscono viene mostrato il requisito mancante. Le cartelle di altri utenti e i segreti del server non devono essere esposti dai selettori dei file del plugin. Non viene aperto un dispositivo audio sul server.

## Riproduzione live sul server

Con il DSP C++ selezionato e almeno un insert VST3 attivo o una traccia MIDI, Play prepara le sorgenti e avvia un worker separato per questa sessione utente. Le istanze degli effetti rimangono vive mentre piccoli blocchi PCM stereo vengono inviati al browser autenticato. Il cursore segue l’audio ascoltato, non quello già prodotto. Pausa, ripresa e seek scartano i blocchi futuri e ripartono dal punto corretto; il seek conserva i parametri e azzera la memoria DSP. Le modifiche alla timeline richiedono una nuova preparazione.

La rete e il buffer introducono latenza: normalmente fino a circa 1,4 secondi di audio sono accodati, oltre al ritardo di rete/dispositivo e al lookahead degli effetti. Non è monitoring a bassa latenza. Se la connessione rallenta il cursore attende l’audio e viene segnalato il buffering. Un errore o blocco del worker arresta la sessione senza sostituire gli effetti con audio dry. Ogni utente può avere due sessioni; il limite globale predefinito è otto e le sessioni abbandonate vengono eliminate dopo 60 secondi. La coda finale è limitata a due secondi. Le prove sul server reale e con i plugin effettivamente utilizzati restano necessarie.

## Riproduzione live nelle app native

Nelle impostazioni dell'app scegliere il motore C++. Gli effetti audio VST3 inseriti su tracce e master elaborano piccoli blocchi durante la riproduzione. Il motore corrente rimane selezionabile e continua a usare il rendering degli effetti. Anche l'esportazione rimane un rendering offline.

Il dispositivo di uscita predefinito viene gestito in C++. Un worker separato mantiene vive le istanze VST3 attraverso Pedalboard, il cui processore nativo usa JUCE. I filtri interni passano attraverso PyAV/FFmpeg. La callback del dispositivo consuma un ring buffer senza chiamare Python o plugin e senza attese. Non si tratta di plugin eseguiti direttamente nella callback hardware.

## Installazione e rilevamento

Le build native installano il runtime descritto in requirements-vst3.txt: Pedalboard, PyAV e Mido. I plugin rimangono installati separatamente, con le proprie licenze, nella stessa architettura dell'app. MTA non include plugin commerciali. Sono supportate le directory VST3 standard Windows, macOS e Linux; MTA_VST3_PATHS permette directory aggiuntive, separate secondo il sistema operativo.

## Inserimento e parametri

Dal mixer scegliere Insert e Aggiungi VST3, sul canale desiderato oppure sul master. Gli insert interni e VST3 rispettano l'ordine scelto, anche quando alternati. Il gain della traccia precede gli insert; fader e pan seguono gli insert della traccia. Gli effetti master precedono fader e fade del master. Le tracce bounce marcate come bypass master non vengono elaborate due volte.

Con il motore C++ i cursori normalizzati 0-1 inviano le modifiche al worker durante la riproduzione, senza ricaricare il plugin. Il buffer di uscita contiene normalmente fino a tre blocchi da 512 campioni (circa 32 ms a 48 kHz), oltre alla latenza del dispositivo e al lookahead richiesto dagli effetti. Non è una garanzia di latenza totale. Le modifiche alla struttura o ai filtri interni possono richiedere una breve pausa per ricostruire il grafo.

## Editor originale e salvataggio

Il pulsante Editor originale apre l'interfaccia della stessa istanza usata dal worker live. L'audio continua mentre la finestra è aperta. È possibile aprirla anche prima di avviare la riproduzione: viene predisposta una sessione in pausa. Alla chiusura vengono conservati parametri e stato binario del plugin. Prima di arrestare il worker l'app tenta un'ultima acquisizione dello stato nel progetto. Se il plugin è bloccato non è possibile garantire il recupero delle ultime modifiche: rimane il precedente stato salvato.

Il progetto conserva percorso e impostazioni, non il binario del plugin. Per riaprire il progetto occorre avere lo stesso plugin compatibile. È ammessa una finestra di editor live alla volta; prima di aggiungere/rimuovere plugin nella catena chiudere la finestra corrente.

## Trasporto, allineamento ed errori

Play, pausa, seek e fine elaborazione usano il clock nativo. Il seek azzera la memoria DSP e riparte dal cursore, conservando i parametri: le code sonore precedenti al salto non vengono ricostruite. Ogni percorso attende l'output compensato degli effetti prima della somma, evitando di spostare soltanto la traccia con un plugin bufferizzato. Il lookahead senza output è limitato a 960.000 campioni; oltre tale limite viene segnalato un errore. La coda finale di ascolto è limitata a due secondi.

Crash, valori audio non finiti o timeout del worker interrompono la sessione e mostrano un errore, senza sostituire silenziosamente l'effetto con audio dry. Il dispositivo resta fuori dal processo dell'applicazione; si può riavviare la riproduzione oppure scegliere il motore corrente. I contatori di underrun indicano quando il worker non produce audio abbastanza rapidamente: abbassare il carico degli effetti o usare il motore corrente.

## Strumenti VSTi e MIDI

Da EDIT / IMPORT / MIX scegliere MIDI / VSTi oppure Import MIDI (.mid/.midi tipo 0/1, massimo 8 MiB). I canali sono uniti in una traccia mantenendo il timing originale, inclusi i cambi di tempo; l'audio esistente non cambia velocita. Nell'editor scegliere un plugin e Carica strumento: deve essere un VSTi, non un effetto.

Doppio click nella griglia aggiunge note; trascinamento e bordo destro spostano/ridimensionano con snap. Una nota selezionata espone pitch, inizio/durata in millisecondi, velocity e canale. Salvare con Salva MIDI; Salva e riproduci progetto salva e avvia l'ascolto. Il piano roll si apre anche con doppio click sulla traccia o dal menu contestuale. Parametri ed editor originale dello strumento sono disponibili sia nelle app native sia sul server. Se è attivo il monitoring, l’editor server usa la stessa istanza del bus di ascolto.

Il VSTi precede gain, insert e controlli mixer. Note e controlli restano modificabili dopo riapertura; bounce ed export audio includono lo strumento. Export MIDI conserva eventi e BPM/misura correnti, non plugin o audio. Al seek vengono ripristinati note tenute, sustain e controlli, azzerando le voci precedenti senza ricostruire fase o code. I confini dei clip rilasciano sustain e note.

Registra ingresso MIDI acquisisce note e controlli con Web MIDI oppure RtMidi nativo. Collega dispositivi MIDI permette di scegliere ingresso, uscita e destinazione VSTi/hardware/entrambi. Avvia monitoring consente di suonare il VSTi a progetto fermo; la tastiera a schermo non richiede hardware. Panic rilascia le voci. Il percorso nativo usa il dispositivo C++; il server usa un bus WebSocket autenticato con buffer ridotto e mostra la latenza di rete/buffer. Per includere il suono di strumenti MIDI esterni, usare il pulsante rosso Registra audio esterno e scegliere l’ingresso audio collegato allo strumento o un loopback. È disponibile compensazione della latenza e avvio opzionale della riproduzione. La registrazione viene aggiunta e salvata come traccia prima della conferma; gli export includeranno questa traccia. MIDI Clock opzionale invia 24 PPQ, Start/Continue/Stop e Song Position. Le porte sono preferenze locali per utente/progetto. La registrazione rimane una bozza da tempo zero. Il pannello MPE / SysEx / MIDI 2.0 permette zone MPE lower/upper, canali membri e intervallo pitch bend con RPN automatici. SysEx completi sono conservati negli SMF; l’I/O hardware richiede consenso esplicito e i pacchetti non vengono ripetuti al seek. MIDI 2.0 usa libremidi nelle app native e conserva le parole UMP a piena risoluzione. Nel browser Web MIDI rimane MIDI 1.0; gli eventi UMP possono essere importati/esportati come MTA UMP JSON, senza conversione in SMF. Il bridge VST3 conserva velocity a 16 bit, pressione/controller a 32 bit e note expression per i messaggi mappati; tipi UMP senza mapping VST3 vengono rifiutati esplicitamente per lo strumento ma rimangono utilizzabili sull’uscita UMP hardware. Restano esclusi SMF tipo 2/SMPTE. Limiti: 50.000 note, 100.000 controlli, 150.000 eventi espansi e 24 ore.

Il runtime compilato sincronizza strumenti ed effetti VST con BPM decimali, firma metrica e mappe tempo del metronomo, campioni, secondi, PPQ, inizio battuta e stato play/pausa, anche negli export. Viene compilato durante il packaging, mai all'avvio. Le mappe a zone e adattive aggiornano BPM e misura con PPQ continuo; i blocchi vengono suddivisi ai cambi di tempo e il MIDI Clock segue la stessa mappa. I flag loop descrivono il contesto VST e non attivano da soli il loop del transport. Dettagli e limiti hardware in docs/VSTI_MIDI_R210.md.

## Ambito e verifiche

Sono supportati effetti audio mono/stereo e strumenti VSTi/MIDI fino a 64 tracce complessive. Gli insert con bus ausiliari espongono Sidechain esterna: selezionare traccia sorgente, bus e gain. Il prelievo avviene dopo il gain d’ingresso e prima di insert/fader; anche una sorgente muta può alimentare il bus. Live, bounce ed export usano lo stesso grafo C++. La cattura audio locale usa un ring C++ nelle app native o AudioWorklet nel browser, con upload limitato, controllo quote e import transazionale. Il selettore ASIO dedicato rimane fuori ambito. Il vecchio probe Steinberg sperimentale rimane un percorso diagnostico separato: non è il backend del nuovo host live.

I test usano il VST3 reale CHOWTapeModel, scaricato dal repository ufficiale dei test Pedalboard con commit e SHA-256 bloccati, senza includerlo nel package. Verificano istanza persistente, parametri, stato, master, seek e arresto. La CI predispone un display virtuale per l'editor originale. Restano necessarie prove di ascolto su Windows/macOS e con i plugin effettivamente usati dall'utente.


## Licenze e distribuzione

- MTA Audio Editor: EUPL-1.2.
- Steinberg VST3 SDK (versioni MIT): MIT.
- Pedalboard (backend VST3 opzionale): GPL-3.0.

- Server X.Org (framebuffer privato): MIT/X11; licenza XSERVER-COPYING nel package.
