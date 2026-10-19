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


def optional_vst3_root(data_root=None):
    """Managed plugin directory; stdlib only, also used by standalone SDK tools."""
    default=Path(data_root if data_root is not None else application_data_root()).parent/'mta-optional-vst3'
    return Path(os.getenv('MTA_OPTIONAL_VST3_DIR',str(default))).expanduser().resolve()
