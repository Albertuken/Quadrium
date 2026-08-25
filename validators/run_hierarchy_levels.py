"""
A guard that had never once run, and the two countries that needed it.

`run_eurostat_ixi.py` records that the industry × industry loader's hierarchy
filter "has never had anything to drop", and `SOURCE_REGISTER.md` §3 point 1 said
the same: "All seven fixtures held here populate exactly one level; no country
has yet been seen to serve both."

**Both statements were wrong, and they were wrong for the same reason: the filter
could not see the codes it was given.**

`_covers` and `_divisions` read the classification NOTATION — a letter, two
digits, a range separator. `load_iot` strips the `CPA_` prefix only when it
builds `sector_codes`, long after `_coarsest_tiling` has run, so on every `CPA_`
dataset the filter was handed `CPA_B05` and matched nothing. It returned "no
aggregates found" on all input, and the sweep that produced the "one level"
conclusion used prefixed codes too, so it was blind in exactly the same way. A
no-op reporting success is worse than an absent check.

FRANCE AND DENMARK PUBLISH BOTH LEVELS
---------------------------------------
`CPA_B` beside `CPA_B05`–`CPA_B09`; `CPA_C10-12` beside `C10`, `C11`, `C12`;
`CPA_F` beside `F41`–`F43`; `CPA_I` beside `I55`, `I56`. **39 containments each**,
in `naio_10_cp15`. France's supply table sums to 7,939,582.2 against a published
6,121,102.4 — 30 % over — until the aggregates come out.

`load_sut` never had the filter at all, so France simply would not load. It
refused rather than returning a table 30 % too big, which is the behaviour this
project wants, but it meant a member state was unreachable and the reason was
recorded as a property of the data rather than of the code.

A SECOND DEFECT, LIVE ONLY ONCE THE FIRST WAS FIXED
----------------------------------------------------
With prefixes visible, the section rule `b.startswith(a)` produced two false
positives in every `cp15`/`cp16` fixture: section `O` "covering" `OP_RES`, and
section `D` "covering" `D21X31`. Those are accounting rows, not divisions. In
`load_iot` the both-axes rule removes such rows before the filter runs, so they
were harmless there; `load_sut` has no such rule and they were not. A section now
covers only codes whose remainder is a valid division.

Run:
    python3 validators/run_hierarchy_levels.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "eurostat"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def _populated(path: Path):
    from quadrium.eurostat import _Cube
    cube = _Cube(json.loads(path.read_text()))
    return cube, [c for c in cube.index["prd_amo"]
                  if c != "CPA_TOTAL"
                  and cube.at(ind_impv="TS_BP", prd_amo=c) is not None]


def main() -> int:
    from quadrium.eurostat import _covers, _coarsest_tiling, load_sut

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # 1 -- the filter sees prefixed codes now.
    check("a prefixed section is recognised as covering its own divisions",
          _covers("CPA_B", "CPA_B05") and _covers("CPA_C10-12", "CPA_C11"),
          "`CPA_B` over `CPA_B05`, `CPA_C10-12` over `CPA_C11` — neither was "
          "detected before, because both were read as opaque strings")

    # 2 -- and does NOT claim an accounting row is a division.
    check("and a section does not 'cover' an accounting row that shares its "
          "letter",
          not _covers("CPA_O", "OP_RES") and not _covers("CPA_D", "D21X31"),
          "`OP_RES` and `D21X31` are not divisions of sections O and D; the "
          "startswith test said they were, in every cp15/cp16 fixture")

    # 3 -- the two countries that actually publish both levels.
    counts = {}
    for geo in ("FR", "DK", "AT", "ES", "NL", "NO"):
        p = DATA / f"naio_10_cp15_{geo}_2022.json"
        if not p.exists():
            continue
        _, pop = _populated(p)
        overlaps = sum(1 for a in pop for b in pop if _covers(a, b))
        kept, dropped = _coarsest_tiling(pop)
        counts[geo] = (len(pop), overlaps, len(dropped))
    print()
    print(f"    {'country':<9}{'populated':>11}{'containments':>14}{'dropped':>9}")
    for geo, (n, ov, dr) in counts.items():
        print(f"    {geo:<9}{n:>11}{ov:>14}{dr:>9}")
    print()

    both = {g for g, (_, ov, _) in counts.items() if ov > 0}
    check("France and Denmark publish two levels of the CPA hierarchy",
          both == {"FR", "DK"},
          f"{', '.join(sorted(both))} — 39 containments each. The claim that "
          f"'no country has yet been seen to serve both' was an artefact of a "
          f"filter that could not read prefixed codes")
    check("and everyone else publishes one, so the filter drops nothing there",
          all(counts[g][2] == 0 for g in counts if g not in both),
          "AT, ES, NL, NO unchanged")

    # 4 -- France now loads, and balances.
    fr = (DATA / "naio_10_cp15_FR_2022.json", DATA / "naio_10_cp16_FR_2022.json")
    if all(p.exists() for p in fr):
        import numpy as np
        s = load_sut(*fr)
        # 65x65 until 2026-08-25, when the loaders began keeping the FINEST
        # tiling a publisher offers rather than the coarsest. France publishes
        # both levels, so it now arrives with the detail it actually
        # transmits: 89 products against 88 industries, `T98` being a product
        # and not an industry. The old assertion pinned the coarse shape and
        # would have quietly protected the resolution loss.
        check("France's supply-use pair loads at the detail France publishes",
              s.n_products == 89 and s.n_activities == 88,
              f"{s.n_products}x{s.n_activities} — 65x65 under the coarsest "
              f"tiling, and the unfiltered set summed to 7,939,582.2 against "
              f"a published 6,121,102.4")
        check("and ID-07 holds on it",
              float(np.abs(s.V.sum(1) - s.q).max()) < 1e-6,
              f"max deviation {float(np.abs(s.V.sum(1) - s.q).max()):.3g}")

    print()
    print("    The lesson, for the next guard: a filter that reports success on")
    print("    input it cannot parse is indistinguishable from a filter that")
    print("    found nothing. This one said 'no aggregates' for two nights, and")
    print("    the conclusion drawn from it went into the source register as a")
    print("    fact about Eurostat.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
