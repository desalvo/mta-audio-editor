"""EL10 ffmpeg-free capability handling and Windows source encoding regression."""
import ast
import importlib.util
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).parents[1]


def module():
    spec = importlib.util.spec_from_file_location('el10_ai_setup', ROOT / 'scripts/install_ai_engines.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_el10_installed_ffmpeg_free_does_not_request_ffmpeg_package(monkeypatch):
    setup = module();calls = []
    binaries = {'dnf': '/usr/bin/dnf', 'ffmpeg': '/usr/bin/ffmpeg', 'ffprobe': '/usr/bin/ffprobe'}
    monkeypatch.setattr(setup.shutil, 'which', binaries.get)
    monkeypatch.setattr(setup, 'run', lambda args, **kwargs: calls.append(args))
    setup.system_dependencies()
    package_calls = [call for call in calls if call[0] == 'dnf']
    assert len(package_calls) == 1
    assert 'ffmpeg' not in package_calls[0] and 'ffmpeg-free' not in package_calls[0]
    assert '/usr/bin/ffmpeg' not in package_calls[0]
    assert ['/usr/bin/ffmpeg', '-version'] in calls
    assert ['/usr/bin/ffprobe', '-version'] in calls


@pytest.mark.parametrize('missing', [('ffmpeg',), ('ffprobe',), ('ffmpeg', 'ffprobe')])
def test_missing_el_tools_are_requested_by_file_provides(monkeypatch, missing):
    setup = module();calls = [];installed = set(('ffmpeg', 'ffprobe')) - set(missing)
    monkeypatch.setattr(setup.shutil, 'which', lambda name: '/usr/bin/' + name if name in installed else None)
    def run(args, **kwargs):
        calls.append(args)
        if args[:3] == ['dnf', 'install', '-y']:
            installed.update(Path(item).name for item in args[3:])
    monkeypatch.setattr(setup, 'run', run)
    setup.ensure_media_tools('dnf')
    assert calls[0] == ['dnf', 'install', '-y', *('/usr/bin/' + name for name in missing)]
    assert len(calls) == 3


def test_debian_missing_tools_use_distribution_ffmpeg_package(monkeypatch):
    setup = module();calls = [];installed = False
    monkeypatch.setattr(setup.shutil, 'which', lambda name: '/usr/bin/' + name if installed else None)
    def run(args, **kwargs):
        nonlocal installed
        calls.append(args)
        if args[0] == 'apt-get':installed = True
    monkeypatch.setattr(setup, 'run', run)
    setup.ensure_media_tools('apt-get')
    assert calls[0] == ['apt-get', 'install', '-y', 'ffmpeg']
    assert len(calls) == 3


def test_broken_installed_binary_fails_before_ai_setup(monkeypatch):
    setup = module()
    monkeypatch.setattr(setup.shutil, 'which', lambda name: '/usr/bin/' + name)
    def fail(args, **kwargs):
        raise subprocess.CalledProcessError(1, args)
    monkeypatch.setattr(setup, 'run', fail)
    with pytest.raises(subprocess.CalledProcessError):
        setup.ensure_media_tools('dnf')


def test_provider_install_success_without_executable_is_not_ready(monkeypatch):
    setup = module()
    monkeypatch.setattr(setup.shutil, 'which', lambda name: None)
    monkeypatch.setattr(setup, 'run', lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match='ffmpeg unavailable'):
        setup.ensure_media_tools('dnf')


def test_windows_css_read_explicitly_uses_utf8():
    # Parse the production test so this guard does not depend on Linux's locale.
    source = ROOT / 'tests/test_r210_windows_publication_tabs.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    target = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'test_unselected_arranger_tabs_have_readable_text_and_focus')
    read = next(node for node in ast.walk(target) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'read_text')
    assert any(key.arg == 'encoding' and isinstance(key.value, ast.Constant) and key.value.value == 'utf-8' for key in read.keywords)
    assert (ROOT / 'app/static/app.css').read_bytes().decode('utf-8')


def test_legacy_rpm_dependency_uses_capabilities_too():
    script = (ROOT / 'scripts/install_mta.sh').read_text(encoding='utf-8')
    assert 'python3.14-pip /usr/bin/ffmpeg /usr/bin/ffprobe curl' in script
