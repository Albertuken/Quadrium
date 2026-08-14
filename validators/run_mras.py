"""
`OQ-B-01`: the join between the reliability map and the solver, closed.

Since v1.2 this question has carried one sentence as its residue: "The project
can compute a freedom map and has no specified method that can read one."
`OQ-B-03` gave the map — `pinned` / `restricted` / `free`, `M-032`. UNH_18
¶18.33, p. 558 explains why no method took it: "The RAS method does not allow the
use of relative reliabilities on the initial tables and on external constraints."

CORE_016 was extracted and unread — the thirteenth such file, after CORE_001,
CORE_008 and CORE_009 the same night. It supplies the half that a sign-preserving
method can take.

M-RAS (CORE_016 p. 116, after Paelinck and Waelbroeck 1963)
------------------------------------------------------------
Zero the known cells, subtract their values from both margins, run GRAS on what
is left, put them back. Four steps, stated in one sentence by the source, and it
works because a zero cannot move under `M-044`'s Step 7 — the same
sign-preservation this project records elsewhere as a limitation is here the
mechanism.

Measured below on Austria's published trade-and-transport margins matrix:
projecting onto margins that differ from its own, plain GRAS moves the analyst's
four known cells by up to **362.39 million EUR**; M-RAS moves them by zero and
converges in fewer iterations.

BACHARACH (CORE_016 pp. 110-111)
---------------------------------
"if a matrix is connected, then a solution of the RAS-type problem is unique if
the sum of the row targets matches the sum of the column targets."

**The first sufficient condition for uniqueness in this library.** `CLAUDE.md`
records that convergence is necessary and not sufficient (CORE_006 ¶9.51,
p. 288); every solver here could say when an iteration stopped moving and never
whether the answer was the only one.

A METHOD ERROR MADE AND CORRECTED WHILE WRITING THIS
-----------------------------------------------------
The first projection test built its targets by perturbing the margins and then
rescaling `u` so that `Σu = Σv`. On a margins matrix that is wrong: `ID-08` makes
the whole matrix sum to about zero, so the rescaling factor is the ratio of two
near-zero numbers and it flipped the sign of 26 row targets. `SignInfeasibleError`
caught it. The imbalance is now spread additively in proportion to `|u|`, which
preserves signs. The failure was in the test, not the engine, and it is recorded
because "rescale to match" is the reflex and it is unsafe on any table whose
total is near zero.

WHAT IS STILL OPEN
------------------
`restricted` — a cell that may move but not freely. M-RAS is all-or-nothing per
cell, and CORE_016 p. 116 goes only as far as saying that conflicting information
needs "a compromise, especially when both sets of information are less reliable"
without specifying one. UNH_18 assigns the weighted case to KRAS and gives no
equations either.

Run:
    python3 validators/run_mras.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

from quadrium.gras import gras, is_connected, mras  # noqa: E402

MARGINS = ROOT / "data" / "eurostat" / "naio_10_cp1620_AT_2022.json"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def _austrian():
    from quadrium.eurostat import _Cube
    cube = _Cube(json.loads(MARGINS.read_text()))
    prods = [c for c in cube.index["cpa2_1"]
             if c.startswith("CPA_") and c != "CPA_TOTAL"]
    users = [c for c in cube.index["ind_use"]
             if c not in ("TU", "TOTAL", "TFU")]
    M = np.array([[cube.at(ind_use=u, cpa2_1=p) or 0.0 for u in users]
                  for p in prods], float)
    M = M[~np.all(M == 0, axis=1)]
    return M[:, ~np.all(M == 0, axis=0)]


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # ---- Bacharach's connectedness ---------------------------------------
    blocked = np.array([[1.0, 2, 0], [3.0, 4, 0], [0.0, 0, 5]])
    conn, comps = is_connected(blocked)
    check("a block-diagonal matrix is found disconnected, with its blocks",
          not conn and len(comps) == 2
          and sorted(len(c[0]) for c in comps) == [1, 2],
          f"{len(comps)} components: "
          + "; ".join(f"rows {c[0]} x cols {c[1]}" for c in comps))
    check("and a dense matrix is connected",
          is_connected(np.array([[1.0, 2], [3.0, 4]]))[0])

    if not MARGINS.exists():
        print(f"\nfixture absent: {MARGINS.name}; the rest needs it")
        return 1 if FAIL else 0

    M = _austrian()
    conn, comps = is_connected(M)
    check("Austria's margins matrix is connected, so Bacharach applies to its "
          "shape", conn,
          f"{M.shape[0]}x{M.shape[1]}, one component. NOTE: the guarantee is "
          f"stated for NON-NEGATIVE matrices (CORE_016 p. 110) and this one has "
          f"legitimate negatives, so connectedness is reported and uniqueness "
          f"is NOT claimed")

    # ---- M-RAS returns the seed when asked for the seed's own margins ----
    u0, v0 = M.sum(1), M.sum(0)
    order = np.argsort(-np.abs(M), axis=None)[:4]
    idx = np.dstack(np.unravel_index(order, M.shape))[0]
    known = {(int(i), int(j)): float(M[i, j]) for i, j in idx}

    identity = mras(M, u0, v0, known)
    check("M-RAS projected onto the seed's own margins returns the seed",
          identity.converged and float(np.abs(identity.X - M).max()) < 1e-9,
          f"max|X - M| = {float(np.abs(identity.X - M).max()):.3g}")

    # ---- a real projection, against plain GRAS ---------------------------
    rng = np.random.default_rng(3)
    u = M.sum(1) * (1 + rng.uniform(-0.06, 0.06, M.shape[0]))
    v = M.sum(0) * (1 + rng.uniform(-0.06, 0.06, M.shape[1]))
    # Additively, NOT by rescaling: see the note in the docstring.
    u = u + (v.sum() - u.sum()) * np.abs(u) / np.abs(u).sum()

    plain = gras(M, u, v)
    fixed = mras(M, u, v, known)
    print()
    print(f"    {'cell':<10}{'known':>14}{'plain GRAS':>14}{'M-RAS':>14}")
    for (i, j), value in known.items():
        print(f"    ({i:>2},{j:>2}){'':<3}{value:>14,.2f}"
              f"{plain.X[i, j]:>14,.2f}{fixed.X[i, j]:>14,.2f}")
    moved = max(abs(plain.X[i, j] - val) for (i, j), val in known.items())
    print()

    check("plain GRAS moves cells the analyst asserted",
          moved > 100.0,
          f"by up to {moved:,.2f} million EUR — the solver has no way to know "
          f"they were asserted")
    check("M-RAS holds every one of them exactly",
          all(abs(fixed.X[i, j] - val) < 1e-9
              for (i, j), val in known.items()),
          "zero deviation on all four")
    check("and still meets the margins it was given",
          fixed.converged and fixed.max_row_dev < 1e-6,
          f"row {fixed.max_row_dev:.3g}, column {fixed.max_col_dev:.3g}, "
          f"{fixed.iterations} iterations against plain GRAS's "
          f"{plain.iterations}")
    check("with the sign structure intact, as M-RAS depends on",
          fixed.sign_changes == 0,
          "a zero placeholder cannot move under Step 7, which is exactly why "
          "the method works (CORE_016 p. 116)")

    print()
    print("    Still NOT specified, and this is why OQ-B-01 narrows rather")
    print("    than closes: `restricted` — a cell that may move but not")
    print("    freely — has no method. M-RAS is all-or-nothing per cell, and")
    print("    CORE_016 p. 116 asks for 'a compromise' without giving one.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
