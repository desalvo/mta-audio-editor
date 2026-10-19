"""Prepared native timeline queries, boundaries, seeks and atomic failures."""
import random
import pytest
from app import cpp_audio,cpp_timeline as tl
from test_r210_cpp_audio_engine import compiled_core as timeline_core  # noqa: F401


@pytest.fixture
def core(request,monkeypatch):
    compiled_core=request.getfixturevalue('timeline_core')
    monkeypatch.setenv('MTA_AUDIO_CORE_PATH',str(compiled_core));cpp_audio._load.cache_clear()
    return cpp_audio.runtime()


def tuples(slices):return [(x.clip,x.route,x.offset,x.source,x.frames) for x in slices]


def test_seek_exact_boundaries_source_offsets_and_plan_copy(core):
    clips=[(10,100,5,0),(15,200,8,0),(12,50,9,1)]
    with tl.Timeline(clips) as plan:
        clips[0]=(0,0,1,0)
        assert tuples(plan.query(8,10))==[(0,0,2,100,5),(1,0,7,200,3),(2,1,4,50,6)]
        assert tuples(plan.query(15,2))==[(1,0,0,200,2),(2,1,0,53,2)]
        assert tuples(plan.query(0,10))==[]
        assert tuples(plan.query(23,10))==[]
        assert tuples(plan.query(10,1))==[(0,0,0,100,1)]
    with pytest.raises(RuntimeError):plan.query(10,1)
    plan.close()


def test_invalid_overlaps_overflows_and_capacity_leave_output_unchanged(core):
    for clips in ([(0,0,10,0),(9,0,3,0)],[(0,0,0,0)],[(2**63-2,0,3,0)],[(0,0,1,64)]):
        with pytest.raises(ValueError):tl.Timeline(clips)
    with tl.Timeline([(0,0,100,0),(0,0,100,1)]) as plan:
        output=(tl.Slice*1)(tl.Slice(123,9,9,9,9));before=bytes(output)
        assert core.lib.mta_timeline_query(plan._handle,0,10,output,1)==-2
        assert bytes(output)==before
        assert core.lib.mta_timeline_query(plan._handle,2**63-1,10,output,1)==-1
        assert bytes(output)==before
        with pytest.raises(ValueError):plan.query(-1,1)


def test_random_access_queries_match_independent_interval_reference(core):
    rng=random.Random(210);clips=[]  # noqa: S311 -- reproducible audio schedule fuzzing
    for route in range(8):
        pos=0
        for _ in range(100):
            pos+=rng.randrange(0,30);length=rng.randrange(1,100)
            clips.append((pos,rng.randrange(10000),length,route));pos+=length
    with tl.Timeline(clips) as plan:
        for _ in range(500):
            pos=rng.randrange(9000);n=rng.randrange(1,4097);expected=[]
            for i,(start,source,length,route) in enumerate(clips):
                a,b=max(pos,start),min(pos+n,start+length)
                if a<b:expected.append((i,route,a-pos,source+a-start,b-a))
            assert tuples(plan.query(pos,n))==expected
