# Default separazione Demucs — 2 novembre 2026

Corretto il ripristino involontario di “Solo percussioni” dalle preferenze: entrambe le finestre partono da tutti gli stem standard Demucs, senza secondo passaggio drums/percussioni. Metodo avanzato inattivo finché non richiesto esplicitamente; checkbox e target vengono sincronizzati anche all'invio. Dettagli, prove e limiti: `STANDARD_STEM_DEFAULT_R210_IT_EN.md` e `validation/r210-standard-stem-default-result.json`. Verifiche: 179 test passati, inclusi 36 nuovi casi; Ruff, sintassi JS e gate correlati superati. Nessuna nuova prova neurale/browser/nativa o CI remota. Baseline utente `f235f4c3ca67af72006bfc6262474ccb0ff0a705`; RC invariata **34/42 = 81,0% PRE-RC**.

# File progetto: tracce, conversione e backup — 2 novembre 2026

La finestra File del progetto mostra le tracce attive e inattive associate alle sorgenti. I file WAV PCM interi a 8/16/24 bit e FLAC possono essere convertiti fra WAV e FLAC: prima della sostituzione vengono verificati canali, frequenza e campioni decodificati, aggiornando tutte le tracce e le clip che condividono il file. Una copia originale rimane nell'area originali; è ripristinabile e manualmente eliminabile, mentre la pulizia automatica la conserva. Il ripristino conserva una copia della versione corrente. Le conversioni sono bloccate in presenza di job di progetto attivi e non coprono PCM floating-point o formati compressi con perdita. Passando a WAV viene disattivata la conversione automatica FLAC del progetto. Dettagli: `docs/PROJECT_MEDIA_CONVERSION_R210_IT.md`.

Sono passati 147 test mirati e altri 19 test mirati su profilo/conversione/UI, con sovrapposizione fra i gruppi; Ruff e sintassi JavaScript passano. Comprendono verifica audio senza perdita, file condivisi, scelta della sorgente da sostituire, ripristino, cancellazione manuale, quota, symlink e job attivi. Playwright e prove native reali non sono disponibili localmente; la CI completa e i registri di sicurezza rimangono da verificare.

# M-Live nel profilo utente — 2 novembre 2026

ID e parametro SYL sono configurati in **Profilo → M-Live**, con un pulsante per importarli da un proprio MTA. I valori predefiniti andrebbero sostituiti con quelli personali. Ogni export usa il profilo dell'utente che lo avvia; un job in background conserva uno snapshot all'avvio. I valori non vengono serializzati nei nuovi progetti. All'apertura di un progetto preesistente, una coppia completa personale può essere adottata nel profilo del proprietario solo se questo non è già stato configurato; in caso di più coppie diverse viene adottata la prima. Le coppie incomplete non vengono trasferite automaticamente. Gli allegati originali conservati da un MTA importato non vengono eliminati.

La CI precedente resta bloccata dalle revisioni sicurezza già documentate. RC **34/42 = 81,0% PRE-RC**.

# Merish: metadati predefiniti e lyrics miste — 2 novembre 2026

I valori predefiniti M-Live sono modificabili e andrebbero sostituiti con quelli personali. Questa versione sposta impostazioni e importazione nel profilo: l'export usa il profilo di chi avvia l'operazione e il progetto serializzato non contiene ID o parametro SYL. I dettagli di verifica e migrazione sono riportati nel checkpoint sopra.

Con righe lyrics a sincronizzazione mista, l'export mantiene tutte le righe, accordi e marker e passa a evidenziazione per riga, avvisando nella finestra di export. La temporizzazione originale delle parole nel progetto rimane intatta. Superati 90 test mirati MTA, compresi export completi MTA8/MTA16 con lyrics miste e marker e controllo del pulsante; Ruff e sintassi JS passano. I file sintetici per righe sono stati provati in precedenza, ma questa nuova combinazione e i metadati di default non sono ancora stati verificati su un nuovo export reale del progetto dell'utente. La CI resta bloccata dai quattro registri sicurezza obsoleti e le ultime modifiche browser non sono state ancora testate in CI. RC **34/42 = 81,0% PRE-RC**.

# CI 41419661058 — 2 novembre 2026

