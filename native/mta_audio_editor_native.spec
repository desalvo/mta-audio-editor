# PyInstaller specification for Windows/macOS native installers.
from pathlib import Path
import os
import sys

from PyInstaller.utils.hooks import collect_all

project = Path(SPECPATH).parent.parent

datas = [
    (str(project / "app" / "templates"), "app/templates"),
    (str(project / "app" / "static"), "app/static"),
    (str(project / "app" / "docs"), "app/docs"),
    (str(project / "VERSION"), "."),
]
build_file = project / "BUILD_INFO"
if build_file.exists():
    datas.append((str(build_file), "."))

binaries = []
for env_name, dest_name in (("MTA_NATIVE_FFMPEG", "ffmpeg"), ("MTA_NATIVE_FFPROBE", "ffprobe")):
    value = os.environ.get(env_name)
    if value:
        suffix = ".exe" if os.name == "nt" else ""
        binaries.append((value, "bin"))

hiddenimports = []
for package in ("webview", "demucs", "torch", "torchaudio"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

a = Analysis(
    [str(project / "native" / "mta_audio_editor_native.py")],
    pathex=[str(project)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MTA Audio Editor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MTA Audio Editor",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="MTA Audio Editor.app",
        bundle_identifier="com.desalvo.mtaaudioeditor",
        info_plist={
            "CFBundleDisplayName": "MTA Audio Editor",
            "NSHighResolutionCapable": True,
        },
    )
