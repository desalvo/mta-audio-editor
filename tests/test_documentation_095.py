from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_only_canonical_bilingual_manual_pdfs_are_packaged():
    docs = ROOT / "app" / "docs"
    assert not (docs / "MTA-Audio-Editor-User-Manual.pdf").exists()
    assert not (docs / "MTA-Audio-Editor-Administrator-Manual.pdf").exists()
    for name in (
        "MTA-Audio-Editor-User-Manual-IT.pdf",
        "MTA-Audio-Editor-User-Manual-EN.pdf",
        "MTA-Audio-Editor-Administrator-Manual-IT.pdf",
        "MTA-Audio-Editor-Administrator-Manual-EN.pdf",
    ):
        assert (docs / name).is_file()
