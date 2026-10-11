# Remix / Auto-Remix — r175

The AI Arranger now exposes the independent **Remix** operation at planning level.

Modes: `instrument_swap` (one or more track-to-instrument replacements) and `auto_remix` (style preset and optional free-form prompt). Existing options `preserve_chords`, `preserve_structure`, `preserve_tempo`, `preserve_voice` and `preserve_melody` remain available.

Python integration: `prepare_remix_plan(project, RemixRequest(...))`. No inference model is downloaded or invoked by this function. A real backend, UI wiring, provenance metadata, preview approval, isolated stem output and post-render musical verification remain required before production use.

Use only music for which the user has processing rights. Do not impersonate a singer.
