"""Billing never silently activates just because indicative tariffs exist."""
from __future__ import annotations

import sqlite3

import pytest

from app import ai_billing
from app.ai_billing_profiles import canonical_cpu, canonical_gpu, local_gpu_model, suggested_prices


def test_suggested_costs_by_hardware():
    data = suggested_prices(cpu_model='AMD Ryzen AI MAX+ 395', gpu_model='AMD Radeon 8060S')
    assert data['suggested_micro_per_unit'] == {
        'cpu_seconds': 1, 'gpu_slot_seconds_estimated': 10, 'disk_gb_hours': 2,
    }
    assert data['billing_enabled_by_default'] is False
    assert canonical_gpu('AMD Radeon 8050S Graphics') == 'AMD Radeon 8050S'
    assert canonical_cpu('AMD Ryzen AI MAX+ 395 w/ Radeon 8060S') == 'AMD Ryzen AI MAX+ 395'
    assert suggested_prices(cpu_model='Unknown', gpu_model='Unknown')['suggested_micro_per_unit']['gpu_slot_seconds_estimated'] is None


def test_user_optin_defaults_disabled(monkeypatch, tmp_path):
    root = tmp_path / 'data'
    root.mkdir()
    monkeypatch.setenv('MTA_DATA_DIR', str(root))
    # auth.data_root() is configurable; avoid any production database.
    monkeypatch.setattr('app.auth.DATA_ROOT', root)
    db_file = root / 'auth.sqlite3'
    with sqlite3.connect(db_file) as c:
        c.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, active INTEGER NOT NULL)')
        c.executemany('INSERT INTO users(id,active) VALUES(?,?)', [(1,1),(2,1)])
    assert not ai_billing.user_billing_enabled(1)
    assert not ai_billing.user_billing_enabled(2)
    assert ai_billing.set_user_billing_enabled(1, True)['billing_enabled'] is True
    assert ai_billing.user_billing_enabled(1)
    assert not ai_billing.user_billing_enabled(2)
    ai_billing.set_user_billing_enabled(1, False)
    assert not ai_billing.user_billing_enabled(1)
    with pytest.raises(ValueError):
        ai_billing.set_user_billing_enabled(2, 1)


def test_radeon_780m_profile():
    data = suggested_prices(cpu_model='Unknown', gpu_model='AMD Radeon 780M Graphics')
    assert data['gpu_model'] == 'AMD Radeon 780M'
    assert data['suggested_micro_per_unit']['gpu_slot_seconds_estimated'] == 4
    assert data['billing_enabled_by_default'] is False

def test_gpu_autodiscovery_rocminfo_gpu_agent_only(monkeypatch):
    import subprocess
    from types import SimpleNamespace

    payload = """Agent 1
  Device Type: CPU
  Marketing Name: AMD Radeon 8060S
Agent 2
  Device Type: GPU
  Marketing Name: AMD Radeon 780M Graphics
"""
    monkeypatch.delenv('MTA_AI_GPU_MODEL', raising=False)
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=payload))
    assert local_gpu_model() == 'AMD Radeon 780M'
    assert suggested_prices(cpu_model='Unknown')['gpu_model'] == 'AMD Radeon 780M'

def test_gpu_autodiscovery_missing_or_ambiguous(monkeypatch):
    import subprocess
    from types import SimpleNamespace

    monkeypatch.delenv('MTA_AI_GPU_MODEL', raising=False)
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout='Agent 1\n  Device Type: CPU\n  Marketing Name: AMD Radeon 8060S'))
    assert local_gpu_model() == 'unknown'
    assert suggested_prices(cpu_model='Unknown')['suggested_micro_per_unit']['gpu_slot_seconds_estimated'] is None
    monkeypatch.setenv('MTA_AI_GPU_MODEL', 'Radeon 780M')
    assert local_gpu_model() == 'Radeon 780M'


def test_ryzen_9_7940hs_cpu_and_radeon_780m_gpu_profile():
    data = suggested_prices(
        cpu_model='AMD Ryzen 9 7940HS w/ Radeon 780M Graphics',
        gpu_model='AMD Radeon 780M Graphics',
    )
    assert data['cpu_model'] == 'AMD Ryzen 9 7940HS'
    assert data['gpu_model'] == 'AMD Radeon 780M'
    assert data['suggested_micro_per_unit'] == {
        'cpu_seconds': 1, 'gpu_slot_seconds_estimated': 4, 'disk_gb_hours': 2,
    }
    assert data['billing_enabled_by_default'] is False


def test_7940hs_cpu_name_matching_and_unknown_fallback():
    assert canonical_cpu('AMD Ryzen 9 7940HS with Radeon Graphics') == 'AMD Ryzen 9 7940HS'
    assert canonical_cpu('AMD Ryzen 7 7840HS') is None
    assert suggested_prices(cpu_model='AMD Ryzen 7 7840HS', gpu_model='unknown')[
        'suggested_micro_per_unit']['cpu_seconds'] is None
