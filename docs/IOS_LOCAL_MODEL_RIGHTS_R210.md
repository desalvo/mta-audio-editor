# Core ML iOS — ammissione locale dei diritti

29 ottobre2026 · MTA0.3.0-r210 PRE-RC · baseline confermata `4c3c73afe6d3829aad155c23f5f1bbb6d375433a`.

**28/42 criteri originali,66,7%,E completa1/7;RC falsa. Nessun criterio promosso:l’aumento numerico richiesto non è raggiunto.** Il contratto Core ML è implementato nel ciclo completo di selezione/download/installazione/cache/caricamento/inferenza. L’accettazione Apple rimane **bloccata**,non passata. F4 completo,F5/F6 e gli altri criteri originali rimangono aperti.

Input:MTA-0.3.0-r210-pre-RC-legacy-separators-cumulative.zip,SHA256 `48db1dba2889d914780138b724f7c2412b01001f3e8df7994d3b715380901ef3`,98.830.780byte/4772file. Ripristinato dalla copia persistente dopo il reset del workspace:SHA,CRC,manifest completo e modi verificati. La vecchia copia admin-cutover è conservata fuori dal progetto. Nessun lavoro già validato è stato ricostruito.

## Problema e confine di fiducia

L’ingresso iOS precedente compilava il file scaricato prima di una verifica dei diritti e trattava il fingerprint ricevuto come metadato da salvare. Anche i compilati già presenti e il valore `bundled-default` potevano essere riusati senza un contratto dei diritti locale. La revisione del sorgente conferma quel percorso;non si dichiara di averlo eseguito su un dispositivo Apple in questo ambiente.

La nuova autorità locale è `Models/model-rights.json` incluso nel bundle firmato dell’app. Ogni selezione lega modello/cardinalità/formato a byte sorgente esatti,LICENSE/NOTICE effettive e rispettivi SHA256,base di autorizzazione,reviewer,riferimento HTTPS e intervallo della revisione. Il solo contesto non commerciale non è accettato come permesso. Nome del server,header HTTP,token di download,sidecar,UserDefaults e presenza di un vecchio modello non generano una revisione.

**Il registro distribuito è intenzionalmente vuoto. Nessun checkpoint Core ML reale è stato revisionato o approvato in questo ciclo.** La selezione locale resta indisponibile finché una revisione effettiva del checkpoint esatto non entra nell’app. La validazione del formato del registro non sostituisce la revisione indipendente F6. Le modalità server esistenti conservano i propri controlli;Auto vede la capacità locale non disponibile. La scelta Locale produce un rifiuto leggibile IT/EN. I vecchi file restano conservati e visibili per la cancellazione anche se il catalogo server non li elenca più.

## Percorso implementato

1. Bootstrap,aggiornamento periodico,manager e richiesta locale verificano la revisione prima di richiedere/scaricare il modello. Un formato autorizzato solo come compilato incluso nell’app non abilita un download di sorgenti diverso. Restano le preferenze Wi-Fi e aggiornamento periodico;nessun nuovo endpoint o credenziale server è introdotto.
2. L’installatore crea uno staging privato e copia la sorgente. Prima di chiamare il compilatore Core ML verifica realmente i byte di quella copia contro la revisione del bundle e contro l’eventuale fingerprint annunciato. I compilati inclusi devono invece corrispondere all’esatto inventario revisionato. Symlink,hardlink,file speciali,inventari incompleti e dimensioni fuori budget sono rifiutati.
3. La ricevuta lega ID/cardinalità,sorgente,contenuto della revisione e intero inventario compilato. L’inventario ordina per byte UTF8 nome relativo,dimensione e SHA256 di ogni file,compresi membri vuoti;non accetta aggiunte/rinomine invisibili. La ricevuta vive nel portachiavi del dispositivo,con sincronizzazione disabilitata e accessibilità `AfterFirstUnlockThisDeviceOnly`. Le vecchie preferenze restano soltanto metadati compatibili e non autorizzano l’uso.
4. Pubblicazione della directory e scrittura della ricevuta sono coordinate. Un errore prova a ripristinare modello/ricevuta precedenti;un rollback OS irrisolto conserva il backup privato e non conferisce autorizzazione. Un crash tra i due passaggi lascia un mismatch verificabile e il modello non viene caricato automaticamente. Non si inventa una ricevuta per una cache legacy.
5. Prima di `MLModel(contentsOf:)` viene verificato nuovamente l’intero compilato. Durante l’inferenza si rilegge la revisione prima e dopo ogni `prediction` e prima della consegna. Scadenza o revisione cambiata fanno fallire il lavoro e puliscono gli output privati. Aggiornamento,cancellazione e inferenza condividono un lock;gli aggiornamenti concorrenti non sostituiscono il modello caricato. Cancellazione usa uno stato sincronizzato;il percorso numerico/chunk/overlap-add resta quello esistente.
6. La ricevuta offline è valida nel dominio della versione firmata dell’app e dell’intervallo della revisione. Le nuove revisioni dell’app e le scadenze possono invalidarla. Il server non firma queste autorizzazioni e non viene promessa una revoca online istantanea durante uso offline. Il software non confina un OS jailbroken,un builder ostile o codice esterno privilegiato. F5 e la prova su OS installati rimangono distinti.