Il run completo sul commit `28b0e0f435de9d9cc2ea1e5d8d7f133dcd6db2ef` segnala 12 test falliti, 8.505 superati e 126 saltati. SAST e compilazione VST3 sono passati; i job dipendenti non sono stati eseguiti. Le correzioni della run precedente hanno ridotto i fallimenti da 24 a 12.

Quattro casi browser Stripe verificavano ancora che il pulsante di verifica scomparisse dopo un errore; ora controllano che la cronologia e il comando di riprova restino disponibili e che il pagamento rimanga sospeso. In quattro casi browser PayPal il pannello dei movimenti poteva essere aperto prima della fine dell'aggiornamento asincrono successivo alla risposta: il test attende ora il messaggio che viene pubblicato dopo il refresh, prima di aprire il pannello. Superati 193 test locali di regressione e Ruff; i 20 casi browser dei due file sono stati raccolti correttamente, ma Playwright/Chromium non sono disponibili nell'ambiente locale: occorre eseguirli in CI.

Restano quattro test di revisione sicurezza source-bound obsoleti. La scansione locale Bandit 1.9.4 ha rilevato zero HIGH, 21 MEDIUM e 150 LOW, con 11 nuove identità rispetto al registro: non sono state approvate automaticamente né sono stati aggiornati i soli hash. L'inventario dei delta è `docs/security/CI_41419661058_REVIEW_DELTA.md`, senza attribuire approvazioni. La CI resta quindi attesa rossa fino a una revisione effettiva dei sorgenti e dei finding. RC **34/42 = 81,0% PRE-RC**.

# CI 41387688751 — 2 novembre 2026

Sul commit `eb37017fb52aee5bac10b080a8a5bafcb6b9160f`, il job Quality fallisce con 24 test: 4 test di selezione/transport/lyrics non aggiornati, 16 test browser PayPal che aspettavano il successo su esiti ambigui, e 4 registri di revisione sicurezza non aggiornati. Altri 8.489 test superati, 126 saltati. I job SAST e VST3 SDK sono passati; i job dipendenti sono stati saltati.

Aggiornati i quattro test al comportamento attuale dell'Inspector, del focus timeline e dello spostamento non distruttivo delle parole. L'interfaccia pagamenti, dopo una verifica fallita, ricarica lo storico e mostra l'errore senza perdere le informazioni sui fondi trattenuti; l'admin ricarica il ledger anche dopo l'errore. I test browser e tre nuovi test API verificano il rifiuto fail-closed e la successiva riconciliazione soltanto con un esito ammissibile. Passano 175 test mirati e un test Node per l'interfaccia, più Ruff e controlli sintattici JavaScript; 4 prove browser del transport sono saltate perché Playwright non è disponibile in questo ambiente. I 16 casi browser PayPal modificati non sono stati eseguiti qui e richiedono CI/Chromium.

La scansione Bandit locale, 1.9.4, riporta zero HIGH, 21 MEDIUM e 150 LOW senza soppressioni; rispetto al registro precedente risultano 11 nuove identità e 8 non più presenti. Le quattro revisioni source-bound restano obsolete e i relativi test falliscono ancora: occorre una revisione effettiva delle differenze e dei nuovi finding, senza aggiornare gli hash come approvazione automatica. La CI non è dichiarata verde. Restano aperti anche i limiti hardware descritti sotto. RC **34/42 = 81,0% PRE-RC**.

# Merish5+ avvio MTA e testo finale — 2 novembre 2026

Riscontro hardware sugli export senza marker generati dall'app: MTA8 e MTA16, con e senza testo, partono da 0 e riproducono correttamente tutti i 12 suoni fino a 12 s; nei file con testo gli accordi cambiano a 0, 3 e 6 s e terminano con SOL. L'evidenziazione termina a 9 s come da dati di prova, ma l'ultima riga tornava bianca intorno a 10 s. L'utente ha confermato che tutte e quattro le prove A/B successive, per entrambi i formati, mantengono l'ultima riga evidenziata fino al termine. Il writer ora adotta la variante A: il terminatore COLORS è portato all'ultimo centesimo rappresentabile della durata audio e il precedente record indica il minuto del terminatore. L'utente conferma che sono a posto anche le quattro prove successive con marker INTRO/STROFA/FINALE, con e senza testo, MTA8 e MTA16. La prova hardware copre file sintetici di 12 s; i salti di minuto e durate molto lunghe sono verificati solo localmente. Restano da verificare il progetto reale Cherish senza compensazione, Xynthia2 e la CI. RC **34/42 = 81,0% PRE-RC**, nessun gate completo aggiuntivo.

