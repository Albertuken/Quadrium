#!/usr/bin/env python3
"""Run Quadrium from this checkout, without installing it.

The real entry point is `quadrium.cli:main`, which `pip install quadrium`
exposes as the `quadrium` command. This wrapper only puts `src/` on the path
first, so the repository runs as it stands.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from quadrium.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