Limiti dichiarati:registro≤256KiB/256selezioni,LICENSE/NOTICE≤1MiB ciascuna,singolo file modello≤2GiB,inventario≤8192file/8GiB. Questi sono limiti di verifica,non garanzie di memoria/qualità o di esecuzione di un checkpoint reale.

## Preparazione di un modello effettivamente revisionato

Conservare la revisione umana delle condizioni del checkpoint convertito esatto e di tutti i componenti. Inserire nel bundle i testi reali LICENSE/NOTICE e una voce completa nel registro,con gli hash dei byte effettivi e le date della revisione. Non usare le fixture dei test come un grant di produzione. Per nuove distribuzioni iOS la build verifica il registro prima di scaricare un eventuale modello di default;successivamente verifica il payload e ogni modello incluso. Un asset presente senza revisione corrispondente fa fallire la build invece di diventare automaticamente autorizzato.

La voce richiede:`id,stemCount,sourceFormat,sourceSHA256,licenseFile,licenseSHA256,noticeFile,noticeSHA256,authorizationBasis,reviewReference,reviewer,reviewedAt,expiresAt,localNoncommercialOnly`. ID ASCII chiuso,cardinalità2..64;formati supportati `mlmodel` e `mlmodelc`;solo `written_permission` o `verified_license`;riferimento HTTPS senza credenziali;epoche in secondi e revisione corrente. L’alias di bundle `demucs-default-4` corrisponde unicamente a `demucs-4`. Il formato sorgente e quello compilato non si scambiano automaticamente il permesso.

Verifica locale degli input di build,senza scaricare o approvare modelli:

```bash
python scripts/check_ios_model_rights.py --check-bundled
python scripts/check_ios_model_rights.py --model-id demucs-4 --stem-count 4 --source-format mlmodel --source /percorso/demucs-default-4.mlmodel
```

Il primo comando passa anche con registro vuoto e zero modelli:autorizza zero checkpoint,non un’inferenza. Il secondo richiede una revisione corrente e il payload esatto. La modalità CLI `--optional-model` serve soltanto a non scegliere un download non registrato;non permette di verificare un file senza revisione.

## Verifica corrente e blocco Apple

**90 casi locali distinti passati,41 nuovi;zero failure/error/skip correnti.** `validation/r210/ios-rights-result.json` contiene l’unione degli esiti più recenti e gli SHA degli XML. Comprende registro/evidenze/byte reali delle fixture,CLI eseguita davvero,conservazione dei file non revisionati,JSON duplicato/campi estranei,sorgenti/inventari alterati,gate del rapporto nativo e rifiuto di un precedente falso verde quando manca un input corrente. Le prove Python non eseguono Swift,Keychain o Core ML e non sono una prova di checkpoint neurali.

La prima esecuzione del censimento ha correttamente rifiutato il ledger non ancora aggiornato. La revisione ora conserva anche le occorrenze duplicate;il checker non è stato modificato.15 casi del censimento passano e l’ultimo caso sui byte correnti è verde. Inventario:551sorgenti/782punti. Nuovo processo classificato come diagnostica esplicita dell’operatore,non lavoro utente o uso fatturabile.

Ruff completo app/native/tests/scripts e compilazione Python passano. La grammatica Swift0.7.4 con tree-sitter0.25.2 non introduce nuovi flag nei6sorgenti ispezionati. Sono conservati6flag della grammatica sulle stesse righe originali `Result<Void>.success(())`;non è un verdetto del compilatore. Il primo runtime tree-sitter0.26.0 ha avuto un crash dello strumento,non conteggiato come prova riuscita o errore del prodotto. Questi strumenti restano fuori dalle dipendenze di produzione.

**Swift e Xcode non sono disponibili qui.** Il comando nativo ha restituito exit2 e `accepted:false,status:blocked,passed:0,skipped:0` in `validation/r210/ios-rights-target/acceptance.json`,vincolato ai sorgenti correnti. Non esiste una nuova compilazione iOS,una prova Keychain o un’inferenza Core ML riuscita in questo checkpoint.

