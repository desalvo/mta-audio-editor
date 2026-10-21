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
    (str(project / "app" / "optional_plugins_catalog.json"), "app"),
    (str(project / "app" / "optional_plugin_licenses"), "app/optional_plugin_licenses"),
    (str(project / "app" / "i18n_catalog.json"), "app"),
    (str(project / 'app' / 'studio_assets'), 'app/studio_assets'),
    (str(project / 'native' / 'third_party' / 'oddvoices'), 'native/third_party/oddvoices'),
    (str(project / 'native' / 'third_party' / 'tinysoundfont' / 'LICENSE'), 'native/third_party/tinysoundfont'),
    (str(project / "app" / "templates"), "app/templates"),
    (str(project / "app" / "static"), "app/static"),
    (str(project / "app" / "docs"), "app/docs"),
    (str(project / "app" / "sam_audio_worker.py"), "app"),
    (str(project / "app" / "sam_audio_compat.py"), "app"),
    (str(project / "app" / "drumsep_onnx_worker.py"), "app"),
    (str(project / "VERSION"), "."),
    (str(project / "REVISION"), "."),
    (str(project / "RELEASE_CHANNEL"), "."),
]
# Isolated AI interpreters need real Python source files beside the frozen
# application. PYZ bytecode cannot be imported by that separate interpreter.
for worker_source in (project / 'app').glob('*.py'):
    datas.append((str(worker_source), 'app'))
for runtime_recipe in ('requirements-studio-basic-pitch.txt','requirements-studio-yourmt3.txt'):
    datas.append((str(project / runtime_recipe), '.'))

for adapter_file in ('ace_step_http_worker.py','ace_gpu_process_meter.py','ai_gpu_process_meter.py',
                     'ai_proxmox_gpu_agent_client.py','ace_gpu_profiler.py','ai_gpu_verified.py','ace_task_progress.py','ai_execution_limits.py'):
    datas.append((str(project / 'app' / adapter_file), 'app'))

if sys.platform == 'darwin':
    for language in ('it','en'):
        datas.append((str(project/'native/macos-localizations'/f'{language}.lproj/InfoPlist.strings'),f'{language}.lproj'))

# uv supplies a managed Python/runtime for ACE, including on a frozen desktop.
import uv
binaries = [(str(uv.find_uv_bin()), 'tools')]

build_file = project / "BUILD_INFO"
if build_file.exists():
    datas.append((str(build_file), "."))

binaries = list(binaries)
for env_name, dest_name in (("MTA_NATIVE_FFMPEG", "ffmpeg"), ("MTA_NATIVE_FFPROBE", "ffprobe")):
    value = os.environ.get(env_name)
    if value:
        suffix = ".exe" if os.name == "nt" else ""
        binaries.append((value, "bin"))


# Portable C++ render DSP; selected explicitly in Settings. Current engine is default.
audio_core_path = os.environ.get("MTA_NATIVE_AUDIO_CORE", "")
if audio_core_path and Path(audio_core_path).is_file():
    binaries.append((audio_core_path, "bin"))

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
for package in ("sounddevice", "_sounddevice_data", "pylibremidi", "rtmidi", "mido", "pedalboard", "av", "webview", "demucs", "torch", "torchaudio", "torchvision", "audio_separator", "onnxruntime", "librosa", "soundfile", "whisper", "madmom_infer", "truststore", "certifi", "six"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    # ASIO DLL redistribution awaits its corresponding-source/license bundle.
    # Standard PortAudio remains bundled; an operator-provided ASIO build can
    # still be discovered by sounddevice through its documented loader.
    datas += [item for item in package_datas if '-asio.dll' not in str(item[0]).lower()]
    binaries += [item for item in package_binaries if '-asio.dll' not in str(item[0]).lower()]
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

# Hooks may discover additional DLLs after collect_all; enforce the same
# redistribution boundary on the final analysis, not only the input lists.
a.binaries = [entry for entry in a.binaries if not any('-asio.dll' in str(value).lower() for value in entry[:2])]
a.datas = [entry for entry in a.datas if not any('-asio.dll' in str(value).lower() for value in entry[:2])]

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
            "CFBundleLocalizations": ["en", "it"],
            "NSMicrophoneUsageDescription": "MTA Audio Editor records the selected microphone or audio input into the current project only when recording is requested.",
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
