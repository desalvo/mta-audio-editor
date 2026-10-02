from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
build = (ROOT / "BUILD_INFO").read_text(encoding="utf-8").strip() if (ROOT / "BUILD_INFO").exists() else "unknown"

numbers = [int(x) for x in re.findall(r"\d+", version)[:4]]
while len(numbers) < 4:
    numbers.append(0)
major, minor, patch, revision = numbers[:4]
tuple_text = f"({major}, {minor}, {patch}, {revision})"

creator = "Alessandro De Salvo"
repository = "https://github.com/desalvo/mta-audio-editor"

content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={tuple_text},
    prodvers={tuple_text},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', '{creator}'),
          StringStruct('FileDescription', 'MTA Audio Editor'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', 'MTA Audio Editor'),
          StringStruct('LegalCopyright', 'EUPL-1.2'),
          StringStruct('OriginalFilename', 'MTA Audio Editor.exe'),
          StringStruct('ProductName', 'MTA Audio Editor'),
          StringStruct('ProductVersion', '{version}'),
          StringStruct('Comments', 'Build {build} - {repository}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
(ROOT / "native" / "windows-version-info.txt").write_text(content, encoding="utf-8")
print(f"Generated Windows metadata for {version} build {build}")
