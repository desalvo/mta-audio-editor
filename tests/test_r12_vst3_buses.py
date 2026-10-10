"""r12 bus information validation and release documentation."""
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import json
from native.vst3_probe.probe import probe_plugin

def test_bus_metadata_is_bounded_and_opt_in(tmp_path):
    plugin = tmp_path / 'test.vst3'; plugin.write_bytes(b'x')
    executable = tmp_path / 'probe'; executable.write_bytes(b'x')
    buses = [{'media':'audio','direction':'input','index':0,'channels':2,'bus_type':0}, {'media':'event','direction':'output','index':1,'channels':1,'bus_type':1}, {'media':'audio','direction':'input','index':-1,'channels':-5,'bus_type':0}]
    data = {'factory_export':True,'buses':buses}
    with patch('native.vst3_probe.probe.validate_plugin_path', return_value=plugin), patch('native.vst3_probe.probe.resolve_module_binary',return_value=plugin), patch('native.vst3_probe.probe.subprocess.run', return_value=SimpleNamespace(returncode=0,stdout=json.dumps(data),stderr='')):
        assert len(probe_plugin(str(plugin),str(executable),instantiate_cid='a'*32,lifecycle=True)['buses']) == 2
        assert probe_plugin(str(plugin),str(executable))['buses'] == []

def test_license_sections_are_license_only():
    for lang in ('IT','EN'):
        text=(Path('docs')/f'VST3_USER_GUIDE_{lang}.md').read_text()
        section=text.split('## Licenze e distribuzione' if lang=='IT' else '## Licenses and redistribution')[1].split('### r10:')[0]
        assert 'EUPL-1.2' in section and 'MIT' in section and 'GPL-3.0' in section
        assert 'Consult' not in section and 'Consultare' not in section
