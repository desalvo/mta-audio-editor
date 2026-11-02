# Export Merish con metronomo a zone o adattivo

Su richiesta esplicita dell’utente il metronomo generato come audio non blocca più l’export Merish sperimentale per BPM a zone/adattivi, nemmeno con marker. Il rendering esporta la traccia click presente nel progetto; le posizioni dei marker sono codificate in tempo assoluto con tempo MIDI costante e il metadata BaseBpm rimane quello base. La mappa BPM variabile non viene trasferita come mappa dinamica e la visualizzazione BPM dinamica sul Merish non è dimostrata. L’utente ha confermato il funzionamento di tutti i file dell’ultimo gruppo di prove; il nuovo percorso completo di export a zone/adattivo è verificato localmente e rimane sperimentale. Sono passati 121 test mirati (export MTA e beat sync), inclusi quattro export con click audio a tempo variabile e marker, Ruff del perimetro CI e controllo sintassi JavaScript. I vincoli indipendenti, come le righe con sincronizzazione granulare mista, restano invariati. RC **34/42 = 81,0%**, nessun commit o CI remota.

---

# Marker, testo a righe e MIDI a tempo variabile

Il 2 novembre 2026 l’utente conferma sul proprio Merish5+ per MTA8 e MTA16: nei file TEMPO apertura/play e posizione/salto dei marker sono corretti, ma non sono visibili cambi BPM; nei file RIGHE il testo avanza correttamente. Non è stato confermato il comportamento dei marker nei file RIGHE né che la mappa di tempo controlli la visualizzazione BPM o la sincronizzazione musicale. L’export sperimentale ora ammette marker anche con lyrics a righe, mantenendo il rifiuto per righe con sincronizzazione granulare mista/incompleta; BPM a zone/adattivi restano bloccati per i marker. I quattro originali analizzati contengono tutti un singolo evento MIDI di tempo, per cui non chiariscono la visualizzazione dei cambi BPM. Generati due export diretti MTA8/MTA16 con marker e lyrics a righe: sezioni SYL e XML coincidono con le prove RIGHE precedenti, nelle quali è stato confermato solo l’avanzamento del testo; marker e contenitore completo attendono riscontro. Preparati due file diagnostici da 20 s, MIDI 120→60 BPM a 4 s e marker a 2/10/18 s: se il tempo iniziale fosse applicato per tutta la durata, i tick corrisponderebbero a 2/7/11 s. I toni audio restano a intervalli fissi e non verificano la sincronizzazione musicale. Superati localmente 98 test mirati, Ruff perimetro CI, sintassi JS e decodifica audio dei quattro file. RC **34/42 = 81,0%**. Nessun commit o CI remota.

---

# Conferma marker senza testo

Il 2 novembre 2026 l’utente conferma sul proprio Merish5+ che entrambi gli export MTA8 e MTA16 dell’app, senza testo e con marker e toni ripetuti fino alla fine, funzionano bene. Il caso sintetico senza lyrics è quindi verificato su questo dispositivo; altri progetti, Xynthia2, marker con righe senza sincronizzazione granulare e BPM variabili restano aperti. Implementato generatore interno di prova per mappa MIDI a zone/adattiva usando MusicalClock, con test di conversione dei tempi assoluti; l’export generale resta bloccato per BPM variabili. Preparati quattro file diagnostici MTA8/MTA16 per confrontare marker con cambi di tempo MIDI 120/90/150 BPM e marker con testo solo a righe. I nuovi file attendono prova hardware. Superati 95 test MTA mirati, compresi 4/4 e 6/8, Ruff perimetro CI e controllo sintassi JavaScript. RC **34/42 = 81,0%**, nessun commit o CI remota.

---

# Marker senza testo e audio delle prove

