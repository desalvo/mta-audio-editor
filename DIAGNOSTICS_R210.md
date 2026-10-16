# r210 AI worker failure diagnostics

When the cgroup-isolated worker exits nonzero, the server logs its PID, exit code, and a short, filtered exception summary. Raw stderr is drained using a bounded in-memory 8 KiB tail and is not sent to the browser or included in any billing record. Invalid / failed metering still aborts the AI job, without certified usage.

Retrieve failure context after reproducing the issue:

```bash
sudo journalctl -u mta-server.service --since '15 minutes ago' --no-pager -o short-iso | grep -E 'AI metered worker exited|AI cgroup launch failed|AI worker failed'
```

The output can expose operational details; review it before sharing. This patch does not establish why ACE-Step currently exits nonzero on the test machine, and no live GPU/cgroup validation has been performed.
