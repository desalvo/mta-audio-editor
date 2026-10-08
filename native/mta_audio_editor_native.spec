# PyInstaller specification for Windows/macOS native installers.
from pathlib import Path
import os
import sys

from PyInstaller.utils.hooks import collect_all

project = Path(SPECPATH).parent
version_text = (project / "VERSION").read_text(encoding="utf-8").strip()
revision_text = (project / "REVISION").read_text(encoding="utf-8").strip()
build_text = (project / "BUILD_INFO").read_text(encoding="utf-8").strip() if (project / "BUILD_INFO").exists() else "unknown"
numeric_version = ".".join(__import__("re").findall(r"\d+", version_text)[:3] + [revision_text])
icon_dir = project / "native" / "icons"
windows_icon = icon_dir / "mta-audio-editor.ico"
mac_icon = icon_dir / "mta-audio-editor.icns"
version_file = project / "native" / "windows-version-info.txt"

datas = [
    (str(project / "app" / "templates"), "app/templates"),
    (str(project / "app" / "static"), "app/static"),
    (str(project / "app" / "docs"), "app/docs"),
    (str(project / "VERSION"), "."),
    (str(project / "REVISION"), "."),
    (str(project / "RELEASE_CHANNEL"), "."),
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


# Optional private Chordino runtime provisioned by CI.  It is bundled beside
# FFmpeg and never needs to be installed into the user's system directories.
chordino_bin = os.environ.get("MTA_NATIVE_CHORDINO_BIN_DIR", "")
chordino_vamp = os.environ.get("MTA_NATIVE_CHORDINO_VAMP_DIR", "")
if chordino_bin and Path(chordino_bin).is_dir():
    for child in Path(chordino_bin).iterdir():
        if child.is_file():
            binaries.append((str(child), "bin"))
if chordino_vamp and Path(chordino_vamp).is_dir():
    for child in Path(chordino_vamp).iterdir():
        if child.is_file():
            # Dynamic library files must be collected as binaries; RDF/category
            # metadata is ordinary data but lives in the same private Vamp dir.
            if child.suffix.lower() in {".dll", ".dylib", ".so"}:
                binaries.append((str(child), "vamp"))
            else:
                datas.append((str(child), "vamp"))

hiddenimports = []
for package in ("webview", "demucs", "torch", "torchaudio", "whisper", "madmom_infer", "truststore", "certifi"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

# madmom-infer loads the chord processors lazily at runtime.  Keep these
# explicit even when collect_all() cannot discover them while freezing.
for module in (
    "madmom_infer.features.chords",
    "madmom_infer.audio.chroma",
    "madmom_infer.audio.signal",
    "madmom_infer.audio.stft",
    "madmom_infer.audio.spectrogram",
    "madmom_infer.ml.crf",
    "madmom_infer.ml.nn",
    "madmom_infer.models",
    "madmom_infer.backends",
    "madmom_infer.processors",
):
    if module not in hiddenimports:
        hiddenimports.append(module)

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
    argv_emulation=(sys.platform == "darwin"),
    icon=str(windows_icon) if os.name == "nt" and windows_icon.exists() else None,
    version=str(version_file) if os.name == "nt" and version_file.exists() else None,
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
        icon=str(mac_icon) if mac_icon.exists() else None,
        info_plist={
            "CFBundleDisplayName": "MTA Audio Editor",
            "CFBundleName": "MTA Audio Editor",
            "CFBundleShortVersionString": version_text,
            "CFBundleVersion": revision_text,
            "MTAEditorRevision": revision_text,
            "NSHumanReadableCopyright": "Alessandro De Salvo - EUPL-1.2",
            "MTAEditorBuild": build_text,
            "MTAEditorCreator": "Alessandro De Salvo",
            "MTAEditorRepository": "https://github.com/desalvo/mta-audio-editor",
            "NSHighResolutionCapable": True,
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeName": "Portable MTA Audio Editor Project",
                    "CFBundleTypeRole": "Editor",
                    "LSHandlerRank": "Owner",
                    "LSItemContentTypes": ["com.desalvo.mtaaudioeditor.portable-project"],
                    "CFBundleTypeExtensions": ["maeprojz"],
                },
                {
                    "CFBundleTypeName": "MTA Audio Editor Project (Legacy)",
                    "CFBundleTypeRole": "Editor",
                    "LSHandlerRank": "Alternate",
                    "LSItemContentTypes": ["com.desalvo.mtaaudioeditor.project"],
                    "CFBundleTypeExtensions": ["maeproj"],
                },
            ],
            "UTExportedTypeDeclarations": [
                {
                    "UTTypeIdentifier": "com.desalvo.mtaaudioeditor.portable-project",
                    "UTTypeDescription": "Portable MTA Audio Editor Project",
                    "UTTypeConformsTo": ["public.data"],
                    "UTTypeTagSpecification": {
                        "public.filename-extension": ["maeprojz"],
                        "public.mime-type": "application/vnd.mta-audio-editor.portable-project",
                    },
                },
                {
                    "UTTypeIdentifier": "com.desalvo.mtaaudioeditor.project",
                    "UTTypeDescription": "MTA Audio Editor Project (Legacy)",
                    "UTTypeConformsTo": ["public.data"],
                    "UTTypeTagSpecification": {
                        "public.filename-extension": ["maeproj"],
                        "public.mime-type": "application/vnd.mta-audio-editor.project",
                    },
                },
            ],
        },
    )