Il 2 novembre 2026 l’utente conferma il funzionamento completo degli export MTA8/MTA16 con marker prodotti dall’app. Nelle due prove senza testo i marker funzionano, mentre l’audio è stato udito fino a circa 5 s. L’analisi locale mostra che nel file MTA16 di prova l’ultimo tono termina a 5,19 s e il resto dell’audio è silenzioso; in MTA8 i toni arrivano fino a 7,69 s su singoli slot. La durata del contenitore è 10,025 s. Non è dunque dimostrata un’interruzione del dispositivo: preparare test con toni ripetuti fino alla fine per entrambi i formati. Abilitato l’export sperimentale dei marker senza lyrics, con chiave importata e tempo fisso; se sono presenti lyrics restano richieste parole sincronizzate. Preparati due nuovi export completi con marker e toni ogni secondo fino al nono: su tutti gli stream sono stati verificati localmente i 10 impulsi e il MIDITK è identico alla prova senza testo che l’utente ha aperto. Resta da verificare il comportamento dei nuovi export completi senza testo e dell’audio sui dispositivi. Superati 90 test MTA mirati, Ruff perimetro CI e controllo sintassi JavaScript. RC **34/42 = 81,0%**. Nessun commit o CI remota.

---

# Marker T2 su MTA8 e MTA16

Il 2 novembre 2026 l’utente conferma sul proprio Merish5+ per entrambi i formati: T1 mostra marker selezionabili a 2/5/8 s e durata 10 s, ma non evidenzia l’ultima parola; T2 mostra marker selezionabili agli stessi tempi, durata 10 s ed evidenzia correttamente l’ultima parola. Implementato nell’export sperimentale T2 con MIDITK e PreCntUSec=0 in presenza di marker. Per evitare perdita silenziosa, occorrono righe tutte con parole sincronizzate, metadati testuali validi e modalità tempo fissa; marker senza testo granulare e con BPM variabili sono bloccati in attesa di prove. Due nuovi export completi dell’app hanno sezioni LYRICS/COLORS/MIDITK/CHORDS e XML identici alle rispettive prove T2 già confermate; l’intero nuovo contenitore richiede prova hardware. Sono stati preparati due export completi diretti dell’app e due ulteriori prove marker senza testo, non ancora verificate sul dispositivo. Verifiche locali: 88 test MTA mirati, inclusi export/import marker MTA8/MTA16, Ruff perimetro CI e sintassi JavaScript. La tonalità TKEY è testata per Dm; BaseKey/trasposizione e Xynthia2 rimangono aperti. RC **34/42 = 81,0%**; nessun commit o CI remota.

---

# Riscontro marker e tonalità Merish

Il 2 novembre 2026 l’utente riferisce sul proprio Merish5+: MTA16 A (solo TKEY Dm) mostra Dm; B (solo BaseKey 21) mostra 21; C (entrambi) mostra Dm. Tutti si aprono e vanno in play. MTA16 D e MTA8 D si aprono e riproducono, con marker selezionabili visualizzati a 4/7/10 s rispetto ai tempi MIDI 2/5/8 s. Il file di prova durava 12 s, come creato, non 10 s. Implementato TKEY dai metadata del progetto per la visualizzazione; il significato di BaseKey e l’effetto sulla trasposizione restano aperti. Export ordinario con marker ancora bloccato. Preparate prove con audio effettivo di 10 s, TKEY Dm e due ipotesi separate: MIDI anticipato di 2 s oppure PreCntUSec zero. La posizione e il comportamento dei marker devono essere verificati sul dispositivo. Verificati localmente codifica dei marker, TKEY negli export MTA8/MTA16, durata e decodifica audio delle prove; 85 test MTA mirati, Ruff perimetro CI e sintassi JavaScript superati. RC **34/42 = 81,0%**. Nessun commit o CI remota.

---

# Conferma hardware export granulare dell’app

Il 2 novembre 2026 l’utente conferma che tutti e tre gli export granulari completi generati dall’app funzionano correttamente sul proprio Merish5+: MTA8 parole, MTA8 lettere e MTA16 parole. È verificato il comportamento di queste prove sintetiche, non la compatibilità di ogni progetto né Xynthia2; sillabe, marker e tonalità rimangono da verificare. Analizzati quattro MTA originali: il campo TKEY e BaseKey differiscono tra brani; non sono sufficienti per ricavare una tabella generale. Implementato un generatore interno di probe MIDITK con marker MIDI e tempi assoluti; l’export ordinario continua a rifiutare marker attivi. Preparati cinque file sintetici: MTA16 con solo TKEY, solo BaseKey, entrambi; MTA16 e MTA8 con marker INTRO/STROFA/FINALE. Test locali di decodifica MIDI, audio e round-trip contenitore superati; mancanti risultati hardware. Superati 84 test MTA mirati, Ruff sul perimetro CI e controllo della sintassi JavaScript. RC **34/42 = 81,0%**. Nessun commit o CI remota.

