from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_individual_voicebank_ui_submission():
    code = (ROOT / 'app/static/ai_studio.js').read_text()
    assert 'data-singer-bank' in code
    assert 'request.settings.voice_banks=chosen.map(id=>byId[id])' in code
    assert 'Missing singer voicebank' in code


def test_source_isolation_in_studio_worker():
    code = (ROOT / 'app/studio_jobs.py').read_text()
    assert "source_settings['voicebank']=source_settings.pop('voice_banks')[index]" in code
    assert "if cfg.voice_banks and len(cfg.voice_banks)!=len(tracks)" in code
    assert "for voice in (cfg.voice_banks or [cfg.voicebank]):bank(voice)" in code
