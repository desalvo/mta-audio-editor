**Formato aggiuntivo r210:** i bundle DiffSinger possono dichiarare `format: openutau-onnx`, metadati vocoder separati (`vocoder_config`) e controlli `expression_defaults` con gli stessi hash/policy indipendenti. Il vecchio formato native rimane invariato. Il builder Qixuan conserva l’intera banca originale e il vocoder: [guida e limiti](R210_DIFFSINGER_DEEP_ACCEPTANCE_IT_EN.md).

# Managed neural Studio — 0.3.0-r210 / Asset neurali gestiti

## IT — Funzionamento

Questo cumulativo mantiene tutti i motori legacy e i lessici DiffSinger IT/EN/FR. Aggiunge il registro locale di asset neurali e vocoder, selezione per cantante, conversione RVC/Seed-VC, specialista piano Transkun, curve espressive, allineamento testo/score e ripresa per stadio. **La presenza dell'adattatore non certifica un checkpoint né autorizza la sua licenza.** I test con output di modello sostituiti da fixture sono esplicitamente dichiarati tali.

### Preparazione sul server o computer nativo

1. Installare il runtime originale del modello in un ambiente Python separato; fissare versioni/commit e conservare tutte le licenze. Acquisire solo checkpoint, vocoder, dizionari, cache ausiliarie e riferimenti vocali autorizzati per l'uso previsto. Il codice del motore non autorizza automaticamente i pesi o la voce. Anche configurazioni Python e checkpoint pickle possono eseguire codice: il pacchetto deve essere preparato dall'amministratore fidato.
2. Costruire una directory sorgente con runtime, checkpoint, config, profilo fonetico e avvisi; nessun percorso deve dipendere da download al momento dell'inferenza. Per Seed-VC includere la cache HF completa e tutti i modelli ausiliari. Per RVC includere RMVPE/HuBERT e, se usato, l'indice. Per Transkun includere runtime, config moduleconf e checkpoint della medesima architettura.
3. Scrivere un template JSON come descritto sotto. `files` nel template è un elenco esplicito di file/directory locali. Eseguire `python3 scripts/build_studio_bundle.py template.json sorgenti /percorso/esterno/bundle.zip`. Il builder copia i link interni come file regolari, rifiuta quelli che escono dalla directory sorgente, calcola hash e verifica nuovamente i byte mentre li scrive. Non scarica e non concede diritti.
4. In Impostazioni → Modelli Studio caricare lo ZIP e confermare la verifica delle licenze. L'installazione è in coda, annullabile, atomica e **disabilitata per default**. In alternativa: `python3 scripts/manage_studio_assets.py install bundle.zip --licenses-reviewed`. Limite: 4 GiB espansi, 10.000 file. Usare un ID nuovo per una nuova versione; non sovrascrivere un asset in uso.
5. Per ogni `policy_model`, impostare l'autorizzazione nella policy modelli già presente, con prove effettive dei diritti e modalità `free_only` oppure `cost_recovery` solo quando consentita. Viene applicata la condizione più restrittiva di tutti i componenti. Le nuove identità Seed-VC/RVC/Transkun sono bloccate finché non revisionate. La sola conferma del caricamento ZIP non abilita i modelli. Abilitare il pacchetto dopo la revisione; l'abilitazione ricontrolla tutti gli SHA-256.
6. Impostare l'interprete dedicato e il suo SHA-256: `MTA_DIFFSINGER_PYTHON`/`MTA_DIFFSINGER_PYTHON_SHA256`, `MTA_STUDIO_SEED_VC_PYTHON`/`MTA_STUDIO_SEED_VC_PYTHON_SHA256`, `MTA_STUDIO_RVC_PYTHON`/`MTA_STUDIO_RVC_PYTHON_SHA256`, `MTA_STUDIO_TRANSKUN_PYTHON`/`MTA_STUDIO_TRANSKUN_PYTHON_SHA256`. Per Transkun `MTA_STUDIO_TRANSKUN_DEVICE` ammette `cpu`, `cuda`, `mps` (ROCm usa l'API torch `cuda`). La selezione di un device non ne certifica il funzionamento.
7. Eseguire inferenza reale, riapertura progetto, esportazione e ascolto. Verificare pronuncia di ogni lingua e compatibilità di tutte le curve col checkpoint. Questi passaggi richiedono i propri asset/hardware e non sono stati simulati come collaudi superati.

