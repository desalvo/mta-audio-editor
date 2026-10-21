import logging
import pathlib
import oddvoices.corpus

ROOT = pathlib.Path(__file__).resolve().parent.parent
VOICES_DIR = ROOT / "voices"
OUTPUT_DIR = ROOT / "compiled_voices"

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    OUTPUT_DIR.mkdir(exist_ok=True)
    for entry in VOICES_DIR.iterdir():
        if entry.is_dir():
            segment_database = oddvoices.corpus.CorpusAnalyzer(entry).render_database()
            out_file = OUTPUT_DIR / (entry.stem + ".voice")
            with open(out_file, "wb") as f:
                oddvoices.corpus.write_voice_file(f, segment_database)
