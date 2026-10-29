Aggiornamento29 ottobre2026: nuovo controllo diritti diretto nell’adapter.5 prove F3/HTTPS reali e2 coda/progetto ONNX passano con i nuovi hash del caricatore. Profilo e perimetro F3 invariati. Leggere DIRECT_EXECUTOR_RIGHTS_R210.md;non riusare il vecchio hash sorgente come se fosse identico.

# MTA 0.3.0-r210 — Accettazione F3 e handoff

**28 ottobre 2026, Europe/Rome. PRE-RC: 28/42 criteri verificati (66,7%), prima 27/42 (64,3%).** E rimane l’unica macroarea completa (1/7). F3 conserva testo e peso originali: “Authenticated remote checkpoint identity and rights attestation”, peso 1. La RC non è raggiunta. Nessun commit, modifica a GitHub o intervento su server e provider reali.

La baseline committata confermata è `4c3c73afe6d3829aad155c23f5f1bbb6d375433a`. È stato ripristinato e verificato il cumulativo precedente `MTA-0.3.0-r210-pre-RC-admin-workflow-cumulative.zip`: SHA256 `48daae0638871a1ac01ebbec63b2ee11a6bbbae39520d0460b57773f9d4cfc26`, 98.171.354 byte, 4.609 file. SHA, CRC, manifest e modalità verificati. Il nuovo cumulativo include B5, drain, E4 e F3 nello stesso delta non committato. La full CI 40584085026 sul commit 4c3 resta valida per quella revisione; una nuova CI cumulativa non è stata eseguita.

## Contratto completato

Il profilo opt-in `MTA_PULL_MODEL_ATTESTATION=verified-pull-v1` completa il protocollo di identità e diritti per i checkpoint ammessi. Il solo checkpoint revisionato e supportato è **BasicPitch 0.4.0 ONNX**, SHA256 `2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec`. Gli altri motori sono rifiutati prima della creazione del ledger. I trasporti generici client, gateway e ACE sono rifiutati in entrambi i regimi quando questo profilo è attivo.

Il contratto comprende il grant revisionato dall’autorità, LICENSE e NOTICE della revisione upstream fissata, byte del modello, hash del codice di caricamento/verifica/ricevuta e runtime approvato. Il worker verifica indipendentemente contratto, documenti installati e runtime prima dell’inferenza. La sessione ONNX carica gli stessi byte verificati senza riaprire il percorso del checkpoint.

L’autorità congela il contratto con policy originale, job, owner, epoch di ammissione, nonce e istanza worker, hash del sorgente e del piano. La ricevuta successiva al caricamento include PID effettivamente misurato, modello, diritti e runtime. Il worker si autentica con la credenziale originale attraverso HTTPS con verifica CA. Ricevuta e hash del risultato entrano nella prova immutabile di completamento. Sostituzioni, revoche, claim errati e prove mancanti impediscono pubblicazione e chiusura economica. La perdita del contratto originale non consente il downgrade a un job legacy, né sul worker né sull’autorità.

Anche un’esecuzione fallita con CPU positiva richiede la ricevuta originale prima della chiusura economica. Se la prova manca o la discendenza del processo è incerta, l’assegnazione originale resta aperta: nessuna misura zero inventata e nessuna riesecuzione automatica. Un completamento già congelato viene riconfermato senza ricaricare il modello o duplicare il ledger. Il pilot v1 conserva la compatibilità precedente e non acquisisce un’autorizzazione commerciale.

**Confine di fiducia:** sono attestazioni autenticate di worker installati e controllati dall’operatore. Non sono attestation hardware/TEE o confinamento di host ostili. Il supporto si limita al checkpoint fissato; F4, F5 e F6 rimangono aperti. Una nuova famiglia richiede codice di caricamento, revisione del grant e prove nuove. Il default `off` e i percorsi di compatibilità non sono certificati dal nuovo profilo.

## Configurazione riproducibile

Autorità e nodi devono usare lo stesso build e impostare esplicitamente `MTA_PULL_MODEL_ATTESTATION=verified-pull-v1`. L’autorità usa `MTA_AI_EXECUTION_MODE=pull`. Registrare soltanto `audio-to-midi-basic-pitch` sui nodi abilitati, mantenendo credenziali, CA e normale enablement del registro worker. Configurare l’adapter fisso `app/ai_studio_adapter.py` e l’interprete assoluto con `MTA_AI_WORKER_AUDIO_TO_MIDI_BASIC_PITCH_PYTHON`. Nessuna configurazione reale è stata modificata.

Il runtime richiesto è basic-pitch 0.4.0 / onnxruntime 1.23.2, con LICENSE e NOTICE originali presenti nella distribuzione. Il codice vincola i loro hash e la revisione upstream `9991303bba609a3b93089d13ec80d1d495083596`. Eseguire il self-test dell’adapter nell’ambiente isolato prima di abilitare un nodo.

I test reali sono opt-in:

```bash
MTA_TEST_OFFLINE=1 MTA_STUDIO_PYTHON=/percorso/assoluto/python python -m pytest -q tests/test_r210_reviewed_checkpoint.py tests/test_r210_pull_model_attestation_real.py
```

