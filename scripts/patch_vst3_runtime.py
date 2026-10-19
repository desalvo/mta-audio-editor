"""Apply a checked, minimal host-clock extension to an immutable upstream tree.

No vendor source is stored in MTA. Reapplying to the same clean pinned tree is
idempotent; an unexpected upstream layout fails the build.
"""
from pathlib import Path
import shutil

UPSTREAM='05e8f0b3c4851e77485d7e842dc0355b44106471'
ABI=2


def patch(root):
    root=Path(root)
    path=root/'pedalboard/ExternalPlugin.h';text=path.read_text()
    if 'MTA_HOST_TRANSPORT_ABI_2' in text:
        inputs=[('MtaHostTransport.h',root/'pedalboard/MtaHostTransport.h'),('MtaSidechainMethods.h',root/'pedalboard/MtaSidechainMethods.h'),('MtaUmpEvents.inc',root/'JUCE/modules/juce_audio_processors/format_types/MtaUmpEvents.inc')]
        for name,target in inputs:
            if not target.is_file() or target.read_bytes()!=(Path(__file__).resolve().parents[1]/'native/host_transport'/name).read_bytes():raise ValueError('Stale explicit VST host source: provide a clean pinned tree')
        return
    def replace(old,new,count=1):
        nonlocal text
        if text.count(old)!=count:raise ValueError('Pinned VST host source layout changed: '+old[:70])
        text=text.replace(old,new)
    replace('namespace Pedalboard {','#include "MtaHostTransport.h"\n// MTA_HOST_TRANSPORT_ABI_2\nnamespace Pedalboard {')
    replace('    pluginInstance->setStateInformation(savedState.getData(),','    pluginInstance->setPlayHead(&mtaTransport);\n    pluginInstance->setStateInformation(savedState.getData(),')
    replace('      pluginInstance->processBlock(audioBuffer, emptyMidiBuffer);','      pluginInstance->processBlock(audioBuffer, emptyMidiBuffer);\n      mtaTransport.advance(static_cast<int>(outputBlock.getNumSamples()));')
    replace('        pluginInstance->processBlock(audioChunk, midiChunk);','        pluginInstance->processBlock(audioChunk, midiChunk);\n        mtaTransport.advance(static_cast<int>(chunkSampleCount));')
    replace('  long samplesProvided = 0;',' public:\n  MtaHostTransport mtaTransport;\n#include "MtaSidechainMethods.h"\n  long samplesProvided = 0;')
    marker='      .def("_get_parameter",\n           &ExternalPlugin<juce::PatchedVST3PluginFormat>::getParameter,'
    replace(marker,'''      .def("_mta_process_sidechain", &ExternalPlugin<juce::PatchedVST3PluginFormat>::mtaProcessSidechain,py::arg("audio"),py::arg("sidechain"),py::arg("sample_rate"),py::arg("bus")=1)
      .def_property_readonly("_mta_sidechain_inputs", &ExternalPlugin<juce::PatchedVST3PluginFormat>::mtaSidechainBuses)
      .def("_mta_set_musical_position", [](ExternalPlugin<juce::PatchedVST3PluginFormat>& p,double ppq,double bar){p.mtaTransport.musical(ppq,bar);})
      .def("_mta_set_transport", [](ExternalPlugin<juce::PatchedVST3PluginFormat>& p,
          double bpm,int n,int d,long long sample,double rate,bool playing,
          bool looping,double loopStart,double loopEnd) {
            p.mtaTransport.set(bpm,n,d,sample,rate,playing,looping,loopStart,loopEnd);
          }, py::arg("bpm"),py::arg("numerator"),py::arg("denominator"),
          py::arg("sample"),py::arg("rate"),py::arg("playing"),
          py::arg("looping")=false,py::arg("loop_start")=0.,py::arg("loop_end")=0.)
      .def_property_readonly("_mta_transport", [](ExternalPlugin<juce::PatchedVST3PluginFormat>& p) {
          auto s=p.mtaTransport.snapshot();py::dict result;
          result["abi"]=2;result["bpm"]=s.bpm;result["sample"]=s.timeInSamples;
          result["ppq"]=s.ppqPosition;result["bar_start"]=s.ppqPositionOfLastBarStart;
          result["numerator"]=s.timeSigNumerator;result["denominator"]=s.timeSigDenominator;
          result["playing"]=s.isPlaying;result["looping"]=s.isLooping;
          return result;
        })
'''+marker)
    shutil.copy2(Path(__file__).resolve().parents[1]/'native/host_transport/MtaHostTransport.h',root/'pedalboard/MtaHostTransport.h')
    shutil.copy2(Path(__file__).resolve().parents[1]/'native/host_transport/MtaSidechainMethods.h',root/'pedalboard/MtaSidechainMethods.h')
    path.write_text(text)
    common=root/'JUCE/modules/juce_audio_processors/format_types/juce_VST3Common.h'
    source=common.read_bytes();needle=b'            auto msg = metadata.getMessage();'
    if source.count(needle)!=1:raise ValueError('Pinned JUCE MIDI event converter changed')
    eol=b'\r\n' if b'\r\n' in source else b'\n'
    common.write_bytes(source.replace(needle,needle+eol+b'            #include "MtaUmpEvents.inc"'))
    shutil.copy2(Path(__file__).resolve().parents[1]/'native/host_transport/MtaUmpEvents.inc',common.parent/'MtaUmpEvents.inc')
    # Keep the application revision untouched. This is dependency build identity.
    project=root/'pyproject.toml'
    source=project.read_text();needle='version = "0.9.26"'
    if source.count(needle)!=1:raise ValueError('Unexpected upstream package version')
    project.write_text(source.replace(needle,'version = "0.9.26+mta2"'))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);patch(parser.parse_args().source)
