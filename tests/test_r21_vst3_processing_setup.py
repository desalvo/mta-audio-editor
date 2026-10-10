"""r21: isolated, opt-in processor negotiation safeguards."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from native.vst3_probe.probe import probe_plugin

ROOT = Path(__file__).resolve().parents[1]
CID = '0123456789abcdef0123456789abcdef'


def test_configuration_requires_explicit_cid():
    with pytest.raises(ValueError):
        probe_plugin('missing.vst3', 'missing', configure=True)


def test_configuration_is_explicit_and_safe():
    code = (ROOT / 'native/vst3_probe/main.cpp').read_text()
    assert '"--configure"' in code
    assert 'processor->setupProcessing(setup)' in code
    assert 'setup.maxSamplesPerBlock = 512' in code
    assert 'setup.sampleRate = static_cast<double>(pcmSampleRate)' in code
    assert 'processor->setupProcessing(setup)' in code
    assert 'processor->setActive(' not in code
    assert 'processor->process(data)' in code
    assert 'if (offline && processor && processingSetupSucceeded)' in code
    assert 'native_host_ready' in code and 'false' in code


def test_configure_propagates_safe_metadata():
    payload = {'factory_export': True, 'classes': [], 'processing_setup_requested': True,
               'processing_setup_succeeded': True, 'processing_sample_rate': 48000,
               'processing_block_size': 512, 'processing_sample_size': 32}
    with patch('native.vst3_probe.probe.validate_plugin_path', return_value=Path('/opt/test.vst3')):
        with patch('native.vst3_probe.probe.resolve_module_binary', return_value=Path('/opt/test.vst3')):
            with patch('pathlib.Path.is_file', return_value=True):
                with patch('subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=__import__('json').dumps(payload)) ) as run:
                    result = probe_plugin('/opt/test.vst3', '/opt/probe', instantiate_cid=CID, configure=True)
    assert run.call_args.args[0][-2:] == ['--configure', CID]
    assert result['processing_setup_succeeded'] is True
    assert result['native_host_ready'] is False


def test_mobile_revision_matches_release():
    revision = (ROOT / 'REVISION').read_text().strip()
    android = (ROOT / 'mobile/android/app/build.gradle.kts').read_text()
    ios = (ROOT / 'mobile/ios/MTAEditorMobile/Info.plist').read_text()
    assert f'versionCode = {30000 + int(revision)}' in android
    assert f'MTA_REVISION", "\\\"{revision}\\\""' in android
    assert f'<key>MTAEditorRevision</key><string>{revision}</string>' in ios
