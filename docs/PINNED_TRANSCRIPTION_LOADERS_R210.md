# Loader MT3 vincolati a sorgenti e tensori — 30 ottobre 2026

MTA 0.3.0-r210, PRE-RC. Input `MTA-0.3.0-r210-pre-RC-work16-recovery-cumulative.zip`,100.821.410 byte,SHA-256 `2fc29bc50eb2c2633f978fe85821fefab51882367aed71fef31962c7d854c41c`. Ultimo commit dichiarato `4014a1fd5bfccc4e7f65c32345cb4c52f98f3d8d`; tutti i delta rights/adapter/guardian/recovery precedenti rimangono cumulativi. Nessun commit dichiarato nel frattempo.

## Cambiamento funzionale completo di questo blocco

YourMT3 noPS e MR-MT3 confrontano ora i sorgenti e l'identità dei tensori con un contratto fisso incluso nell'applicazione, non con hash scelti dal runtime stesso. Il contratto JSON è a sua volta vincolato a un digest nel codice distribuito. Le sue fonti sono gli inventari storici già conservati nel progetto:103 file sorgenti/notices YourMT3 e11 MR-MT3. I sorgenti YourMT3 corrispondono al manifest originale salvo i due adattamenti già prodotti dall'installer (model_helper.py e t5mod.py), il modulo compatibilità incluso e gli avvisi/licenze. Identità del codice e dei tensori non concedono nuovi diritti d'uso: la policy corrente resta obbligatoria e F6 resta distinta.

Prima della disponibilità del backend, il catalogo verifica il contratto sorgenti. La ricevuta non può riscrivere gli hash attesi, omettere file o aggiungere moduli Python/estensioni native negli import root ammessi. Link e alias non nascondono file estranei. La verifica evita di attraversare i grandi alberi delle dipendenze del virtualenv, che restano un confine distinto e ancora aperto.

Durante il lavoro, un loader importlib dedicato compila soltanto i byte verificati, ignorando le cache .pyc, incluse quelle con dimensione e timestamp contraffatti. Non eredita namespace upstream già presenti in sys.modules. Gestisce package ordinari, namespace package e import relativi; dopo il lavoro rimuove finder e moduli upstream caricati. Questo percorso appartiene al worker isolato che gestisce un modello: non è un'importazione concorrente condivisa tra richieste web.

I loader dei tensori ricevono una snapshot di byte verificati, evitando il controllo di un pathname seguito dalla sua riapertura da parte di safetensors. MR-MT3 carica i byte in CPU; YourMT3 conserva il successivo trasferimento esplicito al dispositivo scelto. La policy viene riletta per ogni forward e prima di restituire il risultato. Il percorso su GPU è coperto qui soltanto dal contratto di trasferimento con tensori sintetici, non da un collaudo GPU reale.

**La variante YourMT3 PS viene rifiutata**: manca nel progetto un'identità indipendente verificabile dei suoi tensori convertiti. Il flag tested e il digest dichiarato nella sua ricevuta non vengono promossi ad autorità. La variante noPS mantiene il suo contratto noto. Per riaprire PS occorre ricostruire/verificare indipendentemente i tensori dall'originale pinned, senza accettare il solo hash di un file fornito come ricevuta.

Anche il CLI `scripts/run_mrmt3_resumable.py` applica lo stesso contratto prima di creare output o avviare FFmpeg: richiede `MTA_STUDIO_MRMT3_RUNTIME` configurato e `--model` uguale al checkpoint originale `weights/model.safetensors` di quel runtime. Non accetta più un Safetensors arbitrario con sorgenti recuperati dal solo PYTHONPATH. Identità dei risultati riprendibili vincolata ai byte effettivamente caricati; rimangono i controlli per finestra e revoca durante decode.

Il caricamento da snapshot può richiedere più RAM del precedente mmap di safetensors; i nuovi loader neurali non sono stati misurati su modello completo in questo ambiente. Questa limitazione resta esplicita e impedisce di equiparare le prove di contratto a una nuova accettazione musicale o hardware.

## Verifiche

**789 test distinti passati,3 saltati,29 nuovi,zero failure/error correnti.** Rapporto `validation/r210/source-contract-all-final.xml`, identità e digest in `source-contract-result.json`. I3skip sono la prova opt-in con YourMT3 reale e due prove che richiedono Torch assente (conversione e token del CLI riprendibile). Le fixture dei nuovi import e dei tensori sono dichiaratamente sintetiche; le importazioni Python, le cache .pyc, le sostituzioni filesystem e i percorsi API/token/SQLite sono reali. Le quattro prove API YourMT3/MR-MT3 JSON/upload rifiutano ricevute riscritte prima di avvio e ledger. Nessun nuovo modello scaricato o inferenza neurale eseguita.

La regressione copre anche diritti legacy,diretti/offline,modelli gestiti,checkpoint Basic Pitch,trasporto pull e guardian Linux. Ha individuato una vecchia aspettativa pre-B2 che pretendeva uno stato incerto anche dopo la prova kernel del guardian. Il test ora richiede espressamente prova kernel originale,CPU misurata,scope e claim chiusi; un elenco /proc vuoto non viene accettato come misura dell'albero. I log iniziali con quella failure sono conservati. Non è una modifica di soglie, soppressioni o opt-in.

Ruff completo passa. Bandit completo invariato:308 sorgenti/168 finding,0HIGH/21MEDIUM/147LOW,nessun nuovo finding o soppressione. Inventari source-bound:555 sorgenti/780 punti runtime,173 confini di ammissione,30 siti HTTP/21 file. Checker invariati; aggiornata la review dei sorgenti e degli spostamenti di funzione/linea.

## Avanzamento e blocchi esatti

**PRE-RC 29/42=69,0%,invariato; l'incremento percentuale richiesto non è ancora raggiunto.** La metrica originale conta criteri RC completi, non helper né test. Nessuna promozione di F4 e nessuna revisione di testi,pesi o denominatore. La percentuale globale delle funzionalità del prodotto non è misurata da questa checklist.

F4 rimane aperto: gli interpreti/runtime esterni selezionati automaticamente e le relative dipendenze non hanno ancora un contratto indipendente completo; inoltre il modello effettivamente eseguito dal backend ACE non è provato dalla sola identità del client locale. La verifica dei sorgenti upstream e delle loro ricevute non risolve questi confini. Non dichiarare quei problemi esterni o chiusi solo perché le nuove prove passano.

Restano A4,A5,A6,B6,C3,C5,C6,D6,F4,F5,F6,G5,G6. Proseguire i contratti runtime/ACE e la finanza generale/legacy; non ripetere questo blocco sorgenti/tensori né B2. Per la validazione neurale del nuovo caricamento mancano Torch,il runtime completo e il modello reale; per G5 mancano Docker/Podman/Kubernetes e la creazione di user namespace è rifiutata dal kernel dell'ambiente. Non sono esiti positivi né criteri riclassificati.

Cumulativo `MTA-0.3.0-r210-pre-RC-pinned-transcription-loaders-cumulative.zip`. Nessun commit/staging/push/tag,dispatch CI o intervento su server/provider. Messaggio cumulativo suggerito dopo4014a1f:

`Enforce model rights, pin transcription loaders and recover original worker state`
