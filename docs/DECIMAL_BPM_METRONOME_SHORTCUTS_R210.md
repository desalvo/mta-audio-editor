# Decimal BPM and generated-track shortcuts — 0.3.0-r210

## Behavior

- Manual BPM from the transport context menu accepts dot/comma decimals, from 30 to 300, with up to two meaningful decimal places. The transport displays the fractional value. Automatic estimation retains two decimal places throughout import, analysis, storage and display; PDF metadata continues to round BPM to an integer.
- A manual context-menu BPM sets both the project tempo and the independent metronome grid, preserving audio playback speed. Existing click tracks, including muted tracks, are regenerated. Adding or refreshing fixed/zone metronomes uses the explicit manual grid instead of reference-track inference. Explicit per-zone overrides retain priority. Adaptive metronomes remain driven by the analyzed audio.
- The ordinary transport tempo control preserves its existing playback-speed semantics; it also accepts fractional values. Fixed click rendering positions each beat from its absolute fractional interval to avoid accumulated sample-rounding drift.
- Metronome settings are persisted before generation, waiting for an in-flight autosave. Native project archives are synchronized again after regeneration so reopening retains the regenerated audio. Cached decoded click audio is invalidated.
- Unmodified R regenerates a selected metronome or generated chords track. Track selection restores shortcut focus; the contextual menu displays R in a styled key label with an accessible shortcut attribute. Text entry, dialogs and modified/repeated keystrokes are protected.

## Regression coverage

The new regression module executes actual editor JavaScript with Node and covers fractional input/display, manual-grid precedence, muted tracks, autosave ordering, native post-generation synchronization, cache invalidation and the registered keyboard handler. API tests exercise persistence/reopening, fixed and zone generation, per-zone overrides and unchanged original audio. Audio tests verify regenerated PCM and sample positions; a rendered PDF test verifies integer-only BPM metadata.

Targeted regression: 61 passed. Ruff and Node syntax checks passed.

Full regression: 3,824 passed, 5 skipped (optional Steinberg SDK / real Win32 APIs), 10 deselected (AF_UNIX host-agent socket tests unavailable under this runner network policy), zero failures. Coverage 76.47%, above the required 70%. Additional integration regression: 44 passed. Three initial full-suite failures were resolved by updating the obsolete integer-BPM expectation, loading the actual focus helper into the drag test harness, and retaining the release prefix in the asset cache key.

Full regression results are recorded in validation/r210-decimal-bpm-full.xml and validation/r210-decimal-bpm-full.log. Optional platform/SDK skips and AF_UNIX host-agent exclusions are described in the final delivery; they do not constitute a live server or physical native-app certification.

## Cumulative delivery

This package retains every file from MTA-0.3.0-r210-admin-backup-ai-queue-cumulative.zip, including its admin erasure, backup/restore, AI job ownership/accounting changes and previous development. VERSION remains 0.3.0 and REVISION remains 210. No commit, push, tag or release is performed.

Physical Windows/macOS interaction and verification on the deployed server remain to be performed after installation. Decimal precision describes retained estimator output, not a guarantee of tempo-estimation accuracy for every recording.
