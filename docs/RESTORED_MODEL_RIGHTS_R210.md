# Autorizzazioni ripristinate e ultimi ingressi legacy

30 ottobre 2026 · MTA 0.3.0-r210 PRE-RC · checkpoint autosufficiente.

Questo blocco corregge autorizzazioni incomplete importate da file e ingressi di inferenza legacy rimasti senza controllo corrente. **Il criterio originale F4 resta aperto; nessuna promozione dei 42 criteri. Avanzamento RC: 28/42, 66,7%; E completa, RC non raggiunta.** La matrice `validation/r210/restored-rights-result.json` separa prove correnti, riuso e residui.

## Baseline e CI

La baseline confermata è `4014a1fd5bfccc4e7f65c32345cb4c52f98f3d8d`, tree `9cd308daa505ef7c01c743ef2b5ce7461f1cd488`, messaggio `Retry busy queue observations and isolate worker tests`. Tutti i **4208 blob tracciati** corrispondono all'archivio in ingresso. Input: `MTA-0.3.0-r210-pre-RC-queue-busy-cumulative.zip`, SHA256 `51b9696e9ca2eeecf6248c312117ecd9b250fab7cca474e99b755d4aaa729db2`, 99.525.251 byte, 4878 file. SHA/CRC, manifest e modi verificati al ripristino; la precedente directory locale è stata conservata separatamente.

