"""Run pytest against an explicitly supplied test-only Chromium executable.

No application/browser runtime is modified. Without MTA_TEST_CHROMIUM_EXECUTABLE,
standard Playwright installation and existing test capability checks apply.
This bridges legacy tests that launch default Chromium and newer path fixtures.
"""
import os
from pathlib import Path
import sys


def main():
    root=Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0,str(root));sys.path.insert(0,str(root/'tests'))
    supplied=os.environ.get('MTA_TEST_CHROMIUM_EXECUTABLE')
    if supplied:
        executable=Path(supplied).resolve()
        if not executable.is_file():raise ValueError('Configured test Chromium is absent')
        from playwright.sync_api import BrowserType
        original_launch=BrowserType.launch
        original_path=BrowserType.executable_path

        def launch(browser,**kwargs):
            if browser.name=='chromium' and not kwargs.get('channel'):
                kwargs.setdefault('executable_path',str(executable))
                if kwargs['executable_path']==str(executable):
                    needed=['--no-sandbox','--disable-dev-shm-usage','--no-zygote','--single-process',
                            '--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']
                    args=list(kwargs.get('args',[]))
                    kwargs['args']=args+[flag for flag in needed if flag not in args]
            return original_launch(browser,**kwargs)

        BrowserType.launch=launch
        BrowserType.executable_path=property(lambda browser:str(executable) if browser.name=='chromium' else original_path.fget(browser))
    import pytest
    return pytest.main(sys.argv[1:])


if __name__=='__main__':raise SystemExit(main())
