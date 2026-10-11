"""One-shot UTC billing period closure runner for systemd timer / cron."""
from __future__ import annotations
import json
import logging
from .ai_billing import run_scheduled_closures


def main():
    from .ai_storage_sampler import sample_all
    print(json.dumps({'storage': sample_all()}, sort_keys=True))
    results = run_scheduled_closures()
    for result in results:
        print(json.dumps(result, sort_keys=True))
    # Fail closed: errors are visible to systemd and monitored via journalctl.
    if any('error' in result for result in results):
        logging.error('One or more billing periods were not closed')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
