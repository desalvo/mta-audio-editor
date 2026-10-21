#!/usr/bin/env python3
"""Source-tree wrapper for python -m app.restore_dump."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.restore_dump import main  # noqa: E402
if __name__ == '__main__':
    main()
