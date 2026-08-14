"""
`OQ-B-06`: UNH_18 prints two convergence thresholds an order of magnitude apart.
This file stops treating that as a defect to be adjudicated and measures why the
source needed both.

WHAT THE ENTRY ALREADY KNEW
----------------------------
* ¶18.81 Step 6, p. 569 (normative): "for example 10-8".
* Box 18.3, p. 570 (the worked example that is meant to demonstrate it): 1e-7.
* v1.24 established the cause of the gap by counterfactual: the chapter's own
  margins sum to 866,987.032 against 866,987.000, GRAS parks at 4.09e-08, and
  squaring the margins makes 1e-8, 1e-9 and 1e-10 all reachable.
* v1.3 widened it to four worked examples in the literature using three
  different tolerances, with no two agreeing.

What was missing is the step from "the imbalance is the cause here" to a rule
that predicts the floor anywhere.

THE MEASUREMENT
----------------
Write `ρ = |Σu − Σv| / |Σu|`, the RELATIVE inconsistency of the margins — known
before the solver runs. Induce it deliberately, across four decades, on the
chapter's own fixture with its margins squared first:

    ρ          1e-12     1e-11     1e-10     1e-9      3e-9
    park       1.107e-12 1.107e-11 1.107e-10 1.107e-9  3.322e-9
    park / ρ   1.107     1.107     1.107     1.107     1.107

**The step test parks at a fixed multiple of ρ.** Not approximately — the ratio
is constant to four figures across four decades. And the same constant appears
on the untouched fixture: ρ = 3.691e-08, park = 4.09e-08, ratio 1.108.

Across six random fixtures of different shapes, some carrying negatives, the
ratio runs **1.01 to 1.18**. So, empirically:

    **no ε below about 1.2·ρ is reachable, whatever the algorithm does.**

WHAT THAT DOES TO THE ENTRY
-----------------------------
The two printed values stop being a contradiction and become a consequence. On
the chapter's own data ρ = 3.69e-08, so:

  * 1e-8 is **below the floor** and cannot stop the iteration — which is exactly
    what the chapter's normative text prints;
  * 1e-7 is the smallest round value **above** it — which is exactly what the
    caption of the chapter's own converged table prints.

Box 18.3's caption is therefore not a slip and not a preference. It records what
the authors' own margins forced on them. And the three different tolerances in
the wider literature (`OQ-B-06` v1.3: Coleman 1e-7, Temurshoev 1e-6, this
chapter 1e-8) need no reconciling either: **a convergence threshold is not a
property of GRAS, it is a property of the fixture's margins**, and those four
worked examples are four different fixtures.

WHAT THIS DOES NOT ESTABLISH
------------------------------
The constant ~1.1 is measured, not derived: nothing here proves it is bounded by
1.2 for every table, and a fixture with very different structure could move it.
The claim that transfers is the proportionality — park ∝ ρ, with a coefficient
near 1 — and the operational consequence, which does not depend on the exact
coefficient: **compute ρ before choosing ε.**

Run:
    python3 validators/run_gras_eps_floor.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

FAIL: list[str] = []
MAX_ITER = 4000


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def park(T, u, v) -> tuple[float, float, int]:
    """Run to exhaustion and report (rho, where the step test parked, iters)."""
    from quadrium.gras import gras

    u = np.asarray(u, float)
    v = np.asarray(v, float)
    rho = abs(u.sum() - v.sum()) / max(abs(u.sum()), abs(v.sum()))
    r = gras(T, u, v, eps=1e-15, max_iter=MAX_ITER)
    return rho, r.max_s_step, r.iterations


def main() -> int:
    import run_gras_austria as ga

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    T = np.asarray(ga.IOT_2005, float)
    u = np.asarray(ga.U_2006, float)
    v_raw = np.asarray(ga.V_2006, float)
    v_sq = v_raw * (u.sum() / v_raw.sum())      # squared, per OQ-B-06 v1.24

    # 1 -- the sweep. Induce rho deliberately on the squared margins.
    print("\n    UNH_18 Box 18.2, p. 568, margins squared, then an imbalance "
          "induced\n")
    print(f"    {'induced ρ':>12}{'iterations':>12}{'s-step park':>14}"
          f"{'park / ρ':>12}")
    ratios = []
    for target in (1e-12, 1e-11, 1e-10, 1e-9, 3e-9):
        rho, parked, iters = park(T, u, v_sq * (1 + target))
        ratios.append(parked / rho)
        print(f"    {rho:>12.2e}{iters:>12}{parked:>14.3e}"
              f"{parked / rho:>12.3f}")

    check("the step test parks at a fixed multiple of the margins' relative "
          "imbalance",
          max(ratios) - min(ratios) < 0.01,
          f"park/ρ = {min(ratios):.3f}–{max(ratios):.3f} across four decades "
          f"of ρ — a proportionality, not a coincidence at one scale")

    # 2 -- and the untouched fixture lands on the same constant, which is what
    #      ties the law to what the chapter actually printed.
    rho_real, parked_real, _ = park(T, u, v_raw)
    check("the chapter's own untouched fixture obeys the same law",
          abs(parked_real / rho_real - ratios[0]) < 0.01,
          f"ρ = {rho_real:.4g} (the 0.032 imbalance), park = "
          f"{parked_real:.4g}, ratio {parked_real / rho_real:.3f} — the same "
          f"constant as the induced sweep")

    # 3 -- so the source's two values are both explained.
    print()
    print(f"    the floor on the chapter's own data is "
          f"{parked_real:.3g}, so:")
    print(f"      1e-08  (¶18.81 Step 6, p. 569, normative)  is BELOW it "
          f"— unreachable")
    print(f"      1e-07  (Box 18.3, p. 570, the worked example) is above it "
          f"— reachable, and the smallest round value that is")
    check("1e-8 is unreachable and 1e-7 is the smallest round value that is",
          1e-8 < parked_real < 1e-7,
          f"{parked_real:.4g} sits between them. The caption of the chapter's "
          f"own converged table records a necessity, not a preference")

    # 4 -- squared margins remove the floor entirely, which is the control.
    rho_sq, parked_sq, iters_sq = park(T, u, v_sq)
    check("and squaring the margins removes the floor",
          parked_sq < 1e-14 and iters_sq < MAX_ITER,
          f"ρ = {rho_sq:.2e} (float64 noise), park = {parked_sq:.2e} in "
          f"{iters_sq} iterations — with consistent margins the iteration "
          f"stops where the arithmetic runs out, not where the data does")

    # 5 -- the coefficient is stable across shapes and signs.
    rng = np.random.default_rng(3)
    print()
    print(f"    six random fixtures, some with a negative cell, ρ = 1e-10\n")
    print(f"    {'shape':>10}{'ρ':>12}{'park':>13}{'park / ρ':>12}")
    coeffs = []
    for trial in range(6):
        m, n = int(rng.integers(4, 12)), int(rng.integers(4, 12))
        B = rng.uniform(1, 500, (m, n))
        if trial % 2:
            B[rng.integers(0, m), rng.integers(0, n)] *= -1
        uu = B.sum(1) * rng.uniform(0.9, 1.2, m)
        vv = B.sum(0) * rng.uniform(0.9, 1.2, n)
        vv = vv * (uu.sum() / vv.sum()) * (1 + 1e-10)
        rho, parked, _ = park(B, uu, vv)
        coeffs.append(parked / rho)
        print(f"    {f'{m}x{n}':>10}{rho:>12.2e}{parked:>13.3e}"
              f"{parked / rho:>12.3f}")

    check("the coefficient is near 1 whatever the shape or the signs",
          1.0 <= min(coeffs) and max(coeffs) < 1.5,
          f"{min(coeffs):.2f}–{max(coeffs):.2f} across six fixtures — so "
          f"'no ε below about 1.2·ρ is reachable' is a usable rule, and the "
          f"exact coefficient is not what the rule depends on")

    print()
    print("    A convergence threshold is not a property of GRAS. It is a")
    print("    property of the fixture's margins, and ρ is computable before")
    print("    the solver runs. The three tolerances in the literature")
    print("    (OQ-B-06 v1.3) are three fixtures, not three opinions.")
    print("    D_open_questions.md OQ-B-06.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
