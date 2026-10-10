"""Bounded, control-thread-only recovery for the isolated VST3 IPC worker.

There is NO transparent replay of a failed block: a VST3 processor may have
changed internal state before its IPC response failed. Recovery starts a NEW
plugin instance and marks a new epoch, after the failed block was returned dry.
Never use this object in a realtime audio callback.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable

from .native_chain import NativeChainError
from .stream_worker import EventBlock, NativeVST3Worker

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecoveryStats:
    epoch: int
    restarts: int
    faults: int
    dry_blocks: int
    processed_blocks: int
    disabled: bool
    resets: int = 0
    deferred_blocks: int = 0
    restored_sessions: int = 0
    restore_failures: int = 0
    checkpoints: int = 0
    controller_checkpoints: int = 0
    controller_restorations: int = 0
    unsupported_controllers: int = 0


class SupervisedVST3Worker:
    """Synchronous *worker-thread* supervisor with finite restart budget.

    One call is one audio quantum. The caller owns timeline compensation and
    must reset event scheduling to the new epoch after a failure.
    """

    def __init__(self, factory: Callable[[], NativeVST3Worker], *,
                 channels: int = 2, max_restarts: int = 3,
                 recovery_gap_blocks: int = 0,
                 restore_state: Callable[[NativeVST3Worker], None] | None = None):
        if not callable(factory):
            raise ValueError('Expected a worker factory')
        if type(channels) is not int or channels not in (1, 2):
            raise ValueError('Expected mono or stereo channels')
        if type(max_restarts) is not int or not 0 <= max_restarts <= 32:
            raise ValueError('Invalid restart budget')
        if type(recovery_gap_blocks) is not int or not 0 <= recovery_gap_blocks <= 4096:
            raise ValueError('Invalid recovery gap')
        if restore_state is not None and not callable(restore_state):
            raise ValueError('Expected a callable restore_state')
        self._restore_state = restore_state
        self._restored_sessions = 0
        self._restore_failures = 0
        self._state_snapshot: bytes | None = None
        self._checkpoints = 0
        self._controller_snapshot: bytes | None = None
        self._controller_checkpoints = 0
        self._controller_restorations = 0
        self._unsupported_controllers = 0
        self.recovery_gap_blocks = recovery_gap_blocks
        self._pending_gap = 0
        self._resets = 0
        self._deferred = 0
        self._factory = factory
        self.channels = channels
        self.max_restarts = max_restarts
        self._worker = None
        self._epoch = 0
        self._restarts = 0
        self._faults = 0
        self._dry = 0
        self._processed = 0
        self._closed = False
        self._disabled = False
        self._has_started = False

    @property
    def stats(self) -> RecoveryStats:
        return RecoveryStats(self._epoch, self._restarts, self._faults,
                             self._dry, self._processed, self._disabled,
                             self._resets, self._deferred,
                             self._restored_sessions, self._restore_failures,
                             self._checkpoints, self._controller_checkpoints,
                             self._controller_restorations, self._unsupported_controllers)

    def _discard_worker(self) -> None:
        old, self._worker = self._worker, None
        if old is not None:
            try:
                old.close(force=True)
            except Exception:
                _LOGGER.warning("VST3 worker cleanup failed after plugin fault", exc_info=True)

    def _ensure_worker(self) -> bool:
        if self._disabled or self._closed:
            return False
        if self._worker is not None:
            return True
        if self._has_started:
            if self._restarts >= self.max_restarts:
                self._disabled = True
                return False
            self._restarts += 1
        self._has_started = True
        self._epoch += 1
        worker = None
        try:
            worker = self._factory()
            if worker is None or worker.channels != self.channels or not worker.events_enabled:
                raise NativeChainError('Recovery worker has incompatible configuration')
            if self._state_snapshot is not None:
                # Restore component state before the first PCM quantum of a new
                # isolated epoch; caller serializes this with all processing.
                try:
                    worker.restore_state(self._state_snapshot)
                except Exception:
                    self._restore_failures += 1
                    raise
                self._restored_sessions += 1
            if self._controller_snapshot is not None:
                # Component state must be restored before independent controller state.
                # An unsupported controller never acquires a snapshot here.
                try:
                    worker.restore_controller_state(self._controller_snapshot)
                except Exception:
                    self._restore_failures += 1
                    raise
                self._controller_restorations += 1
            if self._restore_state is not None:
                # The control-thread callback MUST finish before the first PCM
                # quantum is delivered to the newly created plugin instance.
                # It may restore a caller-maintained parameter snapshot; no
                # generic Steinberg component-state serialization is implied.
                try:
                    self._restore_state(worker)
                except Exception:
                    self._restore_failures += 1
                    raise
                self._restored_sessions += 1
            self._worker = worker
            return True
        except Exception:
            # A factory can create a live subprocess before its capabilities are
            # checked. Release that process on *every* rejected start, including
            # a mismatch in channel count or event protocol.
            if worker is not None:
                try:
                    worker.close(force=True)
                except Exception:
                    _LOGGER.warning("VST3 worker cleanup failed after rejected start", exc_info=True)
            self._faults += 1
            if self._restarts >= self.max_restarts:
                self._disabled = True
            return False

    def checkpoint_state(self) -> bytes:
        """Capture actual VST3 SDK processor state between audio blocks.

        The caller must serialize this call with process()/seek; it must never
        run on a realtime callback. A failed snapshot closes the worker and
        preserves the LAST valid checkpoint (no partial state writes).
        """
        if self._closed or self._worker is None:
            raise RuntimeError('No running VST3 worker to checkpoint')
        try:
            state = self._worker.snapshot_state()
            if not isinstance(state, bytes) or len(state) > 1024 * 1024:
                raise NativeChainError('VST3 state exceeds snapshot budget')
        except Exception:
            self._faults += 1
            self._discard_worker()
            self._pending_gap = self.recovery_gap_blocks
            raise
        self._state_snapshot = state
        self._checkpoints += 1
        return state

    def checkpoint_controller_state(self) -> bytes | None:
        """Capture optional controller state between PCM blocks.

        NotImplementedError means that this plugin has no separate controller
        snapshot, which is NOT a worker fault. Other errors invalidate the
        worker and preserve the last complete checkpoint.
        """
        if self._closed or self._worker is None:
            raise RuntimeError('No running VST3 worker to checkpoint')
        try:
            state = self._worker.snapshot_controller_state()
        except NotImplementedError:
            # Do not carry state from a previously configured controller.
            self._controller_snapshot = None
            self._unsupported_controllers += 1
            return None
        except Exception:
            self._faults += 1
            self._discard_worker()
            self._pending_gap = self.recovery_gap_blocks
            raise
        if not isinstance(state, bytes) or len(state) > 1024 * 1024:
            self._faults += 1
            self._discard_worker()
            self._pending_gap = self.recovery_gap_blocks
            raise NativeChainError('VST3 controller state exceeds snapshot budget')
        self._controller_snapshot = state
        self._controller_checkpoints += 1
        return state

    def checkpoint_full_state(self) -> tuple[bytes, bytes | None]:
        """Capture component and optional controller snapshots together.

        Both snapshots become visible only after both reads succeed; an
        unsupported controller is represented by None. If the second read
        fails, the previous pair is preserved and worker is discarded.
        This method is strictly control-thread-only.
        """
        if self._closed or self._worker is None:
            raise RuntimeError('No running VST3 worker to checkpoint')
        try:
            component = self._worker.snapshot_state()
            if not isinstance(component, bytes) or len(component) > 1024 * 1024:
                raise NativeChainError('VST3 state exceeds snapshot budget')
            try:
                controller = self._worker.snapshot_controller_state()
            except NotImplementedError:
                controller = None
            if controller is not None and (not isinstance(controller, bytes) or
                                           len(controller) > 1024 * 1024):
                raise NativeChainError('VST3 controller state exceeds snapshot budget')
        except Exception:
            self._faults += 1
            self._discard_worker()
            self._pending_gap = self.recovery_gap_blocks
            raise
        self._state_snapshot = component
        self._controller_snapshot = controller
        self._checkpoints += 1
        if controller is None:
            self._unsupported_controllers += 1
        else:
            self._controller_checkpoints += 1
        return component, controller

    def export_checkpoint(self, path, plugin_id: str) -> None:
        """Persist a previously captured coherent state pair (control thread)."""
        from .state_store import save_checkpoint
        if self._closed or self._state_snapshot is None:
            raise RuntimeError('No complete VST3 checkpoint available')
        save_checkpoint(path, plugin_id, self._state_snapshot, self._controller_snapshot)

    def import_checkpoint(self, path, plugin_id: str) -> None:
        """Stage validated state for the NEXT worker; never modify a live one."""
        from .state_store import load_checkpoint
        if self._closed or self._worker is not None:
            raise RuntimeError('Checkpoint import requires a stopped worker')
        component, controller = load_checkpoint(path, plugin_id)
        # Both assignments occur only once the ENTIRE blob is verified.
        self._state_snapshot, self._controller_snapshot = component, controller

    def clear_checkpoint(self) -> None:
        """Invalidate saved state before switching to a different VST3 class."""
        if self._closed:
            raise RuntimeError('Supervisor is closed')
        self._state_snapshot = None
        self._controller_snapshot = None

    def reset_session(self) -> None:
        """Control-thread seek/stop barrier: discard in-flight plugin state.

        Must not race with process(); the caller serializes seek and processing.
        A seek does not consume the fault-restart budget, and the next block
        always opens a new isolated plugin instance with a new epoch.
        """
        if self._closed:
            raise RuntimeError('Supervisor is closed')
        self._discard_worker()
        self._pending_gap = 0
        self._has_started = False
        self._disabled = False
        self._restarts = 0
        self._resets += 1

    def process(self, block: EventBlock) -> list[float]:
        """Return wet or dry, never replay a failed quantum after a fault.

        All validation happens BEFORE opening a worker and even while disabled.
        """
        from .stream_worker import prepare_event_batch
        prepare_event_batch((block,), self.channels)
        dry = list(block.pcm)
        if self._pending_gap:
            self._pending_gap -= 1
            self._deferred += 1
            self._dry += 1
            return dry
        if not self._ensure_worker():
            self._dry += 1
            return dry
        try:
            results = self._worker.process_event_batch((block,))
            if not isinstance(results, (list, tuple)) or len(results) != 1:
                raise NativeChainError('Worker returned an invalid block count')
            wet = results[0]
            if not isinstance(wet, (list, tuple)):
                raise NativeChainError('Worker returned an invalid PCM container')
            if len(wet) != len(dry):
                raise NativeChainError('Worker returned an incompatible PCM shape')
            # The IPC decoder rejects NaN/Inf, but enforce finite output for mock/adapters.
            import math
            if any(isinstance(x, bool) or not isinstance(x, (int, float)) or
                   not math.isfinite(x) or abs(x) > 16 for x in wet):
                raise NativeChainError('Worker returned invalid or out-of-range PCM')
            self._processed += 1
            return wet
        except Exception:
            # A third-party adapter may raise an unexpected Python exception
            # after partially advancing its DSP state. Contain it on the
            # supervisor thread: never replay that quantum, discard the child.
            # BaseException (KeyboardInterrupt/SystemExit) is not swallowed.
            self._faults += 1
            self._dry += 1
            self._discard_worker()
            self._pending_gap = self.recovery_gap_blocks
            if self._restarts >= self.max_restarts:
                self._disabled = True
            return dry

    def close(self) -> None:
        self._closed = True
        self._disabled = True
        self._discard_worker()
