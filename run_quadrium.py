#!/usr/bin/env python3
"""Run Quadrium from a checkout, without installing it."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from quadrium.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
