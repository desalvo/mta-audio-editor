# Strumenti, canto, trascrizione e licenze — 0.3.0-r210

Verifica: 20 ottobre 2026. Versione e revisione invariate. Questo documento descrive l'implementazione effettiva; non dichiara completate le specifiche integrali di AI Vocal Studio, né certifica hardware non provato.

## Uso gratuito e risorse server

Le applicazioni native e l'elaborazione locale restano totalmente gratuite. Il server può richiedere un rimborso esclusivamente per CPU, GPU e disco dell'infrastruttura, senza finalità di lucro, anche quando la richiesta proviene da una native app. Abbonamenti e crediti riguardano queste risorse: non vendono licenze del software o dei modelli.

Questa distinzione **non determina automaticamente** la qualificazione prevista da una licenza terza. Una clausola NonCommercial o il divieto di inferenza a pagamento può essere applicabile anche al rimborso hardware. Vanno esaminati separatamente codice, checkpoint, voicebank, vocoder, dizionario, dipendenze e condizioni del servizio. La sola impostazione di un prezzo a zero non risolve condizioni ulteriori. Riferimenti: [FAQ Creative Commons](https://creativecommons.org/faq/#does-my-use-violate-the-noncommercial-clause-of-the-licenses), [testo NC](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en).

## Installer GM

Da **AI Studio → Esecuzione → Modelli Studio e impostazioni**, un admin o l'utente locale nativo può accettare gli avvisi, installare FluidR3 GM, controllarne lo stato, verificarlo e disinstallarlo. Il download mostra i byte effettivi; durante verifica, estrazione e test il progresso è indeterminato. Il modello viene attivato dopo un test che produce PCM reale. Sono disponibili percorsi API admin e alias nativi, questi ultimi inaccessibili sul server.

In alternativa, usare l'interprete dell'app/server con le sue dipendenze:

```sh
python scripts/install_music_assets.py gm --accept-licenses
# Archiviazione offline: stesso archivio, stessa verifica SHA-256
python scripts/install_music_assets.py gm --accept-licenses --offline-gm-archive /percorso/fluid-soundfont_3.1.orig.tar.gz
```

Non usare un interprete di sistema differente da quello del runtime per avviare il test. Impostare `MTA_DATA_DIR` sullo stesso percorso del servizio, con lo stesso utente del servizio. Gli asset vengono conservati nel data directory; l'installer non cambia la configurazione del servizio in esecuzione.

| Componente | Provenienza e licenza | Integrità |
|---|---|---|
| TinySoundFont | [Upstream](https://github.com/schellingb/TinySoundFont), MIT; commit `853a0a171759f1ddba0de1442133a75912bbeffa` | Header `70d55963c98f60ebb81518eaa1f25d46888d5180eb5f5289fd6b74ffc177d197` |
| FluidR3 GM 3.1 | Frank Wen, MIT; [archivio Debian originale](https://deb.debian.org/debian/pool/main/f/fluid-soundfont/fluid-soundfont_3.1.orig.tar.gz); COPYING e README originali conservati | Archivio 134.835.922 byte, SHA-256 `2621acaa1c78e4abdb24bdd163230cc577e61276936d6aa6e3180582142f0343` |
| Banco SF2 | 148.398.306 byte; download opzionale, non incluso nello ZIP sorgenti | `74594e8f4250680adf590507a306655a299935343583256f3b722c48a1bc1cb0` |
| FluidSynth alternativo | LGPL-2.1-or-later; eventuale libreria dinamica installata dall'operatore | Conserva i propri obblighi e avvisi; nessun binario FluidSynth incluso |

TinySoundFont è il fallback C++ quando FluidSynth non è disponibile. Le tracce MIDI restano modificabili senza soundbank. Programmi GM, canale percussioni, velocity, CC, pitch bend e controlli live sono gestiti; aftertouch richiede FluidSynth o un VSTi. I due riverberi hanno implementazioni differenti; non garantiscono identico risultato. La matrice hardware attuale instrada il master stereo, non bus hardware indipendenti per ogni traccia.

## Canto reale con voci autorizzate

Il nuovo backend **OddVoices** è sintesi concatenativa PSOLA/difonica su CPU, **non sintesi neurale DiffSinger**. [Sorgente fissata](https://gitlab.com/oddvoices/oddvoices/-/tree/33a248af8df88edf5166593bf36b7e24e7bc1f94): codice Apache-2.0, registrazioni vocali CC0-1.0. Il dizionario CMUdict 0.7b conserva le condizioni BSD e il disclaimer integrale. Gli avvisi sono inclusi nel progetto e nell'installazione.

| ID voce | Nome e registro | Stato del collaudo CPU |
|---|---|---|
| air | Air Navier, alto | Download, checksum, compilazione, PCM reale |
| cicada | Cicada Lumen, baritono | Download, checksum, compilazione, PCM reale |
| quake | Quake Chesnokov, basso | Download, checksum, compilazione, PCM reale |

Installazione esplicita nella stessa pagina Modelli Studio o mediante `python scripts/install_music_assets.py air --accept-licenses` (analogamente `cicada` e `quake`). Non vengono scaricate voci alla prima generazione senza consenso. I file di registrazione vengono eliminati al termine della compilazione o di un errore. Il banco compilato e il dizionario servono al runtime; non eliminarli manualmente. I dati originali grandi sono scaricati separatamente, non inclusi nello ZIP cumulativo.

Procedura: generare o importare una melodia MIDI, eventualmente creare armonie con AI Vocal Studio, correggere le parti nel piano roll; dalla scheda Cantanti aprire **Genera canto da MIDI**, scegliere le tracce monofoniche, la regione, il cantante e vocalizzo o sillabe inglesi. Per l'inglese specificare una sillaba per nota separando le sillabe con `|`. Ogni gruppo deve contenere un solo nucleo vocalico. In modalità vocalizzo si può scegliere una vocale X-SAMPA, per esempio `A`. Sono disponibili rapporto dei formanti e velocità di articolazione.

Le lingue italiana e francese non sono dichiarate supportate da queste voci; non vengono sostituite silenziosamente con l'inglese. L'inglese è inglese americano; non è una garanzia di corretta pronuncia di qualsiasi parola. Le note hanno articolazione indipendente; melismi legati, respirazioni controllate, vibrato esposto, seed, espressività neurale, conversione timbrica e rigenerazione con crossfade contestuale restano da completare. Non vengono simulate opzioni che il backend non espone.

Il job passa dalla coda globale, supporta annullamento e timeout, mantiene il contesto della regione e salva atomicamente audio e MIDI insieme se il progetto è invariato. Se il progetto cambia, il risultato resta disponibile per revisione e importazione esplicita. Chiudere la finestra non cancella il job. I risultati sono idempotenti, riapribili e scaricabili; banco, hash, commit e parametri rimangono nei metadati. Il parser `.voice` upstream non è sicuro su file arbitrari: si accettano soltanto banchi gestiti compilati dalle registrazioni fissate, con ricevuta e checksum. Nessun upload eseguibile o `.voice` arbitrario.

## Riconciliazione multimodello

La modalità **Accurata** richiede entrambi i runtime abilitati: YourMT3 noPS CPU e Basic Pitch ONNX CPU. Non sostituisce silenziosamente un motore assente. Esegue i modelli sulla stessa regione, confronta pitch/onset/offset, associa gli eventi uno a uno e conserva le ipotesi originali come alternative modificabili. Strumenti discordanti, unisoni ambigui e note non concordi restano disponibili; non vengono inventate percentuali di correttezza. Sono previste tolleranze per strumento nel modulo di riconciliazione. Il timing primario non viene quantizzato.

I checkpoint sono per sorgente e modello: retry compatibili riprendono i modelli già persistiti senza rieseguirli. Dalla scheda Risultati è possibile rivedere le alternative salvate e importarne una copia come traccia MIDI per ascolto/editing. Le alternative rimangono nel progetto dopo la riapertura. Basic Pitch non classifica il mix in strumenti: il confronto con un modello multistrumento non costituisce una prova di maggiore accuratezza. Servono benchmark comparabili su registrazioni multistrumento reali.

La modalità **Massima accuratezza** con separazione, più modelli specialistici, confronto renderizzato e revisione avanzata non è abilitata. Non si creano tracce fittizie per raggiungere dieci strumenti. I limiti della pipeline e delle tracce rimangono quelli documentati nel checkpoint MIDI.

## Motori e voicebank disabilitati o esclusi

La tabella distingue un divieto noto da un diritto o backend non ancora verificato. Un componente assente non diventa installato modificando la policy.

| Componente | Default | Motivo e fonte primaria | Eventuale attivazione |
|---|---|---|---|
| Madmom: pesi Deep Chroma/CNN-CRF e altri pesi upstream | Disabilitato; default accordi passa a MTA Chromagram | [Codice BSD, modelli CC-BY-NC-SA-4.0](https://github.com/CPJKU/madmom/blob/main/LICENSE); rimborso hardware non equivale automaticamente a permesso | Verifica operatore di uso consentito non commerciale o autorizzazione separata; modalità senza addebiti quando richiesta |
| ChordFormer checkpoint attuale | Disabilitato | [Provenienza configurata](https://github.com/shojha24/ChordFormer-Artificial-Dataset-Benchmarking): i riferimenti interrogati non hanno fornito condizioni verificabili dei pesi | Occorrono fonte/versione utilizzabile, diritti e runtime verificati |
| Backing vocals audio-separator/UVR | Pesi non verificati disabilitati; fallback DSP center/side disponibile | [UVR](https://github.com/Anjok07/ultimatevocalremovergui): la licenza del programma non prova quella di ogni checkpoint MDX/VR | Verificare esattamente il modello scelto e registrare il permesso; non è un divieto generale di audio-separator |
| DrumSep checkpoint | Disabilitato in attesa verifica del peso selezionato | [Repository modelli](https://github.com/ZFTurbo/Music-Source-Separation-Training): servono termini della specifica pubblicazione | Come sopra; il codice ONNX non autorizza da solo i pesi |
| DiffSinger Qixuan | Nessun backend MTA produttivo/voicebank distribuita; disabilitato | [Termini](https://github.com/yqzhishen/qixuan-diffsinger/blob/main/terms_of_use/Terms_of_Use.zh-CN.md): servizio gratuito consentito con condizioni, inferenza a pagamento/abbonamento vietata; attribuzione e redistribuzione integrale | Solo dopo integrazione verificata e accesso effettivamente gratuito secondo tutti i termini; la policy non consente cost recovery sotto questi termini |
| DiffSinger Nishiren | Disabilitato, non distribuito | [Termini](https://github.com/Gardanana/Nishiren-AI-Diffsinger/blob/main/terms-of-service.md): approvazione specifica per uso commerciale e altre condizioni | Consenso/autorizzazione e compatibilità effettivi, non semplice esenzione dal billing |
| DiffSinger SPORE | Disabilitato, non distribuito | [Termini upstream](https://github.com/knoxstation/SPORE): NC/ND modificati e restrizioni ulteriori | Verifica/autorizzazione specifica, nessun download implicito |
| Altri banchi DiffSinger, Amphion/SVS, RVC, Seed-VC | Candidati non abilitati | Mancano backend MTA completati e verifica separata di pesi, voci, vocoder e lingue | Non basta abilitare il nome del modello; servono adapter, diritti e prove reali |
| Google MT3, MR-MT3, Transkun, MT3-Infer | Candidati non abilitati | Adapter/pesi/dipendenze e collaudo non completati | Integrazione e verifica prima dell'uso produttivo |
| Nuovo motore aggiunto al registro | Disabilitato finché non verificato | Diritti non presumibili per componenti futuri | Revisione manuale esplicita e fonte dei diritti |

Basic Pitch e YourMT3 fissati hanno dichiarazioni Apache-2.0; ACE-Step Apache-2.0; Whisper e Demucs MIT. BTC-HCQT dichiara esplicitamente [MIT per codice e pesi](https://github.com/marcusfkelley/btc-hcqt), fermo restando il collaudo del suo runtime. SAM Audio usa la [SAM License](https://github.com/facebookresearch/sam-audio/blob/main/LICENSE), con condizioni proprie: non è classificato erroneamente come NC. Questi componenti **non sono esclusi dal billing per la sola licenza indicata**; installazione, dipendenze, condizioni aggiuntive e compatibilità effettiva restano controlli distinti.

## Policy manuale e contabilizzazione

La pagina Modelli Studio espone stato della licenza e modulo amministrativo: modalità disabilitata, interamente gratuita o rimborso hardware consentito; URL HTTPS della licenza/autorizzazione, motivazione, responsabilità dell'operatore e conferma dell'accesso gratuito quando necessario. È disponibile anche nelle native per l'uso locale sotto responsabilità dell'operatore. L'acknowledgement **non concede diritti e non sostituisce un'autorizzazione mancante**. Non disattiva i controlli tecnici di sicurezza.

Il worker registra una fotografia immutabile della decisione. I job gratuiti mantengono misure CPU/GPU per accounting ma hanno `billable=0`, nessun addebito, nessun consumo dei crediti o delle quote a pagamento. Sono distinti dai job diagnostici nei report. Il percorso token API permette inferenza gratuita senza abbonamento/crediti, con cache temporanea non fatturata; restano autenticazione, autorizzazione, coda e sicurezza. Non configurare come gratuita una pubblicazione web che richieda comunque un piano: l'operatore deve garantire il percorso gratuito previsto dalla licenza. Per Studio gratuito sul server l'importazione nello storage di progetto è bloccata; i risultati si scaricano come ZIP senza addebiti di progetto. L'uso locale nativo può salvarli liberamente nel progetto locale. Quote e billing normali restano attivi per gli altri job autorizzati.

## Preparazione collaudo ASIO/ROCm

`scripts/verify_music_hardware.py` crea un rapporto JSON con checksum. Senza flag effettua soltanto inventario; non apre un dispositivo audio, non avvia carico GPU e non modifica servizi:

```sh
python scripts/verify_music_hardware.py --output hardware.json
# Nell'interprete ROCm del motore, esplicitamente:
python scripts/verify_music_hardware.py --exercise-rocm --output rocm.json
# Sulla native Windows con driver e PortAudio ASIO installati, impostazioni JSON Audio I/O:
python scripts/verify_music_hardware.py --exercise-audio --audio-settings audio-io.json --require-asio --seconds 10 --output asio.json
```

Il test audio invia silenzio all'uscita fisica selezionata e controlla avanzamento/underrun; non certifica cablaggio, ingresso, ascolto o MIDI. Il test ROCm esegue prodotti matriciali con eventi di uno stream: non certifica i modelli AI né il billing GPU di tutti i processi. `drm-engine-*` assente non prova GPU ferma o kernel incompatibile. I report non dichiarano automaticamente certificato il sistema.

Restano collaudo reale su Windows/ASIO multicanale con loopback e riconnessione, routing per traccia verso bus hardware indipendenti, MIDI hardware, inferenza dei nuovi modelli su Radeon 8060S/ROCm in LXC, confronto dei contatori con agente Proxmox e test end-to-end del server aggiornato. Nessun binario ASIO viene aggiunto senza verifica di licenza e obblighi del sorgente corrispondente. Il banco GM e il canto concatenativo sono CPU: non vengono presentati come GPU per giustificare addebiti.

## Verifica aggiuntiva dei checkpoint e modifiche al controllo licenze (20 ottobre 2026)

Nessuno dei quattro checkpoint ambigui è stato riabilitato automaticamente. Madmom: pesi CC BY-NC-SA 4.0; richiede effettiva conformità NC/autorizzazione specifica, non solo billing disabilitato. ChordFormer: cinque file `cache_data/chordformer_head16(1.0,1.0)_s0..s4.best.sdict` nel fork `shojha24`, provenienza e diritti individuali da dimostrare (upstream `mwaseemrandhawa/ChordFormer`). UVR: la README dei creatori dichiara MIT con attribuzione per i propri modelli; non implica che ogni mirror/variante abbia provenienza documentata; identificare SHA-256 del modello `UVR_MDXNET_KARA_2.onnx` effettivamente usato. DrumSep: repository `inagoy/drumsep` MIT, ma ONNX MTA dal mirror `gridshiftstudio/drumsep-onnx`, SHA-256 previsto `ecb8509383ccd437d84e12c216b002a00a2d4e88601e29f2711ea581f207c92a`: licenza e catena di conversione da verificare.

**Implementato:** blocco policy prima dei download ChordFormer, UVR e DrumSep e prima dell'esecuzione remota DrumSep; storico persistente delle modifiche amministrative con identità e dati di evidenza. Le attestazioni e l'URL non conferiscono diritti da soli. `free_only` esclude il billing ma conserva consumi statistici; il sistema di code, metering e accessi resta in funzione. **Non collaudato:** completezza e correttezza di tutte le vie commerciali web/native/token/fatture in produzione. **Bloccato:** automatico re-enable di pesi senza conferme. Consultare `docs/DEVELOPMENT_STATUS.md` per stato e test.
