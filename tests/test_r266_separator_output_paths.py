from pathlib import Path
import sys
import types
import app.main as main


def test_audio_separator_relative_output_filenames(monkeypatch, tmp_path):
    source = tmp_path / "vocals.wav"
    source.write_bytes(b"input")
    output = tmp_path / "job" / "stems"
    output.mkdir(parents=True)
    monkeypatch.delenv("MTA_LEAD_BACKING_COMMAND", raising=False)
    monkeypatch.setattr(main, "_lead_backing_model_info", lambda name: {"installed": True, "filename": "UVR_MDXNET_KARA_2.onnx"})
    torch = types.ModuleType("torch")
    torch.empty = lambda *args: None
    ops = types.ModuleType("torchvision.ops")
    ops.nms = lambda *args: None
    tv = types.ModuleType("torchvision")
    tv.ops = ops
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "torchvision", tv)
    monkeypatch.setitem(sys.modules, "torchvision.ops", ops)

    class Separator:
        def __init__(self, **kwargs):
            assert Path(kwargs["output_dir"]) == output
        def load_model(self, **kwargs):
            pass
        def separate(self, path):
            (output / "vocals_(Vocals)_UVR_MDXNET_KARA_2.WAV").write_bytes(b"lead")
            (output / "vocals_(Instrumental)_UVR_MDXNET_KARA_2.WAV").write_bytes(b"backing")
            return ["vocals_(Vocals)_UVR_MDXNET_KARA_2.WAV", "vocals_(Instrumental)_UVR_MDXNET_KARA_2.WAV"]
    module = types.ModuleType("audio_separator.separator")
    module.Separator = Separator
    monkeypatch.setitem(sys.modules, "audio_separator", types.ModuleType("audio_separator"))
    monkeypatch.setitem(sys.modules, "audio_separator.separator", module)
    lead, backing, method = main._split_lead_backing_vocals(source, output)
    assert lead.read_bytes() == b"lead"
    assert backing.read_bytes() == b"backing"
    assert method.startswith("audio-separator:")
