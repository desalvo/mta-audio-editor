# r210 — Sample range editing, dBFS scale and personal limits

Version remains **0.3.0-r210**. This cumulative change includes all earlier mixer Gain, language, legal PDF and account quota work. No commit, push, tag, release or live-server operation is performed.

## Sample editor

- The vertical amplitude scale shows mirrored **0 dBFS**, −6, −12 and −24 dB references and the zero-amplitude center. Orange full-scale lines are distinct from the blue waveform. Samples reaching digital full scale are red, with a visible-peak reading and a possible-clipping warning. Reaching full scale alone is not proof of audible distortion. This is a sample-peak display, not an intersample true-peak analyzer.
- A selected track range limits editor navigation, input fields, selection, effect processing and original-audio audition. The range's project coordinates are converted to rendered sample coordinates, including track delay.
- Double-click remembers the range before the timeline's first click clears it. The context-menu entry uses the current selected range. Opening without a selected range exposes the whole track.
- Initial horizontal scale uses the current project pixels-per-second value and visible timeline start. It fits inside a shorter restricted range when that range cannot fill the viewport at the project zoom. The zoom slider represents the actual view; positioning and pointer coordinates respect the scale gutter and bounds.
- Original-audio audition uses a sample-exact ranged WAV response. Full-file requests reuse the existing render. Temporary ranged responses are removed after delivery.
- Sample metadata uses actual frame counts, avoiding millisecond rounding. Processing source renders are pre-gain/pre-insert and do not bake the track delay. Committing a rendered timeline does not add clip placement twice; the independent gain and delay controls remain unchanged. The cache format version invalidates earlier renders.
- Closing/reopening aborts stale previews and releases preview URLs and observers. Effect-preview requests include the normal integrity header.

## Mixer

Browser-provided numeric steppers no longer occupy the text area. Both pan and Gain have separately allocated, scalable step buttons, with keyboard numeric controls preserved. The pan row uses flexible layout so the knob, number and arrows remain separate on compact channels. A rendered visual check covers three tracks and the master strip.

## Limits and Quotas / Limiti e Quote

The profile starts with a collapsed section containing personal storage, CPU, GPU and accounting information, with text and SVG charts. Its expanded/collapsed preference is stored on the authenticated account and survives reloads. Default-collapsed initialization does not write a preference. Token details and email summaries are inside the same section.

The old profile selected the first workspace returned by the administrator storage endpoint. It now requests only the authenticated user's summary; a supplied different user ID cannot select another account. A zero quota is shown as **unlimited**, with no fabricated limit or remaining capacity.

Occupied storage counts regular files in owned projects and counts a shared inode once per owner. It skips symlinks, excludes other owners and does not substitute host-disk usage. Audio and other files are distinguished. Missing files during a scan may disappear concurrently; other filesystem errors are not silently reported as zero. The same measurement backs workspace capacity checks.

CPU/GPU reporting distinguishes:

- verified lifetime usage;
- usage belonging to closed accounting periods;
- eligible successful, measured ledger jobs not yet included in a closed period;
- other verified usage, including unsuccessful/in-progress or diagnostic-only records;
- diagnostic estimates, explicitly nonbillable and never substituted for missing measurements.

The AI compute amount pending billing is an estimate; issued amounts come from immutable billing periods. Statistics preserve existing accounting exclusions and avoid duplicate queue/ledger jobs through the shared reporting layer. Storage and other billing components remain covered by their official accounting reports; the pending compute figure does not claim to include those components.

**Payments are not recorded by the existing application ledger.** Therefore an outstanding payable balance is shown as unavailable, rather than treating all issued amounts as unpaid or inventing a zero balance. No GPU billing authorization, sensor certification or payment state is inferred by this dashboard.

## Regression and limits of verification

Targeted tests exercise own-account isolation including administrators, unlimited quotas, actual occupied file bytes, hardlink deduplication, symlink exclusion, persisted independent collapse preferences, verified/pending/closed resource classification, disabled billing, missing GPU telemetry, canvas full-scale lines and warning, range zoom/clamping, sample-accurate ranged audio, gain/delay/timeline preservation after an effect, actual JavaScript panel rendering and containing all usage controls inside the first collapsible section.

**Final results:** full regression 3,881 passed, 5 skipped, 10 deselected; the added persistent double-click entry-path regression also passed separately (one test). Ruff and all four changed JavaScript syntax checks pass. Application sources remained unchanged during the final full run; only the additional regression file was added afterward.

Full regression, JUnit and coverage results are included under `validation/r210-sample-limits-*`. Ruff, JavaScript syntax checks and static layout renders supplement these checks. Five optional SDK/Win32 checks require their external runtime; ten existing Unix-socket tests cannot execute under this workspace's AF_UNIX restrictions. Native Windows/macOS visual interaction and live-server testing still require the installed builds. This package does not newly certify the server or the physical GPU meter.

## Cumulative base

The base is `MTA-0.3.0-r210-user-language-legal-pdf-quota-cumulative.zip` (1,811 files). The packaging check retains every baseline entry, verifies every archived byte against the final project, runs ZIP CRC verification, preserves executable attributes, checks version/revision and Markdown placement, and emits SHA-256.

Suggested cumulative commit since the last user-confirmed commit:

`Add mixer gain, per-user locales and legal PDFs, default quotas, scoped dBFS sample editing and personal usage dashboard`