---

# Evidenziazione granulare MTA8/MTA16

Il 2 novembre 2026 l’utente conferma sul Merish5+ audio e avanzamento a parole con finale nei tempi per le prove sintetiche MTA8 e MTA16, e avanzamento a lettere con finale nei tempi per MTA8. Aggiunti all’export sperimentale COLORS a parole o lettere, scelta nel progetto, uso opzionale dei tempi sillabici per lettere, verifiche di coerenza e conservazione della modalità nei metadata sincronizzati. Le sezioni LYRICS/COLORS/CHORDS dei tre nuovi export completi generati dall’app corrispondono byte per byte ai rispettivi file sintetici confermati; decodifica audio locale verificata. Superati 79 test mirati MTA e verifica del round-trip con ripristino delle parole e della modalità; Ruff perimetro CI e sintassi JavaScript corretti. I tre nuovi file completi attendono ancora riscontro sul dispositivo; sillabe, casi generali, marker, tonalità e Xynthia2 rimangono aperti. RC **34/42 = 81,0%**: non è chiuso il criterio generale di compatibilità. Nessun commit o CI remota.

---

# Conferma hardware export MTA8 e MTA16

Sul Merish5+ dell’utente, entrambi i file sintetici generati dall’export completo dell’app (MTA8 a 8 slot e MTA16 a 10 slot) riproducono tutte le tracce; testo a righe e accordi sono visibili e avanzano. Riscontro utente del 2 novembre 2026. Generate inoltre tre nuove prove private COLORS, con testo e accordi identici ai due export appena confermati: MTA8 con posizioni a parole o lettere, MTA16 con posizioni a parole. Audio decodificabile, sezioni testuali originali invariate e 256 eventi COLORS decodificati localmente; evidenziazione e tempi sul dispositivo sono ancora da accertare. Questo chiude la verifica delle due prove specifiche, non l’intera compatibilità del formato: rimangono sincronizzazione granulare, marker, tonalità, altri contenuti e Xynthia2. **RC 34/42 = 81,0%**; nessun criterio complessivo promosso automaticamente.

---

# Identificativo suggerito Merish

Su richiesta dell’utente l’identificativo osservato `068336` è il valore iniziale dei nuovi progetti e viene suggerito nell’editor dei metadata se il campo è vuoto. È modificabile e non è stato dimostrato universale. L’import di metadati può sostituire il valore iniziale se non ancora abbinato a parametri SYL; mantiene il blocco per conflitti con identità già configurate. I progetti precedenti con campo vuoto devono salvare i metadata per adottare il suggerimento. Nessun altro criterio RC è chiuso: **34/42 = 81,0%**.

---

# Riscontro hardware e export testuale sperimentale

RC **34/42 = 81,0%, PRE-RC**: nessun criterio RC viene chiuso sulla sola base di queste prove. Sul Merish5+ dell’utente i due MTA16 sintetici da 10 e 16 tracce riproducono 12 toni distinti per ciascuna traccia dalla 2 all’ultima e 12 toni più bassi sul click. Nei due MTA8 test 3/4 gli accordi sono corretti fino al SOL finale; il test 3 avanza per righe e il test 4 lettera per lettera. I riscontri precedenti sotto sono cronologici e superati dove contraddicono questo aggiornamento.

Implementati nell’export sperimentale testo a righe e accordi, con importazione esplicita dei soli metadati da un MTA personale; sincronizzazione per parola, marker e allegati originali conservati restano bloccati. Le strutture del test 3 sono riprodotte ma l’export testuale completo dell’app richiede prova hardware; non è stata verificata Xynthia2. Dettagli e limiti in `docs/MERISH5_MTA16_EXPERIMENTAL_IT.md`. Due prove private MTA8/MTA16 esportate dall’app sono state controllate localmente: sezioni LYRICS/CHORDS identiche al test 3 già provato, audio decodificabile, 8 e 10 stream rispettivamente; manca il riscontro hardware sul nuovo insieme. Verifiche: 62 test MTA mirati, Ruff sull’intero perimetro CI e sintassi JavaScript superati. Nessun commit o CI remota effettuati.