L'utente chiarisce che in Cherish aveva spostato le tracce di circa 5 s per compensare un salto all'avvio sul Merish. Il confronto A/B sul suo Merish5+ usa gli stessi flussi e metadati salvo PreCntUSec: con 2000000 il file parte da circa 4 s e si sente solo l'ultima nota bassa; con 0 parte da 0 e tutte le cinque note basse e le sette alte sono udibili. L'export dei profili Merish MTA8/MTA16 imposta ora PreCntUSec=0 anche senza marker. L'eventuale pre-roll è audio sulla traccia click; nessun ritaglio o spostamento automatico della timeline. Le successive verifiche hardware sono riportate sopra. In precedenza sono passati 107 test mirati; per la correzione dell'evidenziazione sono passati altri 87 test mirati e Ruff. Due test MIDI aggiuntivi non sono stati eseguiti perché nel runtime locale manca mido. CI 41367770618 e revisioni di sicurezza restano aperte. RC **34/42 = 81,0% PRE-RC**, nessun commit o deploy.

---

# Editing timeline, metadati e export MTA — 2 novembre 2026

Il pulsante Elimina intervallo ora elimina anche i segmenti selezionati con lo strumento Select; lo split al cursore transport è disponibile con S e nel menu contestuale quando è attivo Split. Cmd/Ctrl+A dalla timeline seleziona tutti i clip; dalla testata tracce continua a selezionare le tracce. L'Inspector segue la selezione e lo slot MTA è modificabile anche sulla testata. Le nuove backing vocals vengono classificate come `choirs`.

Lyrics e chords vengono analizzati sull'audio renderizzato della timeline, quindi rispettano tagli, ritardi e insert della traccia; il worker server riceve PCM stereo 44,1 kHz. Se la traccia cambia durante l'analisi, il risultato non viene pubblicato. Madmom viene rilevato nell'ambiente del worker configurato e rimane soggetto al controllo delle autorizzazioni. Nell'editor combinato sono disponibili import/export JSON e delay cumulativo per lyrics e chords; gli editor singoli includono il delay e conservano la temporizzazione di parole/sillabe quando vengono spostati integralmente. Lo spostamento dei chords sgancia gli ancoraggi manuali, per poterli riallineare alla nuova posizione.

L'export MTA renderizza i clip e gli insert di ciascuna traccia, i livelli/pan/mute/solo, gli effetti temporali supportati e ora anche il volume master. Un insert attivo sul master non può essere applicato alla somma conservando esattamente le tracce separate: l'export lo segnala e richiede il bypass, invece di ignorarlo. I vecchi profili Merish non funzionanti non sono più proposti nell'export; B.Beat/DIVO e Generic restano selezionabili come non verificati. Le prove locali sul flusso audio decodificato iniziano vicino allo zero; il successivo confronto hardware del preconteggio spiega il salto iniziale come indicato nella sezione qui sopra. Nessuna verifica hardware o inferenza reale è stata effettuata in questo ciclo.

La CI 41367770618 e le revisioni di sicurezza restano aperte come indicato di seguito; nessuna nuova CI, nessun commit o deploy. La stima rimane **34/42 = 81,0% PRE-RC**, senza promozione di gate non verificati.

---

# CI 41367770618 e worker AI: correzione in verifica

Il commit a00e3be ha una CI fallita: oltre ai test di compatibilità MTA e waveform, alla contabilità e alle revisioni di sicurezza non aggiornate, vari test Playwright sui pagamenti raggiungono il timeout e un test SAM si è interrotto per un blocco SQLite. Il server segnalato rifiuta i worker AI: l'installatore configura ambienti Python separati, mentre la verifica precedente accettava solo l'interprete del server. Il registry ora ammette gli ambienti audio/SAM installati sotto /opt/mta, con marker e gruppo corrispondente, venv isolato e proprietà root non scrivibile da gruppo/altri. Anche il modulo interno unified può essere eseguito via Python se privo del bit eseguibile. È una fiducia nell'amministratore e nell'ambiente installato, non un'attestazione dei singoli pacchetti o modelli.

