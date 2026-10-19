# VST3 open-source opzionali — MTA Audio Editor 0.3.0-r210

Revisione del catalogo: **19 ottobre 2026**. Nessun plugin viene installato per
impostazione predefinita. Il catalogo è separato dai motori AI e dai processori
interni MTA. La precedente macroarea di backlog è avviata da questa revisione.

| Categoria | Plugin | Licenza verificata | Revisione sorgente bloccata |
|---|---|---|---|
| Strumenti / Sintetizzatori | Surge XT, con Surge XT Effects | GPLv3 | `4f0da4e423a675cb9c2c3e34ca3d381b43875324` |
| Riverbero | MVerb | GPLv3 o successiva | `5ae9f571642822bbc6b9d2e113e3fb0aada36f93` |
| Riverbero | Dragonfly Hall, Room, Plate, Early Reflections | GPLv3 | `440ec7b3b3db2fec34b9f80cf4890102ca14d1c3` |
| Saturazione / Nastro | CHOW Tape Model | GPLv3, build desktop VST3 | `604372e4ffd9690c3e283362e4598cb43edbb475` |

## Uso e licenze

Le licenze complete sono incluse in `app/optional_plugin_licenses/` e consultabili
prima dell'installazione dalla relativa voce. Il catalogo JSON comprende il
checksum SHA-256 dei testi, i repository, le revisioni e le ricette di build.
GPLv3 permette uso, studio, modifica e redistribuzione alle condizioni della
licenza, anche in contesti commerciali. L'installazione non richiede l'acquisto di
una licenza commerciale di questi plugin. I nomi e i marchi restano dei titolari;
nessun rapporto o avallo commerciale è implicato. I contenuti/preset e le
librerie dipendenti conservano le rispettive attribuzioni e licenze: non si deve
assumere che ogni file abbia esattamente la stessa licenza del progetto principale.

Questa consegna comprende il catalogo, le licenze e l'installer; **non contiene
binari dei quattro plugin**. La modalità implementata è la compilazione in loco,
così il plugin e i suoi sorgenti rimangono separati da MTA e dal progetto audio.
Il checkout conserva anche i submodule alle revisioni indicate dai gitlink.
Prima di distribuire propri pacchetti precompilati occorre conservare tutti gli
avvisi e fornire il codice sorgente corrispondente e gli altri materiali richiesti
dalle licenze applicabili. Il solo collegamento al ramo corrente non basta a
identificare il sorgente di una build precedente. Non distribuire VST2 di Surge:
l'upstream ne esclude la redistribuzione; la ricetta MTA compila solo i target VST3.

DPF utilizza per il formato VST3 la propria implementazione con licenza ISC;
conservarne attribuzione e avvisi. CHOW e Surge utilizzano JUCE e ulteriori
componenti: la build avviene dal checkout completo, senza eliminare avvisi.
La doppia licenza iOS di CHOW non viene usata per autorizzare la build desktop.

## Installazione

- **Native Windows:** durante Setup è disponibile una scelta opzionale, non
  selezionata, per aprire il catalogo. In ogni app nativa il catalogo è anche
  raggiungibile dalle impostazioni VST3. L'avvio con `--optional-plugins` apre
  direttamente la selezione, anche su macOS/Linux.
- **Server:** Impostazioni → Web App → VST3 open-source opzionali. Solo gli admin
  possono avviare installazioni. È possibile scegliere tutto o singole voci
  raggruppate per categoria. Il browser normale non può caricare eseguibili.
- **Installazione server da package:** `sudo ./install_mta.sh early
  --vst3-plugins=all` oppure `--vst3-plugins=mverb,dragonfly`. Questa scelta
  esplicita richiede la consultazione preventiva delle licenze e abilita la build
  nel configuratore. Il resto dell'installazione non installa plugin di nascosto.
- **CLI dal checkout:** `python scripts/install_optional_vst3.py --list`, poi
  `python scripts/install_optional_vst3.py --plugins mverb,dragonfly --accept-licenses`.
  Dal runtime server installato: `python -m app.optional_plugins` con gli stessi
  argomenti, usando l'interprete del runtime e `MTA_DATA_DIR` dell'istanza.

Servono Git e un toolchain C++ locale. Le ricette DPF richiedono GNU Make
(Windows: ambiente MSYS2/MinGW configurato); quelle CHOW/Surge richiedono CMake e
un compilatore supportato da JUCE (Windows: Visual Studio Build Tools, macOS:
Xcode Command Line Tools). Per la GUI Linux servono gli header X11/OpenGL e delle
altre librerie indicate upstream; l'opzione server nel wizard li installa con
APT/DNF. Dalla sola interfaccia web non vengono eseguiti aggiornamenti privilegiati
del sistema operativo. Errori di toolchain sono riportati come errori di build,
non come installazioni riuscite.

