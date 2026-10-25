"""Resolve namespace-local PIDs in the mounted Linux /proc view.

An ancestor's procfs may expose unrelated processes at our local PID numbers.
Missing namespace evidence stays unknown; use local signal probes for absence.
"""
import os
from pathlib import Path


def directory(pid):
    if type(pid) is not int or pid <= 0:
        raise ValueError('Positive namespace-local PID required')
    own = os.getpid()
    if pid == own:
        return Path('/proc/self')
    outer = int(Path('/proc/self/stat').read_text().split()[0])
    if outer == own:
        return Path('/proc') / str(pid)
    namespace = Path('/proc/self/ns/pid').stat().st_ino
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            lines = (entry / 'status').read_text().splitlines()
            values = next(line.split()[1:] for line in lines if line.startswith('NSpid:'))
            if not values or int(values[-1]) != pid:
                continue
            if (entry / 'ns/pid').stat().st_ino != namespace:
                continue
            return entry
        except (OSError, ValueError, StopIteration):
            continue
    return None
