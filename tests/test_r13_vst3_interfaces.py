from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import json
from native.vst3_probe.probe import probe_plugin

def test_r13_interface_discovery_diagnostic(tmp_path):
    plugin=tmp_path/'sample.vst3';plugin.write_bytes(b'a')
    exe=tmp_path/'probe';exe.write_bytes(b'b')
    payload={'factory_export':True,'audio_processor_queried':True,'audio_processor_available':True,'edit_controller_queried':True,'edit_controller_available':False}
    with patch('native.vst3_probe.probe.validate_plugin_path',return_value=plugin), patch('native.vst3_probe.probe.resolve_module_binary',return_value=plugin), patch('native.vst3_probe.probe.subprocess.run',return_value=SimpleNamespace(returncode=0,stderr='',stdout=json.dumps(payload))):
        result=probe_plugin(str(plugin),str(exe),instantiate_cid='f'*32)
        assert result['audio_processor_available'] is True
        assert result['edit_controller_available'] is False
        assert result['native_host_ready'] is False
        assert probe_plugin(str(plugin),str(exe))['audio_processor_available'] is False

def test_r13_cover_title_and_revision():
    import fitz
    for lang in ('IT','EN'):
        p=Path('app/docs')/f'MTA-Audio-Editor-VST3-Manual-{lang}.pdf'
        with fitz.open(p) as doc:
            assert len(doc)>1
            text=doc[0].get_text()
            assert 'VST3' in text and '0.3.0-r13' in text
