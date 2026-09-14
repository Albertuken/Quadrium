"""
What a one-region table leaves out is spillover, and the feedback inside it is
two orders of magnitude smaller.

WHY THIS EXISTS
-----------------
`run_mrio_spillovers.py` splits each unit's output multiplier on the full
2,720-unit system into the rows of its own region and the rest, and reports the
share outside: a median 11.7 %. That quantity is output an impulse sets off in
OTHER regions -- what Miller (1966) calls interregional spillover. Miller's
interregional FEEDBACK is a different quantity: output in the region itself
that the full system adds beyond a table of that region alone, induced through
purchases that leave and come back.

The two were being called by one name. This file measures them separately, on
the same base, so that whatever carries the 11.7 % can say which it is.

WHAT IS MEASURED
------------------
For each unit j of each region r kept by `run_mrio_spillovers.py`:

    total      the column sum of the full inverse          m_j
    spillover  its rows outside r                         m_j - intra_j
    feedback   its rows inside r, beyond r's own table    intra_j - one_j

where `one` is the column sum of the inverse of r's own block alone. Both are
reported as shares of m_j. Thirteen regions are excluded as the spillover file
excludes them: four with no output, nine with no interregional trade.

Run:
    python3 validators/run_feedback_vs_spillover.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MRIO = ROOT / "data" / "mrio"
FAIL: list[str] = []
NOTHING_CHECKED = 3

EMPTY = {"UKI1", "UKI2", "UKM2", "UKM3"}
ISOLATED = {"DED2", "FR10", "HR03", "HR06", "HU11", "PT30", "RO11", "SI04",
            "SK01"}


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)
    if not ((MRIO / "_mrio2018_cache.npz").exists()
            or (MRIO / "MRIO_2018_272regions.xlsx").exists()):
        print("Nothing was checked: the 2018 archive is not in this tree.")
        return NOTHING_CHECKED

    from quadrium.io_loader import _MRIO_S as S
    from quadrium.io_loader import _mrio_block, _mrio_files, _mrio_side

    blk, fdf, _ = _mrio_files(MRIO, 2018)
    Z, labels = _mrio_block(blk)
    regions = list(dict.fromkeys(l.split("-", 1)[0] for l in labels))
    head, FD = _mrio_side(fdf, "rows")
    X = FD[:, head.index("TOTAL")]
    A = Z / np.where(X > 0, X, np.inf)
    L = np.linalg.inv(np.eye(len(X)) - A)
    m = L.sum(0)

    spill, feed = [], []
    kept = 0
    for k, r in enumerate(regions):
        if r in EMPTY | ISOLATED:
            continue
        sl = slice(k * S, (k + 1) * S)
        one = np.linalg.inv(np.eye(S) - A[sl, sl]).sum(0)
        intra = L[sl, sl].sum(0)
        ok = m[sl] > 0
        spill += list(100 * ((m[sl] - intra) / m[sl])[ok])
        feed += list(100 * ((intra - one) / m[sl])[ok])
        kept += 1
    spill, feed = np.array(spill), np.array(feed)
    ps, pf = (np.percentile(spill, [10, 50, 90]),
              np.percentile(feed, [10, 50, 90]))
    print(f"\n    {kept} regions, {len(spill)} units")
    print(f"    spillover  p10 {ps[0]:.1f} %   median {ps[1]:.1f} %   "
          f"p90 {ps[2]:.1f} %")
    print(f"    feedback   p10 {pf[0]:.3f} %  median {pf[1]:.3f} %  "
          f"p90 {pf[2]:.3f} %  max {feed.max():.2f} %\n")

    check("the spillover share is the one run_mrio_spillovers.py reports",
          kept == 259 and 11.0 < ps[1] < 12.5,
          f"median {ps[1]:.1f} % over {kept} regions")
    check("and the feedback inside the same multiplier is two orders of "
          "magnitude smaller, so the two are not one quantity",
          pf[1] < ps[1] / 100 and pf[2] < 1.0,
          f"median {pf[1]:.3f} % against {ps[1]:.1f} %, p90 {pf[2]:.2f} %")
    check("feedback is never negative: returning purchases add output, they "
          "do not remove it",
          float(feed.min()) > -1e-9, f"minimum {feed.min():.2e} %")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: " + ", ".join(FAIL))
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
