"""
Projecting Spain 2021 onto 2022's totals, and comparing with the 2022 the
office actually published.

WHAT HAD AND HAD NOT BEEN TESTED
----------------------------------
SUT-EURO reproduces UNH_18 Box 18.7's printed iterations exactly, and
`run_projection.py` checks that projecting a pair onto its own totals returns
that pair. Both are tests that the CODE implements the chapter. Neither is a
test of whether the ANSWER is any good, and nothing in the chapter claims one.

That test became possible on 2026-08-26: Eurostat serves Spain, Austria, Italy
and the Netherlands as consecutive projectable pairs, so a 2021 table can be
projected onto 2022's published value added, final use, taxes and imports and
then compared, cell by cell, with the 2022 table itself.

TWO PLAIN DEFECTS, FOUND BY RUNNING IT
----------------------------------------
**The iteration ceiling was set from a fixture that converges in three.**
`PROJECT_MAX_ITER` was 200. Iterations actually needed to reach the chapter's
own 1 per cent rule:

    ES 2021 -> 2022     356        IT 2021 -> 2022   2,835
    AT 2021 -> 2022     561        NL 2021 -> 2022   1,703
    AT 2020 -> 2022   1,617

**And the note said it converged anyway.** `project` wrote "Converged in N
iteration(s)" unconditionally. At the 200 ceiling Austria was still 9.4 per
cent from its target and Spain 2.5, and the one sentence a reader would look at
said success. The ceiling is now 5,000 and a run that does not converge raises
instead, naming the deviation and the two things that cause it.

AND THE MEASUREMENT, WHICH IS NOT FLATTERING
----------------------------------------------
Against the published later year, with every run converged:

    case              iterations   projected   base year   base year
                                                unchanged     scaled
    ES 2021 -> 2022        356        34.0 %      29.4 %     28.8 %
    AT 2021 -> 2022        561        24.1 %      22.0 %     19.9 %
    AT 2020 -> 2022      1,617        63.1 %      33.0 %     28.6 %
    IT 2021 -> 2022      2,835        46.2 %      21.5 %     19.9 %
    NL 2021 -> 2022      1,703        25.9 %      19.6 %     15.2 %

    (total absolute error on domestic intermediate use, as a share of it)

The projection is further from the published table than the base year left
alone, in all five. On levels that could be dismissed as a scale effect — but
the same holds on TECHNICAL COEFFICIENTS, which have no scale:

    mean |Δa_ij|, per thousand      projected   base year
    ES 2021 -> 2022                     2.117       2.029
    AT 2021 -> 2022                     1.125       0.847
    AT 2020 -> 2022                     2.582       1.426
    IT 2021 -> 2022                     2.052       1.599
    NL 2021 -> 2022                     1.199       0.884

It is not the project's own parameter either. `OQ-B-10` reads the chapter's `ε`
as a damping exponent and the engine uses 0.9; sweeping it from 0.3 to 1.0
moves the iteration count from 491 to 907 on Austria and the coefficient error
from 1.120 to 1.125 per thousand. **`ε` is a convergence-speed knob, not an
accuracy knob.**

WHAT THIS DOES AND DOES NOT SAY
---------------------------------
It does NOT say the method is wrong, and the comparison is not symmetric: the
projected pair is CONSISTENT with 2022's published value added, final use,
taxes and imports, and the base year is not consistent with any of them. That
consistency is the whole product. Whoever needs a table that adds up to known
2022 aggregates cannot use the 2021 table at all, however close its cells are.

What it says is that the consistency is bought, and this is the price: on five
tests across four countries and one- to two-year horizons, imposing the target
aggregates moved the individual cells AWAY from what the office later
published. Five tests are five tests. But nobody should read "projected to
2026" as "a better estimate of 2026's structure than 2022's table", and until
2026-08-26 nothing in this engine said otherwise.

Run:
    python3 validators/run_projection_backtest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "eurostat"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def pair(geo: str, year: int):
    from quadrium.eurostat import load_sut
    return load_sut(DATA / f"naio_10_cp15_{geo}_{year}.json",
                    DATA / f"naio_10_cp16_{geo}_{year}.json",
                    DATA / f"naio_10_cp1610_{geo}_{year}.json")


def main() -> int:
    from quadrium.sut_euro import PROJECT_MAX_ITER, sut_euro

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    need = [DATA / f"naio_10_{d}_ES_{y}.json"
            for y in (2021, 2022) for d in ("cp15", "cp16", "cp1610")]
    if not all(f.exists() for f in need):
        print("  (Spain's 2021 and 2022 pairs are not both here; nothing to "
              "back-test)")
        return 0

    A, B = pair("ES", 2021), pair("ES", 2022)
    check("two consecutive years of the same pair, on identical axes",
          A.product_codes == B.product_codes
          and A.activity_codes == B.activity_codes
          and A.Y_labels == B.Y_labels,
          f"{len(A.product_codes)} products x {len(A.activity_codes)} "
          f"activities — a projection can only be scored against a table "
          f"indexed the same way")

    api, aai = np.flatnonzero(A.q > 0), np.flatnonzero(A.g > 0)
    bpi, bai = np.flatnonzero(B.q > 0), np.flatnonzero(B.g > 0)
    Ud0 = np.hstack([A.U_domestic[np.ix_(api, aai)], A.Y_domestic[api]])
    Um0 = np.hstack([A.U_imported[np.ix_(api, aai)], A.Y_imported[api]])
    tls0 = np.concatenate([A.taxes_by_activity[aai], A.taxes_by_final_demand])
    na = len(aai)
    target = dict(
        va_target=B.W.sum(0)[bai],
        final_use_target=(B.Y_domestic.sum(0) + B.Y_imported.sum(0)
                          + B.taxes_by_final_demand),
        tls_target=float(B.taxes_by_activity.sum()
                         + B.taxes_by_final_demand.sum()),
        imports_target=float(B.imports[B.q > 0].sum()))

    # 1 -- the ceiling, and the sentence that used to be printed regardless.
    print()
    short = sut_euro(Ud0, Um0, tls0, A.V[np.ix_(api, aai)].T,
                     max_iter=200, **target)
    worst = max(abs(v - 1.0) for v in short.deviations.values()) * 100
    check("200 iterations is not enough for a real pair",
          not short.converged and worst > 1.0,
          f"stops at {short.iterations} with the worst aggregate {worst:.2f} % "
          f"from its target, against the chapter's own 1 per cent rule")
    check("and the ceiling is now past what real data needs",
          PROJECT_MAX_ITER >= 3000,
          f"{PROJECT_MAX_ITER}; measured need is 356 to 2,835 across five "
          f"country-pairs, where the chapter's own fixture takes three")

    # `project` takes the FULL-length vectors and masks them itself; the
    # `sut_euro` calls above take the already-masked blocks.
    try:
        A.project(gva=B.W.sum(0),
                  final_use=target["final_use_target"],
                  taxes=target["tls_target"], imports=target["imports_target"],
                  year=2022, max_iter=200)
        msg = ""
    except ValueError as exc:
        msg = str(exc)
    check("a projection that did not converge now refuses",
          "did not converge" in msg and "%" in msg,
          "it used to return a table whose own note read 'Converged in 200 "
          "iteration(s)' — false, and the one sentence a reader would look at")
    check("and the refusal names both things that cause it",
          "max_iter" in msg and "PURCHASERS" in msg,
          "too few iterations, or targets in the wrong price basis")

    # 2 -- the back-test itself.
    print()
    full = sut_euro(Ud0, Um0, tls0, A.V[np.ix_(api, aai)].T, **target)
    check("with the ceiling raised, it converges",
          full.converged, f"{full.iterations} iterations")

    Ad, Pd = Ud0[:, :na], full.Ud[:, :na]
    Bd = B.U_domestic[np.ix_(bpi, bai)]
    k = Bd.sum() / Ad.sum()
    lv = lambda e: float(np.abs(e - Bd).sum() / np.abs(Bd).sum() * 100)
    co = lambda e, x: float(np.abs(e / np.where(x == 0, 1.0, x)
                                   - Bd / np.where(B.g[bai] == 0, 1.0,
                                                   B.g[bai])).mean() * 1000)
    rows = (("projected", lv(Pd), co(Pd, full.x)),
            ("base year unchanged", lv(Ad), co(Ad, A.g[aai])),
            ("base year scaled", lv(Ad * k), co(Ad * k, A.g[aai] * k)))
    print(f"    {'':22}{'levels':>10}{'coefficients':>15}")
    for name, l, c in rows:
        print(f"    {name:<22}{l:>9.1f}%{c:>13.3f} /1000")

    check("the projection is further from the published year than the base is",
          rows[0][1] > rows[1][1] and rows[0][2] > rows[1][2],
          f"{rows[0][1]:.1f} % against {rows[1][1]:.1f} % on levels and "
          f"{rows[0][2]:.3f} against {rows[1][2]:.3f} per thousand on "
          f"coefficients — the coefficient comparison has no scale in it, so "
          f"this is not the base year winning by being smaller")

    # 3 -- and it is not the project's own damping choice.
    print()
    errs = {}
    for eps in (0.3, 0.9):
        r = sut_euro(Ud0, Um0, tls0, A.V[np.ix_(api, aai)].T,
                     damping_exponent=eps, **target)
        errs[eps] = (r.iterations, co(r.Ud[:, :na], r.x))
    check("the damping exponent moves the iteration count, not the answer",
          abs(errs[0.3][1] - errs[0.9][1]) < 0.05
          and errs[0.3][0] != errs[0.9][0],
          f"ε=0.3 takes {errs[0.3][0]} iterations for {errs[0.3][1]:.3f} and "
          f"ε=0.9 takes {errs[0.9][0]} for {errs[0.9][1]:.3f} — so OQ-B-10's "
          f"reading of ε is a convergence-speed choice and cannot be blamed "
          f"for the accuracy")

    # 4 -- what the projection DOES deliver, which is the point of it.
    print()
    got_va = full.gva.sum()
    want_va = float(target["va_target"].sum())
    base_va = float(A.W.sum())
    check("the projected pair hits the aggregates the base year cannot",
          abs(got_va - want_va) / want_va < 0.01
          and abs(base_va - want_va) / want_va > 0.05,
          f"value added {got_va:,.0f} against a target of {want_va:,.0f} "
          f"({abs(got_va - want_va) / want_va:.2%}), where the base year is "
          f"{base_va:,.0f} ({abs(base_va - want_va) / want_va:.1%} away). "
          f"That consistency is the product; the cell accuracy above is its "
          f"price")

    print()
    print("    Reproducing a chapter's printed iterations shows the code")
    print("    implements the method. It does not show the method is right,")
    print("    and nothing here had ever asked.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