---

# Aggiornamento CI e Merish5 / Xynthia2

RC **34/42 = 81,0%, PRE-RC**. Baseline Git confermata `f544db6acb02216b33e0cdc6e69610f7102180c2`; la CI 41340688815 falliva su due import non utilizzati, ora corretti e Ruff completo locale passato. L'export usa `.mta`, CBR 320 kbit/s e stream di durata uguale. **Il caricamento di un MTA16 generato ex novo su Merish5+ rimane aperto**: la prova sintetica generata normalmente non si apriva, mentre un MTA16 originale dell'utente con l'audio interamente sostituito da toni sintetici si apre, riproduce e mostra il testo originale (riscontro utente). Anche due varianti distinte, con modifica a lunghezza invariata rispettivamente dei nomi delle tracce nell'XML e del titolo ID3 nel SYL, si aprono, riproducono e mostrano il testo (riscontro utente). Questi risultati non stabiliscono quali altri elementi del contenitore siano necessari e non validano un writer generico. L'analisi MTA8 è stata riaperta con prove sintetiche; i risultati sono descritti sotto. I file di prova derivati dall'originale sono riservati all'utente e non vanno inclusi nel repository. Nessun commit o CI remota dopo la correzione.

Il Merish5+ dell'utente ha inoltre aperto le due prove con eventi ricodificati: la variante C mostrava `TEST`, la D accordi `DO`; entrambe riproducevano i toni sintetici. La prova privata E, accorciata a 10,448 secondi con durata, indici e intestazioni audio aggiornati, è stata aperta e riprodotta sul Merish5+; la durata visualizzata è 10 secondi e lo spostamento funziona (riscontro utente). I contenuti originali ancora presenti nei metadati rendono E un esperimento privato basato su modello, non un export generico. F (writer di normalizzazione, blocchi audio di E invariati) si apre e permette riproduzione, indicazione durata e spostamento sul dispositivo; G (remux FFmpeg e normalizzazione) non si apre (riscontro utente). F e G differiscono per scala temporale, struttura delle tracce, allegati e disposizione dei cluster: non è ancora nota la causa del rifiuto. Le prove diagnostiche H/I/J/K isolano rispettivamente cluster grandi, scala temporale in millisecondi, descrizioni delle tracce di FFmpeg e allegati riscritti da FFmpeg; sono validate localmente, la loro rigenerazione di controllo è identica a F, ma manca ancora prova hardware.

Correzione writer: i CueClusterPosition vengono ora rimappati per ogni cluster effettivamente riscritto, anche quando il sorgente contiene elementi fra cluster; un riferimento inesistente causa errore anziché produrre indici errati. Test dedicati e di esportazione superati localmente. Il writer generico resta da validare su Merish.

Il Merish5+ apre e riproduce correttamente H, I e J (cluster grandi, scala dei tempi in millisecondi, tracce riscritte da FFmpeg); K (allegati riscritti da FFmpeg) non si apre: riscontro utente. Gli allegati di F e K contengono dati, nomi, MIME e descrizioni identici; cambiano ordine dei campi, UID e presenza del CRC-32. È stata verificata la ricostruzione binaria esatta dell'allegato FFmpeg da quello di F applicando quelle tre modifiche; L/M/N le isolano separatamente. Questi esiti non dimostrano che l'export generico sia già compatibile o che gli allegati generati oggi contengano tutto ciò che serve.

