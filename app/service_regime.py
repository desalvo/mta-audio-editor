"""Fail-closed persistent service-regime selection, separate from hardware metering.

Changing the setting here does not yet migrate billing or activate commercial
features. Consumers MUST check the transition gate before any mode switch.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Regime(StrEnum):
    NON_COMMERCIAL = "NON_COMMERCIAL"
    COMMERCIAL = "COMMERCIAL"


class RegimeError(ValueError):
    pass


@dataclass(frozen=True)
class RegimeState:
    regime: Regime
    revision: int = 0

    def as_dict(self) -> dict:
        return {"regime": self.regime.value, "revision": self.revision}


def read_regime(path: Path) -> RegimeState:
    """No configuration means non-commercial; damaged configuration fails closed."""
    path = Path(path)
    if path.is_symlink():
        raise RegimeError("Symlink configuration refused")
    if not path.exists():
        return RegimeState(Regime.NON_COMMERCIAL)
    if not path.is_file() or path.stat().st_size > 4096:
        raise RegimeError("Unsafe regime configuration")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or set(record) != {"regime", "revision"}:
            raise ValueError("Invalid configuration fields")
        if type(record["revision"]) is not int or record["revision"] < 0:
            raise ValueError("Invalid revision")
        return RegimeState(Regime(record["regime"]), record["revision"])
    except (OSError, ValueError, TypeError) as exc:
        raise RegimeError("Invalid service regime configuration") from exc


def write_initial_noncommercial(path: Path) -> RegimeState:
    """Provision a default only; never overwrite existing configuration."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = RegimeState(Regime.NON_COMMERCIAL)
    data = json.dumps(state.as_dict(), sort_keys=True).encode()
    fd = None
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as output:
            fd = None
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    except FileExistsError:
        return read_regime(path)
    finally:
        if fd is not None:
            os.close(fd)
    return state


def plan_transition(current: RegimeState, target: Regime, *,
                    outstanding_periods: int = 0, active_jobs: int = 0,
                    subscriptions: int = 0, credit_balances: int = 0,
                    unverified_models: int = 0) -> dict:
    """Read-only admission plan; does not change billing, ledger or regime."""
    target = Regime(target)
    counts = {"outstanding_periods": outstanding_periods, "active_jobs": active_jobs,
              "subscriptions": subscriptions, "credit_balances": credit_balances,
              "unverified_models": unverified_models}
    if any(type(n) is not int or n < 0 for n in counts.values()):
        raise RegimeError("Transition counts must be non-negative integers")
    blockers = [name for name, count in counts.items() if count > 0]
    if current.regime == target:
        blockers = []
    return {"from": current.regime.value, "to": target.value,
            "ready": not blockers, "blockers": blockers,
            "requires_explicit_confirmation": current.regime != target,
            "mutates_usage_ledger": False}


# Shared admission gate: called at the domain service boundary, not just by UI.
def current_regime() -> Regime:
    """Read the effective regime; never expose commercial features mid-cutover.

    Pre-fence noncommercial installations retain their default. A commercial
    installation must have an initialized, matching SQLite fence epoch.
    """
    import sqlite3
    from . import auth
    mirror = read_regime(auth.data_root() / "service-regime.json")
    db_file = auth.db_path()
    if not db_file.exists():
        if mirror.regime == Regime.COMMERCIAL:
            raise RegimeError("Commercial regime requires a matching initialized fence")
        return mirror.regime
    connection = sqlite3.connect(f"{db_file.resolve().as_uri()}?mode=ro", uri=True)
    try:
        table = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='regime_fence_state'").fetchone()
        if table is None:
            if mirror.regime == Regime.COMMERCIAL:
                raise RegimeError("Commercial regime requires a matching initialized fence")
            return mirror.regime
        row = connection.execute("SELECT regime, revision, transitioning FROM regime_fence_state WHERE singleton=1").fetchone()
        if row is None or row[2] or (row[0], row[1]) != (mirror.regime.value, mirror.revision):
            raise RegimeError("Service regime epoch mismatch or transition in progress")
        return mirror.regime
    except sqlite3.DatabaseError as exc:
        raise RegimeError("Unable to verify service regime fence") from exc
    finally:
        connection.close()


def require_commercial(operation: str = "commercial operation") -> None:
    if current_regime() != Regime.COMMERCIAL:
        raise RegimeError(f"{operation} is disabled in NON_COMMERCIAL mode")


def commercial_allowed() -> bool:
    return current_regime() == Regime.COMMERCIAL


def audit_transition_database(connection, target: Regime, *, path: Path) -> dict:
    """Conservative, read-only transition assessment of legacy monetary state.

    Never assume that an absent/migrating schema means a clean production DB.
    An unknown economic table is a blocker until an explicit migration exists.
    """
    current = read_regime(path)
    target = Regime(target)
    from .regime_reconciliation import inventory
    detailed = inventory(connection)
    counts={name:item['count'] for name,item in detailed.items()}
    # Reconciled historic records must NOT simply disappear or be erased.
    # A dedicated migration must explicitly account for each table before enabling switching.
    blockers = [key for key, value in counts.items() if value is None or value > 0]
    return {
        'from': current.regime.value, 'to': target.value,
        'revision': current.revision,
        'counts': counts, 'reconciliation_inventory': detailed, 'blockers': blockers,
        'ready': current.regime == target,
        'transition_enabled': False,
        'requires_accounting_migration': current.regime != target,
        'mutates_usage_ledger': False,
    }
