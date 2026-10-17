# r210 — preserve worker failures in the server journal

The diagnostic export from 17 October 2026 records a stem worker exit code 1
and RuntimeError. The corresponding journal contains HTTP access records but
no application error. It does not identify the original Demucs exception.

`SafeEvents`, the metadata-only diagnostic handler, was the only root logging
handler under the default Uvicorn configuration. Attaching it suppressed
Python's `logging.lastResort` stderr fallback, including with diagnostic
collection disabled. Application errors therefore disappeared from the journal.

Diagnostic initialization now installs a WARNING-level stderr handler first
when the root logger has no handlers. Existing logging configurations are
preserved; initialization remains idempotent. Structured diagnostic exports
continue to exclude raw messages and tracebacks. The worker's existing bounded,
redacted exception summary now reaches stderr/systemd journal. The summary scans
the existing bounded 8 KiB tail instead of only its last 15 lines, preserving
original exceptions followed by long nested subprocess tracebacks.

This fixes missing error visibility, not a proven Demucs runtime defect.
After deploying, retry a short stem separation and collect:

```sh
sudo journalctl -u mta-server.service --since "10 minutes ago" --no-pager \
  -g "AI metered worker exited nonzero"
```

Do not disable metering or bill invalid measurements. Revision remains
0.3.0-r210. Previous TorchCodec provisioning, audio read/write checks, safe
failure metadata, and canonical installer help corrections are included.
