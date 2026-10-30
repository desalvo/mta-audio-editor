"""Real builtin execution/guardian history through the authenticated cutover API."""
from pathlib import Path
import sys

import pytest

from app import auth
from test_r210_admin_cutover_e2e import ready as ready, begin, BASE, HEADERS  # noqa: F401
from test_r210_subscriptions import account as account  # noqa: F401


@pytest.fixture
def completed(ready, monkeypatch):
    from app import ai_metering_agent, ai_studio_adapter
    from app.studio_score import Score
    from app.music_interchange import MusicResult, MusicPart
    from app.models import MidiNote
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_VOCAL_HARMONY_EXECUTABLE', str(Path(ai_studio_adapter.__file__).resolve()))
    monkeypatch.setenv('MTA_AI_WORKER_VOCAL_HARMONY_PYTHON', sys.executable)
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT', raising=False)
    score = Score(music=MusicResult(parts=[MusicPart(id='melody', name='Melody', notes=[
        MidiNote(id='n', pitch=60, start_ms=0, duration_ms=500)])])).model_dump_json().encode()
    payload, meta = ai_metering_agent.execute_registered_worker(ready[1], 'vocal-harmony', {}, source_json=score, timeout_seconds=30)
    assert payload and meta['usage']['cpu_seconds'] > 0
    with auth.db() as con:
        assert con.execute('SELECT count(*) FROM worker_cgroup_receipts').fetchone()[0] > 0
    return ready


def test_closed_intact_guardian_history_allows_two_way_cutover_and_replay(completed):
    client, _, _ = completed
    with auth.db() as con:
        original = [tuple(r) for r in con.execute('SELECT * FROM worker_cgroup_receipts')]
    for target in ('NON_COMMERCIAL', 'COMMERCIAL'):
        body = begin(client, target=target, identifier='guardian-roundtrip-' + target)
        response = client.post(BASE, headers=HEADERS, json=body)
        assert response.status_code == 200, response.text
        assert client.post(BASE, headers=HEADERS, json=body).status_code == 200
    with auth.db() as con:
        assert [tuple(r) for r in con.execute('SELECT * FROM worker_cgroup_receipts')] == original


@pytest.mark.parametrize('damage', ['missing-receipt', 'bad-receipt', 'bad-scope', 'missing-journal', 'count', 'open-operation', 'uncertain-job'])
def test_history_or_obligation_damage_still_blocks_cutover(completed, damage):
    client, _, _ = completed
    # Deliberate offline corruption, bypassing immutable-journal triggers only
    # inside this test. The product has no equivalent mutation switch.
    with auth.db() as con:
        for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall():
            con.execute('DROP TRIGGER "' + name.replace('"', '""') + '"')
        if damage == 'missing-receipt': con.execute('DELETE FROM worker_cgroup_receipts')
        elif damage == 'bad-receipt': con.execute("UPDATE worker_cgroup_receipts SET evidence_json='{}'")
        elif damage == 'bad-scope': con.execute("UPDATE worker_cgroup_scopes SET binding_json='{}'")
        elif damage == 'missing-journal': con.execute('DROP TABLE worker_cgroup_receipts')
        elif damage == 'count': con.execute('UPDATE ai_compute_jobs SET worker_scope_count=worker_scope_count+1')
        elif damage == 'open-operation': con.execute("UPDATE regime_fence_operations SET status='open'")
        else: con.execute("UPDATE ai_compute_jobs SET status='running'")
    response = client.get(BASE + '/preview', params={'target': 'NON_COMMERCIAL'})
    assert response.status_code == 409, response.text
