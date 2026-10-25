"""Bounded local custom separator execution; commands are operator configuration.

No shell, inference retry or metering certification. Process groups cover normal
POSIX descendants, not escaped workers or distributed quiescence.
"""
import math
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


def run(command, *, cancel_event=None, timeout=7200, max_log_bytes=8*1024*1024,cwd=None,env=None):
    if (not isinstance(command,list) or not command or any(not isinstance(x,str) or not x or '\x00' in x for x in command)
            or type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0<timeout<=7200
            or type(max_log_bytes) is not int or not 1024<=max_log_bytes<=8*1024*1024):
        raise ValueError('Invalid configured separator execution limits')
    if cancel_event is not None and cancel_event.is_set():raise RuntimeError('stem separation cancelled')
    with tempfile.TemporaryFile() as log:
        process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=os.name=='posix',cwd=cwd,env=env)
        deadline=time.monotonic()+timeout
        try:
            while True:
                if cancel_event is not None and cancel_event.is_set():raise RuntimeError('stem separation cancelled')
                if time.monotonic()>=deadline:raise RuntimeError('stem separation timed out')
                if os.fstat(log.fileno()).st_size>max_log_bytes:raise RuntimeError('separator diagnostic output limit exceeded')
                if process.poll() is not None:break
                time.sleep(.02)
            log.seek(max(0,os.fstat(log.fileno()).st_size-3000))
            diagnostic=log.read(3000).decode('utf-8',errors='replace')
            if process.returncode:raise RuntimeError(diagnostic or 'lead/backing vocal separator failed')
        finally:
            if process.poll() is None:
                if os.name=='posix':
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                else:
                    subprocess.run([str(Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/taskkill.exe'),
                                    '/PID',str(process.pid),'/T','/F'],stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10,check=False)
                    process.kill()
                process.wait(timeout=10)
