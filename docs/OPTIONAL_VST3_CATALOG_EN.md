# Optional open-source VST3 — MTA Audio Editor 0.3.0-r210

Catalog reviewed **19 October 2026**. Nothing is installed by default. Plugins
remain separate from MTA, AI engines and project files.

| Category | Plugin | Reviewed license | Pinned source revision |
|---|---|---|---|
| Instruments / Synthesizers | Surge XT and Surge XT Effects | GPLv3 | `4f0da4e423a675cb9c2c3e34ca3d381b43875324` |
| Reverb | MVerb | GPLv3 or later | `5ae9f571642822bbc6b9d2e113e3fb0aada36f93` |
| Reverb | Dragonfly Hall, Room, Plate, Early Reflections | GPLv3 | `440ec7b3b3db2fec34b9f80cf4890102ca14d1c3` |
| Saturation / Tape | CHOW Tape Model | GPLv3 desktop VST3 | `604372e4ffd9690c3e283362e4598cb43edbb475` |

Full license texts are shipped in `app/optional_plugin_licenses/` and linked from
the installation selector. The JSON catalog pins repositories, commits and
license SHA-256 digests. GPLv3 permits use, study, modification and redistribution
under its terms, including commercial use. These plugins do not require purchasing
a commercial plugin license. Trademarks remain with their owners; no endorsement
is implied. Individual source files, libraries, presets and other assets retain
their respective terms and notices.

This package includes catalog, license texts and installer, **not precompiled
plugin binaries**. The implemented delivery route builds locally from pinned
source, including recursive submodules. Sources and notices remain on disk.
Anyone redistributing resulting binaries must satisfy the applicable source and
notice obligations, including exact corresponding source; a moving upstream
branch is not sufficient evidence. Do not redistribute Surge VST2 builds: the
upstream explicitly excludes that route. MTA recipes select VST3 targets only.
DPF's own VST3 implementation uses ISC with attribution; preserve its notices.
CHOW and Surge use JUCE and additional components. CHOW's iOS dual licensing does
not substitute for the desktop license reviewed here.

## Installation and build requirements

- Windows Setup offers an unchecked optional task to open the catalog. All native
  apps expose it through VST3 settings; `--optional-plugins` opens the selector
  directly on Windows/macOS/Linux.
- Server administrators use Settings → Web App → optional open-source VST3.
  Select all available plugins or choose individual entries grouped by category.
  Ordinary server users cannot install executable code.
- Signed server installer: `sudo ./install_mta.sh early --vst3-plugins=all`, or
  `--vst3-plugins=mverb,dragonfly`. Review the licenses before this explicit opt-in.
- Source checkout: `python scripts/install_optional_vst3.py --list`, then
  `python scripts/install_optional_vst3.py --plugins mverb --accept-licenses`.
  The installed server runtime supports `python -m app.optional_plugins` with the
  same flags and the correct instance `MTA_DATA_DIR`.

Git and a supported C++ toolchain are required. DPF needs GNU Make (MSYS2/MinGW
on Windows); CHOW/Surge need CMake and JUCE-supported compilers (Visual Studio
Build Tools on Windows, Xcode Command Line Tools on macOS). Linux GUI builds need
X11/OpenGL and upstream dependency headers. The explicit server wizard option
installs these via APT/DNF; the web UI does not perform privileged OS upgrades.
Build failures are reported as failures, not successful installations.

Progress shows current plugin, build stage, tool activity and elapsed time.
Detailed logs and source checkouts live under
`MTA_DATA_DIR/optional-plugin-builds/<id>/<revision>/`. Managed VST3 files live
outside project workspaces, with operator override `MTA_OPTIONAL_VST3_DIR`.
Completed bundles are published atomically. Do not replace/remove a plugin while
an active session uses it.

## Periodic review

The monthly/manual `Review optional VST3 catalog licenses` workflow checks pinned
license digests without updating software automatically. After 90 days without
catalog review, new installations are disabled and the UI explains why; existing
plugins are not deleted. Review source, dependencies, formats and platforms before
updating pins, license texts, digests and `reviewed_at`. Set `enabled: false` for
withdrawn entries and document the reason. License text tampering invalidates the
catalog check.

Primary sources: [MVerb](https://github.com/DISTRHO/MVerb),
[Dragonfly](https://github.com/michaelwillis/dragonfly-reverb),
[CHOW Tape](https://github.com/jatinchowdhury18/AnalogTapeModel),
[Surge XT](https://github.com/surge-synthesizer/surge),
[DPF format licensing](https://github.com/DISTRHO/DPF/blob/main/LICENSING.md).
The pinned source links and full review details are also recorded in the Italian
overview and machine-readable catalog.

Actual validation this cycle: Linux MVerb and four Dragonfly source builds, VST3 loading and stereo
processing. Full CHOW/Surge builds and Windows/macOS native builds
still require validation on their respective systems.

## Per-plugin installation activity (r210)

Each card exposes its installation state. Only the plugin currently being built displays a progress bar, with actual download/build/install activity. Its bar disappears immediately on completion or failure, even while the rest of the batch is running. Progress remains indeterminate when build tools do not expose a reliable total. Final outcomes survive reopening the catalog; monitoring of an active job resumes in the same server process. See `VST3_PROGRESS_CPP_LIVE_CONTROLS_R210.md` for implementation and validation details.


## Uninstall optional packages

Open the same catalog from **Settings → Web App → Optional open-source VST3**, or from native settings. Installed cards offer **Uninstall**, with **Also remove downloaded sources and build cache** selected by default. One confirmation is required.

Removal covers the complete package, including all four Dragonfly reverbs. The confirmation reports how many saved projects reference it. Such projects will need the plugin reinstalled or their affected inserts removed; project data is retained. Stop live playback, editors and monitoring using that package first. Concurrent installation blocks removal.

Only allowlisted packages in MTA's managed directory can be removed. Internal DSP effects and independently installed operating-system VST3 packages are outside this action. Detached uninstall directories cannot be discovered or executed, including on separately mounted plugin volumes.
