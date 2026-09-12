#!/usr/bin/env python3
"""Entry point: python3 scripts/edit.py [--prepare-only|--preview|--validate-only]."""
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
try:
    import PIL
except ImportError:
    bundled=Path('/Users/magnet/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3')
    if bundled.exists():
        os.execv(str(bundled),[str(bundled),str(Path(__file__).resolve()),*sys.argv[1:]])
    raise SystemExit('Pillow is required. Install Pillow in your Python environment.')
sys.path.insert(0,str(ROOT/'src'))
from ffmpeg_edit import main
if __name__=='__main__':
    main()