Il [run 40972934180](https://github.com/desalvo/mta-audio-editor/actions/runs/40972934180) è ora **completato con successo**: Quality 7155 passati, 50 skip, copertura 76,71% su soglia 70%; SAST/dependency audit, SDK VST3 Linux, build Windows/Chordino, macOS x64/arm64, Linux x86_64/arm64, container, Android e archivio iOS passano. Le pubblicazioni sono saltate. È il profilo unit standard, `complete_regression:false`, non un nuovo run full. Artefatto diagnostico 12942381400, SHA256 `b6b900e488610f57ad62a10fc0ec3d9cf19ac318469ed85be0ee024005404284`; le selezioni e gli esiti CI sono conservati. Questa CI riguarda la baseline, non il nuovo delta.

## Comportamento corretto

Prima, un file `license-policy.json` ripristinato o modificato a mano poteva abilitare un modello con il solo `mode`, evitando i requisiti del pannello amministrativo. Ora una deroga abilitante deve contenere revisione completa: evidenza HTTPS senza credenziali, motivo, responsabilità, conferma di accesso gratuito quando necessaria, autore e data validi; per i modelli soggetti a restrizioni anche base autorizzativa e seconda conferma. Campi ignoti, JSON con chiavi duplicate o valori non finiti sono rifiutati. Le condizioni NonCommercial richiedono anche la disattivazione del servizio commerciale globale; non sostituiscono permessi ignoti sui checkpoint. Le sole restrizioni `disabled` restano valide senza inventare una revisione. In assenza di deroga restano le impostazioni predefinite del catalogo. Una singola voce malformata viene mostrata come indisponibile dal catalogo.

Non viene migrata automaticamente una vecchia autorizzazione incompleta: l'amministratore deve riesaminare i permessi reali e salvare la revisione tramite il pannello/API esistenti. Non copiare le attestazioni sintetiche dei test in produzione. L'attestazione dell'operatore non conferisce diritti e non è una revisione legale indipendente.

I subprocess BTC/ChordFormer e Mega53 verificano la policy subito prima e dopo il lavoro; i risultati non sono restituiti dopo revoca. I callback Madmom già caricati controllano la policy a ogni invocazione. Il backend profilato Demucs non può eseguire una callback dopo una revoca avvenuta durante la preparazione del profilo. Launcher ACE locale, server desktop, smoke e benchmark di generazione verificano i permessi prima dell'avvio; il probe hardware senza inferenza resta utilizzabile. MR-MT3 resumable verifica prima di importare/caricare il runtime, a ogni forward e prima di salvare finestre o risultato finale, anche dopo la decodifica. Non si aggiunge un'esenzione per diagnostica o lavoro gratuito. La revoca non è un arresto preventivo atomico di una libreria esterna già in esecuzione: questi controlli impediscono un nuovo avvio e la consegna successiva quando la revoca viene osservata.

## Prove e limiti

**1104 esiti correnti distinti passati, 305 nuovi, 7 skip espliciti, zero failure/error correnti.** Il rapporto JSON conta gli ultimi esiti per identità, senza sommare le riesecuzioni. Le prove comprendono tutte le identità del catalogo più un'estensione sintetica, record incompleti/ambigui, revoca prima/durante i callback, veri processi Python generati per accordi/Mega53, CLI standalone e le API token JSON/upload per **tutti i 18 tipi registrati**, con policy disabilitata o incompleta: **72 rifiuti, zero esecuzioni del worker e zero ledger**. Per i due tipi vocali l'upload usa uno score valido invece di WAV non accettato. La prova MR-MT3 usa rete/Torch sintetici e decodifica FFmpeg reale: non è inferenza neurale né accettazione GPU.

I 7 skip sono espliciti: quattro casi richiedono un modello/runtime reale approvato non installato, tre richiedono `espeakng_loader`. Non sono pass né nuovi blocchi risolti. I rapporti diagnostici iniziali conservano i fallimenti delle fixture corrette e i due puntatori di review obsoleti; gli esiti correnti indicati nel JSON li sostituiscono. Non sono stati tolti test, aggiunti opt-in o ridotte soglie/checker/dipendenze. Ruff e i gate source-bound passano sul delta corrente: Bandit304 sorgenti/165 finding (0HIGH/21MED/144LOW), C2 170 confini, runtime551 sorgenti/782 punti, HTTP30 siti/21 file. Quattro identità finding ACE cambiano per contesto/riga e sono state riesaminate esplicitamente; nessun finding nuovo. Gitleaks8.24.3 non rileva segreti nelle righe introdotte/sostituite e nei file nuovi, manifest finale incluso.

Si riusano le prove di finanza, UI/Chromium, albero FFmpeg e loader F3 per le rispettive parti byte-identiche. I 13 hash della prova Apple `40858613243` sono ancora identici: 32 controlli SDK, Keychain reale e build unsigned già validati; nessun nuovo run iOS. Registro Core ML reale vuoto, nessuna approvazione di checkpoint o accettazione su dispositivo installato.

## Matrice residua e prossima chiusura

| Confine | Esito di questo blocco | Residuo originale |
|---|---|---|
| File di policy importati, tutti i domini del catalogo | Contratto della revisione verificato e non aggirabile con un solo mode | La revisione sintetica non prova i diritti delle effettive weights |
| Callback e subprocess accordi/Madmom/Mega53/profilazione | Revoca prima/durante e rifiuto della consegna verificati | Esaustività di altre librerie/runtime dinamici non certificata |
| Diagnostiche ACE/MR-MT3 | Inferenza soggetta alla policy corrente | Eseguibile ACE configurabile e checkpoint reali non attestati qui |
| API dei 18 tipi registrati | Entrambi i trasporti negano permessi disabilitati/incompleti senza lavoro/ledger | Un eseguibile scelto dall'operatore non prova da solo il modello che carica |
| Remote/pull/native/mobile | Prove precedenti riusate solo sui confini invariati | Nessuna accettazione universale di codice opaco, rete dinamica o sistemi nativi installati |

F4 richiede ancora un contratto verificabile fra eseguibile configurato, loader e checkpoint realmente usato, oltre alla verifica completa degli ingressi dinamici/native. Il censimento AST source-bound di 10 famiglie è un ausilio alla review, non prova di reachability di codice arbitrario. Non basta riclassificare i residui come diagnostica o restringere retroattivamente il criterio. Il profilo F3 già accettato offre un modello di binding per un solo adapter; non autorizza tutti gli altri.

Prossimo blocco: inventariare esplicitamente i punti configurabili `ai_worker_registry`, launcher ACE e runtime esterni; per ciascuno applicare un contratto di identità verificabile oppure negare il percorso privo di contratto, preservando le integrazioni approvate e provando i bypass reali. Solo dopo completare l'accettazione F4, senza confonderla con F5 (tutti i sistemi operativi) o F6 (revisione indipendente dei checkpoint). Finanza globale/legacy resta lavoro indipendente di implementazione. Restano aperti A4,A5,A6,B2,B6,C3,C5,C6,D6,F4,F5,F6,G5,G6.

## Consegna e ripresa

Cumulativo: `MTA-0.3.0-r210-pre-RC-restored-rights-cumulative.zip`, SHA256 adiacente. Conserva tutti i 4878 percorsi e i 670 log di ingresso, asset, licenze, manuali e byte dei log originali, con modi/metadati ZIP. Escludere cache/runtime/DB/helper di trasferimento. Riprendere da questo archivio dopo un eventuale reset, confrontando prima SHA/CRC/manifest. Non ripetere le 1104 prove invariate; usare la selezione e i rapporti nel JSON e rieseguire soltanto i confini modificati.

Nessun commit/staging/push/tag/release, dispatch CI, operazione su server/provider reale o modello scaricato. Dopo il commit dell'utente verificare Quality e SAST standard; la baseline verde e iOS invariato non richiedono ora una nuova full CI.

Commit inglese suggerito, cumulativo dopo `4014a1f`:

`Require complete model reviews and guard legacy inference entry points`

## English handoff

Baseline 4014a1f matches all 4208 tracked blobs; run40972934180 completed successfully, including all build jobs, standard unit Quality7155/50skip/76.71% and SAST. This does not validate the new delta. Restored enabling policy records now require the complete operator-review contract. Cached model callbacks, chord/Mega53 children and ACE/MR-MT3 diagnostics enforce current permission; resumable output is rechecked after decoding. All18 registered API kinds reject disabled/incomplete reviews through JSON and valid upload routes before worker execution or ledger creation. Synthetic records/children are not real neural/checkpoint/OS acceptance.

F4 remains open for complete opaque executable/model identity and dynamic/native acceptance; no original criterion or weight changed. Progress28/42,66.7%,RCfalse. The source-bound result JSON identifies current/reused proofs and explicit prerequisite skips. Preserve all input paths/log bytes and ZIP metadata in the cumulative. The environment outage was recovered with local work intact; it did not supply acceptance evidence. User commits later; no remote mutation was performed.
