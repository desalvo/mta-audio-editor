import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_VERSION = os.getenv("MTA_APP_VERSION", (ROOT / "VERSION").read_text().strip() if (ROOT / "VERSION").exists() else "0.0.0")
APP_REVISION = os.getenv("MTA_APP_REVISION", (ROOT / "REVISION").read_text().strip() if (ROOT / "REVISION").exists() else "0")
APP_RELEASE = f"{APP_VERSION}-r{APP_REVISION}"
BUILD_ID = os.getenv("MTA_BUILD_ID", (ROOT / "BUILD_INFO").read_text().strip() if (ROOT / "BUILD_INFO").exists() else "unknown")
CREATOR = "Alessandro De Salvo <braket71@gmail.com>"
REPOSITORY = "https://github.com/desalvo/mta-audio-editor"