Le app native condividono schema e interfaccia. Se l'operazione è instradata al server remoto, la lista degli asset viene ottenuta dal server tramite token HTTPS, senza ricaduta silenziosa sui modelli locali; l'ammissione e la misurazione sono eseguite dal server effettivo. La gestione locale dei pacchetti riguarda solo il computer su cui viene effettuata. Testi/curve voluminosi viaggiano nel corpo `mta-studio-request-1` (massimo 8 MiB inclusa la partitura), con opzioni tipizzate fino a 240 KiB e header piccoli; aggiornare entrambi i lati per questa estensione. I vecchi header conservano i limiti originali.

### Manifest `mta-studio-bundle-1`

Campi: `schema`, `id` (`[a-z][a-z0-9-]{0,63}`), `name`, `kind`, `languages`, `files`, `bindings`, `licenses`, `components`, `component_files`. Nel manifest finale `files` associa ogni percorso relativo a `{"bytes": N, "sha256": "64 caratteri esadecimali"}`. Sono vietati traversal, file non dichiarati, link ZIP e duplicati senza distinzione fra maiuscole/minuscole.

Ogni licenza è `{"policy_model":"id-policy","notice":"LICENSE.txt","evidence_url":"https://..."}`. L'avviso deve essere non vuoto e incluso negli hash. `components` associa ogni ruolo al relativo ID policy; `component_files` associa lo stesso ruolo all'elenco dei file coperti. Ogni file runtime/modello deve essere assegnato; si possono aggiungere ruoli per altre dipendenze. I ruoli non sostituiscono la verifica giuridica delle licenze e delle autorizzazioni vocali.

| kind | bindings obbligatori | ruoli minimi in components |
|---|---|---|
| diffsinger | runtime_root, acoustic, config, vocoder, phonemes, experiment | engine, acoustic, vocoder |
| vocoder | checkpoint | checkpoint |
| seed-vc | runtime_root, script, checkpoint, config, reference, hf_home | engine, acoustic, pitch_extractor, speaker_encoder, semantic_encoder, vocoder, reference_voice |
| rvc | runtime_root, script, checkpoint; index opzionale | engine, acoustic, pitch_extractor, semantic_encoder, voice_authorization |
| transkun | runtime_root, checkpoint, config | engine, checkpoint |

Le licenze dei componenti devono includere rispettivamente `seed-vc-assets`, `rvc-assets` o `transkun-assets` per quei backend. Si possono usare ulteriori ID distinti per le dipendenze; nessuna identità è ammessa senza autorizzazione esplicita nella policy.

Per DiffSinger `config` deve essere `runtime_root/checkpoints/experiment/config.yaml`, `acoustic` deve appartenere a quella directory e usare il nome supportato dal bridge OpenVPI (`model_ckpt_steps_N.ckpt`). `vocoder` deve essere all'interno del runtime e coincidere con `vocoder_ckpt` del config; anche la verifica del config rimane obbligatoria. Includere `runtime_root/scripts/infer.py`. Dichiarare inoltre `policies:{"singer":"id-acoustic","vocoder":"id-vocoder"}`, con identità distinte e coerenti con i ruoli acoustic/vocoder. Il registro vocoder consente installazione/verifica separata; per un'inferenza DiffSinger, il vocoder scelto deve essere incluso e dichiarato nel pacchetto esperimento, affinché il config non selezioni un checkpoint esterno non verificato.

Per banche multilingue `language_bindings` deve contenere un profilo per lingua, per esempio `{"it":{"phonemes":"profiles/it.json","lexicon":"lexicons/it.json"},"en":...,"fr":...}`. I file devono essere inclusi negli hash. Non inventare una corrispondenza tra IPA e fonemi di una banca: usare il formato revisionato documentato in `THREE_AREA_IMPLEMENTATION_R210_IT_EN.md`, con `bank_sha256` del checkpoint esatto, inventario, vocali e mappa IPA. I lessici manuali legacy restano utilizzabili.

Esempio minimo **solo strutturale, senza modelli né autorizzazione**, per un template vocoder:

