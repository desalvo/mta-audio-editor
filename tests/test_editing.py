from app.models import Track, Clip, Project, Marker
from app.audio_engine import delete_range, delete_song_range, shift_track


def track():
    return Track(id="t", name="T", filename="x.wav", duration_ms=10000,
                 clips=[Clip(id="c", source_start_ms=0, source_end_ms=10000, timeline_start_ms=0)])


def test_delete_non_ripple_leaves_gap():
    t=track(); delete_range(t,2000,4000,False)
    assert len(t.clips)==2
    assert (t.clips[0].source_start_ms,t.clips[0].source_end_ms,t.clips[0].timeline_start_ms)==(0,2000,0)
    assert (t.clips[1].source_start_ms,t.clips[1].source_end_ms,t.clips[1].timeline_start_ms)==(4000,10000,4000)


def test_delete_ripple_closes_gap():
    t=track(); delete_range(t,2000,4000,True)
    assert t.clips[1].source_start_ms==4000
    assert t.clips[1].timeline_start_ms==2000


def test_song_delete_shifts_metadata():
    p=Project(id="p",title="x",tracks=[track()],markers=[Marker(time_ms=1000,label="a"),Marker(time_ms=5000,label="b")])
    delete_song_range(p,2000,4000)
    assert [m.time_ms for m in p.markers]==[1000,3000]
    assert p.tracks[0].clips[1].timeline_start_ms==2000


def test_negative_track_shift_trims_before_zero():
    t=track(); shift_track(t,-1500)
    assert t.clips[0].timeline_start_ms==0
    assert t.clips[0].source_start_ms==1500
