"""Native historical request pagination is bounded and read-only."""
from pathlib import Path

def test_history_supports_more_than_first_fifty_requests():
    src=(Path(__file__).resolve().parents[1]/'app/static/app.js').read_text()
    section=src.split('let nativeRemoteHistoryGeneration=0;',1)[1].split('async function downloadNativeDiscoveredArtifact(',1)[0]
    assert 'offset=${offset}' in section
    assert 'next<total' in section
    assert 'appendNativeRemoteHistory(kind,next,section,generation)' in section
    assert 'generation!==nativeRemoteHistoryGeneration' in section
    assert 'textContent' in section
    assert 'method:\'POST\'' not in section
    assert '/import-' not in section
