"""Project metadata, generated tracks and annotation mutations use shared lock."""
import inspect
import pytest
from app import main

@pytest.mark.parametrize('name', [
    'project_migrate_flac', 'project_put', 'reset_project_lyrics',
    'reset_project_chords', 'api_project_rights_records',
    'create_metronome_track', 'set_metronome_zone_bpm',
    'refresh_metronome_at_playhead', 'shift_adaptive_metronome',
    'set_transport_time_mode', 'create_chords_track', 'refresh_chords_track',
])
def test_additional_mutations_are_guarded_and_preserve_signature(name):
    endpoint = getattr(main, name)
    assert hasattr(endpoint, '__wrapped__')
    assert 'pid' in inspect.signature(endpoint).parameters
    assert getattr(endpoint, '__signature__', None) is None or 'pid' in inspect.signature(endpoint).parameters
