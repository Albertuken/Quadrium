"""
Every provenance sidecar carries the fields the engine reads out of it.

WHY THIS EXISTS
----------------
`data/eurostat/*.provenance` is written two ways: by `eurostat.fetch()` on a
download, and by hand when a file is brought into the repository from a probe
that ran somewhere else. On 2026-08-26 seven were written by hand with the key
`retrieved` where `fetch()` writes `retrieved_at`, and `config.py` read the
second with `rec['retrieved_at']`.

The result was not a warning. The table loaded, transformed and projected, and
then the run died with

    KeyError: 'retrieved_at'

while composing the sentence that says where the data came from. **A note about
the data killed the run that had already produced the answer.**

Two things came out of it and both are here: the seven sidecars are written the
way `fetch()` writes them, and every reader now uses `.get` with a stated
fallback, so a missing field degrades the stamp instead of ending the run.

What this checks is the first: that the hand-written ones and the fetched ones
carry the same fields, so the two kinds cannot drift apart again silently.

Run:
    python3 validators/run_provenance_sidecars.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# What `eurostat.fetch()` writes, and therefore what a reader may expect.
REQUIRED = ("url", "dataset", "geo", "year", "bytes", "sha256", "retrieved_at")
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    files = sorted(DATA.rglob("*.provenance"))
    check("there are sidecars to check", bool(files),
          f"{len(files)} across {len({f.parent.name for f in files})} folder(s)")

    bad, unreadable = {}, []
    for f in files:
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            unreadable.append((f.name, type(exc).__name__))
            continue
        missing = [k for k in REQUIRED if k not in rec]
        if missing:
            bad[f.name] = missing

    check("every sidecar is readable JSON", not unreadable,
          ", ".join(f"{n}: {e}" for n, e in unreadable) or f"{len(files)} read")
    check("and every one carries the fields the engine reads",
          not bad,
          "\n".join(f"      {n}: missing {', '.join(m)}"
                    for n, m in list(bad.items())[:8])
          or f"{', '.join(REQUIRED)} — present in all {len(files)}")

    # The hashes are the point of the sidecar; check they still hold.
    import hashlib
    wrong = []
    for f in files:
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        data = f.with_suffix("")
        if not data.exists() or "sha256" not in rec:
            continue
        b = data.read_bytes()
        if hashlib.sha256(b).hexdigest() != rec["sha256"] or len(b) != rec.get("bytes", len(b)):
            wrong.append(data.name)
    check("and the file beside it still hashes to what the sidecar records",
          not wrong, ", ".join(wrong) or f"{len(files)} verified")

    print()
    print("    A provenance stamp is a note about the data. A missing field in")
    print("    one must degrade the note, not end a run that has already")
    print("    produced its answer.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
