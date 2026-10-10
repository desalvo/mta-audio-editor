"""Atomic, versioned VST3 checkpoint store for control-thread use only.

Not an audio-callback API. Caller supplies a stable plugin identity (e.g. signed
module path + class CID); a mismatched identity MUST NOT restore stale state.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .native_chain import NativeChainError

MAX_STATE = 1024 * 1024
MAX_FILE = 3 * 1024 * 1024
FORMAT = "mta-vst3-checkpoint-v1"


def _valid_identity(plugin_id: str) -> None:
    if not isinstance(plugin_id, str) or not 1 <= len(plugin_id) <= 1024 or any(ord(c) < 32 for c in plugin_id):
        raise ValueError("Invalid plugin identity")


def _valid_state(value: bytes | None, optional: bool = False) -> None:
    if optional and value is None:
        return
    if not isinstance(value, bytes) or len(value) > MAX_STATE:
        raise ValueError("Invalid VST3 state size or type")


def encode_checkpoint(plugin_id: str, component: bytes, controller: bytes | None) -> bytes:
    """Return a self-checking portable blob (no executable serialization)."""
    _valid_identity(plugin_id)
    _valid_state(component)
    _valid_state(controller, optional=True)
    payload = {"format": FORMAT, "plugin": plugin_id,
               "component": base64.b64encode(component).decode("ascii"),
               "controller": None if controller is None else base64.b64encode(controller).decode("ascii")}
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    envelope = {"sha256": hashlib.sha256(body).hexdigest(), "payload": payload}
    return json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")


def decode_checkpoint(blob: bytes, plugin_id: str) -> tuple[bytes, bytes | None]:
    """Reject mismatched, oversized, noncanonical or damaged checkpoint blobs."""
    _valid_identity(plugin_id)
    if not isinstance(blob, bytes) or not 0 < len(blob) <= MAX_FILE:
        raise NativeChainError("Invalid VST3 checkpoint length")
    try:
        envelope = json.loads(blob)
        if not isinstance(envelope, dict) or set(envelope) != {"payload", "sha256"}:
            raise ValueError("Invalid envelope")
        payload = envelope["payload"]
        if not isinstance(payload, dict) or set(payload) != {"format", "plugin", "component", "controller"}:
            raise ValueError("Invalid fields")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if hashlib.sha256(canonical).hexdigest() != envelope["sha256"]:
            raise ValueError("Checksum mismatch")
        if payload["format"] != FORMAT or payload["plugin"] != plugin_id:
            raise ValueError("Plugin identity/format mismatch")
        def parse_b64(value):
            if not isinstance(value, str) or len(value) > 4 * ((MAX_STATE + 2) // 3):
                raise ValueError("State encoding exceeds limit")
            return base64.b64decode(value, validate=True)
        component = parse_b64(payload["component"])
        controller = None if payload["controller"] is None else parse_b64(payload["controller"])
        _valid_state(component)
        _valid_state(controller, optional=True)
        return component, controller
    except (ValueError, TypeError, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativeChainError("Invalid or mismatched VST3 checkpoint") from exc
    except Exception as exc:
        # binascii.Error and unexpected malformed encodings are invalid data,
        # not an instruction to restore partial plugin state.
        raise NativeChainError("Corrupt VST3 checkpoint encoding") from exc


def save_checkpoint(path: str | Path, plugin_id: str, component: bytes,
                    controller: bytes | None) -> None:
    """Atomically replace checkpoint, never persist a partially written pair."""
    destination = Path(path)
    payload = encode_checkpoint(plugin_id, component, controller)
    if len(payload) > MAX_FILE:
        raise ValueError("VST3 checkpoint exceeds file budget")
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=destination.parent,
                                         prefix=".mta-vst3-", suffix=".tmp", delete=False) as handle:
            temp = Path(handle.name)
            os.chmod(temp, 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, destination)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def load_checkpoint(path: str | Path, plugin_id: str) -> tuple[bytes, bytes | None]:
    """Read a bounded file; reject mismatched plugins before state restoration."""
    with Path(path).open("rb") as handle:
        blob = handle.read(MAX_FILE + 1)
    return decode_checkpoint(blob, plugin_id)
