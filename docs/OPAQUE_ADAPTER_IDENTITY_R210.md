# Identità degli adapter configurati — handoff MTA r210

30 ottobre 2026 · versione 0.3.0-r210 · PRE-RC.

Ripartenza dall'ultimo cumulativo allegato e dall'handoff `RESTORED_MODEL_RIGHTS_R210.md`, recuperato anche dall'ultima chat Work. **28/42 criteri originali verificati: 66,7%; macroarea E completa, RC=false. Nessuna promozione di F4, F5 o F6.** Questo blocco completa il rifiuto delle selezioni di script generici censite qui; non certifica l'identità di ogni interprete, libreria o runtime esterno.

## Baseline conservata

Ultimo commit esplicitamente confermato: `4014a1fd5bfccc4e7f65c32345cb4c52f98f3d8d`, tree `9cd308daa505ef7c01c743ef2b5ce7461f1cd488`. Il precedente handoff conserva la CI standard 40972934180 riuscita: Quality 7155 passati, 50 skip, copertura 76,71%, SAST e build verdi. Questa è prova storica della baseline, non del delta successivo.

Input effettivo: `MTA-0.3.0-r210-pre-RC-restored-rights-cumulative(1).zip`, 99.830.185 byte, SHA-256 `125b08ff10497d877f41198253d33e9a4bbf0494f289d69a0d2ca00306692f93`. CRC verificati, 4910 percorsi e 680 file `.log`; modi originali ripristinati. Tutti questi percorsi, asset, licenze e log originali restano nel nuovo cumulativo.

## Comportamento consegnato

Il registro per tipo e il resolver legacy ACE ammettono solo l'integrazione MTA installata per quella famiglia. Uno script eseguibile scelto dall'operatore, anche con nome o byte uguali a un adapter, non ottiene una delega per caricare modelli arbitrari. Sono rifiutati anche adapter di un'altra famiglia, alias attraverso symlink e plugin del registro con sole etichette o metering dichiarato. Un override esplicito non valido rimane indisponibile; non avvia automaticamente un altro motore. I nomi Studio riservati non possono più essere ridefiniti dal registro delle estensioni.

La copia ACE gestita dalla GUI resta supportata solo nel percorso gestito e con tutti i moduli sibling distribuiti identici agli originali; una modifica, un modulo assente o un link rende il resolver indisponibile. Il file ACE incluso nei bundle può essere eseguito tramite Python anche senza bit Unix eseguibile, come già accade per l'adapter Studio: non viene concesso questo trattamento a script esterni.

Il vecchio launcher `app.ace_step_local --executable ...` nega ogni eseguibile opaco valido prima di creare la cache o avviare processi. Il consenso al download non costituisce un contratto del loader. Il backend di canto `neural-external` viene rifiutato dalla selezione della policy, dall'accesso diretto agli asset e dal renderer diretto prima di leggere lo score o produrre output. Il solo hash del checkpoint e il nome di una policy non provano che codice arbitrario carichi quel checkpoint. L'opzione generica è disabilitata nella UI bilingue; la sua variabile executable da sola non pubblicizza più la disponibilità del canto. OddVoices e il bridge DiffSinger supportato conservano i propri controlli separati su voce, vocoder e componenti.

## Migrazione delle configurazioni

| Configurazione precedente | Operazione richiesta |
|---|---|
| `MTA_AI_WORKER_<KIND>_EXECUTABLE` verso script generico o copia esterna | Usare l'adapter MTA installato della famiglia, oppure rimuovere l'override e usare l'opt-in supportato già esistente. Lo script personale resta conservato ma indisponibile. |
| Registro estensioni con kind Studio incorporato | Rimuovere quella ridefinizione. Usare le variabili per il tipo incorporato con l'adapter Studio originale e il runtime già revisionato. |
| Estensione con nuovo kind ed eseguibile arbitrario | Il nome resta censito ma non è eseguibile finché non esiste un'integrazione del loader revisionata nel codice. Non basta aggiungere un hash o un flag. |
| `ace_step_local --executable ...` | Usare l'installazione Local ACE-Step gestita nell'app nativa oppure l'adapter HTTP MTA distribuito verso il servizio installato separatamente, con gli stessi limiti di regime e diritti remoti precedenti. |
| Canto `neural-external` | Selezionare il bridge DiffSinger con voce/componenti revisionati, oppure OddVoices. I vecchi dati restano leggibili ma non autorizzano esecuzione generica. |

Nessuna configurazione, policy o installazione reale dell'utente è stata modificata automaticamente. Nessuna nuova autorizzazione dei modelli o del servizio commerciale.

## Prove correnti e riuso

**905 casi distinti correnti passati, 101 nuovi, 6 skip espliciti, zero failure/error correnti.** Ultimo esito per identità JUnit, senza sommare ripetizioni. I 101 nuovi casi sono nel modulo `tests/test_r210_opaque_adapter_identity.py`. La matrice completa, i file eseguiti e gli hash sono in `docs/validation/r210/adapter-identity-result.json`.