Corretti i test non aggiornati per slot MTA, undo waveform e suffisso .mta; la riconciliazione PayPal ora rifiuta prove JSON malformate. La prova della mancata riscossione distingue un GET di recupero dal POST di incasso. Localmente superati 191 test mirati, 81 test cronologia PayPal e 10 test adapter; Ruff dei file interessati passa. Playwright non è disponibile nell'ambiente locale; le quattro revisioni di sicurezza rimangono obsolete e non sono state automaticamente approvate. Serve una revisione esplicita e una nuova CI completa. Il funzionamento reale degli ambienti AI e dei modelli sul server non è ancora verificato. Nessun commit, deploy o intervento sul server. RC **34/42 = 81,0%, PRE-RC**; nessun criterio promosso.

---

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

### Timeline e lyrics — richieste completate

Tracce vuote audio/MIDI da menu contestuale; inserimento dei file del progetto nelle tracce; copia/incolla e trascinamento dei segmenti tra sorgenti diverse. I trasferimenti pubblicano una nuova sorgente PCM e conservano gli originali per undo/redo, riapertura e archivi. Le sovrapposizioni e i trasferimenti obsoleti sono rifiutati prima della pubblicazione.

Divisione delle lyrics >=40 caratteri su import JSON, estrazioni Whisper e recupero remoto, con tempi affidabili conservati oppure stimati e ancoraggi degli accordi rimappati. Avvisi e azione Dividi negli editor. Dettagli e limiti: `TIMELINE_MEDIA_R210.md`.

**RC generale invariata: 34/42 = 81,0%.** Le funzionalità di questo batch sono implementate e verificate localmente; nessun criterio esterno viene promosso senza la relativa evidenza. CI remota, browser grafico e prova hardware nativa restano da verificare.

### Hotfix CI 41473520966 — dopo il commit 8bc97f4

Baseline confermata: `8bc97f4385b609a601da898d51dbb8f07937a1ab`. Corretti i test non aggiornati alle modifiche di menu, slot/ritardo, lyrics e tastiera. Il worker ritenta esclusivamente la lettura originale dei limiti quando SQLite è temporaneamente occupato; nessuna ripetizione di scritture contabili e nessun fallback che ignori limiti/barriere. Danni e contesa persistente conservano il comportamento di arresto.

La suite mirata che comprende tutti i fallimenti del run, guardian/cutover, contesa DB e regressioni di timeline/lyrics passa con 112 test. Le revisioni di sicurezza sono riallineate ai sorgenti senza nuove disposizioni automatiche: i contesti Bandit/AST dei processi e delle chiamate di rete restano identici. Dettagli: `CI_41473520966_R210.md`.

RC **34/42 = 81,0%**, senza promozione di criteri esterni; nuova full CI remota da verificare sul commit successivo. Il messaggio di commit suggerito riguarda soltanto questo hotfix.

### Hotfix CI 41491614671 — revisione dei test di identità gestita

Baseline: `5e9743d1a2938be9689d9e88e1afb98468b4fe77`. Il run ha un solo fallimento: il test di portabilità creava due revisioni dei permessi e ne pretendeva la stessa impronta. La fixture ora trasferisce la stessa revisione ai due host; i test forzano anche uno scarto di 60 secondi e confermano separatamente che una nuova revisione debba cambiare l'impronta. I test authority/worker condividono lo stesso documento di policy quando intendono variare soltanto l'installazione del modello.

Nessuna modifica ai sorgenti applicativi, alle licenze o ai manifest di sicurezza. Rapporto: `CI_41491614671_R210.md`. **RC 34/42 = 81,0%**, nuova CI remota da verificare sul prossimo commit.

Verifica finale hotfix 41491614671: **550 test passati, zero skip/fallimenti/errori**, Ruff superato; 566 sorgenti runtime invariati e revisione di sicurezza coerente.


## 2026-11-03 — normalizzazione MTA e installazione Mega 53

