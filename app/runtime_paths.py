"""Shared data locations before the desktop launcher prepares the environment."""
import os
from pathlib import Path
import sys


def native_data_root():
    override=os.getenv('MTA_NATIVE_DATA_DIR','').strip()
    if override:return Path(override).expanduser().resolve()
    if sys.platform=='darwin':base=Path.home()/'Library'/'Application Support'
    elif sys.platform=='win32':base=Path(os.getenv('LOCALAPPDATA') or (Path.home()/'AppData'/'Local'))
    else:base=Path(os.getenv('XDG_DATA_HOME') or (Path.home()/'.local'/'share'))
    return (base/'MTA Audio Editor').resolve()


def application_data_root():
    override=os.getenv('MTA_DATA_DIR','').strip()
    if override:return Path(override).expanduser().resolve()
    if os.getenv('MTA_NATIVE_SINGLE_USER','').lower()=='true':return native_data_root()
    return Path('/data/projects').resolve()
