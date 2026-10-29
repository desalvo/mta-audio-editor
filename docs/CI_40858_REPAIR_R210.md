# CI 40858 — correzioni e accettazione Apple acquisita

29 ottobre 2026 · MTA 0.3.0-r210 PRE-RC · checkpoint autosufficiente.

**Il job iOS è passato; le 8 regressioni della CI standard sono corrette localmente. Avanzamento originale invariato: 28/42 (66,7%), macroarea E completa, RC aperta.** Nessun criterio originale è promosso da queste sole prove. Il prossimo commit spetta all’utente.

## Baseline verificata

Entrambi i run eseguono il commit `96c27c37e508564edc1cd4aee978896b1612e5a5`, che contiene il precedente cumulativo. Il confronto in sola lettura dell’intero albero Git, non troncato, conferma che tutti i **4164 blob tracciati** corrispondono ai byte consegnati. Nessuna modifica remota è stata effettuata.

Il workspace locale era tornato al vecchio checkpoint admin-cutover. È stato ripristinato **MTA-0.3.0-r210-pre-RC-ios-rights-cumulative.zip**, SHA256 `e638eb04aa6a04b87397efd4dda3416a359d6ac52747d86cbc1e47c779a367fd`, 98.884.818 byte / 4805 file. SHA, CRC, manifest completo e modi sono stati verificati; la copia precedente è conservata fuori dal progetto. Non è stato ricostruito lavoro già accettato.

## Risultati remoti osservati

