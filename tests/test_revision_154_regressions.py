from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_text_analysis_renders_before_persisting_extracted_timed_text():
    source = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    block = source[source.index("pollMediaJob(job.id,`Estrazione ${label}`"):]
    block = block[: block.index("});", block.index("pollMediaJob")) + 3]
    assert block.index("render();") < block.index("await persistCurrentProject(false)")


def test_youtube_import_posts_json_and_paste_buttons_are_readable():
    source = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    css = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
    assert "youtube-import-jobs`,{method:'POST',headers:{'content-type':'application/json'}" in source
    assert ".youtube-paste-btn{display:inline-flex!important" in css
    assert "if(editable)return;" in source


def test_sidebar_project_file_precedes_edit_import_mix():
    html = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
    assert html.index("PROJECT / FILE") < html.index("EDIT / IMPORT / MIX")


def test_bpm_is_integer_in_transport_ui():
    html = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
    source = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert 'id="transportBpmInput"' in html and 'step="1" value="120"' in html
    assert "Math.round(Number(current.bpm||120))" in source


def test_whisper_mps_float64_failure_retries_on_cpu():
    from app.music_text import _whisper_transcribe

    class FakeModel:
        def __init__(self):
            self.device = "mps"
            self.calls = []
            self.float_calls = 0

        def float(self):
            self.float_calls += 1
            return self

        def to(self, device):
            self.device = device
            return self

        def transcribe(self, source, **kwargs):
            self.calls.append((self.device, source, kwargs))
            if self.device == "mps":
                raise RuntimeError("Cannot convert a MPS Tensor to float64 d type as the MPS framework doesn't support float64")
            return {"segments": []}

    model = FakeModel()
    result = _whisper_transcribe(model, "song.wav", language=None, device="mps")
    assert result == {"segments": []}
    assert model.calls[0][0] == "mps"
    assert model.calls[-1][0] == "cpu"
    assert model.calls[-1][2]["fp16"] is False
    assert model.float_calls >= 2