```json
{
  "schema":"mta-studio-bundle-1", "id":"my-vocoder-v1", "name":"Reviewed vocoder",
  "kind":"vocoder", "languages":["en"], "files":["model.pt","LICENSE.txt"],
  "bindings":{"checkpoint":"model.pt"},
  "components":{"checkpoint":"my-vocoder-rights"},
  "component_files":{"checkpoint":["model.pt"]},
  "licenses":[{"policy_model":"my-vocoder-rights","notice":"LICENSE.txt","evidence_url":"https://example.org/actual-license"}]
}
```

### Uso vocale e rigenerazione

- Selezionare voci comuni o indipendenti per ogni traccia cantante. Testi e conteggi melismi indipendenti seguono gli ID sorgente, non l'ordine accidentale dell'interfaccia.
- Il testo completo usa eSpeak reale IT/EN/FR e la mappa revisionata della banca. Le sillabe sono ripartite usando i nuclei vocalici dichiarati. Il numero deve coincidere con le note; per legature/melismi indicare quante note appartengono a ciascuna sillaba. È un allineamento deterministico testo/score, non forced alignment appreso da audio.
- I preset controllano F0/vibrato/articolazione e dinamica esplicita. Le curve puntuali sono in millisecondi dall'inizio della regione: pitch, dinamica, energia, soffio, sonorità, tensione, formanti e velocità fonemi. Le curve di varianza arrivano realmente agli input OpenVPI; i checkpoint senza le rispettive embedding le rifiutano. La dinamica PCM è dichiarata DSP, non inferenza di espressività appresa.
- Le take salvate conservano parole, sillabe e ID note. Selezionare una parola/frase oppure una sillaba per impostare l'intervallo di una nuova take. La sillaba permette di modificare i fonemi per nota, verificati contro l'inventario hash della voce. Le note eliminate o fuori dalle clip producono un errore; nessun intervallo viene indovinato. Per take precedenti prive di questi metadati usare la normale selezione manuale di note/regione.
- La conversione lancia il CLI effettivo Seed-VC o RVC. È successiva alla sintesi reale; non viene sostituita da un pitch shifter. Seed-VC usa riferimento autorizzato, F0 condizionato e durata fissa; RVC usa speaker/pitch/RMVPE e indice solo se presente. Audio finito, durata e formato sono controllati prima di sostituire il file. Un errore conserva l'originale. Sono consentiti al massimo 250 ms di trim/padding, senza time stretching.
- Rete Python negata durante DiffSinger/Seed-VC/RVC/Transkun; cache ausiliarie assenti falliscono esplicitamente. L'audit hook integra i limiti del processo già presenti: non è una sandbox contro codice nativo malevolo fornito dall'amministratore.

### Trascrizione, recupero e limiti

Veloce seleziona Basic Pitch, YourMT3 o Transkun. Accurata riconcilia YourMT3/Basic Pitch e opzionalmente Transkun; Approfondita aggiunge Demucs per sorgenti e conserva identità/programmi ripetuti. Transkun è uno specialista piano, non un classificatore GM; viene usata l'API effettiva del modello per leggere WAV correttamente, conservando velocity e sustain MIDI. La presenza di piano in un mix va verificata.

Uno stadio senza note è un risultato esplicito `empty_reason: no-notes`, non una traccia muta inventata. Se tutte le ipotesi sono vuote il job termina senza creare tracce; l'importazione manuale viene rifiutata. Le sorgenti separate non contano come modelli indipendenti per aumentare la confidenza.

Veloce, Accurata e Approfondita salvano ogni stadio completato prima di confermare il risultato remoto. Un retry della stessa richiesta, proprietario e revisione può recuperarlo con SHA-256 del contenuto, piano, asset/runtime e policy coincidenti. Nessun secondo addebito del lavoro recuperato; i nuovi stadi restano misurati normalmente. Un file corrotto viene ricalcolato, uno stadio fallito non è memorizzato, un link è rifiutato. Il recupero non certifica né migliora la precisione.

YourMT3+ è una famiglia di varianti: non rinominare il checkpoint YourMT3/noPS esistente come un modello diverso. Google MT3, MR-MT3 e MT3-Infer rimangono alternative valutate/documentate, non backend pronti senza runtime/checkpoint/licenze compatibili. La pipeline e il formato gestiscono molte parti e programmi uguali, ma **non è garantita l'accuratezza su 10–16 strumenti**, né la separazione di esecutori con identico timbro in una singola sorgente. Queste sono misure da benchmark reale, non ottenibili aggiungendo tracce sintetiche.

