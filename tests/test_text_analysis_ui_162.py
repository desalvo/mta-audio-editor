from pathlib import Path
import importlib.machinery
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def test_whisper_turbo_is_default_everywhere(tmp_path,monkeypatch):
    from app import ai_models,auth,music_text,model_license_policy
    monkeypatch.delenv('MTA_LYRICS_WHISPER_MODEL',raising=False)
    monkeypatch.setenv('MTA_LYRICS_MODEL_DIR',str(tmp_path/'cache'))
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'auth')
    monkeypatch.setattr(model_license_policy,'_path',lambda:tmp_path/'empty-policy.json')
    monkeypatch.setattr(music_text,'native_ai_device',lambda:'cpu')
    loaded=[]
    def load_model(name,**kwargs):
        loaded.append(name)
        return SimpleNamespace(transcribe=lambda *a,**kw:{'segments':[{'start':0,'end':1,'text':'Fixture'}]})
    whisper=SimpleNamespace(load_model=load_model,__spec__=importlib.machinery.ModuleSpec('whisper',loader=None))
    monkeypatch.setitem(sys.modules,'whisper',whisper)
    direct=music_text.extract_lyrics(tmp_path/'fixture.wav')
    progressive=music_text.extract_lyrics_progressive(tmp_path/'fixture.wav')
    assert [line.text for line in direct]==[line.text for line in progressive]==['Fixture']
    assert loaded==['turbo','turbo']
    assert ai_models.LYRICS_DEFAULT_MODEL=='turbo'
    assert ai_models.lyrics_catalog()['default_model']=='turbo'
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "default_model||'turbo'" in js


def test_chord_job_does_not_expose_inline_chords():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    music = (ROOT / "app/music_text.py").read_text(encoding="utf-8")
    assert 'partial={"kind":"chords","items":[]}' in main
    assert "Multi-stage chord extraction" in music


def test_analysis_dialogs_warn_about_long_processing_time():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "l’estrazione può richiedere molto tempo" in js
    assert "l’analisi degli accordi può richiedere molto tempo" in js
    assert "Nota sui tempi di elaborazione" in js


def test_native_hides_open_local_project_action():
    html = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
    css = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
    assert 'id="openLocalProjectBtn"' in html and 'onclick="openLocalProject()" hidden' in html
    assert '.native-single-user .web-project-action{display:none!important}' in css
