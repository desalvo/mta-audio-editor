from app.models import Project, Track

def test_project_defaults():
    p=Project(id="x",title="Song")
    assert p.target=="MTA8" and p.bpm==120

def test_track():
    t=Track(id="1",name="Drums",type="drums",filename="d.mp3")
    assert not t.mute
