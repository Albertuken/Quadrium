"""
`OQ-B-09`: how often a cell really changes sign, and how to know before you run.

UNH_18 ¶18.33, pp. 557–558 names sign preservation as a drawback of the whole
biproportional family "where the cell value can switch sign between periods, as,
for example, with taxes less subsidies on products or changes in inventories".
`OQ-B-09` recorded that as a proved impossibility — GRAS's Step 7 with `r, s > 0`
cannot take a cell across zero — and left two things unknown: how the projection
should behave, and **whether the case is detectable in advance from the base
table and the margins alone**.

The second is answerable without any source. The first is not, and stays open.

PART ONE — HOW OFTEN, MEASURED ON PUBLISHED DATA
------------------------------------------------
The entry said "any multi-year projection of this project's own test table can
hit the case". That was a plausibility argument. Three real Austrian and four
Spanish vintages turn it into a measurement, and the answer is not one number —
it is three, two orders of magnitude apart:

    trade and transport margins   `cp1620` AT 2018/2020/2022      0.00 %
    taxes less subsidies          `cp1630` AT 2018/2020/2022      0.24 – 0.78 %
    changes in inventories `P52`  `cp1700` ES 2019–2022          18   – 42 %

**The margins matrix never flips, and that is not luck.** A trade-service product
gives up margin and a good receives it; the sign is structural, which is what
`ID-08` and `ID-19` are about. Sign preservation is the CORRECT behaviour there,
not a limitation — and the margins matrix is the block with the most negatives in
the whole framework, so the intuition "lots of negatives means lots of flipping"
is exactly backwards.

**Changes in inventories flip constantly.** Four products in ten, year on year.
For this cell UNH_18's "may also be seen as a drawback" is an understatement:
sign preservation is not an edge case to guard against, it is the normal case,
and any projection of a final-demand block containing `P52` will meet it.

PART TWO — DETECTABLE IN ADVANCE, EXACTLY
------------------------------------------
GRAS can only return a table with the base table's sign pattern. So "does this
projection need a sign change?" is "does ANY matrix with that sign pattern have
these margins?", and that is a linear feasibility problem:

    X_ij = sign(T_ij)·x_ij,   x_ij ≥ 0 on supp(T),   X·1 = u,   1ᵀX = v

`sign_pattern_feasible()` solves it. It is **strictly stronger** than the
per-line test the module already had, which checks one row or column at a time
and is necessary but not sufficient. The smallest separating case is 2×2 and is
checked below.

The useful direction is the refusal: infeasible here means GRAS certainly cannot
do it. Feasible means the sign pattern is not the obstruction — it does not
promise convergence, because the LP admits `x = 0` where GRAS needs strictly
positive factors.

WHAT IS STILL OPEN
------------------
What the engine should DO when the case is detected — fail, warn, or fall back.
That needs Lenzen and others (2014), cited at ¶18.33, p. 558 and not held.
Detection at least turns a silent wrong answer into a stated one.

Run:
    python3 validators/run_sign_change.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

from quadrium.gras import sign_pattern_feasible  # noqa: E402

DATA = ROOT / "data" / "eurostat"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def _matrix(tag, geo, year, rowdim, coldim, pref, drop):
    from quadrium.eurostat import _Cube
    p = DATA / f"naio_10_{tag}_{geo}_{year}.json"
    if not p.exists():
        return None, None, None
    cube = _Cube(json.loads(p.read_text()))
    rows = [c for c in cube.index[rowdim]
            if c.startswith(pref) and c != pref + "TOTAL"]
    cols = [c for c in cube.index[coldim] if c not in drop]
    kw = {"stk_flow": "TOTAL"} if "stk_flow" in cube.ids else {}
    M = np.array([[cube.at(**kw, **{coldim: c, rowdim: r}) or 0.0
                   for c in cols] for r in rows], float)
    return M, rows, cols


def _flip_rate(a, b):
    both = (a != 0) & (b != 0)
    if not both.any():
        return None, 0, 0
    flips = both & (np.sign(a) != np.sign(b))
    return flips.sum() / both.sum(), int(flips.sum()), int(both.sum())


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # ---- PART ONE: measurement --------------------------------------------
    series = {}
    for tag, geo, years, label in (
            ("cp1620", "AT", (2018, 2020, 2022), "trade and transport margins"),
            ("cp1630", "AT", (2018, 2020, 2022), "taxes less subsidies")):
        mats = {y: _matrix(tag, geo, y, "cpa2_1", "ind_use", "CPA_",
                           ("TU", "TOTAL", "TFU"))[0] for y in years}
        if any(m is None for m in mats.values()):
            print(f"  (fixture(s) absent for {tag} {geo})")
            continue
        rates = []
        for a, b in zip(years, years[1:]):
            rate, nf, nb = _flip_rate(mats[a], mats[b])
            rates.append((f"{a}→{b}", rate, nf, nb))
        series[label] = rates

    inv = {}
    for y in (2019, 2020, 2021, 2022):
        p = DATA / f"naio_10_cp1700_ES_{y}.json"
        if not p.exists():
            continue
        from quadrium.eurostat import _Cube
        cube = _Cube(json.loads(p.read_text()))
        if "P52" not in cube.index["prd_use"]:
            continue
        prods = [c for c in cube.index["prd_ava"]
                 if c.startswith("CPA_") and c != "CPA_TOTAL"]
        inv[y] = np.array([cube.at(stk_flow="TOTAL", prd_use="P52", prd_ava=c)
                           or 0.0 for c in prods], float)
    ys = sorted(inv)
    if len(ys) > 1:
        series["changes in inventories (P52)"] = [
            (f"{a}→{b}",) + _flip_rate(inv[a], inv[b])
            for a, b in zip(ys, ys[1:])]

    for label, rates in series.items():
        detail = "; ".join(f"{p} {r:.2%} ({nf}/{nb})" for p, r, nf, nb in rates)
        print(f"  {label:<32} {detail}")
    print()

    margins = series.get("trade and transport margins", [])
    taxes = series.get("taxes less subsidies", [])
    stocks = series.get("changes in inventories (P52)", [])

    if margins:
        check("the margins matrix never changes sign, across three vintages",
              all(nf == 0 for _, _, nf, _ in margins),
              "the sign there is structural — a trade-service product gives up "
              "margin, a good receives it — so sign preservation is CORRECT, "
              "in the block with the most negatives in the framework")
    if taxes:
        check("taxes less subsidies do change sign, as ¶18.33 says, but rarely",
              any(nf > 0 for _, _, nf, _ in taxes)
              and max(r for _, r, _, _ in taxes) < 0.02,
              f"worst {max(r for _, r, _, _ in taxes):.2%}")
    if stocks:
        worst = max(r for _, r, _, _ in stocks)
        check("changes in inventories flip constantly, which is a different "
              "order of problem",
              worst > 0.15,
              f"up to {worst:.0%} of products year on year — for this cell "
              f"sign preservation is not an edge case but the normal case")

    # ---- PART TWO: detection ----------------------------------------------
    print()
    T = np.array([[1.0, 0.0], [0.0, -1.0]])
    u_bad, v_bad = np.array([200.0, -100.0]), np.array([300.0, -200.0])
    ok_line = (u_bad[0] > 0 and u_bad[1] < 0 and v_bad[0] > 0 and v_bad[1] < 0
               and abs(u_bad.sum() - v_bad.sum()) < 1e-12)
    feasible, why = sign_pattern_feasible(T, u_bad, v_bad)
    check("the per-line test passes a case that is actually infeasible",
          ok_line and not feasible,
          "every line has the right sign available and the margins agree; the "
          "one positive cell would still have to be 2 and 3 at once")
    check("and the exact test catches it",
          not feasible and "sign preserving" in why,
          why.split(".")[0])

    ok2, _ = sign_pattern_feasible(T, np.array([200.0, -100.0]),
                                   np.array([200.0, -100.0]))
    check("while a genuinely reachable target is accepted", ok2,
          "the test refuses infeasibility, it does not refuse negatives")

    # On real data: a table's own margins are reachable by construction.
    M, _, _ = _matrix("cp1620", "AT", 2022, "cpa2_1", "ind_use", "CPA_",
                      ("TU", "TOTAL", "TFU"))
    if M is not None:
        M = M[~np.all(M == 0, axis=1)][:, ~np.all(M == 0, axis=0)]
        ok3, _ = sign_pattern_feasible(M, M.sum(1), M.sum(0))
        check("and a real margins matrix is feasible against its own totals",
              ok3, f"{M.shape[0]}×{M.shape[1]}, "
                   f"{int((M != 0).sum()):,} cells in the support")

    print()
    print("    Still open: what the engine should DO on detection — fail, warn")
    # ---- v1.33: CORE_016 does take a position, and it is not Lenzen's ----
    import re as _re
    c16 = (ROOT / "library" / "extracted"
           / "CORE_016_OECD_EU2025_CH05_Balancing_Extended_SUTs.txt")
    if c16.exists():
        f16 = _re.sub(r"\s+", " ", c16.read_text())
        print()
        check("sign preservation is named as a PROPERTY of the RAS family, not "
              "an accident",
              "characteristic of sign preservation inherent in RAS/GRAS "
              "problems" in f16,
              "CORE_016 — this entry's premise, stated by a source rather than "
              "inferred from three vintages of data")
        check("and the source takes a position on what a forced sign change "
              "MEANS",
              "renders the problem economically meaningless o r unfeasible, as "
              "it forces the remaining coefficients in the vector to change "
              "signs" in f16,
              "when predetermined cells exceed their targets the additional "
              "information 'renders the problem economically meaningless or "
              "unfeasible'. **A forced sign change is a diagnosis of ill-posed "
              "inputs, not a capability to be added.** That is the opposite of "
              "looking for a method that permits sign flips")
        check("with a remedy that is about the data, not the solver",
              "either the target values or the additional information must be "
              "reconciled" in f16,
              "'potentially requiring a compromise, especially when both sets "
              "of information are less reliable'. So the answer to 'what "
              "should the engine do' is: refuse, name which two inputs "
              "disagree, and hand it back — which is what the detection half "
              "already built")
        print()
        print("    This does not make Lenzen unnecessary: CORE_016 says an")
        print("    infeasible problem is infeasible, and says nothing about the")
        print("    cells that legitimately need to flip — inventories, which")
        print("    flip in up to 42 % of products year on year. Those are not")
        print("    ill-posed inputs and they still have no method.")
    else:
        print("    or fall back. That needs Lenzen and others (2014), ¶18.33,")
        print("    p. 558, which this project does not hold.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
