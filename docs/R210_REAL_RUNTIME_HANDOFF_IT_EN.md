# r210 — Runtime reali e collaudi / Real runtimes and acceptance

Versione **0.3.0-r210**, 21 ottobre 2026. Questo stato sostituisce, per i controlli ripetuti qui, le precedenti note cronologiche. Nessun commit/push/tag/release o intervento sui server reali.

## Esito italiano

Sono state eseguite inferenze neurali reali CPU con **RVC, Seed-VC, Transkun e YourMT3**, usando checkpoint verificati e input tecnici autorizzati. Le fixture dei test unitari non vengono conteggiate come inferenze. **Non è certificata la chiusura completa delle tre macroaree:** il test reale YourMT3 sul mix di dieci programmi non raggiunge il target; manca una voicebank DiffSinger nativa completa e autorizzata; Chromium e trasporto Unix locale sono impediti dall'ambiente. Questi ultimi vincoli e la qualità del modello non sono tutti problemi di hardware.

| Area | Verificato qui | Limite residuo |
|---|---|---|
| RVC | Inference reale RMVPE/HuBERT, CPU, offline, WAV 48 kHz mono, 2,98 s | Campione GM sintetizzato, non canto registrato; qualità, latenza e consenso della voce scelta vanno collaudati |
| Seed-VC | Modello singing F0 44,1 kHz, Whisper **small**, BigVGAN 44k, CAMPPlus e RMVPE locali; caricamento rigoroso e vera diffusione | Cinque step CPU sono una verifica tecnica; la qualità del canto richiede campioni rappresentativi |
| Transkun | Pesi 2.0 reali e caricamento rigoroso; note 60, 64, 67 riconosciute sul piano GM | Non è un trascrittore multistrumento generale |
| YourMT3 | Installer completo, checksum, conversione sicura safetensors, inferenza con adapter MTA: piano corretto 60/64/67 | Mix tecnico dieci programmi: 5 parti, 7 note, solo 1 match con programma/pitch/tempi; F1 0,117647. Target dieci strumenti **non superato** |
| General MIDI | FluidR3 MIT reale; TinySoundFont C++; 128 programmi e 47 note di batteria con PCM valido; 23 test reali dedicati | FluidSynth condiviso assente; backend portabile non dichiara aftertouch; ascolto e dispositivi fisici da collaudare |
| UI | Flussi DOM effettivi HappyDOM e regressioni JavaScript | Chromium assente: il CDN restituisce HTML “Site Unavailable”, non un archivio. Nessun aggiramento o mirror |
| DiffSinger | Bridge, contratti e readiness check | Sorgenti soli: servono checkpoint acustico OpenVPI `.ckpt`, config flattened, vocoder compatibile, inventario/profilo fonetico e condizioni dei componenti/voce; nessuna autorizzazione inventata |

### Correzioni software di questo ciclo

- Il wrapper offline rimuove `app/` dal percorso d'importazione del runtime: `app/i18n.py` non oscura più il package `i18n` di RVC. Il blocco di rete resta attivo.
- Seed usa un runner dedicato che verifica **tutti i tensori attivi** prima del caricamento `strict=True`, anziché accettare il filtraggio silenzioso upstream. Il checkpoint ufficiale conserva dieci chiavi di layer storici inattivi; sono ammesse soltanto queste chiavi esatte, con output MLP presente. Posizioni e frequenze sono rigenerate soltanto nei due casi deterministici verificati. Parametri appresi mancanti/incompatibili e chiavi sconosciute causano errore. Il primo output upstream non rigoroso non è evidenza di accettazione. I successivi test reali sono eseguiti dal runner MTA protetto.
- Il runner Seed lascia headroom per il successivo resampling: applica, prima della quantizzazione, un unico guadagno lineare se necessario per mantenere il picco originale e quello proiettato dopo resampling entro 0,98, usando lo stesso filtro del bridge, e lo registra nel log. Conserva i rapporti tra campioni; non aggiunge hard clipping. BigVGAN applica già un clamp interno e il campione originale raggiungeva il fondo scala: questo guadagno non ripara quella saturazione del vocoder e non certifica il timbro. Metadati MTA dichiarano il ceiling.
- Ricetta CPU isolata riproducibile `requirements-studio-conversion-runtime.txt`: PyTorch/torchaudio 2.4 CPU, NumPy 1.26.4, contourpy 1.3.3, DAC e dipendenze risolte insieme. Non contaminare l'ambiente del server con il runtime upstream. `pip check` e freeze inclusi per i tre ambienti effettivamente usati.
- I test browser che richiedono realmente Chromium controllano la presenza dell'eseguibile; la sua assenza produce uno skip esplicito. Se l'eseguibile è presente, gli errori di avvio/runtime restano errori. Nessun test DOM o browser è dichiarato superato per sostituzione.

