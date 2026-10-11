"""Report ACE-Step operational prerequisites without claiming model inference success."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
from .ai_worker_protocol import configured_worker


def readiness(*, probe: bool = False, timeout_seconds: int = 5) -> dict:
    """Return observable stages, never promote endpoint reachability to inference."""
    worker = configured_worker()
    result = {
        "worker_configured": worker is not None,
        "worker_capabilities_verified": False,
        "accepts_source_audio": False,
        "server_reachable": False,
        "inference_verified": False,
        "ready_for_real_generation": False,
        "reason": "worker_not_configured" if worker is None else "capabilities_not_checked",
    }
    if worker is None or not probe:
        return result
    if not 1 <= timeout_seconds <= 30:
        raise ValueError("invalid readiness timeout")
    try:
        completed = subprocess.run([str(worker), "--capabilities"], shell=False,
            capture_output=True, text=True, timeout=timeout_seconds, check=False)
        if completed.returncode:
            result["reason"] = "capability_probe_failed"
            return result
        caps = json.loads(completed.stdout)
        if not isinstance(caps, dict) or caps.get("protocol") != "mta.ai.worker.v1":
            result["reason"] = "invalid_capabilities"
            return result
        result["worker_capabilities_verified"] = True
        result["accepts_source_audio"] = caps.get("supports_audio_input") is True
        result["reason"] = "real_inference_not_verified"
        # A health-check never proves that the model loaded or generated usable audio.
        if os.environ.get("MTA_AI_READINESS_PROBE_SERVER") == "true":
            checked = subprocess.run([str(worker), "--check-server"], shell=False,
                capture_output=True, text=True, timeout=timeout_seconds, check=False)
            if checked.returncode == 0:
                payload = json.loads(checked.stdout)
                result["server_reachable"] = isinstance(payload, dict) and payload.get("server_reachable") is True
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired):
        result["reason"] = "probe_failed"
    return result