L'installazione mostra plugin corrente, fase, attività dei tool e tempo trascorso;
i log completi sono in `MTA_DATA_DIR/optional-plugin-builds/<id>/<revisione>/`.
Il percorso gestito dei VST3 è esterno alle cartelle progetto (override operatore
`MTA_OPTIONAL_VST3_DIR`); la pubblicazione dei bundle completi è atomica.
Non disinstallare o sostituire un plugin mentre è usato da sessioni attive.

## Manutenzione del catalogo

Il workflow `Review optional VST3 catalog licenses` esegue ogni mese e manualmente
un confronto dei checksum dei testi alla revisione bloccata. Non aggiorna
silenziosamente il software né amplia automaticamente i diritti concessi.
Dopo 90 giorni senza revisione del catalogo, le nuove installazioni sono
sospese e l'interfaccia lo segnala; i plugin già installati non vengono eliminati.
Per una nuova revisione verificare anche dipendenze, target e piattaforme, poi
aggiornare pin, testi, digest e `reviewed_at`. Se una voce non è più distribuibile
o supportabile, impostare `enabled: false` ed esplicitarne il motivo in questo
registro. Anche un solo testo alterato invalida l'integrità del catalogo.

## Fonti primarie

- [MVerb e GPLv3+](https://github.com/DISTRHO/MVerb/tree/5ae9f571642822bbc6b9d2e113e3fb0aada36f93)
- [Dragonfly Reverb](https://github.com/michaelwillis/dragonfly-reverb/tree/440ec7b3b3db2fec34b9f80cf4890102ca14d1c3)
- [CHOW Tape Model e istruzioni build](https://github.com/jatinchowdhury18/AnalogTapeModel/tree/604372e4ffd9690c3e283362e4598cb43edbb475)
- [Surge XT, build e limitazioni VST2](https://github.com/surge-synthesizer/surge/tree/4f0da4e423a675cb9c2c3e34ca3d381b43875324)
- [DPF, licenze per formato](https://github.com/DISTRHO/DPF/blob/main/LICENSING.md)

Prove effettive di questo ciclo: compilazione Linux MVerb e dei quattro Dragonfly da sorgente, caricamento
VST3 ed elaborazione stereo. Le build complete CHOW/Surge e le
build native Windows/macOS restano da verificare sui relativi sistemi.

## Stato e avanzamento per plugin (r210)

Durante l'installazione ciascuna scheda mostra il proprio stato e il plugin attivo presenta una barra di attività con fase di download/compilazione/installazione. La barra scompare appena termina quel plugin; gli esiti compaiono subito, senza attendere l'intero lotto. Le percentuali complessive non vengono inventate: la barra rimane indeterminata quando i tool non espongono un totale affidabile. Errori finali e installazioni riuscite rimangono identificabili riaprendo il catalogo; il monitoraggio di un job ancora attivo riprende nello stesso processo server. Dettagli e verifiche in `VST3_PROGRESS_CPP_LIVE_CONTROLS_R210.md`.


## Disinstallazione dei pacchetti opzionali

Aprire lo stesso catalogo da **Impostazioni → Web App → VST3 open-source opzionali** (oppure dalle impostazioni native). La scheda di un pacchetto installato presenta **Disinstalla** e l'opzione, inizialmente selezionata, **Rimuovi anche sorgenti scaricati e cache di compilazione**. È richiesta una sola conferma.

La rimozione riguarda l'intero pacchetto, quindi tutti i quattro riverberi nel caso di Dragonfly. Il sistema elenca il numero di progetti che lo utilizzano: quei progetti richiederanno una reinstallazione o la rimozione degli insert interessati. I dati dei progetti vengono conservati. Prima di procedere occorre fermare le sessioni live che usano il plugin e chiuderne editor e monitoring. Un'installazione già in corso impedisce la disinstallazione concorrente.

Il pulsante opera esclusivamente sui pacchetti del catalogo nella directory gestita da MTA. Non rimuove gli effetti DSP interni né pacchetti VST3 installati autonomamente dal sistema operativo. Le directory temporaneamente staccate durante la rimozione sono escluse dalla discovery e dall'esecuzione, anche quando il catalogo risiede su un volume separato.
