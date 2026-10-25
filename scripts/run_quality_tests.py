"""Select ordinary Python checks or the complete browser/runtime regression.

No-option pytest remains unchanged. Only this CI entry point defers whole
modules importing Playwright; every deferred path is recorded in an artifact.
"""
import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys


def suites(root):
    ordinary=[];browser=[]
    paths=set((root/'tests').rglob('test_*.py'))|set((root/'tests').rglob('*_test.py'))
    for path in sorted(paths):
        tree=ast.parse(path.read_text())
        uses_browser=any(
            (isinstance(node,ast.Import) and any(x.name.startswith('playwright') for x in node.names)) or
            (isinstance(node,ast.ImportFrom) and (node.module or '').startswith('playwright')) or
            (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and
             node.func.attr=='importorskip' and node.args and isinstance(node.args[0],ast.Constant) and
             isinstance(node.args[0].value,str) and node.args[0].value.startswith('playwright'))
            for node in ast.walk(tree))
        (browser if uses_browser else ordinary).append(path.relative_to(root).as_posix())
    if not ordinary or not browser:raise ValueError('Quality test partition is unexpectedly empty')
    return ordinary,browser


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',choices=('unit','full'),required=True)
    parser.add_argument('--list-only',action='store_true')
    parser.add_argument('pytest_args',nargs=argparse.REMAINDER)
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1]
    ordinary,browser=suites(root)
    selected=sorted(ordinary+browser) if args.suite=='full' else ordinary
    deferred=[] if args.suite=='full' else browser
    if args.list_only:
        print(json.dumps({'suite':args.suite,'selected':selected,'deferred':deferred},indent=2))
        return 0
    report=root/'quality-test-selection.json'
    report.write_text(json.dumps({'commit':os.getenv('GITHUB_SHA','local-uncommitted'),
        'suite':args.suite,'selected':selected,'deferred':deferred,
        'complete_regression':not deferred,'release_candidate':False},indent=2)+'\n')
    options=args.pytest_args[1:] if args.pytest_args[:1]==['--'] else args.pytest_args
    return subprocess.call([sys.executable,'-m','pytest',*options,*selected],cwd=root,
        env={**os.environ,'PYTHONPATH':str(root),'MTA_TEST_OFFLINE':'1',
             'MTA_ALLOW_INSECURE_NO_AUTH':'false'})


if __name__=='__main__':
    raise SystemExit(main())
