"""
The industry x industry table, and what it costs to select a sector set.

`naio_10_cp1750` is the industry-by-industry input-output table. The project
already read `naio_10_cp1700`, product by product, and the two look
interchangeable from the outside: same API, same shape, same identities. They
are not, and the difference is one that only shows up in the codes.

  * `cp1700` indexes products as `CPA_A01`, `CPA_B`, `CPA_TOTAL`.
  * `cp1750` indexes industries as `A01`, `B`, `TOTAL` -- NO PREFIX AT ALL.

The prefix was doing silent work. `c.startswith("CPA_")` kept the value-added
rows out of the product set for free, because `D1`, `B2A3G`, `P1` and `IMP` are
not prefixed. With `pref = ""` that filter admits everything, and "carries a
value" is not a second line of defence: value-added rows carry values.

WHAT THAT COST, MEASURED
------------------------
The sector set came to 68 codes summing to 10,096,344.3 against a published
total of 4,124,091.0 -- 2.4x. The excess was `P1` (output itself), `P2_ADJ` and
`IMP` counted as though they were branches of activity.

The first diagnosis was that Eurostat had served an aggregate beside its own
components, and a hierarchy filter was written for it. That diagnosis was
WRONG, and the record says so: all seven Eurostat fixtures here publish exactly
one level, and the filter has never had anything to drop. What fixed it was a
different rule -- A SECTOR APPEARS ON BOTH AXES. An industry both buys and
sells, so it is indexed on `ind_ava` and on `ind_use` alike; value-added rows
appear only as suppliers, final-demand columns only as users.

That rule is also the only one that is safe. Letting the hierarchy filter do
the work dropped `D21X31`, `P2_ADJ` and `IMP` -- the right three codes, for a
false reason: their initials collide with NACE sections D, P and I, so the
section appeared to "contain" the tax row. The same collision had already cost
this project NACE section P (Education) once.

TWO MORE THINGS THIS FIXTURE FORCED, BOTH ABOUT TOLERANCE
---------------------------------------------------------
1. A missing cell is not a missing row. Italy's `D1` omits one industry, and
   the loader read that as "compensation of employees unavailable" and zeroed
   the whole 783,597.5 row -- caught downstream as a 70,444 imbalance. Eurostat
   omits structural zeros and suppressions alike, so neither reading is safe by
   itself. The row's own published total settles it: fill with zeros, then
   reconcile. Italy's `D1` reconciles exactly, so the absence is a genuine zero
   -- an industry with no employees, which for imputed rents is expected.

2. Flat tolerances do not survive rounding. Cells are published to two
   decimals, so a sum of `n` of them is entitled to `0.005n`. A flat 1e-3
   rejected Italy's final-demand identity at 0.0200 across 8 columns. A real
   imbalance is not close to that line: the two this loader has actually caught
   were 78,638 and 70,444.

WHAT IS NOT ESTABLISHED HERE
----------------------------
That an Italian ixi table and a Spanish pxp table may be compared. They may
not. ES, AT, DE and FR publish NO industry x industry table for any year
2019-2022, so the two fixtures below are different countries by necessity, and
`cp1750` is a national transformation of a national supply-use pair. THE METHOD
DOES NOT TRAVEL WITH THE DATA.

Run:
    python3 validators/run_eurostat_ixi.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quadrium.eurostat import (  # noqa: E402
    _Cube, _covers, _rounding_tol, load_iot,
)

DATA = ROOT / "data" / "eurostat"
IXI = DATA / "naio_10_cp1750_IT_2022.json"
PXP = DATA / "naio_10_cp1700_ES_2022.json"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    missing = [p.name for p in (IXI, PXP) if not p.exists()]
    if missing:
        print(f"fixture(s) absent: {', '.join(missing)}")
        return 0

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 72)

    # 1 -- the loader returns a table, and it is the one the source published.
    for path, variants in ((IXI, ("domestic", "total")),
                           (PXP, ("domestic", "total"))):
        for variant in variants:
            t = load_iot(path, variant=variant)
            tol = _rounding_tol(t.n + t.Y.shape[1])
            r = float(np.abs(t.Z.sum(1) + t.Y.sum(1) - t.X).max())
            c = float(np.abs(t.Z.sum(0) + t.VA.sum(0) - t.X).max())
            check(f"{t.table_id} balances both ways",
                  max(r, c) < tol,
                  f"{t.n} sectors, row {r:.3g}, column {c:.3g} "
                  f"(tolerance {tol:g} for {t.n + t.Y.shape[1]} rounded cells)")

    ixi = load_iot(IXI, variant="domestic")
    pxp = load_iot(PXP, variant="domestic")

    # 2 -- the axis really is different, and the codes prove it.
    check("the industry table indexes NACE with no prefix at all",
          "A01" in ixi.sector_codes and "CPA_A01" not in ixi.sector_codes,
          f"first codes {', '.join(ixi.sector_codes[:5])} — against "
          f"{', '.join(pxp.sector_codes[:3])} in the product table, where the "
          f"loader strips a `CPA_` that is genuinely there")

    # 3 -- the rule that actually selects sectors, stated as a test.
    cube = _Cube(json.loads(IXI.read_text()))
    on_both = set(cube.index["ind_use"]) & set(cube.index["ind_ava"])
    va_only = [c for c in ("D1", "B2A3G", "P1", "IMP", "TS_BP", "P2_ADJ",
                           "D21X31") if c in cube.index["ind_ava"]]
    check("value-added rows are indexed as suppliers but never as users",
          all(c not in on_both for c in va_only),
          f"{len(va_only)} of them — {', '.join(va_only)} — which is why "
          f"'appears on both axes' identifies a sector and 'carries a value' "
          f"does not")
    check("and none of them survived into the sector set",
          all(c not in ixi.sector_codes for c in va_only),
          f"{ixi.n} sectors, none of which is an accounting row")

    # The failure this replaced, reconstructed so the number is not folklore.
    naive = [c for c in cube.index["ind_ava"] if c != "TOTAL"
             and cube.at(stk_flow="DOM", ind_use="TU", ind_ava=c) is not None]
    naive_sum = sum(cube.at(stk_flow="DOM", ind_use="TU", ind_ava=c)
                    for c in naive)
    published = cube.at(stk_flow="DOM", ind_use="TU", ind_ava="TOTAL")
    check("selecting on 'carries a value' alone still double counts, 2.4x",
          naive_sum > 2 * published,
          f"{len(naive)} codes summing to {naive_sum:,.1f} against "
          f"{published:,.1f} — the failure the prefix used to hide")
    check("and the published total is what refuses it",
          abs(sum(cube.at(stk_flow="DOM", ind_use="TU", ind_ava=c)
                  for c in ixi_codes(cube)) - published)
          <= 1e-6 * published,
          f"the {ixi.n} selected codes reconcile to {published:,.1f} exactly")

    # 4 -- the hierarchy filter, reported honestly as unexercised.
    mixed = [(a, b) for a in ixi.sector_codes for b in ixi.sector_codes
             if _covers(a, b)]
    check("no fixture here mixes hierarchy levels, so that filter never fires",
          not mixed,
          "sections P, D and I are present as sectors and their divisions "
          "P85, D35, I55 are not — one level, as published")

    # 5 -- a missing cell is a zero only when the row total says so.
    codes = ixi_codes(cube)
    for r, expect_missing in (("D1", True), ("IMP", False)):
        vals = [cube.at(stk_flow="DOM", ind_use=j, ind_ava=r) for j in codes]
        n_missing = sum(v is None for v in vals)
        total = cube.at(stk_flow="DOM", ind_use="TOTAL", ind_ava=r)
        got = sum(v or 0.0 for v in vals)
        check(f"{r}: {n_missing} absent cell(s), and the row total settles it",
              (n_missing > 0) == expect_missing
              and abs(got - total) <= _rounding_tol(len(codes)),
              f"{got:,.1f} against a published {total:,.1f} — "
              + ("the absence is a true zero, not a suppression"
                 if n_missing else "nothing absent to adjudicate"))

    # 6 -- and the row is carried, not silently zeroed. This is the regression.
    d1 = ixi.VA[ixi.VA_labels.index(
        next(l for l in ixi.VA_labels if "employee" in l.lower()))]
    check("the D1 row reaches the table with its value, not as zeros",
          d1.sum() > 700_000,
          f"{d1.sum():,.1f} — it arrived as {0.0:,.1f} before the row total "
          f"was consulted, and the column identity caught it as 70,444")

    print("\n" + "=" * 72)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


def ixi_codes(cube) -> list[str]:
    """The sector set, by the loader's own three rules."""
    on_both = set(cube.index["ind_use"])
    return [c for c in cube.index["ind_ava"]
            if c != "TOTAL" and c in on_both
            and cube.at(stk_flow="DOM", ind_use="TU", ind_ava=c) is not None]


if __name__ == "__main__":
    sys.exit(main())
