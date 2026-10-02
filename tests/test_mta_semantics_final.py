from pathlib import Path


def test_final_spec_exists():
    text = (Path(__file__).resolve().parents[1] / "docs" / "MTA_FORMAT_FINAL_SPEC.md").read_text(encoding="utf-8")
    assert "Verified byte-level structure" in text
    assert "display-page reset control" in text
    assert "12,654" in text


def test_reverse_module_declares_page_reset_semantic():
    text = (Path(__file__).resolve().parents[1] / "app" / "mta_reverse.py").read_text(encoding="utf-8")
    assert '"control": "page_reset" if position == 127 else None' in text
    assert '"page_reset_position": 127 if 127 in positions else None' in text