### Evidenze

Gli input audio sono sintesi GM reale della banca MIT: piano e synth vowel a 48 kHz, tre secondi. Il vowel è usato come sorgente e riferimento tecnico Seed; non imita una persona. Il mix di dieci programmi è generato dalla partitura MIDI inclusa, dieci note contemporanee, senza dataset registrato: reference e prediction restano separate e con hash. Non è un benchmark rappresentativo della musica commerciale, ma il suo insuccesso impedisce di promettere il riconoscimento affidabile di dieci strumenti.

`validation/r210-acceptance-*` contiene log reali, MIDI, WAV tecnici, metriche, ricevute hash e report. Le metriche del benchmark non sono una confidenza calibrata. Velocity 96 YourMT3 è generata, non stimata. Non sono inventati bend, CC o esecutori separati dello stesso programma.

L'archivio asset ricostruito resta **991.830.047 byte**, SHA-256 `7e2803bb0e8bd1b92815eb8ca1a147ed2c59c66889e4f04b878f4dbb6590fe15`; segmenti, archivio completo e CRC già verificati. Non viene incorporato nuovamente nel cumulativo sorgenti. Modelli, SoundFont, venv e cache di download non sono redistribuiti nel nuovo ZIP.

### Provenienza e licenze della verifica

- RVC: [Saisho Utane, pubblicazione dell'autore](https://huggingface.co/Saisho-Utane/Saisho-Model-RVC/tree/7a61b17e4f014fc5013a489f2b5cd3a7ee9e2b1a), CC BY 4.0. Modello SHA-256 `82312a29a3996a451aaa3d3776566cec85b47b5414fce53da82b2d66b04f3d35`. Attribuzione dei WAV derivati: **Voice model created by Saisho Utane (https://huggingface.co/Saisho-Utane), used under CC BY 4.0.**
- Seed: [Plachta/Seed-VC](https://huggingface.co/Plachta/Seed-VC/tree/257283f9f41585055e8f858fba4fd044e5caed6e), GPL-3.0; checkpoint F0 44k SHA-256 `42aef93ffe65857c840d270252fa040f7ba04514945ec460f3ac1ac2a96de684`. Il nome storico del file contiene “base”, ma la config ufficiale richiede **openai/whisper-small**. Le precedenti note “Whisper-base” sono superate.
- [NVIDIA BigVGAN 44k](https://huggingface.co/nvidia/bigvgan_v2_44khz_128band_512x), MIT; [OpenAI Whisper small](https://huggingface.co/openai/whisper-small), Apache-2.0; revisioni/hash nelle ricevute. HuBERT, RMVPE e CAMPPlus sono quelli forniti nel bundle verificato; la registrazione di un bundle operativo richiede comunque la revisione individuale dei relativi componenti.
- [YourMT3 originale dell'autore](https://huggingface.co/spaces/mimbres/YourMT3/tree/5e66c1ea173a8186e0d20432b841d3180cc015b5), Apache-2.0. Checkpoint originale verificato `ae38e415c79efd5592dcb9b658cdb99ddb11d4c4e1eaa364cab04a052473fc25`; conversione con `weights_only=True`, senza override pickle non sicuri. Avvisi e modifiche compatibilità conservati.
- FluidR3 GM SHA-256 `74594e8f4250680adf590507a306655a299935343583256f3b722c48a1bc1cb0`, [licenza MIT originale](https://sources.debian.org/src/fluid-soundfont/3.1-6/COPYING/). Attribuzione: Frank Wen, Copyright 2000–2002, 2008; testo incluso in `validation/r210-acceptance-FluidR3-COPYING.txt`.

Le prove dirette offline non registrano né autorizzano automaticamente bundle nel servizio commerciale. Restano valide le policy di ammissione esistenti. Nessun server reale viene modificato.

## English result

Real offline CPU inference ran with RVC, Seed-VC, Transkun and YourMT3; real licensed FluidR3/TinySoundFont synthesis covered all 128 programs and 47 standard drums. These are actual checkpoint executions, not unit fixtures. RVC namespace shadowing was fixed. Seed now checks every active tensor strictly and applies documented linear export headroom for subsequent resampling (this cannot undo BigVGAN’s own output clamp); the only checkpoint compatibility exceptions are explicit inactive legacy output keys and verified deterministic buffers. A clean isolated conversion dependency recipe and browser-binary capability checks are included.

**Full three-area completion is not certified.** YourMT3 correctly transcribed the three-note piano, but on the actual ten-program GM mixture it returned five parts/seven notes and only one exact instrument/pitch/timing match (F1 0.117647). This is a real model-quality limit, not a hardware-only gate. A representative recorded multitrack benchmark remains required; no extra parts or confidence were fabricated. DiffSinger still lacks an authorized complete native acoustic bank/vocoder/phonetic profile. Chromium download is unavailable in this environment, and Unix socket transport is forbidden. Physical devices, ASIO, VST hosts, GPU platforms and musical listening require target acceptance.

Version remains 0.3.0-r210. All earlier archive paths, legacy AI, VST SDK, sources, docs and tests are retained. No Git or production operations. Checkpoint weights and external runtimes are excluded from the cumulative source ZIP. The RVC voice attribution above applies to the generated RVC examples; the original FluidR3 MIT notice accompanies the technical audio examples. See the final general-regression counts below and the executable acceptance steps in `R210_TARGET_ACCEPTANCE_IT_EN.md`.

## Commit suggerito / Suggested commit

`docs/COMMIT_MESSAGE_R210.txt` contiene una sola riga cumulativa, comprendente i cicli precedenti e questa verifica. La base disponibile è l'ultima conferma utente del 19 ottobre 2026; lo SHA Git preciso non è presente negli archivi ricevuti, quindi non viene inventata una differenza Git esatta. Il file non esegue alcuna operazione Git.

## Regressione finale / Final regression

**4.596 passed, 0 failed, 0 errors, 80 skipped, 6 warnings**, uscita 0, 543,30 secondi; 4.676 casi totali. XML e log completi: `validation/r210-acceptance-general-final.xml` e `.log`. I 22 test mirati sui runner/checkpoint e i 23 test GM reali si sovrappongono alla suite generale: **non sommare** i conteggi. DOM HappyDOM: test effettivamente eseguito e incluso nella suite.

Gli 80 skip sono: 33 VST/SDK/plugin esterni, 26 browser, 10 trasporto Unix vietato dall'ambiente, 4 FluidSynth, 3 Basic Pitch/Deep, 1 voicebank, 1 opt-in YourMT3 non attivato nell'ambiente generale (inferenza reale eseguita separatamente nel proprio runtime), 1 dispositivo audio e 1 Win32. Elenco per caso: `validation/r210-acceptance-general-skips.json`. Nessuno skip equivale a un test superato.

Restano visibili sei avvisi: deprecazione Starlette/httpx, tre operation ID OpenAPI duplicati preesistenti e due ZIP volutamente duplicati in test negativi. Non sono stati soppressi. Il primo giro esteso è conservato: 4.595 pass, 11 errori dovuti esclusivamente al Chromium assente, 68 skip; non costituisce la regressione finale.

Final source changes passed Ruff and Python compilation. All three runtime environments passed `pip check`; exact freezes are included. No further functional changes were made after the final complete suite. This green software regression **does not override the failed real ten-program benchmark or certify the missing DiffSinger bank, browser, hardware or GPU paths**.
