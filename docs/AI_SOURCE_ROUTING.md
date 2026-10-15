# AI Arranger / Remix input routing (r185)

Select Master Out to render the complete export mix (track/master inserts, mute/solo, gains, pan, project time/pitch). The source is a WAV snapshot, not the browser preview where master gain is applied later. Select Track to render a single selected track with its inserts, isolated from other tracks and regardless of its mute/solo flags. Right-clicking a track and choosing AI Arranger / Remix preselects that track.

The worker manifest `source_audio[].kind` is `master` or `track`; `rendered_with` describes the processing path. Source files remain temporary. A real AI model and import workflow are still required.

### Generated track behavior (r185)
AI outputs are appended as **new, independent tracks** to the existing project. The source track(s) remain unchanged; generated audio is written to a unique filename and registered in the project clip library. Choosing Master Out supplies a render honoring the current mute, solo, faders, pan, and inserts. Generating requires a configured external AI worker; AI inference is not bundled.
