"""Execute the actual rolling-release shell step with an offline CLI double."""
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

ROOT = Path(__file__).resolve().parents[1]

CLI_DOUBLE = r'''
import json
import os
from pathlib import Path
import sys

state_path = Path(os.environ['MTA_TEST_RELEASE_STATE'])
state = json.loads(state_path.read_text())
command = Path(sys.argv[0]).name
args = sys.argv[1:]
state['calls'].append([command, *args])
code = 0
stdout = stderr = ''
if command == 'gh':
    if args[:3] == ['release', 'view', 'early-main']:
        code = 0 if state['exists'] else 1
    elif args[:2] in (['release', 'edit'], ['release', 'create']):
        pass
    elif args[:3] == ['release', 'upload', 'early-main']:
        state['uploaded'] = True
    elif args[:2] == ['api', '--method']:
        assert args[2:5] == ['DELETE', '--include', '--silent'], args
        asset = args[5].rsplit('/', 1)[1]
        attempt = state['attempts'].get(asset, 0)
        state['attempts'][asset] = attempt + 1
        replies = state['replies'].get(asset, [[0, 'HTTP/2.0 204 No Content\r\n', '']])
        code, stdout, stderr = replies[min(attempt, len(replies) - 1)]
    elif args[0] == 'api' and args[1].endswith('/releases/tags/early-main'):
        stdout = '402961323\n'
    elif args[0] == 'api' and args[1].endswith('/releases/402961323/assets'):
        assert '--paginate' in args, args
        stdout = state['assets']
    else:
        raise AssertionError(args)
elif command not in ('git', 'sleep'):
    raise AssertionError(command)
state_path.write_text(json.dumps(state))
sys.stdout.write(stdout)
sys.stderr.write(stderr)
raise SystemExit(code)
'''


def run_publish(tmp_path, replies=None, *, exists=True, assets='707499900\n707499901\n'):
    workflow = (ROOT / '.github/workflows/ci-cd.yml').read_text()
    step = workflow.split('      - name: Update rolling early-main GitHub prerelease\n', 1)[1]
    script = textwrap.dedent(step.split('        run: |\n', 1)[1].split('\n  publish:', 1)[0])
    binaries = tmp_path / 'bin'
    binaries.mkdir()
    for name in ('gh', 'git', 'sleep'):
        executable = binaries / name
        executable.write_text(f'#!{sys.executable}\n' + CLI_DOUBLE)
        executable.chmod(0o755)
    staging = tmp_path / 'early-assets'
    staging.mkdir()
    (staging / 'test-installer.exe').write_bytes(b'offline installer fixture')
    state_path = tmp_path / 'state.json'
    state_path.write_text(json.dumps({
        'exists': exists, 'assets': assets, 'replies': replies or {},
        'attempts': {}, 'calls': [], 'uploaded': False,
    }))
    env = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ['PATH'],
               MTA_TEST_RELEASE_STATE=str(state_path), RUNNER_TEMP=str(tmp_path),
               GITHUB_REPOSITORY='desalvo/mta-audio-editor',
               GITHUB_SHA='f8ed2c37f95a08ed1c9b887390ab2fb100503fb3')
    # Credentials cannot reach the CLI double, and it never invokes GitHub.
    for key in ('GH_TOKEN', 'GITHUB_TOKEN'):
        env.pop(key, None)
    result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=20)
    return result, json.loads(state_path.read_text())


def test_empty_delete_response_cleans_all_assets_before_upload(tmp_path):
    result, state = run_publish(tmp_path)
    assert result.returncode == 0, result.stderr
    assert state['attempts'] == {'707499900': 1, '707499901': 1}
    assert state['uploaded']
    assert not any(call[0] == 'sleep' for call in state['calls'])
    assert state['calls'][-1][1:4] == ['release', 'upload', 'early-main']


@pytest.mark.parametrize('recovered', [
    [0, 'HTTP/2.0 204 No Content\r\n', ''],
    [1, 'HTTP/2.0 404 Not Found\r\n', 'unexpected end of JSON input\n'],
])
@pytest.mark.parametrize('header', ['', 'HTTP/2.0 502 Bad Gateway\r\n', 'HTTP/2.0 429 Too Many Requests\r\n'])
def test_truncated_response_retries_and_accepts_confirmed_absence(tmp_path, recovered, header):
    result, state = run_publish(tmp_path, {'707499900': [
        [1, header, 'unexpected end of JSON input\n'], recovered,
    ]})
    assert result.returncode == 0, result.stderr
    assert state['attempts'] == {'707499900': 2, '707499901': 1}
    assert state['uploaded']
    assert [c for c in state['calls'] if c[0] == 'sleep'] == [['sleep', '2']]


@pytest.mark.parametrize('status', [401, 403, 422])
def test_permission_or_validation_error_stops_without_upload(tmp_path, status):
    result, state = run_publish(tmp_path, {'707499900': [
        [1, f'HTTP/2.0 {status} Error\r\n', 'request rejected\n'],
    ]})
    assert result.returncode != 0
    assert state['attempts'] == {'707499900': 1}
    assert not state['uploaded']
    assert not any(call[0] == 'sleep' for call in state['calls'])


@pytest.mark.parametrize('header', ['', 'HTTP/1.1 503 Service Unavailable\r\n'])
def test_persistent_error_has_bounded_retries_and_blocks_upload(tmp_path, header):
    result, state = run_publish(tmp_path, {'707499900': [
        [1, header, 'unexpected end of JSON input\n'],
    ]})
    assert result.returncode != 0
    assert state['attempts'] == {'707499900': 4}
    assert not state['uploaded']
    assert [c for c in state['calls'] if c[0] == 'sleep'] == [
        ['sleep', '2'], ['sleep', '4'], ['sleep', '6'],
    ]


@pytest.mark.parametrize('exists,assets', [(False, ''), (True, ''), (True, '\n707499900\n\n')])
def test_new_empty_or_partially_cleaned_release_is_publishable(tmp_path, exists, assets):
    result, state = run_publish(tmp_path, exists=exists, assets=assets)
    assert result.returncode == 0, result.stderr
    assert state['uploaded']
    assert len(state['attempts']) == (1 if assets.strip() else 0)


def test_invalid_asset_identifier_is_never_used_as_an_api_path(tmp_path):
    result, state = run_publish(tmp_path, assets='../other-release\n')
    assert result.returncode != 0
    assert not state['attempts']
    assert not state['uploaded']
