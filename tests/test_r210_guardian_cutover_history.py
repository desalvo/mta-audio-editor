"""Real builtin execution/guardian history through the authenticated cutover API."""
from pathlib import Path
import sys
import threading

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
        body = begin(client, target=target, identifier='guardian-roundtrip-' + target, retry_lease_seconds=3)
        response = client.post(BASE, headers=HEADERS, json=body)
        assert response.status_code == 200, response.text
        assert client.post(BASE, headers=HEADERS, json=body).status_code == 200
    with auth.db() as con:
        assert [tuple(r) for r in con.execute('SELECT * FROM worker_cgroup_receipts')] == original


def test_preview_retry_waits_for_real_reader_to_release_lease(ready):
    client, _, _ = ready
    acquired, release = threading.Event(), threading.Event()
    errors = []
    def holder():
        try:
            with auth.db():
                acquired.set()
                if not release.wait(5):
                    raise AssertionError('reader lease was not released')
        except BaseException as exc:
            errors.append(exc)
            acquired.set()
    thread = threading.Thread(target=holder, daemon=True)
    thread.start()
    try:
        assert acquired.wait(5) and not errors
        responses = []
        class ObservedClient:
            def get(self, *args, **kwargs):
                response = client.get(*args, **kwargs)
                responses.append(response.status_code)
                if response.status_code == 409:
                    release.set()
                return response
        body = begin(ObservedClient(), identifier='guardian-retry-real-lease', retry_lease_seconds=3)
        assert responses[0] == 409 and responses[-1] == 200
        assert client.post(BASE, headers=HEADERS, json=body).status_code == 200
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive() and not errors


def test_preview_retry_never_authorizes_a_persistent_lease(ready):
    client, _, _ = ready
    with auth.db():
        with pytest.raises(AssertionError, match='Service activity or another cutover holds the lease'):
            begin(client, identifier='guardian-held-lease', retry_lease_seconds=.1)


def test_preview_retry_does_not_retry_other_readiness_conflicts():
    calls = []
    class Response:
        status_code = 409
        text = 'other readiness conflict'
        def json(self):
            return {'detail': self.text}
    class Client:
        def get(self, *args, **kwargs):
            calls.append(1)
            return Response()
    with pytest.raises(AssertionError, match='other readiness conflict'):
        begin(Client(), retry_lease_seconds=3)
    assert len(calls) == 1


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
