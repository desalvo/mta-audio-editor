# MTA 0.3.0-r210 — Identificativi checkpoint e ammissione originale

29 ottobre 2026, Europe/Rome. **PRE-RC:28/42 criteri originali(66,7%),E completa1/7. Nessun criterio promosso;l’aumento numerico richiesto non è raggiunto.** Completato il percorso dei selettori dei tre motori qui descritti;non è tutta F4 né una revisione indipendente dei pesi F6. RC falsa.

Baseline confermata:`4c3c73afe6d3829aad155c23f5f1bbb6d375433a`;commit differito all’utente. Ingresso completo:`MTA-0.3.0-r210-pre-RC-executor-rights-cumulative.zip`,SHA256 `ddd9f6debd0f32e2923f70250e661771b647bbf0eeb8d3f7ad30622dbf4db09a`,4724 file. Nessun ripristino vecchio,commit,staging,push,tag,dispatch CI o azione su GitHub/server/provider reali. Conservati tutti i delta precedenti:esecuzione,amministrazione,F3,merchant,settlement e componenti offline.

## Difetto chiuso

Autorizzare un motore non autorizza qualsiasi checkpoint passato al suo caricatore. La precedente `evaluate` poteva approvare la classe Whisper con un percorso locale nel piano,SAM con un repository estraneo o Demucs con un nome arbitrario. Per SAM il controllo del piano esplicito non copriva allo stesso modo il default di ambiente;il CLI diretto ammetteva qualsiasi valore `--model`. I tre casi sono riprodotti sul corpo originale della funzione,dallo ZIP esatto,in `validation/r210/selector-baseline-repro.json`. La riproduzione usa soltanto policy reale locale e selettori sintetici,senza caricare pesi.

Ora il controllo avviene nel dominio `evaluate`,prima dell’ammissione nella coda/ledger,e viene ripetuto agli ingressi dei caricamenti diretti. Non si adotta un modello diverso quando il valore non è ammesso. Le API originali con token,JSON e WAV,restituiscono400 per i tre selettori estranei;non parte il worker e non viene creata una riga `ai_compute_jobs`. Le normali ricevute/idempotenza del protocollo mantengono le proprie regole:questa non è una dichiarazione che ogni forma di journal sia assente.

## Identificativi e compatibilità

| Motore | Selezione corrente |
| --- | --- |
| Whisper |14 nomi della dipendenza di produzione20250625,inclusi i nomi `.en`,gli alias `large` e `large-v3-turbo` e tutti i7 nomi della UI attuale. Percorsi locali,URL e nomi estranei rifiutati. |
| SAM Audio |I3 checkpoint `sam-audio-small`,`sam-audio-base`,`sam-audio-large`,nelle forme brevi o `facebook/…`;il caricatore riceve la forma canonica. Anche `MTA_AI_SAM_MODEL` segue lo stesso controllo. |
| Demucs |Gli11 profili già dichiarati in `OFFICIAL_DEMUCS_MODELS`;valori e metadati originali invariati. Il model updater importa lo stesso registro,senza seconda copia divergente. |