L’interprete modello può essere separato dal worker applicativo e deve contenere le dipendenze dell’adapter. Le prove correnti usano Python 3.12, librosa 0.11.0, resampy 0.4.2, setuptools 80.9.0 e ONNX CPU. **Limite di packaging:** i metadata upstream BasicPitch su Python 3.12 richiedono anche TensorFlow, omesso nell’ambiente esplicitamente ONNX-only. Non si dichiara `pip check` pulito o certificazione dell’intero ambiente opzionale. Requisiti e dipendenze di produzione invariati; F5/G6 e packaging dei target restano separati. Modello e runtime non sono inclusi nel cumulativo.

## Difetti corretti

Il limite interno del trasporto pull di 16 MiB era rifiutato dal validatore della configurazione pubblica da 64–8192 MiB. Il parser dell’envelope worker ammette ora esattamente il limite interno di 16 MiB; minimo pubblico e rifiuto dei valori intermedi o malformati restano invariati. Nessun limite è stato alzato.

Il decoder generico upstream/librosa sondava AudioToolbox con GCC e FFmpeg anche per WAV privati. Il metering rilevava correttamente i processi discendenti e conservava il claim incerto. Il decoder WAV usa ora SoundFile e resampling esplicito, conservando padding e finestre di BasicPitch 0.4.0, pesi e inferenza originali. Il generatore upstream viene sostituito soltanto nel processo dedicato e ripristinato al termine; non sono state introdotte eccezioni al metering.

Sono stati corretti anche i tentativi di adozione di un job privo del contratto originale e la fixture della risposta persa: il primo client fallisce dopo il commit remoto, il successivo riconferma il completamento originale. I tentativi falliti restano nei report storici; la selezione finale completa è passata. Una credenziale sintetica scaduta è stata oscurata soltanto nella nuova diagnostica fallita, senza alterare esiti o log originali.

## Evidenza e accettazione

`validation/r210/reviewed-checkpoint-acceptance.json` contiene **246 casi distinti passati, zero fallimenti/errori/skip correnti, 55 casi nuovi**. Nessuna somma delle riesecuzioni:

- `reviewed-checkpoint-current.xml`: 185 passati. Comprende sostituzioni, revoca, perdita del contratto originale, fallimenti con CPU, rifiuto dei motori non revisionati e dei trasporti generici, compatibilità pilot e prove reali.
- `reviewed-checkpoint-gates.xml`: 61 passati sui controlli di revisione sorgenti, sicurezza, ammissione, trasporti ed esecuzione.

In totale cinque prove con modello reale: quattro usano processi worker indipendenti e HTTPS con verifica CA, nei regimi COMMERCIAL/NON_COMMERCIAL, con e senza perdita della risposta finale. L’inferenza sulla sinusoide generata produce la nota MIDI 69 attesa. Il replay conserva PID, ricevuta e risultato senza riesecuzione; worker e autorità non condividono SQLite.

F3 è accettato per il protocollo verificato: identità, grant e caricamento prima dell’inferenza, ricevuta autenticata legata al lavoro originale e rifiuto dei trasporti alternativi nel profilo. F4 riguarda ancora esecutori e bypass opachi; F6 richiede la revisione indipendente degli altri checkpoint opzionali. Gli inventari statici continuano correttamente a non certificare l’attestation: non sono stati indeboliti per accettare il protocollo.

Ruff e compilazione passano. Bandit: 300 sorgenti e 164 finding revisionati invariati (0 HIGH, 21 MEDIUM, 143 LOW); ammissione C2: 170 confini; trasporti: 30 siti in 21 file; runtime: 541 sorgenti e 780 punti. Nessuna soppressione, checker o soglia allentata e nessun nuovo sito di rete. Le prove E4/Chromium e full CI invariate sono conservate senza riesecuzione.

Fonti primarie confrontate: repository Spotify BasicPitch alla revisione fissata, LICENSE e NOTICE identici ai file della distribuzione 0.4.0; MANIFEST.in include i modelli distribuiti. Licenza e attribuzione sono in `licenses/basic-pitch-0.4.0/`. La verifica riguarda il grant pubblicato e i byte supportati, senza estenderla a dati di addestramento, output musicali o modelli di terzi.

## Ripresa e consegna

Restano 14 criteri originali: nove di implementazione/diritti (A4, A5, B2, C3, C5, C6, D6, F4, F6) e cinque di target/ambiente (A6, B6, F5, G5, G6). La prossima priorità è C3, poi C5/D6, riutilizzando C2 ed E. Storico globale PayPal, payout/protection e quota/surplus legacy richiedono ancora prove originali: non si ricostruiscono dai prezzi attuali. Nessuna RC o transizione finanziaria generale dichiarata pronta.

Unico cumulativo completo: **MTA-0.3.0-r210-pre-RC-reviewed-checkpoint-cumulative.zip**, checksum adiacente e questo handoff. Conserva tutti i 4.609 percorsi di ingresso, asset, manuali, licenze, modalità e attributi ZIP; tutti i 616 log originali sono byte-identici. Il manifest corrente vincola ogni file incluso. Commit ancora differito.

Commit cumulativo inglese suggerito dopo l’ultimo commit confermato 4c3, non eseguito:

`Complete execution ownership, guarded administration and reviewed remote checkpoints`
