"""
A second manual on supply, use and imports — and one warning that lands here.

`M-059`, `M-060` and `M-056` rest on the UN Handbook alone. Eurostat's 2008
manual covers the same three operations in chapters 4, 5 and 7, all three
extracted and unread until now. Written up as `M-064`. This file measures the
part that can be measured.

WHERE THE TWO MANUALS AGREE AND WHERE THEY PART
------------------------------------------------
    CORE_009 ¶6.36, p. 164   totals by industry -> known cells     -> cost structures
    CORE_019 §5.4.1, p. 146  totals by industry -> commodity flows -> row/col equilibrium

Same first step. The UN's remainder is an estimation problem, Eurostat's a
reconciliation against the product rows. Not in conflict — a compiler does both —
but `M-060`'s (E3) is the UN's order and it is not the only one.

CORE_019 also splits compilation into an **input (column) approach** and an
**output (row) approach**, the latter "identical with the commodity-flow method",
and requires that they check each other: p. 132, "the results of the
commodity-flow method have to be verified by the main findings of the input
method." **This engine works only in the input direction.** That is not a defect
— it disaggregates a balanced table rather than compiling one — but the
safeguard CORE_019 relies on has no counterpart here.

THE IMPORT WARNING, AND IT IS MEASURABLE
------------------------------------------
CORE_020 p. 195 refuses the obvious method: "a proportional allocation of imports
to the various uses would be misleading. Firstly, the import shares are not equal
(for example the import share in exports will usually be quite lower)".

Measured below on Spain and Italy 2022, that first reason holds and is not
marginal: exports carry the lowest import share of any use in both countries, and
in Italy it is 2.6 % against 22.0 % for intermediate consumption — a factor of
eight. A proportional allocation would hand exports the 14.9 % average.

WHAT IT DOES AND DOES NOT SAY ABOUT THIS ENGINE
-------------------------------------------------
CORE_020 is about allocating imports across **uses**. `split_sector` allocates a
parent's imported inputs across **subsectors**. Different operation; the warning
transfers only by analogy, and only as far as subsectors vary the way uses do.

That variation is measurable between existing industries, and it is large: the
import intensity of intermediate inputs spans 3.3 %–87.6 % in Spain and
0 %–65.4 % in Italy, a 5× to 9× spread between the tenth and ninetieth
percentile. Giving two subsectors the parent's average is therefore a strong
assumption of the same kind CORE_020 declines to make one level up.

`SplitSpec.va_row_keys` already allows a separate key for the imports row, with
`va_residual_row` required so the rest stays consistent. This is the citation for
using it and the measurement of what ignoring it risks.

Run:
    python3 validators/run_eurostat_manual_crosscheck.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "eurostat"
EXTRACTED = ROOT / "library" / "extracted"
FAIL: list[str] = []

_USES = [("TOTAL", "intermediate consumption"), ("P3_S14", "households"),
         ("P51G", "gross fixed capital formation"), ("P6", "exports"),
         ("TU", "all uses")]


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def _shares(geo: str, tag: str, use_dim: str, ava_dim: str, pref: str):
    from quadrium.eurostat import _Cube
    p = DATA / f"naio_10_{tag}_{geo}_2022.json"
    if not p.exists():
        return None, None
    cube = _Cube(json.loads(p.read_text()))
    total_code = pref + "TOTAL"

    def at(flow, col):
        return cube.at(stk_flow=flow, **{use_dim: col, ava_dim: total_code})

    by_use = {}
    for col, label in _USES:
        t, i = at("TOTAL", col), at("IMP", col)
        if t and i is not None and t != 0:
            by_use[label] = i / t

    # import intensity of each industry's intermediate inputs
    from quadrium.eurostat import _drop_aggregates
    on_both = set(cube.index[use_dim])
    codes = [c for c in cube.index[ava_dim]
             if c != total_code and c.startswith(pref) and c in on_both
             and at("TOTAL", c) is not None]
    codes, _ = _drop_aggregates(codes)
    intensity = []
    for j in codes:
        t, i = at("TOTAL", j), at("IMP", j)
        if t and t > 0 and i is not None:
            intensity.append(i / t)
    return by_use, np.array(intensity)


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # ---- the sources say what they say ------------------------------------
    for cid, fname, phrase, what in (
            ("CORE_019", "CORE_019_Eurostat2008_CH05_The_Use_Table.txt",
             "The output approach is identical with the commodity-flow method",
             "an output/row approach this engine has no counterpart for"),
            ("CORE_019", "CORE_019_Eurostat2008_CH05_The_Use_Table.txt",
             "The most commonly used approach consists of starting",
             "a fill order that agrees with CORE_009 on step one only"),
            ("CORE_020", "CORE_020_Eurostat2008_CH07_Import_Matrices.txt",
             "would thus be a method which is difficult to accept",
             "proportional allocation of imports, refused outright")):
        p = EXTRACTED / fname
        if p.exists():
            check(f"{cid} states {what}",
                  phrase in re.sub(r"\s+", " ", p.read_text()),
                  f'"{phrase}"')

    # ---- the measurable half ----------------------------------------------
    tables = {}
    for geo, tag, ud, ad, pref in (("ES", "cp1700", "prd_use", "prd_ava", "CPA_"),
                                   ("IT", "cp1750", "ind_use", "ind_ava", "")):
        by_use, intensity = _shares(geo, tag, ud, ad, pref)
        if by_use:
            tables[geo] = (by_use, intensity)
    if not tables:
        print("\n  (no fixture with an IMP variant available)")
        return 1 if FAIL else 0

    print()
    print(f"    import share by use, 2022")
    print(f"    {'':<34}" + "".join(f"{g:>10}" for g in tables))
    for _, label in _USES:
        row = "".join(f"{tables[g][0].get(label, float('nan')):>9.1%}"
                      for g in tables)
        print(f"    {label:<34}{row}")
    print()

    for geo, (by_use, _) in tables.items():
        exp = by_use.get("exports")
        others = [v for k, v in by_use.items()
                  if k not in ("exports", "all uses")]
        check(f"{geo}: exports carry the LOWEST import share of any use",
              exp is not None and exp < min(others),
              f"{exp:.1%} against {min(others):.1%}–{max(others):.1%} elsewhere "
              f"— CORE_020 p. 195 says 'the import share in exports will usually "
              f"be quite lower' and it does")
        check(f"  and a proportional allocation would overstate it",
              by_use["all uses"] / exp > 1.5,
              f"the average is {by_use['all uses']:.1%}, "
              f"{by_use['all uses'] / exp:.1f}x the truth")

    print()
    for geo, (_, intensity) in tables.items():
        lo, hi = np.percentile(intensity, 10), np.percentile(intensity, 90)
        check(f"{geo}: import intensity varies {hi / max(lo, 1e-9):.0f}x between "
              f"industries",
              hi / max(lo, 1e-9) > 4,
              f"p10 {lo:.1%}, p90 {hi:.1%}, range {intensity.min():.1%}–"
              f"{intensity.max():.1%} across {intensity.size} industries — so "
              f"giving two subsectors the parent's average is a strong claim")

    print()
    print("    The capability to avoid it exists: SplitSpec.va_row_keys takes a")
    print("    separate key for the imports row, and va_residual_row is required")
    print("    so the rest stays consistent (OQ-B-12). What was missing was the")
    print("    reason to reach for it.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
