"""
`OQ-B-07`: the case GRAS could not handle was solvable from the chapter itself.

UNH_18 ¶18.81 Steps 3 and 5, p. 569 divide by `p_j(r)` and `p_i(s)`, the sums of
the non-negative parts of a column and of a row. An entirely non-positive line
makes that zero. Both steps footnote that "Temurshoev and others (2013) propose a
different formulation in which p_j(r) = 0", and the chapter never gives it, so
this project raised `DegenerateMarginError` rather than guess.

Raising was one step too cautious, and it had a price: **GRAS could not be run on
a real published trade-and-transport margins matrix.** ¶18.36, pp. 558–559 names
this situation precisely — Temurshoev and others "deal with full non-positive
rows and/or columns, for example, the row elements of trade industries in a trade
margins matrix are always negative".

WHAT WAS MISSING WAS NOT A FORMULATION
---------------------------------------
The scaling factor is not defined by the printed root. It is defined by the
CONSTRAINT that root solves, which is Step 7 aggregated along the axis:

        p·x − n/x = t

At `p = 0` this does not become undefined. It stops being quadratic:

        −n/x = t     =>     x = n / (−t)

unique and positive whenever `n > 0` and `t < 0`, which is exactly the case
¶18.36 describes. Steps 3 and 5 divide by `p` because they print the root of the
quadratic, not because the problem requires `p > 0`.

This is DERIVED from the chapter's own Step 7 and is checked below two ways: it
satisfies the constraint exactly, and it is the limit of the printed root as
`p → 0⁺`. It is **not** claimed to be Temurshoev's formulation — `CORE_042` is
still unobtained, and that paper also treats infeasible RAS cases this does not.
The claim made here is narrower and sufficient: the degenerate case has exactly
one positive solution, and this is it.

THE WORKAROUND THE CHAPTER REPORTS COSTS MORE THAN IT LOOKS
------------------------------------------------------------
¶18.36, p. 559: "In practice, this is very helpful since small positive numbers
are often added to the initial table in order to guarantee convergence." Measured
below on the Austrian matrix, against the exact solution:

  * it is **wrong**, and not slightly — a perturbation of 1e-2 on a table whose
    largest cell is 25,174 moves the answer by 3.93, more than many real margin
    cells are worth;
  * it **breaks the sign structure it was applied to**. Adding a positive number
    to an all-non-positive row creates a positive cell, and GRAS preserves signs
    by construction (¶18.35, p. 558), so the result asserts that a trade-service
    product RECEIVES trade margin. It does not — that is what `ID-19` and the
    negatives in `ID-08` are about;
  * it is **numerically worse than useless below `p ≈ 1e-8`**, because with
    `t < 0` the printed root loses its significant digits to cancellation in
    `t + sqrt(t² + 4pn)`.

WHAT REMAINS OPEN
-----------------
`OQ-B-07` also covers "infeasible RAS cases as covered by Miller and Blair
(2009, page 336)", which this does not address, and the comparison against
Temurshoev's actual formulation cannot be made until `CORE_042` is obtained.

Run:
    python3 validators/run_gras_degenerate.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

from quadrium.gras import (  # noqa: E402
    SignInfeasibleError, gras, quadratic_scaling_factor, split_pn,
)

MARGINS = ROOT / "data" / "eurostat" / "naio_10_cp1620_AT_2022.json"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def _austrian_margins():
    """The real trade-and-transport margins matrix, product by user."""
    from quadrium.eurostat import _Cube
    cube = _Cube(json.loads(MARGINS.read_text()))
    prods = [p for p in cube.index["cpa2_1"]
             if p.startswith("CPA_") and p != "CPA_TOTAL"]
    users = [u for u in cube.index["ind_use"]
             if u not in ("TU", "TOTAL", "TFU")]
    M = np.array([[cube.at(ind_use=u, cpa2_1=p) or 0.0 for u in users]
                  for p in prods], float)
    keep_r = ~np.all(M == 0, axis=1)
    labels = [cube.labels["cpa2_1"].get(p, p) for p, k in zip(prods, keep_r) if k]
    M = M[keep_r][:, ~np.all(M == 0, axis=0)]
    return M, labels


def main() -> int:
    if not MARGINS.exists():
        print(f"fixture absent: {MARGINS.name}")
        return 0

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 76)

    # 1 -- the closed form solves the constraint, and IS the limit of the root.
    n_, t_ = 7.5, -3.0
    x = float(quadratic_scaling_factor(np.array([t_]), np.array([0.0]),
                                       np.array([n_]), "row")[0])
    check("with p = 0 the closed form satisfies Step 7's constraint exactly",
          abs(0.0 * x - n_ / x - t_) < 1e-12,
          f"x = n/(-t) = {x:.6f}; p·x − n/x = {0.0 * x - n_ / x:.12g} "
          f"against t = {t_}")
    approach = [(p, (t_ + np.sqrt(t_ * t_ + 4 * p * n_)) / (2 * p))
                for p in (1e-2, 1e-4, 1e-6)]
    check("and it is the limit of the printed quadratic root as p → 0⁺",
          all(abs(v - x) < 10 * p for p, v in approach),
          "; ".join(f"p={p:.0e} → {v:.6f}" for p, v in approach)
          + f"; limit {x:.6f}")

    # 2 -- the unreachable cases still refuse, and for the right reason.
    for t_bad, why in ((0.0, "target zero needs x → ∞"),
                       (3.0, "an all-non-positive line cannot reach a positive "
                             "total")):
        try:
            quadratic_scaling_factor(np.array([t_bad]), np.array([0.0]),
                                     np.array([n_]), "row")
            check(f"p = 0 with target {t_bad:g} is refused", False, "it was not")
        except SignInfeasibleError:
            check(f"p = 0 with target {t_bad:g} is still refused", True, why)

    # 3 -- the real matrix, which the project could not previously touch.
    M, labels = _austrian_margins()
    P, N = split_pn(M)
    deg = P.sum(1) == 0
    check("the Austrian margins matrix really does contain the named case",
          deg.sum() >= 3,
          f"{int(deg.sum())} entirely non-positive rows of {M.shape[0]} — "
          f"{', '.join(str(l)[:26] for l, d in zip(labels, deg) if d)[:150]}")

    u, v = M.sum(1), M.sum(0)
    res = gras(M, u, v)
    check("GRAS runs on it at all, which it could not before",
          res.converged, f"{res.iterations} iteration(s)")
    check("and projecting a table onto its own margins returns that table",
          float(np.abs(res.X - M).max()) < 1e-9,
          f"max|X − M| = {float(np.abs(res.X - M).max()):.3g}, and the "
          f"degenerate rows get a scaling factor of exactly "
          f"{np.unique(np.round(res.r[deg], 9)).tolist()}")

    # 4 -- a genuine projection, onto margins that are not the table's own.
    rng = np.random.default_rng(7)
    u2 = M.sum(1) * (1 + rng.uniform(-0.08, 0.08, M.shape[0]))
    v2 = M.sum(0) * (1 + rng.uniform(-0.08, 0.08, M.shape[1]))
    u2 *= v2.sum() / u2.sum()
    proj = gras(M, u2, v2)
    check("a real projection converges with the degenerate rows in it",
          proj.converged and float(np.abs(proj.X.sum(1) - u2).max()) < 1e-9,
          f"{proj.iterations} iterations, row targets hit to "
          f"{float(np.abs(proj.X.sum(1) - u2).max()):.3g}")
    check("the all-negative rows stay all-negative, as ID-19 requires",
          bool((proj.X[deg] <= 0).all()) and proj.sign_changes == 0,
          f"{proj.sign_changes} sign changes across the whole table")

    # The factors themselves are large, and that is not a defect: r and s are
    # jointly determined only up to their products, so a degenerate row can
    # carry a big r against small s. The table is what is determined.
    i = int(np.flatnonzero(deg)[0])
    n_i = (N[i] / proj.s).sum()
    check("each degenerate factor is exactly n_i(s) / (−u_i)",
          abs(proj.r[i] - n_i / (-u2[i])) < 1e-6 * proj.r[i],
          f"{n_i / (-u2[i]):.6f} against the solver's {proj.r[i]:.6f} — large "
          f"because r and s are determined only up to their products, which is "
          f"why the table and not the factor is what gets checked")

    # 5 -- and what the chapter's reported workaround would have cost.
    print()
    print("    The workaround ¶18.36 reports, measured against the exact answer:")
    print(f"    {'epsilon':>10}{'iter':>6}{'max|X − exact|':>16}   signs")
    worst_sign_ok = True
    for eps in (1e-2, 1e-4, 1e-6, 1e-8, 1e-10):
        Mp = M.copy()
        for k in np.flatnonzero(deg):
            Mp[k, M[k] == 0] = eps
        r = gras(Mp, u2, v2)
        d = float(np.abs(r.X - proj.X).max())
        signs_ok = bool((r.X[deg] <= 0).all())
        worst_sign_ok &= signs_ok
        print(f"    {eps:>10.0e}{r.iterations:>6}{d:>16.4g}   "
              f"{'preserved' if signs_ok else 'BROKEN'}")
    check("perturbing the seed breaks the sign structure it was applied to",
          not worst_sign_ok,
          "a positive number added to an all-non-positive row makes a positive "
          "cell, and GRAS preserves signs — the result then asserts that a "
          "trade-service product RECEIVES trade margin")
    print(f"\n    For scale: the largest cell in this matrix is "
          f"{np.abs(M).max():,.1f}.")

    print("\n" + "=" * 76)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
