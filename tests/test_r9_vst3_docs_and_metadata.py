"""r9 documentation and native probe metadata regression checks."""
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import json
import fitz
from native.vst3_probe.probe import probe_plugin

ROOT=Path(__file__).resolve().parents[1]

def test_vst3_pdf_cover_uses_distinct_vst3_title():
    for lang in ('IT','EN'):
        a=fitz.open(ROOT/'app/docs'/f'MTA-Audio-Editor-User-Manual-{lang}.pdf')
        b=fitz.open(ROOT/'app/docs'/f'MTA-Audio-Editor-VST3-Manual-{lang}.pdf')
        assert len(b)>=2
        # Since r13 the VST3 cover deliberately uses a VST3-specific title,
        # while preserving the original manual's layout and page dimensions.
        assert a[0].rect == b[0].rect
        assert a[0].get_pixmap(matrix=fitz.Matrix(.5,.5)).samples != b[0].get_pixmap(matrix=fitz.Matrix(.5,.5)).samples
        assert 'VST3' in ''.join(page.get_text() for page in list(b)[1:])

def test_probe_deduplicates_and_scrubs_untrusted_classes(tmp_path):
    bundle=tmp_path/'test.vst3'; bundle.write_bytes(b'test')
    exe=tmp_path/'probe'; exe.write_bytes(b'test')
    cid='0123456789abcdef0123456789abcdef'
    data={'factory_export':True,'classes':[{'cid':cid,'name':'First','category':'Audio'}, {'cid':cid.upper(),'name':'Duplicate','category':'Audio'},{'cid':'a'*32,'name':'bad\x00label','category':'Audio'}]}
    with patch('native.vst3_probe.probe.validate_plugin_path',return_value=bundle),patch('native.vst3_probe.probe.resolve_module_binary',return_value=bundle),patch('native.vst3_probe.probe.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(data),stderr='')):
        result=probe_plugin(str(bundle),str(exe))
    assert result['classes']==[{'cid':cid,'name':'First','category':'Audio'}]