- Normalizzazione MTA: misura e guadagno escludono click, accordi generati e tracce contrassegnate nell’Inspector; slot misti separati fino al ricalcolo, clipping rilevato, tracce mute effettivamente silenziose. Test locali PCM/MP3 per MTA8/MTA16; verifica fisica su Merish ancora necessaria.
- Amministrazione: installazione locale esplicita Mega 53 con commit Git fissato, YAML/checkpoint ufficiali verificati, ambiente separato, caricamento stretto del modello e pubblicazione solo a verifica superata. Job annullabile, esecuzione effettiva e GPU ancora da validare. I test automatici simulano download e installazione.
- Ancora aperto: installazione remota dei worker e installazione web completa di tutti i runtime accessori non già coperti dalle ricette esistenti; non dichiarare chiusa l’area fino a test reali. Nessun server reale è stato modificato.

## CI 41673509118 — correzione permessi eseguibili

Il commit da01cdd ha perso i bit eseguibili su tre file che nel commit precedente erano 100755. Questo ha causato sette test falliti, compreso il controllo dell'adapter Demucs. L'archivio cumulativo conserva ora questi tre file come 100755 e include una patch Git per ripristinare i bit nell'indice anche sui filesystem che non conservano il permesso Unix. I sette test interessati sono stati ripetuti localmente con esito positivo. La full CI deve essere rieseguita dopo il commit; restano aperte le prove reali su hardware e l'installazione AI remota.

## CI 41688455408 — collocazione del rapporto

La CI conferma il ripristino dei permessi. Il solo test fallito riguarda il rapporto Markdown nella radice, riservata ai README. Il rapporto è stato spostato in docs/.

## Messaggistica tra account e pulsanti di export

- La campanella con contatore dei non letti è disponibile nelle pagine dell’editor e dell’account, incluse le sezioni amministrative. Apre una dashboard flottante e richiudibile per conversazioni tra due account attivi e confermati, indipendenti dai progetti. Gli aggiornamenti arrivano entro circa sei secondi a pagina attiva.
- La dashboard gestisce testo, immagini, audio e video. Gli allegati sono verificati lato server, con limite di 20 MiB per file e quota di 512 MiB per mittente. Le conversazioni restano disponibili ai partecipanti finché gli account e i relativi dati sono conservati. Le email sono accodate sul server e contengono un avviso generico e, con URL pubblico configurato, il link alla dashboard. La consegna richiede SMTP configurato.
- Reso esplicito il contrasto e il rendering delle etichette nei pulsanti della scelta formato, dei parametri di export e della mappatura MTA.
- **RC invariata al 73%**. Questo batch aggiunge una funzionalità al perimetro e non chiude un gate esterno. CI remota, verifica visiva nel browser e consegna SMTP su server reale da confermare.

## CI 41717062183 — cutover e revisione sicurezza dopo la messaggistica

- Baseline verificata contro l’albero Git del commit `e54f7113fd26d01592dcb2a11e0895e024e5e799`. La full CI ha riportato 101 test falliti e un falso positivo Gitleaks sul digest pubblico di `app/auth.py`.
- Il cutover riconosce esplicitamente `direct_messages` come tabella di comunicazione. La prova di cutover in entrambe le direzioni conserva i messaggi esistenti e il controllo continua a rifiutare tabelle ignote o storico finanziario inatteso.
- Un nuovo collegamento SQLite può ripetere una sola volta la lettura iniziale della barriera su BUSY/LOCKED. L’errore persistente e le prove mancanti continuano a bloccare l’operazione. Il test browser del profilo aspetta il pulsante di annullamento con un’asserzione Playwright mantenendo il conteggio atteso.
- Il registro Bandit marca i digest pubblici con `sha256:` e li confronta integralmente. La regola Gitleaks responsabile del falso positivo è stata verificata sulla riga originale e su quella corretta. Nessuna allowlist aggiunta. Le disposizioni Bandit restano le stesse e le verifiche degli inventari restano attive.
- **RC 73%**. Le verifiche locali coprono API, cutover, cronologia privata, contesa e inventari. Chromium e lo scanner Gitleaks completo vanno rieseguiti nella prossima full CI.

## Riconoscimento accordi e recupero BTC-HCQT