Prove L/M/N sul Merish5+: L (CRC) e N (nuovi UID) si aprono e funzionano; M (FileDescription prima degli altri campi) non si apre, secondo il riscontro dell'utente. Il writer sposta ora FileDescription in fondo a ogni AttachedFile, preservando i dati e verificando/aggiornando gli eventuali CRC dei contenitori interessati. Test unitari, di regressione e con un allegato FFmpeg reale superati localmente. La prova G corretta, con audio identico a G e allegati riordinati, è stata aperta e riprodotta sul Merish5+; durata e navigazione funzionano (riscontro utente). Prove P/Q/R/S: solo S (coppie SYL/XML originali e JSON aggiuntivo) si apre e funziona; P senza allegati, Q con i soli SYL e R con i soli XML non si aprono (riscontro utente). La compatibilità degli MTA generati ex novo e la struttura minima degli allegati restano da verificare. Le prove private T/U/V/W contengono, rispettivamente, XML generato, SYL minimo generato, nomi allegati cambiati e tutte queste modifiche insieme; i controlli locali sono superati; i risultati hardware sono riportati sotto.

Riscontro hardware T/U/V/W: T e W si aprono ma non vanno in play; U con SYL minimale generato funziona senza testo; V con nomi allegati nuovi funziona con testo. Il SYL minimo è quindi utilizzabile nella configurazione U, ma non sono stati verificati testo o accordi generati ex novo. L'XML generato in T/W non è ancora riproducibile: risultati delle prove X1-X5 riportati sotto.

Riscontro hardware X1-X5: X1 (padding XML rimosso), X3 (formattazione diversa) e X5 (NoteOn attivi) funzionano; X2 (XML generato) e X4 (UserId azzerato) si aprono ma non vanno in play. I quattro originali forniti dall'utente hanno lo stesso UserId. Non è ancora stabilito se serva quell'identificativo o un qualsiasi valore valido, né se altri campi dell'XML generato impediscano il play: risultati delle prove Y1-Y4 riportati sotto. Non inserire identificativi dell'utente nel repository o in valori predefiniti pubblici.

Riscontro Y1/Y2: i due valori alternativi sono rifiutati. Y3 (XML generato con l'ID dell'utente) funziona con testo originale; Y4 (XML e SYL generati, nomi nuovi) riproduce l'audio senza testo. Profilo Merish5+ MTA16 **sperimentale, solo audio** implementato per nuovi progetti: genera SYL/XML senza usare contenuti dell'originale, richiede un identificativo per progetto e lo recupera se disponibile senza conflitti importando i propri MTA. Export con lyrics, accordi, marker o allegati SYL/XML conservati è bloccato esplicitamente, per non perdere dati. La tonalità non viene trasferita e i file generati completamente dall'app sono in attesa di prova sul Merish con 10 e 16 tracce. Dettagli e limiti: `docs/MERISH5_MTA16_EXPERIMENTAL_IT.md`. Non promuovere il criterio RC prima della verifica end-to-end.

Ricerca MTA8: il manuale ufficiale Xynthia2 conferma 8 tracce con melodia allo slot 7 e click allo slot 8; non è stato trovato un campione originale pubblicamente scaricabile. Aggiunto profilo separato MTA8 Xynthia2 sperimentale audio-only, che applica la generazione degli allegati e le correzioni comuni e impone l'ordine 7/8; test automatici su stream, allegati e mappatura superati. L'ipotesi deriva dall'MTA16 e non è ancora confrontata con un originale MTA8 né verificata su Xynthia2. Il profilo DIVO/B.Beat ha ordine 7/8 invertito e non è stato modificato.

L'utente ha confermato che la prova MTA8 generata da progetto nuovo si apre e riproduce sul proprio Merish5+ PLUS, senza testo: ha udito due toni sull'uscita principale e un tono sul click. La verifica locale ha rilevato segnali in tutte e otto le tracce, ciascuna a un secondo diverso; non è ancora verificato se ogni slot sia udibile/routato singolarmente sul dispositivo o su Xynthia2. Il campo UserId è in chiaro e non è dimostrato sia una credenziale segreta, ma il suo legame con account o hardware e la portabilità non sono noti. Nessuna conclusione universale né identificativo personale nei sorgenti.

La successiva prova MTA8 con toni ripetuti ha prodotto il riscontro utente «si sentono tutti e 8 i toni per ogni traccia e anche per il click», più acuto. Il chiarimento successivo sull'isolamento SOLO è riportato sotto. Il test locale indipendente conferma otto stream con frequenze distinte e il click più acuto. Nessuna prova su Xynthia2, e le prove MTA16 da 10 e 16 tracce restano in attesa di riscontro separato.