GM: mantenere la selezione di soundfont autorizzati, canale 10, controller/tempo SMF 0/1, rendering WAV e mixer. L'audit corrente esercita FluidR3 con TinySoundFont e FluidSynth reali; ripeterlo per ogni banca personalizzata (`scripts/check_gm_soundfont.py --bank-id ID --output report.json`). L'audit di energia finita non sostituisce l'ascolto.

## EN — Operator and acceptance summary

All legacy engines and IT/EN/FR dictionaries remain. The new managed registry installs complete administrator-reviewed ZIP bundles, disabled by default, with exact file inventories, SHA-256 and separate component rights. No checkpoint, voicebank, auxiliary model, reference voice or SoundFont rights are inferred from the engine license. Prepare trusted upstream runtimes in dedicated environments; Python configs/pickle checkpoints can execute code. Declare the manifest fields, bindings and component roles in the table above. Include every dependency and license notice; use `build_studio_bundle.py` and `manage_studio_assets.py`, or the shared web/native administration UI. Set the dedicated interpreter paths and hashes listed above; activate only after genuine permission review.

DiffSinger banks are independently selectable per singer and language. Text alignment uses real eSpeak and a reviewed bank-specific inventory/IPA map. Exact syllable-to-note counts or explicit melisma counts are required. This is deterministic score alignment, not learned acoustic alignment. Point curves drive score F0 and supported OpenVPI embeddings; amplitude dynamics are explicitly DSP. Saved word/syllable regions retain note identities for partial new takes. Explicit syllable phones must belong to the selected bank's pinned inventory. Deleted/moved notes are rejected rather than guessed.

Seed-VC/RVC launch their actual model CLIs with pinned local assets. There is no simulated inference fallback. Conversion preserves timing within a bounded 250 ms trim/pad tolerance, validates finite audio, and leaves the original untouched on failure. Transkun uses the actual upstream piano model API, dedicated interpreter, matching checkpoint/config and real MIDI velocity/sustain. Offline Python guards deny automatic dependency downloads; they supplement process isolation and do not secure malicious administrator native code.

Fast mode selects Basic Pitch, YourMT3 or Transkun; Accurate combines actual model hypotheses; Deep separates sources with Demucs. All three transcription modes persist validated stage outputs before acknowledging remote success. Recovery requires matching source, request, model/runtime and policy fingerprints and does not bill recovered stages twice. No-note results complete without placeholder tracks. Same-program source identities remain separate; source stems never create extra model-confidence votes. Remote native workflows obtain the actual authenticated server catalog and never silently fall back locally.

Actual authorized DiffSinger/Seed-VC/RVC/Transkun checkpoint inference, each bank's pronunciation, ML dependencies/device support, browser/native acceptance, musical quality and 10–16-instrument accuracy remain explicit asset/hardware gates. Contract fixtures are not neural inference validation. GM has real FluidR3/FluidSynth/TinySoundFont software audits; custom banks and target-device listening require separate acceptance. See `DEVELOPMENT_STATUS.md` and validation reports for exact results and remaining failures.

## Primary implementation references

- OpenVPI DiffSinger: https://github.com/openvpi/DiffSinger — acoustic DS CLI and supported expression inputs; bank/runtime compatibility must be reviewed per pinned revision.
- Seed-VC: https://github.com/Plachtaa/seed-vc/blob/main/inference.py — source/target/checkpoint/config/F0 arguments; separately review every auxiliary model.
- RVC: https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/infer/cli.py — model/speaker/pitch/RMVPE/index arguments; separately review voice rights and auxiliary models.
- Transkun: https://github.com/Yujia-Yan/Transkun — model API and config/checkpoint pairing; adapter avoids its CLI's MP3-specific input loader.
- FluidSynth: https://www.fluidsynth.org/api/group__midi__messages.html — note-off may return failure when a one-shot/stolen voice no longer exists; validated release must be idempotent.

These links document integration contracts; they are not blanket license approvals or promises about future upstream revisions.