| Prova | Esito verificato | Limite |
| --- | --- | --- |
| [Optional iOS model rights, run 40858613243 / job 123395824171](https://github.com/desalvo/mta-audio-editor/actions/runs/40858613243/job/123395824171) | 32 controlli reali Swift/CryptoKit/Security passati, zero failure/skip, vero roundtrip Keychain isolato e compilazione unsigned dell’app iOS riuscita | Non inferenza neurale, dispositivo fisico, firma IPA o intero F4/F5/F6 |
| [Quality standard, run 40858442206 / job 123395258375](https://github.com/desalvo/mta-audio-editor/actions/runs/40858442206/job/123395258375) | 7122 passati, 8 falliti, 50 skip, 872,26 secondi; copertura 76,67%, soglia 70% superata | Il run complessivo è fallito; nessun nuovo verde remoto dopo le correzioni |
| SAST / dependency audit, job 123395258444 | Successo | Riferito al commit sopra |
| VST3 SDK compile Linux, job 123395258278 | Successo | Non prova di ogni plugin o hardware |

L’artefatto Apple `ios-model-rights-40858613243`, ID 12890806512, ha SHA256 `1ee2817e4217a7068fef8a40816b6ef6d99346bf27d72e0f6b28b7365813986c`. Il contenuto è stato scaricato tramite il connettore GitHub e verificato contro il digest remoto. Il validatore originale richiede le **32 identità esatte**; sono stati verificati anche tutti i **13 hash correnti** del contratto/build, `accepted:true`, `ios_app_compiled:true` e il messaggio di build riuscita. Gli otto file originali dell’artefatto sono in `validation/r210/ci-40858613243-ios/`.

Il vecchio rapporto locale `ios-rights-target/acceptance.json` resta conservato: documenta l’assenza di Xcode di quel momento. È superato per l’accettazione SDK da questa prova reale, senza riscrivere i log storici. Il registro di produzione rimane vuoto: **nessun checkpoint Core ML reale è stato autorizzato** e la modalità locale resta indisponibile senza revisione effettiva nel bundle.

## Le 8 regressioni e la correzione

| Casi | Causa | Correzione |
| --- | --- | --- |
| 1 limite sorgente | Il test chiamava l’esecutore con ID utente 1 senza creare l’identità attiva richiesta; si fermava correttamente prima del controllo dimensione | Usa la fixture autentica di account/coda già disponibile e conferma che nessun ledger di fatturazione viene creato |
| 5 artefatti lead/backing | Le fixture di trasporto non fornivano la permission ora richiesta per UVR Kara 2 | Policy sintetica esplicita, temporanea e free-only, attraverso il vero valutatore; modello esplicito. I byte del backend sono finti e non autorizzano pesi reali |
| 2 default Whisper | I test contavano stringhe duplicate eliminate dal selettore condiviso | Verificano comportamento corrente: chiamata reale degli ingressi diretto/progressivo con runtime finto, default turbo, catalogo e alias configurato |

Tre nuovi casi negativi verificano che policy assente, disabilitata o malformata rifiutino il modello **prima del trasporto remoto e della creazione degli output**. Nessun controllo di produzione è stato aggirato o modificato. Tutti i cinque moduli corretti restano nella selezione standard unit; nessun test spostato in opt-in e nessuna soglia o workflow modificato.

**26 test locali passati, 3 nuovi; zero failure/error/skip.** Gli otto fallimenti remoti sono compresi nel gruppo corretto. Ruff sui sei file modificati passa. XML, identità dei casi e hash dei sorgenti sono in `validation/r210/ci-40858-result.json`. La verifica usa il runtime Python locale; non è una nuova full CI Python 3.14 né una nuova misura di copertura.

La prima scansione dei nuovi artefatti ha segnalato 12 digest SHA256 nella mappa nome-sorgente/valore: erano impronte di file verificabili, non credenziali. Il report redatto è conservato. Il formato è stato corretto in record separati `path`/`sha256`, coerenti con il manifest esistente; nessuna regola o esclusione è stata aggiunta.

## Riuso e stato RC

Tutti i **304 sorgenti app**, tutti i sorgenti native/mobile, script, workflow, dipendenze, checker, review di sicurezza e soppressioni restano byte-identici all’input. Sono riusate le prove corrispondenti, inclusi F3/ONNX, finanza, Chromium e censimenti. Il gate Apple non viene ripetuto perché i suoi 13 input sono identici. Non è stata ripetuta l’intera suite per correggere fixture isolate.

Restano i 14 criteri originali aperti: **A4,A5,A6,B2,B6,C3,C5,C6,D6,F4,F5,F6,G5,G6**. Le basi economiche legacy, la finanza globale e l’accettazione completa di tutti gli esecutori richiedono ancora lavoro; non sono tutti blocchi esterni. La prova SDK Apple chiude un prerequisito concreto di F4, non il criterio intero. F5/G6 richiedono ancora gli OS/dispositivi effettivi; F6 le revisioni indipendenti dei checkpoint installati. Transizione finanziaria generale e dichiarazione RC restano disabilitate.

## Prossima azione e consegna

Applicare **MTA-0.3.0-r210-pre-RC-ci-40858-cumulative.zip**, completo, con SHA256 adiacente. Conserva tutti i 4805 percorsi di ingresso, tutti i log di ingresso byte per byte, modi/metadati originali, asset, licenze e manuali. Non contiene runtime, credenziali, database o modelli aggiunti.

Dopo il commit dell’utente, verificare il solo nuovo run **Quality standard** che parte normalmente dal push. Non occorre rieseguire il workflow iOS invariato per queste modifiche alle fixture. La precedente full CI `40584085026` resta prova storica della baseline `4c3c73a`, non un verde della baseline `96c27c3` o del nuovo delta. L’agente non ha effettuato commit, staging, push, tag, release, dispatch CI o modifiche a server/provider reali.

Commit inglese suggerito, limitato al delta dopo `96c27c3`:

`Align CI fixtures with execution and model rights guards`

## English handoff

Both supplied runs bind commit `96c27c37e508564edc1cd4aee978896b1612e5a5`; all 4164 tracked blobs match the previous delivery. The Apple artifact is verified: 32 exact real SDK checks, actual isolated Keychain roundtrip, unsigned application build and 13 current source hashes. No real neural/installed-device/full-F4 acceptance is claimed. Preserve the historical blocked local report and use the imported CI artifact for current SDK evidence.

Standard quality failed eight stale tests: one lacked an active account fixture, five omitted the newly required synthetic model permission, and two asserted obsolete duplicated Whisper source strings. Only six test files changed; 26 focused tests pass, including all eight regressions and three new pre-transport denial cases. Production code, security gates, workflows and standard unit selection are unchanged. After the user commits, review the next ordinary Quality run; do not repeat unchanged iOS/full acceptance. Original progress remains 28/42, 66.7%, E complete, RC false. No GitHub/server/provider mutation was performed.
