## r177 Remix job planning

POST `/api/projects/{pid}/remix/jobs` creates an authenticated non-destructive plan that may be cancelled using the shared AI job API. Worker execution is not yet enabled.

# Remix / Auto-Remix — r175

The AI Arranger now exposes the independent **Remix** operation at planning level.

Modes: `instrument_swap` (one or more track-to-instrument replacements) and `auto_remix` (style preset and optional free-form prompt). Existing options `preserve_chords`, `preserve_structure`, `preserve_tempo`, `preserve_voice` and `preserve_melody` remain available.

Python integration: `prepare_remix_plan(project, RemixRequest(...))`. No inference model is downloaded or invoked by this function. A real backend, UI wiring, provenance metadata, preview approval, isolated stem output and post-render musical verification remain required before production use.

Use only music for which the user has processing rights. Do not impersonate a singer.


## r176 endpoints
GET /api/ai-arranger/catalog; POST /api/projects/{pid}/ai-arranger/plan; POST /api/projects/{pid}/remix/plan. All require authentication and project permissions. Generation deliberately returns 503 until a verified backend is available. Plans are non-destructive.

### Generated track behavior (r185)
AI outputs are appended as **new, independent tracks** to the existing project. The source track(s) remain unchanged; generated audio is written to a unique filename and registered in the project clip library. Choosing Master Out supplies a render honoring the current mute, solo, faders, pan, and inserts. Generating requires a configured external AI worker; AI inference is not bundled.
