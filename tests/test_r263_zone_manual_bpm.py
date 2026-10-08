from pathlib import Path
from app.models import Marker, Project
from app.main import _metronome_manual_for_zone, _metronome_zone_boundaries

ROOT=Path(__file__).resolve().parents[1]

def test_marker_ids_stable_after_serialization():
    marker=Marker(time_ms=1000,label='Intro')
    assert Marker.model_validate(marker.model_dump()).id==marker.id

def test_manual_zone_survives_marker_timestamp_changes():
    left=Marker(time_ms=1000,label='Verse')
    right=Marker(time_ms=6000,label='Chorus')
    project=Project(id='test-project',title='A',markers=[left,right])
    points=_metronome_zone_boundaries(project,10000)
    key=f'{left.id}|{right.id}'
    project.metronome_manual_zone_bpms[key]=112.5
    right.time_ms=7000
    points2=_metronome_zone_boundaries(project,10000)
    assert points[1][1]==points2[1][1]
    assert _metronome_manual_for_zone(project,left.id,right.id)==112.5

def test_manual_zone_can_use_single_surviving_boundary():
    project=Project(id='test-project',title='A',metronome_manual_zone_bpms={'left|right':96.0})
    assert _metronome_manual_for_zone(project,'left','newright')==96.0
    assert _metronome_manual_for_zone(project,'newleft','newright') is None

def test_ui_exposes_zone_edit_and_auto_context_menu():
    source=(ROOT/'app/static/app.js').read_text()
    assert 'function openMetronomeBpmContext' in source
    assert 'function editMetronomeZoneBpm' in source
    assert 'metronome-zone-bpm?' in source