Riscontro successivo: su Merish5+ la modalità SOLO riproduce soltanto la traccia scelta e senza SOLO si sentono tutte insieme. Questa verifica riguarda il file MTA8 sintetico e non dimostra la compatibilità su Xynthia2. Preparati due ulteriori file MTA8 con testi e accordi di prova codificati da zero, senza contenuti originali; il secondo include eventi COLORS. Lettura dei record generati, integrità del contenitore e decodifica audio sono verificate localmente. La visualizzazione e la sincronizzazione sul dispositivo restano da verificare; l'export nell'app continua a bloccare testi/accordi/marker finché non supportati.

Riscontro hardware test testo/accordi: nel test 1 testo e accordi avanzano; nel test 2 il testo si vede ma non avanza e gli accordi avanzano. In entrambi l'ultimo accordo risulta vuoto. In preparazione test 3/4 con evento finale riformulato e, nel 4, eventi COLORS distribuiti nel tempo: ipotesi ancora da verificare sul dispositivo. Export testuale nell'app ancora disabilitato. L'utente ha inoltre provato gli MTA16 da progetti nuovi: nel file da 10 ha udito solo gli slot 9 e 10, nel file da 16 gli slot 10-16; nessun click riferito. L'audio di ciascuno stream è presente localmente ma i toni precedenti duravano solo 0,18 secondi e iniziavano tra 0,55 e 8,05 secondi. Preparati test MTA16 con segnali ripetuti e controllo SOLO/routing; la causa del comportamento riferito non è ancora accertata.

---

# Aggiornamento - sincronizzazione beat r210

RC **34/42 = 81,0%, PRE-RC**. Ripresa: `MTA-0.3.0-r210-pre-RC-beat-sync-cumulative.zip`; dettagli e limiti in `BEAT_SYNC_R210.md`. Rilevamento beat di sorgente e fase riferimento con mappe progetto fisse, a zone e adattive implementato; ascolto reale e UI nativa restano da verificare. Nessuna nuova CI remota, nessun commit.

---

## Checkpoint precedenti (storici)

# Aggiornamento - matching, selezione ed export MTA

RC **34/42 = 81,0%, PRE-RC**. Ripresa: `MTA-0.3.0-r210-pre-RC-sync-export-selection-cumulative.zip`, dettagli in `SYNC_EXPORT_SELECTION_R210.md`. Matching a zone/adattivo con BPM sorgente costante; fase beat e sorgenti a tempo variabile ancora da completare. Select all e normalizzazione MTA implementati. Nessuna nuova CI remota, nessun commit.

# MTA 0.3.0-r210 - stato corrente

**Verso la RC: 34/42 = 81,0%, PRE-RC**, perimetro `precommercial-20261030`; A4/A5 chiusi, nessun criterio promosso in questo checkpoint.

Riprendere da `MTA-0.3.0-r210-pre-RC-editor-workflows-cumulative.zip`, `EDITOR_WORKFLOWS_R210.md` e `validation/r210/editor-workflows/result.json`. Baseline Git `ee4e37fd30c39a72638b303b01ca0cd5b090f272`, ultima full CI nota `41156985339`; commit all'utente, nessuna nuova CI remota.

Implementati matching tempo/pitch a zona costante con riferimento e valori modificabili, guadagno e undo/redo waveform, delay lyrics e protezione PDF chord/lyrics. I tipi progetto, MIDI quantize, transport musicale e le icone erano già presenti e sono stati verificati. La sincronizzazione con fase automatica e BPM sorgente variabile resta incompleta; qualità musicale e zoom Windows/macOS/Linux/Android/iOS richiedono collaudi reali. Manuali utente HTML/PDF IT/EN aggiornati.

Selezione finale 156 passati, 0 skip, zero fallimenti/errori; Ruff e gate di revisione passano. Restano **A6,B6,C6,F4,F5,F6,G5,G6**; accesso SAM gated ancora da verificare sul server. Dettagli e limitazioni nel rapporto.

Commit cumulativo suggerito: `Recover payments and improve AI security, audio editing, and SAM setup`. Versioni precedenti in `development-history/before-editor-workflows-20261101/`.
