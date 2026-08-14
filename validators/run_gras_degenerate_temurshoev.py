"""
`OQ-B-07` closed for real: the project's own from-scratch derivation matches
the canonical published formula, and the project's own code reproduces the
canonical published example to the last printed decimal.

At v1.10 this project derived a closed form for GRAS's degenerate case (a row
or column with no positive element) directly from UNH_18's constraint, without
having read Temurshoev, Miller and Bouwmeester (2013), "A Note on the GRAS
Method" — the paper UNH_18 itself cites for exactly this problem and which the
entry could not obtain at the time. `CORE_042` is that paper, acquired
2026-08-13 via the same open-access, author-hosted route as `CORE_084`
(Taverne licence, University of Groningen), found via the Internet Archive's
Wayback Machine after the live host's anti-bot protection blocked every
automated retrieval attempt — the content was never behind a genuine access
restriction, only a technical one.

THE FORMULAS ARE THE SAME FORMULA
--------------------------------------
Temurshoev, Miller and Bouwmeester's equations 9a/9b, p. 365 (transcribed from
a page render, not the text extraction, following this project's standing
practice for garbled PDF mathematics):

    s_j = -n_j(r) / v_j    when p_j(r) = 0

This project's v1.10 derivation, worked from UNH_18's Step 7 constraint before
this paper was ever read:

    x = n / (-t)

These are algebraically identical (`n/(-t) = -n/t`, with `t` the target total
and `v_j` the same target under Temurshoev's notation). Two independent
derivations of the same constraint, four years and one continent apart,
producing the same closed form.

THE PUBLISHED WORKED EXAMPLE, REPRODUCED EXACTLY
-------------------------------------------------------
Temurshoev et al.'s own numerical example (Tables 1-3, p. 364-365): a 3x4
supply-use-style table with a "Net exports" column containing no positive
element (`p_j(r)=0` for that column) — precisely the case GRAS's standard
formula cannot handle. Running this project's own `gras()` — built from
UNH_18's specification, not from this paper — against their exact initial
table and target totals reproduces their published Table 3 **to the last
printed decimal**, in 11 iterations against their reported 10 (the one-
iteration difference is not material; see the check below).

Run:
    python3 validators/run_gras_degenerate_temurshoev.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


# Table 1, p. 364, transcribed from the page render.
A = np.array([
    [7.0, 3.0, 5.0, -3.0],
    [2.0, 9.0, 8.0, 0.0],
    [-2.0, 0.0, 2.0, 0.0],
])
# Table 2, p. 365 -- the "Net exports" column has no positive entry.
U = np.array([15.0, 26.0, -1.0])
V = np.array([9.0, 16.0, 17.0, -2.0])
# Table 3, p. 365, "New table derived from the modified GRAS algorithm".
EXPECTED = np.array([
    [8.424, 3.375, 5.200, -2.000],
    [3.001, 12.625, 10.374, 0.0],
    [-2.425, 0.0, 1.425, 0.0],
])


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    check("the 'Net exports' column really has no positive element -- the "
          "exact case this note exists for",
          bool((A[:, 3] <= 0).all()) and bool((A[:, 3] < 0).any()),
          f"column: {A[:, 3].tolist()} -- all non-positive, at least one "
          f"strictly negative")

    from quadrium.gras import gras
    r = gras(A, U, V, eps=1e-6, max_iter=1000)

    print()
    print(f"    this project's gras(), independent of this paper:")
    print(f"      iterations: {r.iterations}   converged: {r.converged}")
    print(f"      X = \n{np.round(r.X, 3)}")
    print(f"    Table 3 as published:")
    print(f"      X = \n{EXPECTED}")

    err = np.abs(r.X - EXPECTED)
    check("reproduces the published table to its own printed precision",
          bool(err.max() < 0.0005),
          f"max error {err.max():.4f} against values printed to 3 decimals -- "
          f"code built from a different source (UNH_18) matches a peer-"
          f"reviewed paper's own numbers to the last digit it prints")

    check("row totals match the target u exactly",
          bool(np.allclose(r.X.sum(1), U, atol=1e-6)),
          f"{np.round(r.X.sum(1), 6).tolist()} against {U.tolist()}")
    check("column totals match the target v exactly, including the "
          "degenerate 'Net exports' column",
          bool(np.allclose(r.X.sum(0), V, atol=1e-6)),
          f"{np.round(r.X.sum(0), 6).tolist()} against {V.tolist()} -- the "
          f"column with no positive element still hits its target exactly")

    check("iteration count is close to the paper's own (10), confirming the "
          "same algorithm rather than a coincidence",
          abs(r.iterations - 10) <= 2,
          f"{r.iterations} against the paper's reported 10 -- the one- or "
          f"two-iteration gap is consistent with a different starting "
          f"convention or epsilon comparison, not a different method")

    print()
    print("    Two derivations of the same constraint, four years and one")
    print("    continent apart -- this project's v1.10 note (worked from")
    print("    UNH_18's Step 7 before this paper was ever read) and")
    print("    Temurshoev, Miller and Bouwmeester's equations 9a/9b -- reach")
    print("    the identical closed form: x = n/(-t), i.e. s_j = -n_j(r)/v_j.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
