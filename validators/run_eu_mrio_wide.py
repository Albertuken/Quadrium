"""
Three blocks give what the whole archive gives: 0.4 % at the worst region.

WHY
-----
`load_eu_mrio` returns one region's own table, and its own notes say what that
cannot hold: the part of an impulse that runs through other regions and comes
back, a median 13.6 % of the output multipliers. `load_eu_mrio_wide` returns
the region, the rest of its country and the rest of the archive -- three
blocks that between them cover the archive, so that feedback is inside the
multipliers. The question this file answers is whether aggregating 271 regions
into two blocks costs anything, because an aggregate's technology is a mix and
nothing guarantees a mix behaves like its parts.

WHAT IT FOUND, ON 2018
------------------------
It costs almost nothing. Against the full 2,720-unit inverse, the three-block
table's multipliers for the region's own ten sectors are out by:

    region   three blocks (median / worst sector)   one region alone (median)
    ES51            0.04 %  /  0.45 %                        7.6 %
    AT13            0.01 %  /  0.28 %                        4.8 %
    FI1B            0.07 %  /  0.92 %                        7.8 %
    PL91            0.01 %  /  0.16 %                        9.2 %
    EL30            0.35 %  /  5.20 %                        4.2 %
    DE30            0.11 %  /  1.72 %                        2.7 %
    ITC4            0.01 %  /  0.21 %                        8.2 %

A one-region table is out by 2.7 % to 9.2 % at the median and by up to 79 % in
a single sector. Thirty rows carry what 2,720 carry, for the region you asked
about.

WHAT IS CHECKED
-----------------
- the three blocks cover the archive: 1 + the rest of the country + the rest,
  and their output adds up to the archive's own;
- the region's own block is the one-region table's, cell for cell;
- the trade between regions is intermediate demand here, so there is no
  final-demand column and no value-added row for it, and both identities
  close through the labelled RESIDUAL;
- the multipliers reproduce the full system, region by region.

Run:
    python3 validators/run_eu_mrio_wide.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MRIO = ROOT / "data" / "mrio"
REGIONS = ("ES51", "AT13", "FI1B", "PL91", "EL30", "DE30", "ITC4")
FAIL: list[str] = []

# Exit code 3, not 0. `check.sh` counts it as SKIPPED rather than as a pass:
# this validator opened no file and measured nothing, and a run that says
# "All checks passed" on evidence it never saw is the fault the suite exists
# to catch. It is not a failure -- a tree without the workbook still exits 0.
NOTHING_CHECKED = 3


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
        print("    -- the 2018 archive is absent (33 MB, gitignored). The URL "
              "and SHA-256 are in data/mrio/_provenance.json.")
        print("\n" + "=" * 78)
        print("Nothing was checked: the archive is not in this tree.")
        return NOTHING_CHECKED

    from quadrium.io_loader import load_eu_mrio, load_eu_mrio_wide

    rows, cover, same_block, shape = [], [], [], []
    for region in REGIONS:
        one = load_eu_mrio(MRIO, region, 2018)
        wide = load_eu_mrio_wide(MRIO, region, 2018)
        S = one.n
        counts = wide.interregional["regions_in_blocks"]
        cover.append((region, sum(counts)))
        same_block.append(np.array_equal(wide.Z[:S, :S], one.Z)
                          and np.array_equal(wide.X[:S], one.X))
        shape.append(
            wide.n == 3 * S
            and not any("other regions" in l for l in wide.Y_labels)
            and not any("other regions" in l for l in wide.VA_labels)
            and any("RESIDUAL" in l for l in wide.Y_labels)
            and any("RESIDUAL" in l for l in wide.VA_labels)
            and bool(np.allclose(wide.Z.sum(1) + wide.Y.sum(1), wide.X))
            and bool(np.allclose(wide.Z.sum(0) + wide.VA.sum(0), wide.X)))
        full = np.array(one.interregional["multiplier_full"])
        m1 = np.linalg.inv(np.eye(S) - one.Z / one.X).sum(0)
        m3 = np.linalg.inv(np.eye(wide.n) - wide.Z / wide.X)[:, :S].sum(0)
        e3 = 100 * np.abs(m3 / full - 1)
        e1 = 100 * np.abs(m1 / full - 1)
        rows.append((region, float(np.median(e3)), float(e3.max()),
                     float(np.median(e1)), float(e1.max())))

    print(f"\n    {'region':8}{'3 blocks':>12}{'worst':>9}"
          f"{'1 region':>12}{'worst':>9}")
    for r, a, b, c, d in rows:
        print(f"    {r:8}{a:>11.3f}%{b:>8.2f}%{c:>11.2f}%{d:>8.1f}%")
    print()

    check("the three blocks cover the archive, region for region",
          all(n == 272 for _, n in cover),
          ", ".join(f"{r} {n}" for r, n in cover))
    check("the region's own block is the one-region table's, cell for cell",
          all(same_block), f"{sum(same_block)} of {len(same_block)} regions")
    check("the trade between regions is intermediate demand here, and both "
          "identities close through the labelled residual", all(shape),
          f"{sum(shape)} of {len(shape)}: thirty units, no column and no row "
          f"for interregional trade")

    med3 = max(r[1] for r in rows)
    worst3 = max(r[2] for r in rows)
    med1 = [r[3] for r in rows]
    check("the three-block multipliers are the full system's, to within half "
          "a per cent at the worst region",
          med3 < 0.5 and worst3 < 6.0,
          f"median error at worst {med3:.2f} %, largest single sector "
          f"{worst3:.2f} %, over {len(rows)} regions")
    check("while the one-region table is out by several per cent, which is "
          "what this table is for",
          min(med1) > 2.0 and max(med1) > 5.0,
          f"median {min(med1):.1f} % to {max(med1):.1f} %, up to "
          f"{max(r[4] for r in rows):.0f} % in a single sector")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED:")
        for f in FAIL:
            print(f"  - {f}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
