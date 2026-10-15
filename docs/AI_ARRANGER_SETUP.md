## r178

Queued musical constraints are defensively copied to avoid mutable request state leaking into jobs. This remains an in-memory planning queue; persistent workers and generation are not enabled.

## r177 job planning

Create POST `/api/projects/{pid}/ai-arranger/jobs`, poll GET `/api/projects/{pid}/ai-jobs/{job_id}`, cancel POST `/api/projects/{pid}/ai-jobs/{job_id}/cancel`. Owner-scoped, per-process, bounded and non-durable; jobs remain `planned`, never report generated audio. A GPU inference worker and durable storage are prerequisites for processing.

# AI Arranger / Riarrangiatore AI — MTA Audio Editor r174

## English
The first stage exposes **read-only, non-destructive planning**, not actual music synthesis. The current adapters are catalog descriptors only. No external model is downloaded and no GPU dependency is installed.

- `GET /api/ai-arranger/catalog`: registered models, licenses, availability and presets.
- `POST /api/projects/{pid}/ai-arranger/plan`: validated request; project permissions enforced; produces structured constraints and a model-oriented prompt.
- `POST /api/projects/{pid}/ai-arranger/generate`: HTTP 503, fail closed, until a supported inference worker is integrated and verified.

Example request:

```json
{"model_id":"ace-step-1.5","preset_id":"jazz-swing","prompt":"Warm vintage piano and double bass","scope":"project","strength":60,"preserve_structure":true,"preserve_chords":true,"preserve_melody":true,"preserve_tempo":true}
```

When `preserve_structure` is enabled, active project markers with their timing/labels become section guidance. When `preserve_chords` is enabled, non-excluded chord annotations become harmony guidance. Such constraints are **not guarantees**: future work must provide alignment checks, arrangement analysis and selective re-generation. Original projects remain unchanged.

Future stages: asynchronous inference worker with explicit opt-in/model installation, source audio/reference pipeline, non-destructive variant preview, stem creation where supported, selective instrument replacement, accompaniment generation, style reference, harmonic and structural conformance scoring, per-section regeneration, desktop/mobile/web/container deployment. Heavy AI processes must never run on the C++ realtime callback. `native_host_ready=false` remains mandatory.

Licenses: ACE-Step 1.5 currently declares MIT and DiffRhythm 2 Apache-2.0 (code and weights), but dependencies, downloaded checkpoints, individual weight terms, and redistributed assets require separate verification before bundling. Users must have rights to transform source recordings.

## Italiano
La prima fase abilita **la pianificazione non distruttiva**, non la sintesi audio. I modelli sono registrati come descrittori, senza scaricare pesi o installare dipendenze GPU.

Il catalogo restituisce modelli e preset; l'API di pianificazione legge il progetto verificando i permessi; l'API di generazione risponde 503 finché non sarà integrato e validato un worker di inferenza.

`preserve_structure` acquisisce i marker attivi, con posizioni e nomi; `preserve_chords` acquisisce gli accordi non esclusi. I dati sono indicazioni **best-effort**, non garanzie: in futuro si aggiungeranno verifica della progressione, conformità delle sezioni e rigenerazione selettiva. L'originale resta immutato.

Roadmap: job asincroni con consenso e installazione modelli, riferimento audio, preview non distruttive, stem dove possibile, sostituzione strumenti, accompagnamento, riferimento stilistico, score armonico/strutturale, rigenerazione mirata e backend per tutte le piattaforme. La generazione non deve mai bloccare il callback realtime C++; `native_host_ready=false`.

Verificare sempre licenze dei checkpoint e delle dipendenze prima della redistribuzione; l'utente deve possedere i diritti necessari sul materiale elaborato.

## r179 / Preflight
POST `/api/projects/{pid}/ai-arranger/preflight` and `/remix/preflight` check readiness and missing annotations before inference. No model is bundled; generation and preview remain unavailable until a validated worker is connected.


## r182 — Worker readiness / Disponibilità worker
`GET /api/ai-arranger/worker-status` requires authentication. `worker_configured` is an infrastructure check only; `inference_verified`, `ace_step_ready`, and `remix_ready` remain false until a real audio-in/audio-out end-to-end test has passed.

### Generated track behavior (r185)
AI outputs are appended as **new, independent tracks** to the existing project. The source track(s) remain unchanged; generated audio is written to a unique filename and registered in the project clip library. Choosing Master Out supplies a render honoring the current mute, solo, faders, pan, and inserts. Generating requires a configured external AI worker; AI inference is not bundled.