- Il checkpoint Beatles-FT è stato ritirato dall’autore. I pesi del BTC originale usano un front-end diverso e il modello GGUF disponibile dichiara una licenza non commerciale. MTA non scarica queste alternative come sostituti HCQT.
- Per abilitare un checkpoint HCQT compatibile e autorizzato, l’amministratore imposta `MTA_BTC_HCQT_CHECKPOINT_URL` (HTTPS, senza credenziali o query) e `MTA_BTC_HCQT_CHECKPOINT_SHA256` nel servizio. Nel pannello dei permessi dei modelli registra l’autorizzazione per `btc-hcqt`, con il riferimento HTTPS alla prova e il frammento `#sha256=<digest>`. Dopo il riavvio usa **Scarica modello** per BTC-HCQT. Per sostituire un’installazione precedente, rimuovila esplicitamente dal gestore modelli. Il download usa l’interprete AI configurato e richiede PyTorch ≥ 2.6. I pesi non vengono inclusi nel pacchetto.
- L’installazione usa sorgenti fissati a commit Git, scarica solo i file di codice necessari da BTC-ISMIR19 e controlla SHA-256 e autorizzazione sul checkpoint. Una prova CPU su audio sintetico carica il corpo BTC e il front-end HCQT prima della pubblicazione atomica. Le installazioni esistenti sono conservate. I nuovi checkpoint sono verificati anche in inferenza.
- Il catalogo distingue file presenti, autorizzazione e possibilità di download. Gli errori di download e di uscita del worker mostrano un codice diagnostico senza esporre percorsi del processo o stderr al client. Il proprietario originale del job e i controlli di contabilizzazione restano in vigore.
- La lettura della barriera riprova una sola volta in caso di BUSY/LOCKED e distingue l’indisponibilità persistente. Il worker Chromagram accetta progetti con BPM assente. Rimangono da verificare Chordino e ChordFormer sul server effettivo e un checkpoint HCQT reale autorizzato.
- **RC 73%**. La baseline è il pacchetto del cutover verificato dalla full CI 41730671538. Questo aggiornamento richiede una nuova full CI.

## Gestione completa di modelli e runtime AI · r210

- **Amministrazione → Modelli AI** separa i runtime dai modelli. Le azioni lavorano sull’intero modello. La rimozione BTC-HCQT include pesi, file e metadati della sua directory gestita, anche per una vecchia installazione Beatles-FT incompleta. La manutenzione per singolo file è in una sezione avanzata.
- Download, installazioni e rimozioni aprono una finestra di progresso. I job che pubblicano misure mostrano una percentuale. Gli altri mostrano una barra indeterminata fino alla risposta o allo stato terminale. I job di rimozione usano la stessa protezione contro le modifiche durante l’inferenza.
- Il runtime audio gestito è un unico ambiente per Whisper, accordi, marker, Demucs, DrumSep e backing vocals. L’installazione locale verifica le dipendenze prima di cambiare l’instradamento, senza riavviare il server o modificare `mta.env`. La rimozione elimina il runtime gestito e conserva i pesi. Per un ambiente provisionato fuori dal gestore web, il tasto disattiva l’instradamento. Le installazioni ACE esterne e i worker remoti si gestiscono sul relativo host. Su installazioni prive dell’installer o di accesso alla directory di sistema l’azione non è disponibile.
- Mega 53 ha azioni distinte per il runtime gestito e il checkpoint v1.0.21. Il modello viene installato solo dopo verifica dei byte. La procedura guidata del runtime verifica anche il caricamento stretto.
- I pannelli di diritti e permessi dei modelli sono in **Modelli AI** sul server e nelle **Impostazioni** native. Le conferme e i controlli di licenza preesistenti restano in vigore.
- Nuovi motori accordi **ChordMini BTC distillato** e **ChordMini 2E1D / ChordNet** con codice e checkpoint fissati a commit. L’installazione scarica solo il checkpoint selezionato, controlla la sua identità e prova il caricamento PyTorch weights-only con inferenza CPU prima di pubblicare l’installazione. Richiedono autorizzazione documentata per i pesi e PyTorch ≥2.6. I benchmark pubblicati motivano la valutazione ma non garantiscono un miglioramento per ogni traccia MTA.
- Corretto il parsing dell’output BTC-HCQT in `master` e la distinzione fra `maj7` e dominante. Verificate localmente le azioni amministrative e i gate di sicurezza. Rimangono la full CI e la prova con runtime e pesi reali. **RC 73%**.

## CI 41759036727 · cache frontend e test delle impostazioni licenze

