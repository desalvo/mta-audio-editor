"""Native/server VST3 discovery, isolated offline host and live worker entry point.

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
import base64
import math


def vst3_roots() -> list[Path]:
    roots: list[Path] = []
    if sys.platform == 'darwin':
        roots = [Path('/Library/Audio/Plug-Ins/VST3'), Path.home() / 'Library/Audio/Plug-Ins/VST3']
    elif os.name == 'nt':
        roots = [Path(os.environ.get('COMMONPROGRAMFILES', 'C:/Program Files/Common Files')) / 'VST3',
                 Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Programs/VST3']
    else:
        roots = [Path('/usr/lib/vst3'), Path('/usr/local/lib/vst3'),Path('/opt/mta/vst3')]
        if os.getenv('MTA_NATIVE_SINGLE_USER','').lower()=='true':
            roots += [Path.home() / '.vst3', Path.home() / '.local/lib/vst3']
    from .runtime_paths import optional_vst3_root
    roots.append(optional_vst3_root())
    roots += [Path(x).expanduser() for x in os.getenv('MTA_VST3_PATHS', '').split(os.pathsep) if x.strip()]
    resolved=[p.resolve() for p in roots if p.is_dir()]
    if os.getenv('MTA_NATIVE_SINGLE_USER','').lower()!='true':
        data=Path(os.getenv('MTA_DATA_DIR','/data/projects')).resolve()
        resolved=[p for p in resolved if not p.is_relative_to(data) and not (p.stat().st_mode & 0o022)]
    return resolved


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


def inspect_parameters(plugin_path: Path, *, metadata=False):
    from pedalboard import load_plugin
    plugin = load_plugin(str(plugin_path))
    result = []
    for name, param in plugin.parameters.items():
        value = getattr(param, 'raw_value', None)
        if value is None:
            continue
        result.append({'name': str(name), 'value': float(value)})
    return {'parameters':result,'is_instrument':bool(plugin.is_instrument),'sidechain_inputs':getattr(plugin,'_mta_sidechain_inputs',[])} if metadata else result


def apply_parameters(plugin, values: dict) -> None:
    state=values.get('__mta_state_b64')
    if state is not None:
        if not isinstance(state,str) or len(state)>12*1024*1024:raise ValueError('VST3 state too large')
        try:plugin.raw_state=base64.b64decode(state,validate=True)
        except (ValueError,TypeError) as exc:raise ValueError('Invalid VST3 state') from exc
    for name, raw in values.items():
        if name=='__mta_state_b64':continue
        if name not in plugin.parameters:
            raise ValueError(f'VST3 parameter unavailable: {name}')
        value = float(raw)
        if isinstance(raw,bool) or not math.isfinite(value) or not (0.0 <= value <= 1.0):
            raise ValueError(f'VST3 parameter outside 0..1: {name}')
        plugin.parameters[name].raw_value = value


def process_audio(source: Path, target: Path, plugin_path: Path, values: dict | None = None, transport=None) -> None:
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
        from .vst3_transport import HostClock
        host=HostClock(rate=reader.samplerate);host.data=transport or {}
        with AudioFile(str(target), 'w', reader.samplerate, reader.num_channels) as writer:
            chunk = max(4096, int(reader.samplerate * 2))
            while reader.tell() < reader.frames:
                position=reader.tell()
                boundary=next(iter(host.segments(position,min(chunk,reader.frames-position))))[1]
                host.apply(plugin,position)
                audio = reader.read(boundary-position)
                if audio.size == 0:
                    break
                processed = board(audio, reader.samplerate, reset=False)
                writer.write(processed)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--process', action='store_true')
    parser.add_argument('--live-config')
    parser.add_argument('--midi-config')
    parser.add_argument('--inspect-plugin', default=None)
    parser.add_argument('--inspect-result')
    parser.add_argument('source', nargs='?')
    parser.add_argument('target', nargs='?')
    parser.add_argument('plugin', nargs='?')
    parser.add_argument('--parameters-json', default='{}')
    parser.add_argument('--parameters-file')
    parser.add_argument('--transport-file')
    parser.add_argument('--editor-plugin')
    parser.add_argument('--editor-result')
    args = parser.parse_args()
    if args.midi_config:
        from .midi_render import run
        return run(args.midi_config)
    if args.live_config:
        from .vst3_live import run
        return run(args.live_config)
    values=json.loads(Path(args.parameters_file).read_text(encoding='utf-8')) if args.parameters_file else json.loads(args.parameters_json)
    if not isinstance(values,dict):raise ValueError('VST3 parameters must be an object')
    if args.editor_plugin:
        from pedalboard import load_plugin
        path=validate_plugin_path(args.editor_plugin);plugin=load_plugin(str(path));apply_parameters(plugin,values)
        from .vst3_x11 import editor_errors
        with editor_errors():plugin.show_editor()
        state=base64.b64encode(plugin.raw_state).decode('ascii')
        if len(state)>12*1024*1024:raise ValueError('VST3 state too large')
        params={name:float(p.raw_value) for name,p in plugin.parameters.items()}
        params['__mta_state_b64']=state
        result=Path(args.editor_result);result.write_text(json.dumps(params,allow_nan=False),encoding='utf-8')
        return 0
    if args.inspect_plugin:
        plugin = validate_plugin_path(args.inspect_plugin)
        result=json.dumps(inspect_parameters(plugin,metadata=True))
        if args.inspect_result:Path(args.inspect_result).write_text(result,encoding='utf-8')
        else:print(result)
        return 0
    if not args.process or not args.source or not args.target:
        parser.error('expected --process SOURCE TARGET PLUGIN')
    plugin = validate_plugin_path(args.plugin)
    if args.transport_file:
        process_audio(Path(args.source),Path(args.target),plugin,values,json.loads(Path(args.transport_file).read_text()))
    else:process_audio(Path(args.source), Path(args.target), plugin, values)
    return 0


def worker_command(*args):
    """A frozen executable needs an explicit dispatcher, never Python's -m flag."""
    return [sys.executable,*(('--vst3-worker',) if getattr(sys,'frozen',False) else ('-m','app.vst3_host')),*map(str,args)]

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None