È pronto un unico workflow manuale,default-off,**Optional iOS model rights**,file `.github/workflows/ios-model-rights.yml`. Dopo il commit dell’utente eseguirlo con **`ios_model_rights=true`**. Nessuna necessità di ripetere prima la fullCI invariata per questa sola prova. Il runner compila ed esegue la classe di policy realmente distribuita con32 controlli Swift/CryptoKit/Security,incluso un servizio Keychain isolato di test,poi compila l’app iOS reale senza firma. Non scarica checkpoint neurali,non pubblica app e non usa credenziali di signing/server/provider.

Accettare il rapporto soltanto con `accepted:true,status:passed,passed:32,skipped:0,native_sdk_tests_executed:true,ios_app_compiled:true` e hash dei sorgenti correnti. Il driver richiede tutte le32 identità esatte,zero sostituzioni,zero duplicati e zero skip;un errore di compilazione o Keychain resta fallimento. La compilazione iOS non è una prova di inferenza su dispositivo fisico o di F5/F6. Il rapporto lascia `full_F4_accepted:false`;quel prerequisito non promuove automaticamente l’intero F4.

## Riuso e residui originali

**Tutti i304 sorgenti app sono byte-identici al cumulativo in ingresso.** Si riusano la review Bandit165finding(0HIGH/21MEDIUM/144LOW),i170 confini C2,i30siti HTTP/21file e le prove di finanza,web/Chromium,F3 e7 casi ONNX reali invariati. I7 vecchi skip opzionali restano aperti. I4 checker,le soglie,ignore e suppressioni sono invariati. La modifica del workflow standard riguarda soltanto l’ammissione degli asset Core ML alla build,senza allentare gli altri gate. Il nuovo workflow Apple non è stato avviato. La fullCI40584085026 resta riferita alla baseline4c3,non al nuovo delta.

Restano14 criteri:A4,A5,B2,C3,C5,C6,D6,F4,F6 di implementazione/diritti e A6,B6,F5,G5,G6 sul target. F4 ha ora questo contratto iOS in codice con accettazione SDK pendente;rimane anche l’accettazione completa degli altri confini nativi/opachi/dinamici. Le basi economiche legacy e la riconciliazione generale non sono risolte. Non classificare ogni residuo come blocco esterno. RC e transizione finanziaria globale restano disabilitate.

Riprendere da questo documento e dai risultati correnti. Non ricostruire il contratto iOS,la DSP/diritti Demucs precedenti,il collector o la finanza già validata. Al prossimo commit eseguire la sola nuova prova Apple;continuare indipendentemente l’accettazione residua F4 e le basi economiche originali. Non usare il numero di test o il registro vuoto per far salire il punteggio.

## Consegna e riferimenti

Cumulativo unico:**MTA-0.3.0-r210-pre-RC-ios-rights-cumulative.zip**,SHA256 adiacente. Conserva tutti i4772file di ingresso e631log originali byte per byte,asset,licenze,manuali e modi/metadati ZIP;manifest completo aggiornato. Nessun modello,runtime,credenziale,DB o cache aggiunto. Nessun commit/staging/push/tag/release,dispatchCI o modifica di GitHub/server/provider reali.

Riferimenti primari usati per le API:[Keychain ThisDeviceOnly](https://developer.apple.com/documentation/security/ksecattraccessibleafterfirstunlockthisdeviceonly),[MLModel e uso serializzato](https://developer.apple.com/documentation/coreml/mlmodel),[compilazione del modello](https://developer.apple.com/documentation/coreml/mlmodel/compilemodel%28at%3A%29-6442s). L’attributo Keychain è configurato dal codice;la sua esecuzione reale è ancora nel gate Apple pendente.

Commit inglese cumulativo suggerito dalla baseline4c3,non eseguito:

`Complete execution safeguards, settlement recovery and native model rights`

## English handoff

Native iOS model selection,bootstrap/update,installation,cache,load and per-chunk execution now share a signed-app-bundle review contract. Exact source bytes and license/notice evidence precede compilation;a protected device Keychain receipt binds the compiled inventory. Mutable server metadata,old UserDefaults or file presence cannot grant rights. Replacement/rollback and inference share the model lock;expiry/review changes are rechecked before/after predictions and result delivery. Unreviewed files remain available for removal. The shipped review registry is empty and approves no real checkpoint:local Core ML is unavailable until genuine independent review enters a signed app build.

Current local proof:90 distinct Python/source/inventory passes,41new;not native SDK execution. All304 server app sources are identical,so unchanged finance/security/web/F3 evidence is reused. Apple acceptance is blocked with zero executed checks and zero passing skips. After the user commits,run **Optional iOS model rights**,input **ios_model_rights=true**. It requires32 actual named Swift/CryptoKit/Security checks,an isolated Keychain test and unsigned compilation of the actual iOS app,with current source hashes. This does not certify real neural inference,installed OS behavior or the whole original F4/F5/F6 criteria. Original progress stays28/42(66.7%),E1/7,RCfalse. No Git or real service action was performed.