Baseline verificata contro tutti i blob e i permessi del commit `819d13405480289b1e9e83e4df50d4df106e9783`. SAST, dipendenze e compilazione VST3 sono passati. Il job di qualità ha riportato cinque fallimenti, 8913 test passati e copertura 78,31%.

Il riferimento di app.js conserva nuovamente il prefisso della release `0.3.0-r210`, seguito dal suffisso del batch. I quattro casi Chromium IT/EN e server/native verificano ora i permessi nella relativa pagina delle impostazioni. La prova nativa usa l’effettiva funzione showNativeSettings; la prova server controlla il contenitore distribuito nel tab Modelli AI. Restano coperti il consenso al download degli asset, il salvataggio dei permessi e la richiesta di sintesi vocale.

Ruff e 100 test locali passano, inclusi i gate di sicurezza e la gestione completa dei modelli. I quattro casi browser sono stati tentati con Chromium di sistema ma l’ambiente blocca la creazione del socket Unix del browser, prima del caricamento della pagina. Con la configurazione standard sono saltati per assenza del binario Playwright. La loro esecuzione deve essere confermata in full CI. I registri di sicurezza restano coerenti perché questo hotfix modifica soltanto HTML, test e stato sviluppo. **RC 73%**.

## CI 41806860730 · pubblicazione rolling early-main

Baseline verificata contro tutti i blob e i permessi del commit `f8ed2c37f95a08ed1c9b887390ab2fb100503fb3`. La full CI conferma **8918 test passati, 126 saltati e copertura 78,31%**, inclusi i quattro casi Chromium delle impostazioni licenze. Superati anche sicurezza, container, pubblicazione Docker, VST3 e build Windows, macOS, Linux, Android e iOS. Il solo job fallito è la pubblicazione rolling early-main: una chiamata DELETE di un allegato precedente restituisce `unexpected end of JSON input`. Il log non espone lo stato HTTP della risposta fallita.

La cancellazione usa ora `gh api --include --silent`, acquisisce lo stato HTTP e riprova fino a quattro volte con attese di 2, 4 e 6 secondi. Un 404 conferma che l’allegato è già assente, anche dopo una risposta troncata; 401, 403 e 422 interrompono immediatamente il job. Gli errori persistenti bloccano l’upload. Restano la pulizia degli allegati delle revisioni precedenti, l’elenco paginato e la pubblicazione con sostituzione dei nomi esistenti. L’elenco temporaneo usa la directory RUNNER_TEMP del job.

**124 test locali passati**, inclusi 16 casi che eseguono il vero step Bash del workflow con Git e GitHub CLI simulati: risposta vuota 204, errore JSON, 502/429 con recupero, 404 dopo cancellazione, permessi negati, errore persistente, release nuova o già parzialmente ripulita e identificatore non valido. Ruff, parsing YAML, sintassi Bash e gate degli inventari di sicurezza superati. I sorgenti applicativi e i registri di sicurezza sono invariati. Nessuna pubblicazione remota eseguita durante la verifica; il percorso corretto sarà confermato dalla prossima full CI. **RC invariata al 73%**.
## 2026-11-08 · Avvisi sui tempi delle parole nelle lyrics

Baseline verificata contro tutti i blob e i permessi del commit `847c9ffe5c67cd5c2ba930a01d7730835eec6880`, confermato dalla full CI 42284335566. La correzione Demucs nativa fa parte del cumulativo.

In **Edit Lyrics** le righe con problemi di sincronizzazione mostrano un simbolo di pericolo e un avviso espandibile. Il dettaglio identifica numero e testo della parola, inizio, fine e limite violato. Sono rilevati sovrapposizioni, durata non valida o nulla alla risoluzione MTA di 10 ms, parole prima della riga o oltre la riga successiva, la fine esplicita della riga e la fine audio. Sono segnalati anche inizi di riga coincidenti o troppo vicini e, in modalità caratteri, tempi di sillaba non validi. Le righe disabilitate o eliminate sono escluse dal controllo e dai limiti fra righe attive.

Gli avvisi si aggiornano durante le modifiche, l’inserimento, la divisione, la cancellazione, la riconciliazione dei timestamp e il delay generale. La verifica anticipa la stessa conservazione o invalidazione delle parole applicata dal salvataggio dell’editor. Il riepilogo indica quante righe richiedono attenzione. L’editor combinato Lyrics + Chords + Markers mostra gli stessi dettagli accanto alle righe interessate.

