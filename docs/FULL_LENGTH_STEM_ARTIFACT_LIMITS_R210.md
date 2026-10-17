# r210 — full-length stem result limits

## Confirmed failure

The server journal reports `RuntimeError: Worker outputs exceed artifact size limit`.
This is raised by the trusted adapter's final artifact publication, after the
backend has generated its output. It is not evidence of a cgroup, ROCm or GPU
profiler failure. A 64 MiB aggregate budget was insufficient: six stereo WAV
stems at 44.1 kHz/16 bit reach it after about 63 seconds.

## Changes

A shared finite budget now aligns the complete worker/result path:

| Resource | Ceiling |
| --- | --- |
| Source WAV | 512 MiB |
| Sum of uncompressed output artifacts | Admin-configurable 64–8192 MiB; default 1 GiB |
| Output manifest | 256,000 bytes |
| Packaged result | Job artifact budget + 2 MiB for ZIP/manifest overhead |
| Transport/cache absolute ceiling | 8 GiB + 2 MiB |
| Output artifact count | 16, unchanged |

Six stereo 44.1 kHz/16-bit stems from a ten-minute song require approximately
606 MiB and fit the new budget. Larger output still fails closed. The per-job budget is stored in Settings > AI Queue and frozen before worker
execution. A finite 8 GiB protocol ceiling remains; these limits do not promise
unlimited song length or concurrency.
The operator must size memory, temporary storage and replay-cache storage for
large jobs; the current API returns results as bounded byte payloads, not a
fully streaming media pipeline. Model/GPU memory requirements are separate.

The limits apply to adapter publication, private-file packaging, web result
unpacking, authenticated remote HTTP upload/download, native remote input,
and durable replay-cache reads/writes. ZIP headers and the manifest no longer
consume the uncompressed audio budget. Checked local reads request the actual
inode size plus one byte, avoiding a ceiling-sized read for small artifacts.
Source inputs exceeding their ceiling are rejected before creating a billing
job. Output size failures have a distinct safe diagnostic code.

Symlink/hardlink guards, manifest checksums, finite ZIP bounds, authentication,
cancellation, cgroup accounting and verified GPU billing requirements remain
in force. Annotation-only JSON import limits and the legacy ACE gateway have
separate existing bounds and are unchanged.

## Validation and deployment

The regression fixture publishes six real 70-second PCM WAV files with
incompressible sample data, exceeding both former 64 MiB worker and 32 MiB
transport/cache limits. It verifies packaging, durable replay, response digest,
strict ZIP validation, web unpacking and native import. Additional tests cover
oversize rejection, ZIP overhead, long native inputs and rejection before
billing admission. No actual ML/GPU inference is simulated by these fixtures.

Deploy the rebuilt server package and retry the same stem separation. This
change does not require reinstalling the AI model environments. Confirm all
stems appear, play, and remain after reopening the project. Hardware validation
and GPU billing certification require the real server's verified evidence;
passing software tests alone does not certify them.

Version remains 0.3.0-r210. All previous cumulative changes are included.
