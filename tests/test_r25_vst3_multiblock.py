"""r25: deterministic offline multiblock diagnostic contract."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from native.vst3_probe.probe import probe_plugin

ROOT = Path(__file__).resolve().parents[1]


def test_multiblock_source_contract():
    source = (ROOT / 'native/vst3_probe/main.cpp').read_text()
    assert 'renderPcm ? static_cast<int>((pcmFrames + 511) / 512) : 128' in source
    assert 'for (int block = 0; renderStream || block < kBlocks; ++block)' in source
    assert 'offlineBlocksProcessed' in source
    assert 'offlineInputEnergy' in source
    assert 'offlineOutputEnergy' in source
    assert 'offlineOutputPeak' in source
    assert 'buses[i].silenceFlags = 0' in source
    assert 'native_host_ready' in source


def test_multiblock_payload_validation(tmp_path):
    binary = tmp_path / 'demo.vst3'
    binary.write_bytes(b'plugin')
    payload = {'factory_export': True, 'offline_blocks_processed': 128,
               'offline_input_energy': 42.0, 'offline_output_energy': 23.0,
               'offline_output_peak': 0.5}
    with patch('native.vst3_probe.probe.validate_plugin_path', return_value=binary), \
         patch('native.vst3_probe.probe.resolve_module_binary', return_value=binary), \
         patch('native.vst3_probe.probe.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload))):
        output = probe_plugin(str(binary), str(binary), instantiate_cid='a' * 32, offline=True)
    assert output['offline_blocks_processed'] == 128
    assert output['offline_output_energy'] == 23.0
    assert output['native_host_ready'] is False


def test_reject_untrusted_nonfinite_and_overbound_metrics(tmp_path):
    binary = tmp_path / 'demo.vst3'
    binary.write_bytes(b'plugin')
    payload = {'factory_export': True, 'offline_blocks_processed': 200,
               'offline_input_energy': float('nan'),
               'offline_output_energy': -4,
               'offline_output_peak': 1e30}
    with patch('native.vst3_probe.probe.validate_plugin_path', return_value=binary), \
         patch('native.vst3_probe.probe.resolve_module_binary', return_value=binary), \
         patch('native.vst3_probe.probe.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload))):
        output = probe_plugin(str(binary), str(binary), instantiate_cid='a' * 32, offline=True)
    assert output['offline_blocks_processed'] is None
    assert 'offline_input_energy' not in output
    assert 'offline_output_energy' not in output
    assert 'offline_output_peak' not in output