Verificati **152 test locali distinti**, Ruff, sintassi JavaScript e gate degli inventari di sicurezza. I nuovi test confrontano i casi di rifiuto con l’encoder Merish effettivo e verificano visualizzazione, traduzioni IT/EN, aggiornamenti e escaping del testo nei normali entry point degli editor. Un test Chromium aggiunto resta saltato per assenza del pacchetto Python Playwright. Il tentativo con Chromium di sistema termina prima del caricamento della pagina perché l’ambiente nega i socket Unix. La prova visiva deve essere eseguita nella prossima full CI. **RC 73%**.



## 2026-11-08 · Correzione automatica dei tempi lyrics

Baseline verificata contro tutti i blob e i permessi del commit `4abc9eeea3ecce09dcee40df3a1501e6c87eb866`. I run 42497190375 (matrice runtime offline) e 42500816485 (pacchetti server firmati) sono conclusi con successo. Il run principale 42497190311 risulta ancora in esecuzione al controllo durante questo batch.

- Ogni problema nell’editor Edit Lyrics e nell’editor combinato Lyrics + Chords + Markers ha un pulsante **Correggi**. Il pulsante **Correggi tutti** applica una correzione globale alla bozza.
- Una parola che supera la fine riga, l’inizio della riga successiva o la fine audio viene accorciata. In caso di sovrapposizione viene prima anticipata la fine della parola precedente, preservando l’inizio della successiva quando possibile. Se i tempi vicini occupano lo spazio necessario, vengono accorciati e ridistribuiti entro i limiti della riga. I segmenti corretti rispettano la risoluzione MTA di 10 ms. I casi gestiti includono durata nulla o invertita, inizio prima della riga, collisioni fra inizi riga e tempi delle sillabe.
- Le correzioni conservano testo, parole e sillabe e aggiornano gli avvisi. Si applicano al progetto con **Salva**. La chiusura senza salvataggio conserva il progetto precedente. Nell’editor combinato ogni correzione è un’operazione Undo/Redo e mantiene gli anchor manuali identificabili. Una combinazione che non può contenere neppure gli intervalli minimi produce un avviso sulla riga e lascia la bozza intatta.
- Verificati **175 test locali distinti**, Ruff, sintassi JavaScript e inventari di sicurezza. I test verificano il passaggio bozza → salvataggio, l’Undo/Redo con anchor, le correzioni individuali e globali contro l’encoder Merish e 300 combinazioni deterministiche di tempi errati. Il test Chromium esteso copre i pulsanti singoli, Correggi tutti e il salvataggio, ma resta saltato localmente per assenza del pacchetto Python Playwright e deve essere eseguito nella prossima full CI. **RC 73%**.


## 2026-11-08 · Leggibilità dei pulsanti Edit Lyrics

Baseline del commit `6cb439f520d285905425a100bb3f00b61b0e10cd`, confermata dai run CI 42508613766, 42508613774, 42508613777 e 42516890572. La full CI precedente ha superato 8976 test con copertura 78,32%.

Il testo chiaro dei pulsanti di Edit Lyrics poteva apparire sullo sfondo chiaro predefinito del browser. Lo stile ora definisce sfondo scuro, bordo, colore del testo e text-fill, dimensione del font e focus. Sono coperti barra, azioni per riga, Correggi, Correggi tutti e pulsanti del footer. Salva ed Elimina mantengono colori distinti. Gli stati disabilitati sono leggibili e i pulsanti con attributo hidden restano nascosti anche in presenza delle regole display del modal. Il riferimento CSS è aggiornato per il caricamento della nuova versione.

Verificati 55 test locali e Ruff. La valutazione della cascata CSS sulle classi dei pulsanti a larghezze 390 e 1000 px restituisce contrasto minimo 6,49:1 per i controlli attivi. Il test Chromium esistente controlla ora colore effettivo, dimensione del testo e visibilità di Correggi tutti. Resta saltato localmente per assenza del pacchetto Python Playwright. Il tentativo con Chromium di sistema termina per mancata autorizzazione ai socket prima del caricamento della pagina, quindi la prova nel browser è demandata alla prossima full CI. **RC 73%**.