Le prove usano i resolver di produzione non sostituiti per i rifiuti: tutti i 18 tipi incorporati, adapter corretti e di altra famiglia, plugin e nomi riservati, copie/link, copia ACE completa/alterata, CLI reale e renderer diretto. **36 richieste token reali**, JSON e upload valido per i 18 tipi, prima autorizzano esplicitamente i soli byte sintetici della fixture e poi verificano il rifiuto dell'eseguibile: zero avvii e zero righe nel ledger. Questo distingue il nuovo controllo dal solo rifiuto dei permessi.

I test di processo, accounting, replay, cancellazione e HTTPS preesistenti usano writer sintetici tramite dependency injection confinata ai test. Non esiste un flag di bypass nel prodotto; queste prove non vengono presentate come inferenza neurale. I positivi degli adapter incorporati e i test dei bridge supportati restano verdi. Le sei prove saltate richiedono quattro volte il modello/runtime revisionato per HTTPS F3, un runtime YourMT3 reale e una libreria Torch assente. I prerequisiti non sono stati scaricati e non diventano accettazione.

Ruff completo e sintassi JavaScript passano. Gate sorgenti e checker invariati: Bandit **305 sorgenti / 163 finding (0 HIGH, 21 MEDIUM, 142 LOW)**, C2 **169 confini**, inventario runtime **552 sorgenti / 781 punti**, HTTP **30 siti / 21 file**. Due finding e un confine di processo sono stati rimossi perché il launcher ACE non importa né avvia più subprocess; sei identità spostate sono state riesaminate. Nessuna soglia, soppressione o controllo indebolito. Il nuovo scan corrente è conservato.

Prove finanziarie e UI non interessata, loader F3, accounting FFmpeg e sorgenti native/mobile sono riusate solo per le parti byte-identiche. I 13 hash della prova Apple precedente rimangono invariati: nessun nuovo run iOS. La UI modificata contiene solo l'opzione generica disabilitata, verificata con sintassi JS e regressioni di invio/routing del canto; nessuna nuova certificazione visiva o installazione nativa.

## Residui originali e prossima ripresa

Restano aperti **A4,A5,A6,B2,B6,C3,C5,C6,D6,F4,F5,F6,G5,G6**. Il lavoro residuo non è tutto esterno. In particolare questo filtro del registro non certifica `worker_python`, ambienti Python configurati, librerie importate dinamicamente o script dei runtime upstream come Mega53/DiffSinger. Il percorso MTA fisso collega il tipo all'integrazione supportata, non prova universalmente i byte effettivamente caricati da qualsiasi codice esterno. La macchina e il codice MTA installato restano nel confine di fiducia dell'operatore; non è una sandbox contro chi li può modificare.

Prossima macroarea F4: vincolare interprete/runtime upstream/loader/checkpoint per ciascuna integrazione ancora configurabile, partendo da `worker_python`, runtime ACE gestito e root upstream Mega53/DiffSinger; verificare il caricamento effettivo e il rifiuto di sostituzioni. Non riaprire i rifiuti del registro/launcher generico/canto generico qui chiusi né trasformare i positivi sintetici in diritti reali. F5 richiede i sistemi installati e F6 la revisione indipendente; finanza globale/legacy e prove kernel/host/hardware restano separati.

Riprendere dal nuovo cumulativo `MTA-0.3.0-r210-pre-RC-adapter-identity-cumulative.zip`. Usare il JSON di esiti e il manifest di preservazione; rieseguire soltanto i confini modificati. Dopo il commit dell'utente verificare Quality/SAST standard. Nessun commit/staging/push/tag/release, dispatch CI, server/provider reale o download modelli effettuato. Non serve una nuova full CI o un run Apple per i byte invariati.

Commit suggerito, cumulativo dopo `4014a1f`:

`Enforce reviewed model rights and reject opaque inference adapters`

## English handoff

Continue from the attached restored-rights cumulative and the recovered latest Work handoff. Confirmed baseline remains4014a1f; historical standard CI40972934180 is green, not validation of this later delta. Input SHA256125b08ff10497d877f41198253d33e9a4bbf0494f289d69a0d2ca00306692f93,4910 entries/680 logs are retained with original ZIP metadata.

Fixed adapter-to-kind resolution now rejects arbitrary configured scripts, copies, wrong-family adapters, extension labels and reserved Studio redefinitions. The managed ACE copy must match every shipped sibling. The opaque ACE compatibility launcher and generic neural singer deny before effects, including with download consent or a pinned checkpoint. Built-in Studio/ACE scripts remain usable through Python in read-only bundles. The generic singing UI option is disabled; supported DiffSinger/OddVoices integration tests remain passing.

905 distinct latest passing cases,101 new,6 explicit prerequisite skips,zero current failures/errors.36 real authenticated API denials cover18 kinds and two valid transports with authorized synthetic permissions,zero executions and zero ledger. Positive synthetic process/ledger fixtures use test-only dependency injection,not a production bypass or neural certification. Source-bound gates and Ruff pass without checker/threshold/suppression changes. Current Bandit305/163(0HIGH,21MEDIUM,142LOW),C2169,runtime552/781,HTTP30/21.

Progress remains28/42,66.7%,E complete,RCfalse. F4 is incomplete for configured Python interpreters,upstream code roots,dynamic loaders and actual checkpoint binding;F5/F6 and the other original residual criteria remain separate. Next address interpreter/upstream-runtime identity rather than repeating this denial block. All user commits and remote actions remain deferred;after the user commits,check standard Quality/SAST only for this delta.