La lista Whisper è verificata sul sorgente primario della release già fissata in `requirements-lyrics.txt`: [Whisper v20250625](https://github.com/openai/whisper/blob/v20250625/whisper/__init__.py). URL,hash SHA256 del sorgente e14 nomi sono in `validation/r210/selector-whisper-source.json`. Nessun sorgente upstream viene eseguito o aggiunto come runtime. Dipendenze e versioni di produzione non cambiano.

Il default Whisper `MTA_LYRICS_WHISPER_MODEL` usa ora lo stesso resolver nel percorso diretto e in quello unificato:prima quest’ultimo selezionava sempre `turbo` quando il piano non conteneva `model`,anche con un default configurato diverso. La precedenza esplicita e gli alias supportati restano disponibili;valori non stringa sono rifiutati senza convertirli in nomi. Il default assente rimane `turbo`.

Il wrapper profilato Demucs richiede un solo nome esplicito `--name`/`-n`,preserva gli altri argomenti validi e ripristina `sys.argv` dopo il figlio. Nomi ripetuti,abbreviazioni ambigue e override di repository `--repo`/`-r`,incluse le forme concatenate,sono rifiutati prima di avviare profiling o codice upstream. Il percorso unificato MTA passa già un nome esplicito;non richiede una nuova configurazione.

## Migrazione operativa — IT/EN

Le normali selezioni della UI e i profili dichiarati non richiedono modifiche. Nei CLI SAM si possono usare le forme brevi pubblicate o quelle `facebook/…`. Per diagnostiche Demucs manuali indicare esattamente un modello dichiarato,per esempio `--name htdemucs`;gli override di repository non sono un modo per estendere il grant della classe Demucs. Per Whisper usare un nome della release supportata,non un file `.pt` locale o un URL.

Un modello personalizzato o un nuovo repository richiede un’integrazione e una revisione dedicate;non basta abilitare una policy generica del motore o alterare un’etichetta di catalogo. Non modificare il registro per aggirare un rifiuto. L’amministratore può ancora disabilitare i motori con la policy originale;questo aggiornamento non concede nuovi diritti. La disponibilità della classe SAM senza un target configurato non è una promessa di inferenza:il caricamento effettivo richiede un selettore valido.

EN:Normal declared UI selections are preserved. Engine authorization does not approve an arbitrary checkpoint file,repository or custom Demucs bag. Direct and configured defaults use the same closed selector rules. Use a supported Whisper name,one of the three canonical SAM models,and one explicit declared Demucs name. Unsupported selectors fail before inference;there is no automatic substitute model. Custom checkpoint support needs a separate reviewed integration.

## Prove correnti e riuso

**274 casi distinti passati,44 nuovi;zero failure,error o skip nella selezione corrente.** Provenienza per identità in `validation/r210/selector-boundaries-result.json`:i tentativi e le riesecuzioni non vengono sommati. La matrice attraversa policy/ambiente,ingressi diretti,parent con SQLite/coda,API con token nei due trasporti e wrapper di profiling. Tre selezioni valide mantengono il percorso del worker contabilizzato reale,con artefatti e ledger;il worker di queste prove è un eseguibile di fixture,non un modello neurale. I rifiuti verificano assenza di processo/ledger e di effetti cache/output/runtime pertinenti.

Gli XML iniziali conservano i fallimenti delle fixture:argomento iniziante con `--` passato come opzione anziché valore,vecchi nomi sintetici `id`/`m`,controllo lessicale di un default ora condiviso e import di un encoder inesistente nei sei nuovi casi API. Sono corretti nelle fixture senza rendere permissiva la produzione;tutti gli stessi casi hanno esito finale positivo. La vecchia verifica lessicale del default è sostituita da asserzioni sul default e sull’override effettivi.

Ruff completo app/native/tests/scripts e compilazione passano. Bandit completo304 sorgenti/166 finding revisionati,0HIGH/21MEDIUM/145LOW;nessun nuovo finding,solo7 identità di riga riallocate/riesaminate nel perimetro modificato. I61 gate dei sorgenti passano con checker,soglie,soppressioni e ignore invariati. Inventari:171confiniC2,30sitiHTTP/21file,548sorgenti runtime/783punti. Nessun nuovo processo o trasporto.

I tre sorgenti vincolati al contratto del caricatore BasicPitch e la sua decisione di policy sono identici al checkpoint precedente;anche gli11 valori Demucs sono confrontati con l’ingresso. Prova:`selector-unchanged-proof.json`. Si riusano quindi le7 prove ONNX/HTTPS/progetto precedenti per quel perimetro,senza dichiararle rieseguite o contarle nei274 casi. UI/Chromium/axe,finanza,hardware e fullCI invariate non sono ripetute. La fullCI40584085026 rimane la prova della baseline4c3;nessuna nuova CI cumulativa dichiarata. I7 skip opzionali del checkpoint precedente restano aperti e non diventano passati.

Gitleaks8.24.3 esamina il delta testuale finale,incluso il manifest:zero finding,configurazione invariata. Runtime,modelli,credenziali,cache e database di test non sono inclusi.

## Residui e ripresa

Questo è controllo del selettore,non attestation dei byte caricati né concessione dei loro diritti. Un nome pubblicato non certifica la copia installata,un repository mutabile o librerie native arbitrarie. F6 resta la revisione indipendente dei checkpoint effettivi. F4 resta aperto per l’accettazione completa di ogni percorso legacy/nativo/opaco e runtime dinamico;non promuoverlo da questo sottoinsieme. Mancano anche implementazioni/prove generali,non soltanto prerequisiti esterni.

Restano14 criteri originali: A4,A5,B2,C3,C5,C6,D6,F4,F6 di implementazione/diritti e A6,B6,F5,G5,G6 sul target. Finanza generale,basi legacy,cgroup quiescente e cutover completo non sono chiusi da questi selettori. Nessuna formulazione,peso o stato originale è cambiato. Non ripetere i selettori di questo documento,gli ingressi diretti,il collector o il settlement già completati. Proseguire sulla successiva lacuna originale con una prova end-to-end effettiva;non usare numero di test o sotto-profili per far salire artificialmente il punteggio.

## Consegna

MTA-0.3.0-r210-pre-RC-model-selectors-cumulative.zip contiene tutti i4724 file di ingresso,asset,manuali,licenze e log byte per byte,con modi e attributi ZIP originali. Manifest completo e preservazione inclusi. Non è una release o una RC.

Commit inglese cumulativo suggerito,non eseguito:

`Complete execution safeguards, administration, settlement recovery and checkpoint admission`
