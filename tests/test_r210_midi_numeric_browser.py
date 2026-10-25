"""Isolate the MIDI editor portion of live VST acceptance on the real page/API."""
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from app import main,storage
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_legal_documents import cookie


def test_actual_page_saves_numeric_note_edits(account,monkeypatch,chromium_capability):
    from playwright.sync_api import sync_playwright
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    monkeypatch.setattr(main,'check_basic_auth',lambda _:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    project=storage.create_project('MIDI numeric acceptance',target='DAW_MIDI',owner_user_id=account)
    client=TestClient(main.app);client.cookies.update(cookie(account))
    def serve(route):
        url=urlsplit(route.request.url)
        assert url.hostname=='mta.test'
        result=client.request(route.request.method,url.path+('?' +url.query if url.query else ''),
            headers={'X-MTA-Request':'1','Content-Type':'application/json'},content=route.request.post_data)
        route.fulfill(status=result.status_code,content_type=result.headers.get('content-type','application/json'),body=result.content)
    with sync_playwright() as api:
        browser=api.chromium.launch(headless=True,args=['--no-sandbox'])
        page=browser.new_page();page.route('**/*',serve);page.goto('https://mta.test/')
        page.wait_for_function('typeof window.createMidiTrack==="function"')
        page.evaluate('async id=>{current=await api(`/api/projects/${id}`);render();await createMidiTrack()}',project.id)
        page.locator('#midiRoll').wait_for()
        page.locator('#midiRoll').dblclick(position={'x':120,'y':1076})
        for key,value in [('pitch','64'),('start_ms','0'),('duration_ms','1500')]:
            field=page.locator(f'#midiNoteFields input[data-key="{key}"]')
            field.fill(value);field.dispatch_event('change')
        assert page.evaluate('mtaMidiEditor.getDraft().midi_notes[0].duration_ms')==1500
        with page.expect_response(lambda r:'/midi/' in r.url and r.request.method=='PUT') as saved:
            page.locator('#midiSave').click()
        assert saved.value.status==200,saved.value.text()
        notes=saved.value.json()['tracks'][-1]['midi_notes']
        assert any(n['pitch']==64 and n['duration_ms']==1500 for n in notes),notes
        page.wait_for_function('current.tracks.some(t=>t.kind==="midi"&&t.midi_notes.some(n=>n.pitch===64&&n.duration_ms===1500))')
        stored=storage.load_project(project.id).tracks[-1].midi_notes
        assert any(n.pitch==64 and n.duration_ms==1500 for n in stored)
        browser.close()
