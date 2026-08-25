"""
`OQ-B-01`'s `restricted` residue, refined: there IS an equation, and the entry
had it half right.

v1.25 concluded the weighted/conflicting-data case "is not an equation at
all", citing CORE_004 ¶19.80 calling the operation judgement and CORE_021
p. 209 reporting full automation was tried and abandoned. That conclusion was
drawn without reading two sources this entry itself recommended as the next
action — CORE_051 (this file) and CORE_041 — both of which had been sitting in
`CORE_04/DOCUMENTS/` unextracted the whole time.

Stanger, M. (2018), "An Algorithm to Balance Supply and Use Tables," IMF
Technical Notes and Manuals 18/03, §V gives the Cholette-Dagum GLS
reconciliation in closed form — rank 1, an official IMF technical publication,
already held and never read.

WHAT CHANGES, PRECISELY
---------------------------
Not the finding that choosing reliability weights is judgement — that stands,
unchanged, and nothing in this source supplies a rule for it either. What
changes is the claim that there is "no equation": there is one, for the other
half of the problem — turning a set of weighted, possibly-conflicting
observations plus accounting constraints into a reconciled table. That is
ordinary GLS, Byron's (1978) feasible approximation of it, and Stanger writes
it out completely as equation 5:

    theta_hat = s + Ve @ G' @ inv(G @ Ve @ G' + Veps) @ (g - G @ s)

Implemented in `quadrium/gls_reconcile.py`.

Run:
    python3 validators/run_gls_reconcile.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quadrium.gls_reconcile import gls_reconcile  # noqa: E402

EXTRACTED = ROOT / "library" / "extracted"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    txt = EXTRACTED / "CORE_051_IMF_Balancing_SUT.txt"
    if txt.exists():
        flat = re.sub(r"\s+", " ", txt.read_text())
        check("the source really does write the equation out, not just name it",
              "= s + F[d]" in flat,
              "§V, eq. 5 — 'theta_hat = s + F[d]', the initial observed values "
              "optimally adjusted (filtered with F) to incorporate all "
              "imbalances")
        # The one piece of arithmetic the paper itself states in prose, which
        # can be checked without parsing its 18-column worked table.
        supply = 74 + 111 - 5 + 2 + 1900 + 56 + 284
        use = 33 + 769 + 228 + 428 + 572 + 3 + 361 + 28
        check("and its own worked example is internally consistent",
              supply == use == 2422,
              f"secondary product supply {supply} = secondary product use "
              f"{use}, both stated as 2,422 in Figure 7's discussion — the "
              f"arithmetic the paper claims actually holds")

    # ---- the formula: constraint satisfaction and reliability weighting ---
    print()
    s = np.array([10.0, 5.0])
    G = np.array([[1.0, -1.0]])
    g = np.array([0.0])

    equal = gls_reconcile(s, G, g, np.diag([1.0, 1.0]))
    print(f"    equal reliability:   s={s} -> theta={equal}")
    check("with equal reliability, the discrepancy splits evenly",
          np.allclose(equal, [7.5, 7.5]),
          "10 and 5 average to 7.5 each — the intuitive GLS answer when "
          "nothing distinguishes the two estimates' trust")

    unequal = gls_reconcile(s, G, g, np.diag([0.01, 100.0]))
    print(f"    unequal reliability: s={s} -> theta={unequal}")
    check("a low-variance (trusted) entry barely moves",
          abs(unequal[0] - 10) < 0.01,
          f"{unequal[0]:.4f} against 10 — variance 0.01 means high confidence, "
          f"and the GLS solution respects it")
    check("a high-variance (untrusted) entry absorbs nearly the whole "
          "correction",
          abs(unequal[1] - 10) < 0.01,
          f"{unequal[1]:.4f} against a starting value of 5 — variance 100 "
          f"means low confidence, and it moves almost all the way to match "
          f"the trusted figure")
    check("and the constraint is still satisfied exactly, regardless of the "
          "weights",
          # `.item()`, not `float()`. numpy deprecated converting an array
          # with ndim > 0 to a scalar in 1.25 and made it an ERROR in 2.3, so
          # `float(G @ unequal)` -- a one-element array, not a 0-d one -- dies
          # on any machine with a current numpy. Found by CI on Python 3.13
          # while this machine, pinned at numpy 1.23, saw nothing.
          abs((G @ unequal - g).item()) < 1e-9,
          f"G @ theta = {(G @ unequal).item():.9f} against target {g[0]} — "
          f"binding (Veps=0) means exact, not approximate, satisfaction")

    # ---- a larger, more realistic case: three constraints, five cells -----
    print()
    rng = np.random.default_rng(7)
    n = 5
    s5 = rng.uniform(50, 200, n)
    G5 = np.array([[1, 1, -1, 0, 0],
                   [0, 0, 1, 1, -1],
                   [1, 0, 0, 0, -1]], dtype=float)
    g5 = np.array([0.0, 0.0, 0.0])
    Ve5 = np.diag(rng.uniform(0.1, 50, n))
    theta5 = gls_reconcile(s5, G5, g5, Ve5)
    resid = G5 @ theta5 - g5
    check("scales to multiple simultaneous constraints on overlapping cells",
          bool(np.abs(resid).max() < 1e-8),
          f"3 constraints, 5 cells sharing rows across constraints, max "
          f"residual {np.abs(resid).max():.2e} — the closed form does not "
          f"degrade with overlap, because it is a single linear solve, not "
          f"an iterative scheme converging constraint by constraint")

    print()
    print("    What is unchanged: choosing Ve (the reliability weights) is")
    print("    still judgement -- CORE_004 par. 19.80, and no loaded source")
    print("    gives a rule for it, this one included. What changes: applying")
    print("    those weights to reconcile the system is GLS, not judgement,")
    print("    and it is now sourced, implemented and verified.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
