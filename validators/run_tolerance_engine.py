"""
`OQ-B-02`, the half no published table can speak to: judging the engine's OWN
output.

WHERE THIS SITS
----------------
`run_tolerance_population.py` measured 18 identity observations on tables other
offices published, and found the acceptance threshold has a 144-fold band to sit
in and decides nothing inside it. That result is about somebody else's rounding.
It says nothing about the object `ABS_TOL` actually judges most of the time: a
table this engine computed, in unrounded float64, where no publisher's rounding
is involved.

That half has its own floor, and it is not the same construct.

THE FLOOR FOR A SOLVER'S OUTPUT IS ITS CONSTRAINTS' OWN INCONSISTENCY
----------------------------------------------------------------------
A solver asked for row totals `u` and column totals `v` is being asked for a
table whose cells sum to `Σu` and to `Σv` at the same time. If those differ, no
such table exists. The residual is then not the solver's error but the
constraints', it cannot be driven out, and it is bounded below:

    max residual >= |Σu - Σv| / (m + n)          `precision.infeasibility_floor`

AND THE PROJECT'S OWN GRAS FIXTURE IS EXACTLY THIS CASE
--------------------------------------------------------
UNH_18 Box 18.2, p. 568 publishes margins summing to 866,987.032 against
866,987.000 — the 0.032 that `OQ-B-06` records. So:

  * GRAS meets the row totals to **1.5e-11** and misses a column total by
    **1.01e-02**, because 0.032 has to land somewhere. The signed column
    residuals sum to exactly 0.032.
  * `identities.ABS_TOL = 1e-6` calls that a failure **by four orders of
    magnitude** — a result that reproduces every printed intermediate of the
    chapter's own iterations 1 and 2 (`run_gras_austria.py`).
  * The floor calls it **2.5x**, which is the right answer. Worth noting which
    floor binds: `|Σu - Σv| / (m + n)` is 0.00246, but the margins are printed
    to three decimals and their own rounding floor is 0.004, so the larger of
    the two wins. The tighter row-exact bound `|Σu - Σv| / n` = 0.0064 puts the
    result at 1.58x.

**So the flat constant is not merely unsourced here — it is wrong**, and in the
one place the project could not see it: on published tables it was right by
accident (`OQ-B-02` v1.10), and on solver output it is wrong by accident, for
the mirror-image reason.

AND THE ENGINE NOW JUDGES SOLVER OUTPUT THIS WAY, SO THIS FILE IS ITS TEST
---------------------------------------------------------------------------
When this file was written nothing in the pipeline applied `ABS_TOL` to solver
output and it existed so that nobody would start. **That was not quite true**:
`quadrium.validation.check_margins_attained` compared the achieved margin
deviations against a bare `1e-6` and printed `margin_imbalance` — the very
`Σu − Σv` this whole argument turns on — in the same sentence, without ever
reading it. On the fixture below it would have failed the Handbook's own result.

`identities.solver_margin_tolerance()` now supplies that check's threshold, and
`ABS_TOL` still governs until the request is provably unsatisfiable by more than
`ABS_TOL` — the change only ever loosens, only where no table exists, and only
by as much as that forces. **One thing had to be added to make it safe**, and it
is worth recording because it is the same trap in a new place:
`infeasibility_floor` takes the larger of the infeasibility bound and the
margins' own rounding floor, and `printed_decimals` cannot tell an exact whole
number from a rounded one — so on a fixture with integer totals it reads
"published to 0 decimals" and returns `0.5·n`. Applied ungated to this project's
own test suite that produced **a tolerance of 10 against a solver residual of
3.6e-15**. The rounding term is right for the margins it was built for, which
are transcribed published figures; it is not right for margins the engine
computed. So the floor is consulted only once `|Σu − Σv|` demonstrates the
request cannot be met, which needs no guess about what was rounded.

AND THE BAND IS AS WIDE HERE AS IT WAS THERE
----------------------------------------------
A genuinely unconverged run — GRAS stopped after one iteration — misses a column
total by **1.7e+03**, five orders of magnitude above the converged run's
1.01e-02. Any criterion between them separates the two identically. The
unsourced acceptance threshold is not deciding anything in this half either;
what decides is the floor, and the floor is derivable per problem.

Run:
    python3 validators/run_tolerance_engine.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

from quadrium.precision import infeasibility_floor  # noqa: E402

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    import run_gras_austria as ga
    from quadrium.gras import gras
    from quadrium.identities import (ABS_TOL, FLOOR_SLACK, solver_margin_tolerance,
                            solver_margins_attained)

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    T = np.asarray(ga.IOT_2005, float)
    u = np.asarray(ga.U_2006, float).ravel()
    v = np.asarray(ga.V_2006, float).ravel()
    gap = abs(u.sum() - v.sum())
    floor = infeasibility_floor(u, v)

    print(f"\n    UNH_18 Box 18.2, p. 568 — the chapter's own Austrian fixture")
    print(f"    projected row totals sum to {u.sum():,.3f}")
    print(f"    projected column totals sum to {v.sum():,.3f}")
    print(f"    the gap is {gap:,.3f}: no table has both, and the residual "
          f"below is not the solver's")
    print(f"\n    floor |Σu − Σv| / (m + n) = {floor:.4g}   "
          f"(row-exact bound |Σu − Σv| / n = {gap / v.size:.4g})")

    print(f"\n    {'run':<26}{'max row resid':>15}{'max col resid':>15}"
          f"{'x floor':>10}")
    rows = []
    for label, kwargs in (("converged (max_iter 5000)", dict(max_iter=5000)),
                          ("stopped after 1 iteration", dict(max_iter=1)),
                          ("stopped after 3", dict(max_iter=3))):
        r = gras(T, u, v, eps=1e-8, **kwargs)
        rr = float(np.abs(r.X.sum(1) - u).max())
        cc = float(np.abs(r.X.sum(0) - v).max())
        rows.append((label, rr, cc))
        print(f"    {label:<26}{rr:>15.4g}{cc:>15.4g}{cc / floor:>10.1f}")

    conv, one = rows[0], rows[1]

    # 1 -- the converged run sits ON its floor, not above it by any margin
    #      that could be called an error.
    check("the converged run is at the floor its constraints impose",
          conv[2] / floor < 10.0,
          f"{conv[2]:.4g} against a floor of {floor:.4g} — {conv[2] / floor:.1f}x "
          f"an irreducible bound, and {conv[2] / (gap / v.size):.2f}x the "
          f"tighter row-exact bound. The 0.032 has to land somewhere")

    # 2 -- the signed residuals account for the gap exactly. This is the proof
    #      that the residual is the constraints' and not the solver's.
    r = gras(T, u, v, eps=1e-8, max_iter=5000)
    signed = float((r.X.sum(0) - v).sum())
    check("and the residual IS the gap, redistributed",
          abs(signed - (u.sum() - v.sum())) < 1e-6,
          f"the signed column residuals sum to {signed:.6f} against a "
          f"constraint gap of {u.sum() - v.sum():.6f} — the same number, not a "
          f"comparable one")

    # 3 -- THE FINDING. The project's own identity tolerance would reject it.
    check("a flat `identities.ABS_TOL` REJECTS a result verified against the "
          "source's own printed iterations",
          conv[2] > 1e4 * ABS_TOL,
          f"{conv[2]:.4g} against ABS_TOL = {ABS_TOL:g}, a factor of "
          f"{conv[2] / ABS_TOL:,.0f}. This is why the engine no longer judges "
          f"solver output by it")

    # 4 -- and a real failure is still five orders away, so the band survives.
    check("a genuinely unconverged run is orders of magnitude worse again",
          one[2] > 1e4 * conv[2],
          f"{one[2]:.4g} after one iteration against {conv[2]:.4g} converged, "
          f"a factor of {one[2] / conv[2]:,.0f} — any criterion between them "
          f"separates the two identically, exactly as on published tables")

    # 5 -- THE RULE THE ENGINE NOW APPLIES, on the two runs that bracket it.
    #      `check_margins_attained` in `quadrium.validation` uses this same
    #      threshold, via `balance()`, which is the only place holding u and v.
    tol = solver_margin_tolerance(u, v)
    accepted = solver_margins_attained(
        gras(T, u, v, eps=1e-8, max_iter=5000).X, u, v, label="converged")
    rejected = solver_margins_attained(
        gras(T, u, v, eps=1e-8, max_iter=1).X, u, v, label="1 iteration")
    check("the rule the engine now applies ACCEPTS the verified result and "
          "REJECTS the unconverged one",
          accepted.passed and not rejected.passed,
          f"tolerance {tol:.4g} = {FLOOR_SLACK:g}x the floor; converged "
          f"{accepted.max_abs_dev:.4g} passes, one-iteration "
          f"{rejected.max_abs_dev:.4g} fails by {rejected.n_violations} "
          f"margin(s). The 10,092x rejection above is now a 0.25x acceptance")

    # 6 -- and it must not have bought that by accepting everything. The floor
    #      is consulted only where the request is demonstrably unsatisfiable;
    #      where it is satisfiable the project's own constant still governs,
    #      whatever the targets look like. Integer totals are the case that
    #      broke this before the gate: `printed_decimals` reads them as
    #      "published to 0 decimals" and returns a rounding floor of 0.5*n.
    consistent = solver_margin_tolerance(np.array([3.0, 4.0, 5.0]),
                                         np.array([2.0, 4.0, 6.0]))
    check("and it does NOT loosen where the targets can both be met",
          consistent <= 2 * ABS_TOL,
          f"integer totals summing to 12 and 12 give {consistent:.4g}, i.e. "
          f"ABS_TOL — ungated, the margins' own rounding floor would make that "
          f"{FLOOR_SLACK * infeasibility_floor([3.0, 4.0, 5.0], [2.0, 4.0, 6.0]):g}")

    print()
    print("    Same shape as the published-table half, opposite cause: what")
    print("    decides is a floor derived from the problem — rounding there,")
    print("    constraint inconsistency here — and the unsourced constant sits")
    print("    in a band where it changes no verdict. Where it WOULD decide, on")
    print("    this fixture, it decides wrongly. D_open_questions.md OQ-B-02.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
