"""Twenty targeted checks for ledger-fence admission semantics."""
import json
import sqlite3

import pytest

from app.regime_job_fence import enroll_metered_job, settle_metered_job
from app.regime_operation_fence import FenceBlocked, begin_transition, inspect


@pytest.mark.parametrize('regime,revision,case', [
    (r, rev, case)
    for r in ('NON_COMMERCIAL', 'COMMERCIAL')
    for rev in (0, 1)
    for case in ('admit', 'duplicate', 'settle', 'block-transition', 'mismatch')
])
def test_metered_job_fence_regimes(tmp_path, monkeypatch, regime, revision, case):
    monkeypatch.setattr('app.regime_job_fence.auth.data_root', lambda: tmp_path)
    (tmp_path / 'service-regime.json').write_text(json.dumps({'regime': regime, 'revision': revision}))
    c = sqlite3.connect(':memory:', isolation_level=None)
    c.execute('BEGIN IMMEDIATE')
    if revision:
        # Simulate an earlier successful transition having updated the fence.
        from app.regime_operation_fence import initialize
        initialize(c, initial_regime=regime)
        c.execute('UPDATE regime_fence_state SET revision=?', (revision,))
    if case == 'mismatch':
        from app.regime_operation_fence import initialize
        initialize(c, initial_regime=regime)
        c.execute('UPDATE regime_fence_state SET regime=?', (
            'COMMERCIAL' if regime == 'NON_COMMERCIAL' else 'NON_COMMERCIAL',))
        with pytest.raises(FenceBlocked):
            enroll_metered_job(c, 'j-1')
        c.rollback()
        return
    receipt = enroll_metered_job(c, 'j-1')
    assert receipt['regime'] == regime and receipt['revision'] == revision
    if case == 'duplicate':
        assert enroll_metered_job(c, 'j-1')['operation_id'] == receipt['operation_id']
        assert inspect(c)['open_by_kind']['job'] == 1
    if case == 'settle':
        settle_metered_job(c, 'j-1')
        settle_metered_job(c, 'j-1')
        assert inspect(c)['open_by_kind']['job'] == 0
    if case == 'block-transition':
        with pytest.raises(FenceBlocked, match='unsettled'):
            begin_transition(c, expected_revision=revision, target=(
                'COMMERCIAL' if regime == 'NON_COMMERCIAL' else 'NON_COMMERCIAL'))
    c.commit()
