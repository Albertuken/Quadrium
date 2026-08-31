"""Make the unit checks fail the runner, which they did not.

`tests/test_engine.py` reports through `check(name, ok, detail)`: it prints a
line and, when `ok` is false, appends to `FAILURES`. Run as a script that is
sound — `main()` reads the list at the end and exits non-zero.

`check.sh` does not run it as a script. It runs `pytest tests -q`, and pytest
only fails a test that RAISES. A `check(..., False, ...)` prints `FAIL`, appends
to a list nobody reads, and the test passes.

So all **250** checks in the suite were advisory under the gate that governs
every commit. Only an exception — a NameError, an unhandled LoaderError — could
fail it. Found on 2026-08-31 by asking the question directly rather than
assuming; the suite turned out to be genuinely clean, so nothing had been
hidden, but nothing would have been shown either.

The fix keeps the collect-and-report shape the project uses everywhere, in
validators as well as here: one hook at the end of the session, so a test that
fails three checks still reports all three instead of stopping at the first.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def pytest_sessionfinish(session, exitstatus):
    try:
        import test_engine
    except Exception:                                   # noqa: BLE001
        return
    failures = getattr(test_engine, "FAILURES", [])
    if not failures:
        return
    print(f"\n{len(failures)} check(s) FAILED:")
    for f in failures:
        print(f"  - {f}")
    session.exitstatus = 1
