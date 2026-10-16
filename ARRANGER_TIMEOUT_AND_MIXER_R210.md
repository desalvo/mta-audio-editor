# r210 — Arranger execution budget, organized form and mixer resizing

Version: 0.3.0-r210 (unchanged). Cumulative with all previously delivered r210 changes, including the uncommitted duplicate/refresh/socket and live status/web controls fixes.

## Arranger

The dialog now has four ordered groups: source/range, arrangement/model/style, preservation options, execution. Two columns collapse on narrow windows. Intensity has a percentage readout. Native ACE configuration is collapsed under a separate advanced disclosure and is never inserted on web sessions. Existing field IDs and handlers remain functional.

The maximum processing time defaults to **60 minutes**. Change it in the execution group from **1 to 240 minutes**. This is independent of the length of the source audio: choose **Entire source / Sorgente intera** to process the whole song, or use start/end seconds for a selected interval. Existing source duration, media size and output validation limits are retained; complete songs remain subject to the actual ACE model's capabilities and memory constraints.

The validated integer `inference_timeout_seconds` is included in the plan and durable request, so queued recovery keeps the chosen budget. The project worker supervisor applies it in both cgroup and process supervision paths. The ACE HTTP adapter uses the same budget, reserving up to two minutes (10% for shorter budgets) for retrieving the result. The previous fixed 1100-second poll default no longer cuts off an explicitly configured job. The legacy deployment poll override still applies to older direct adapter requests without a per-job setting. A timeout does not mark accounting as verified or make invalid usage billable.

The opt-in durable MTA remote executor also uses this budget for its client request timeout. Operator limits imposed by an independent remote service remain applicable; this change does not reconfigure another server. Source preparation and time waiting in the MTA scheduler queue are outside the local worker execution deadline.

## Mixer

The lower dock now fills the row allocated by `--mixer-height`, instead of reducing its own height with a percentage maximum calculated from that same row. Web and native windows share the bounded two-row editor/mixer layout, including narrow windows. Dragging the upper separator raises the mixer top while the bottom stays at the available workspace boundary. The existing resize bounds, keyboard controls and saved project height are preserved.

Channel controls are more compact vertically: name, pan, fader, meters and numeric volume. No fader, pan, mute/solo or insert control was removed. At very low dock heights vertical scrolling remains available; horizontal scrolling remains available across tracks.

## Validation

- 34 focused tests passed: request/plan round trip, invalid budgets, custom budget reaching the cgroup supervisor with measured usage intact, virtual-clock ACE polling beyond the old limit and custom timeout termination, real standalone HTTP adapter round trip, actual modal/watcher JavaScript, form submission, web/native dock geometry and actual channel markup layout.
- Broad regression: 3221 passed, 4 skipped (optional Steinberg SDK/ADelay), 10 deselected (AF_UNIX integrations unavailable here), 4 warnings. Logs and JUnit included in validation/.
- Node syntax and Ruff checks passed for the changed code.
- Final form markup/style refinements were followed by rerunning the focused suite. Layout validation uses the production CSS with WeasyPrint; it is not an interactive browser certification.

Pending physical acceptance: resize/scroll the mixer in the user's server browser and run full-song ACE inference on the actual ROCm installation. The previously reported zero GPU counter still needs a fresh diagnostics ZIP; it remains unverified and unbillable. Windows startup acceptance is also not established by these tests. No commit, push, tag, release or live server operation was performed. No new Proxmox host agent installation is required by this cycle.
