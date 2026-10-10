"""Optional desktop VST3 discovery and isolated offline host.

Only bundles found under recognized local plugin directories can be loaded.
The third-party executable runs in a separate interpreter process during export.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import sys
import json


def vst3_roots() -> list[Path]:
    roots: list[Path] = []
    if sys.platform == 'darwin':
        roots = [Path('/Library/Audio/Plug-Ins/VST3'), Path.home() / 'Library/Audio/Plug-Ins/VST3']
    elif os.name == 'nt':
        roots = [Path(os.environ.get('COMMONPROGRAMFILES', 'C:/Program Files/Common Files')) / 'VST3',
                 Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Programs/VST3']
    else:
        roots = [Path('/usr/lib/vst3'), Path('/usr/local/lib/vst3'),
                 Path.home() / '.vst3', Path.home() / '.local/lib/vst3']
    roots += [Path(x).expanduser() for x in os.getenv('MTA_VST3_PATHS', '').split(os.pathsep) if x.strip()]
    return [p.resolve() for p in roots if p.is_dir()]


def discover_plugins() -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for root in vst3_roots():
        try:
            for path in root.rglob('*.vst3'):
                if len(found) >= 250:
                    return found
                absolute = path.resolve()
                if not absolute.is_relative_to(root) or not absolute.exists():
                    continue
                key = str(absolute)
                if key not in seen:
                    found.append({'name': path.stem, 'path': key})
                    seen.add(key)
        except (OSError, PermissionError):
            continue
    return sorted(found, key=lambda p: p['name'].casefold())


def validate_plugin_path(path: str) -> Path:
    if not path or not path.lower().endswith('.vst3'):
        raise ValueError('VST3 path missing or invalid')
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f'VST3 not installed: {resolved.name}')
    if not any(resolved.is_relative_to(root) for root in vst3_roots()):
        raise ValueError('VST3 is outside configured plugin directories')
    return resolved


def runtime_available() -> bool:
    return importlib.util.find_spec('pedalboard') is not None


def inspect_parameters(plugin_path: Path) -> list[dict]:
    from pedalboard import load_plugin
    plugin = load_plugin(str(plugin_path))
    result = []
    for name, param in plugin.parameters.items():
        value = getattr(param, 'raw_value', None)
        if value is None:
            continue
        result.append({'name': str(name), 'value': float(value)})
    return result


def apply_parameters(plugin, values: dict) -> None:
    for name, raw in values.items():
        if name not in plugin.parameters:
            raise ValueError(f'VST3 parameter unavailable: {name}')
        value = float(raw)
        if not (0.0 <= value <= 1.0):
            raise ValueError(f'VST3 parameter outside 0..1: {name}')
        plugin.parameters[name].raw_value = value


def process_audio(source: Path, target: Path, plugin_path: Path, values: dict | None = None) -> None:
    try:
        from pedalboard import Pedalboard, load_plugin
        from pedalboard.io import AudioFile
    except ImportError as exc:
        raise RuntimeError('VST3 hosting requires pip install -r requirements-vst3.txt') from exc
    # Stream chunks to bound memory usage for large projects.
    plugin = load_plugin(str(plugin_path))
    apply_parameters(plugin, values or {})
    board = Pedalboard([plugin])
    with AudioFile(str(source)) as reader:
        with AudioFile(str(target), 'w', reader.samplerate, reader.num_channels) as writer:
            chunk = max(4096, int(reader.samplerate * 2))
            while reader.tell() < reader.frames:
                audio = reader.read(chunk)
                if audio.size == 0:
                    break
                processed = board(audio, reader.samplerate, reset=False)
                writer.write(processed)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--process', action='store_true')
    parser.add_argument('--inspect-plugin', default=None)
    parser.add_argument('source', nargs='?')
    parser.add_argument('target', nargs='?')
    parser.add_argument('plugin', nargs='?')
    parser.add_argument('--parameters-json', default='{}')
    args = parser.parse_args()
    if args.inspect_plugin:
        plugin = validate_plugin_path(args.inspect_plugin)
        print(json.dumps({'parameters': inspect_parameters(plugin)}))
        return 0
    if not args.process or not args.source or not args.target:
        parser.error('expected --process SOURCE TARGET PLUGIN')
    plugin = validate_plugin_path(args.plugin)
    process_audio(Path(args.source), Path(args.target), plugin, json.loads(args.parameters_json))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
