"""Worker termination after durable cancellation, without a live GPU."""
import sys
import time
import pytest
from app.ai_metering_agent import run_metered_process


def test_cancellation_kills_live_process_group(tmp_path):
    started = time.monotonic()
    with pytest.raises(RuntimeError, match='cancelled'):
        run_metered_process([sys.executable, '-c', 'import time; time.sleep(20)'],
                            cwd=str(tmp_path), timeout_seconds=30,
                            cancel_check=lambda: time.monotonic() - started > .2)
    assert time.monotonic() - started < 4


def test_cancellation_does_not_block_success(tmp_path):
    result = run_metered_process([sys.executable, '-c', 'print("ok")'],
                                 cwd=str(tmp_path), timeout_seconds=5,
                                 cancel_check=lambda: False)
    assert result.exit_code == 0


def test_cancellation_before_worker_exit(tmp_path):
    with pytest.raises(RuntimeError, match='cancelled'):
        run_metered_process([sys.executable, '-c', 'import time; time.sleep(10)'],
                            cwd=str(tmp_path), timeout_seconds=20,
                            cancel_check=lambda: True)
