"""
Test GRAS against the Handbook's own worked example.

The fixture is UNH_18 Box 18.2, p. 568 (Austria, 2005 and 2006, four products
and three industries, basic prices) and the expected values are UNH_18
Box 18.3, p. 570. This is the right test and `UK_IOAT_2023_domestic_ixi.xlsx` is the wrong one:
the UK file is a single-year analytical IOT with no target year, and GRAS needs
a base table AND the target period's margins.

Three levels of check, in increasing strength:

  A. Step-by-step — the printed intermediates of iterations 1 and 2 (p_j(r),
     n_j(r), s, p_i(s), n_i(s), r, and the printed s(2) − s(1) row). If these
     match, the update rule reconstructed from the garbled extraction is right.
  B. Converged table — Box 18.3's "After 11 iterations".
  C. Accuracy claim — ¶18.82, p. 569 states a weighted average percentage error
     of 1.7 % against the real 2006 IOT.

Note on the fixture's negative: it is synthetic. ¶18.78, p. 568 says "The amount
of taxes less subsidies on production paid by the agriculture industry has been
changed into a negative value for illustrative purposes." (The row is in fact
labelled taxes less subsidies on *products* in the tables — a terminological slip
in the source.) It is still a valid exercise of the P/N split, which is the only
part of GRAS that distinguishes it from RAS.

Usage:
    python3 run_gras_austria.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quadrium.gras import (GRAS_EPS, GRAS_EPS_BOX_18_3, MarginImbalanceError,  # noqa: E402
                  SignInfeasibleError,
                  gras, split_pn)

# ---------------------------------------------------------------------------
# The fixture — UNH_18 Box 18.2, p. 568, block "IOT (ixi) 2005" / "2006".
# Rows: 3 domestic industries, 3 import rows, taxes less subsidies on products,
# GVA.  Columns: 3 industries, domestic final demand, exports.
# ---------------------------------------------------------------------------

ROWS = ["Agriculture (dom)", "Manuf. and const. (dom)", "Services (dom)",
        "Agriculture (imp)", "Manuf. and const. (imp)", "Services (imp)",
        "Taxes less subsidies on products", "GVA"]
COLS = ["Agriculture", "Manuf. and const.", "Services", "Dom. demand", "Exports"]

IOT_2005 = np.array([
    [1788.8,  2958.749,  483.5352, 1763.462,   807.4829],
    [ 989.41, 37780.53, 21869.52, 46880.48, 73688.06],
    [ 745.82, 27979.72, 61815.95, 141764.1, 26001.46],
    [ 117.01,  1156.335,  184.1869, 1040.407,  127.5801],
    [ 470.33, 41217.36,  8367.596, 28372.14, 17240.32],
    [  47.662, 4403.309,  9688.217, 1871.449,  2821.099],
    [ -93.0,   1024.0,    4720.0,  18215.0,     117.0],
    [3736.0,  64688.0,  151178.0,      0.0,       0.0],
])

IOT_2006 = np.array([
    [2004.5,   3419.031,   392.9584, 1737.56,   812.9417],
    [1120.9,  45652.04, 23297.04, 48968.74, 81543.25],
    [ 718.57, 29763.92, 66306.0,  148055.7,  28640.8],
    [ 116.61,  1269.412,  169.7097, 1110.434,  148.7118],
    [ 443.36, 46128.63,  8771.805, 29214.82, 19693.76],
    [  50.028, 4491.957, 10340.49,  2025.751, 3626.533],
    [ -77.0,    955.0,    4438.0,  18731.0,     243.0],
    [3990.0,  68902.0,  159769.0,      0.0,       0.0],
])

# The projected margins, exactly as the "Total" row and column of the 2006 IOT
# are PRINTED in Box 18.2, p. 568. They are rounded to different precisions,
# which is itself part of the test: see the imbalance report below.
U_2006 = np.array([8367.0, 200582.0, 273485.0,
                   2814.882, 104252.4, 20534.75, 24290.0, 232661.0])
V_2006 = np.array([8367.0, 200582.0, 273485.0, 249844.0, 134709.0])

# ---------------------------------------------------------------------------
# Expected intermediates — UNH_18 Box 18.3, p. 570, as printed.
# The box prints s and r to 3 decimals and the aggregates to the unit.
# ---------------------------------------------------------------------------

EXPECTED = {
    1: {
        "p_j": [7895, 181208, 258307, 239907, 120803],
        "n_j": [93, 0, 0, 0, 0],
        "s":   [1.071, 1.107, 1.059, 1.041, 1.115],
        "p_i": [8439, 197027, 273849, 2826, 103759, 20277, 25231, 235666],
        "n_i": [0, 0, 0, 0, 0, 0, 87, 0],
        "r":   [0.991, 1.018, 0.999, 0.996, 1.005, 1.013, 0.966, 0.987],
    },
    2: {
        "p_j": [7851, 181215, 256691, 240090, 122205],
        "n_j": [96, 0, 0, 0, 0],
        "s":   [1.077, 1.107, 1.065, 1.041, 1.102],
        "p_i": [8442, 196197, 273819, 2825, 103573, 20305, 25246, 236694],
        "n_i": [0, 0, 0, 0, 0, 0, 86, 0],
        "r":   [0.991, 1.022, 0.999, 0.996, 1.007, 1.011, 0.966, 0.983],
    },
}

# The printed "s(2) - s(1)" row of Box 18.3, p. 570.
EXPECTED_S_STEP_2 = [0.006, 0.000, 0.007, -0.001, -0.013]

# Box 18.3, p. 570, "After 11 iterations (threshold 0.0000001)".
EXPECTED_FINAL = np.array([
    [1914,  3242,   520,   1816,   876],
    [1106, 43183, 23460,  49833, 83000],
    [ 793, 30636, 66496, 147186, 28374],
    [ 126,  1277,   198,   1077,   140],
    [ 511, 45941,  8901,  29665, 19028],
    [  52,  4963, 10574,   1983,  3167],
    [ -89,  1096,  4876,  18283,   124],
    [3955, 70245, 158462,     0,     0],
], dtype=float)


def _cmp(label, got, want, tol, unit=""):
    got = np.asarray(got, float)
    want = np.asarray(want, float)
    dev = np.max(np.abs(got - want))
    ok = dev <= tol
    print(f"    {'ok ' if ok else 'BAD'}  {label:<10s} max|dev| = {dev:.4g}{unit}")
    if not ok:
        for i, (g, w) in enumerate(zip(got, want)):
            if abs(g - w) > tol:
                print(f"           [{i}] got {g:.6g}  printed {w:.6g}")
    return ok


def main() -> int:
    print("GRAS against the Handbook's own worked example")
    print("UNH_18 Box 18.2, p. 568 (fixture) and Box 18.3, p. 570 (expected)")
    print("=" * 74)

    P, N = split_pn(IOT_2005)
    print(f"\nStep 1 (par. 18.81, p. 569)  T = P - N")
    print(f"    negatives in the base table : {int((IOT_2005 < 0).sum())}"
          f"  (sum |N| = {N.sum():.6g})")
    print(f"    zeros preserved as zeros    : {int((IOT_2005 == 0).sum())}")

    imbalance = U_2006.sum() - V_2006.sum()
    print(f"\nMargin feasibility (not stated by UNH_18, reported not repaired)")
    print(f"    sum u = {U_2006.sum():.6f}   sum v = {V_2006.sum():.6f}"
          f"   imbalance = {imbalance:.6g}"
          f"  ({abs(imbalance) / V_2006.sum():.2e} relative)")

    all_ok = True

    # ---------------------------------------------------------------- level A
    print(f"\nA. Iteration-by-iteration against Box 18.3, p. 570")
    res = gras(IOT_2005, U_2006, V_2006, eps=GRAS_EPS, max_iter=200)
    for k, want in EXPECTED.items():
        h = res.history[k - 1]
        print(f"  Iteration {k}")
        # Box 18.3 prints aggregates to the unit and factors to 3 decimals,
        # so the tolerance is the printing precision, not a fudge factor.
        all_ok &= _cmp("p_j(r)", h["p_j"], want["p_j"], 0.5)
        all_ok &= _cmp("n_j(r)", h["n_j"], want["n_j"], 0.5)
        all_ok &= _cmp("s", h["s"], want["s"], 0.0005)
        all_ok &= _cmp("p_i(s)", h["p_i"], want["p_i"], 0.5)
        all_ok &= _cmp("n_i(s)", h["n_i"], want["n_i"], 0.5)
        all_ok &= _cmp("r", h["r"], want["r"], 0.0005)
    step2 = res.history[1]["s"] - res.history[0]["s"]
    print("  Printed s(2) - s(1) row")
    all_ok &= _cmp("s(2)-s(1)", step2, EXPECTED_S_STEP_2, 0.0005)

    # ---------------------------------------------------------------- level B
    print(f"\nB. Converged table")
    X = res.X
    print(f"    {res}".replace("\n", "\n    "))
    res_box = gras(IOT_2005, U_2006, V_2006, eps=GRAS_EPS_BOX_18_3, max_iter=200)
    print(f"    at the threshold Box 18.3, p. 570 states it used "
          f"({GRAS_EPS_BOX_18_3:g}): {res_box.iterations} iterations; "
          f"the box says 11")
    print(f"    the run cannot reach eps = {GRAS_EPS:g}: |s(k+1)-s(k)| stalls at "
          f"{res.max_s_step:.3e},")
    print(f"    which is the relative margin imbalance "
          f"({abs(imbalance) / V_2006.sum():.3e}) of the PRINTED totals.")
    print(f"    Constraint satisfaction of this run:")
    print(f"        max |row total - u| = {res.max_row_dev:.3e}   (exact)")
    print(f"        max |col total - v| = {res.max_col_dev:.3e}   (bounded by the")
    print(f"            0.032 imbalance in the published margins, not by the solver)")

    # The printed final table of Box 18.3 does NOT satisfy the margins printed
    # in Box 18.2. Checked here rather than asserted, so the claim is auditable.
    print(f"\n    Box 18.3's own printed final table, against Box 18.2's margins:")
    print(f"        row sums - u : "
          f"{np.array2string(EXPECTED_FINAL.sum(1) - U_2006, precision=2)}")
    print(f"        col sums - v : "
          f"{np.array2string(EXPECTED_FINAL.sum(0) - V_2006, precision=2)}")
    print(f"    It misses its own row totals on the three import rows by "
          f"+3.1, -206.4 and +204.3.")

    # Where the two tables differ, and where they do not.
    print(f"\n    Locating the difference (see D_open_questions.md OQ-B-08):")
    for lo, hi, label in ((1, 2, "Manuf. + Services, domestic"),
                          (4, 5, "Manuf. + Services, imports")):
        d_pair = np.max(np.abs((X[lo] + X[hi]) - (EXPECTED_FINAL[lo]
                                                  + EXPECTED_FINAL[hi])))
        d_sep = max(np.max(np.abs(X[lo] - EXPECTED_FINAL[lo])),
                    np.max(np.abs(X[hi] - EXPECTED_FINAL[hi])))
        print(f"        {label:<28s} combined max|dev| = {d_pair:8.1f}"
              f"   separately = {d_sep:8.1f}")
    print(f"    The aggregate agrees to rounding; only the split between the")
    print(f"    Manufacturing and Services rows differs. GRAS scales whole rows")
    print(f"    and columns, so no choice of margins can move value between two")
    print(f"    rows column-by-column: the printed final table is not a GRAS")
    print(f"    output of the printed base table, whereas iterations 1-2 are.")

    # ---------------------------------------------------------------- level C
    print(f"\nC. Accuracy against the real 2006 IOT (par. 18.82, p. 569 claims 1.7 %)")
    wape = np.abs(X - IOT_2006).sum() / np.abs(IOT_2006).sum()
    wape_box = (np.abs(EXPECTED_FINAL - IOT_2006).sum()
                / np.abs(IOT_2006).sum())
    wape_none = np.abs(IOT_2005 - IOT_2006).sum() / np.abs(IOT_2006).sum()
    print(f"    weighted average percentage error, this run     = {100 * wape:.2f} %")
    print(f"    same measure on Box 18.3's printed final table  = {100 * wape_box:.2f} %"
          f"   (rounds to the 1.7 % claimed)")
    print(f"    same measure with no projection at all (2005)   = {100 * wape_none:.2f} %")
    gdp_proj = X[6].sum() + X[7].sum()
    gdp_real = IOT_2006[6].sum() + IOT_2006[7].sum()
    print(f"    GDP projected {gdp_proj:.1f} vs official {gdp_real:.1f}"
          f"  ({100 * (gdp_proj / gdp_real - 1):+.4f} %)")
    print(f"    sign changes vs the 2005 base table : {res.sign_changes}"
          f"   (GRAS is sign preserving, par. 18.35, p. 558)")

    # ---------------------------------------------------------------- level D
    print(f"\nD. The NOT SPECIFIED paths are honest, not silent")
    # An entirely non-positive row is two different failures depending on the
    # target it is asked to reach, and the distinction is worth keeping.
    T_bad = IOT_2005.copy()
    T_bad[6] = -np.abs(T_bad[6]) - 1.0          # row 6 now has no positive entry

    # D1 -- positive target. Provably unreachable: a sign-preserving rule can
    # never raise an all-negative row to a positive sum. Caught before iterating.
    try:
        gras(T_bad, U_2006, V_2006)
    except SignInfeasibleError as exc:
        print(f"    ok   non-positive row, positive target -> SignInfeasibleError")
        print(f"         {str(exc)[:70]}...")
    else:
        print("    BAD  an unreachable target was silently accepted")
        all_ok = False

    # D2 -- negative target. THIS EXPECTATION WAS INVERTED AT v1.10, and the
    # note here is the honest record of why. It used to assert that a degenerate
    # row raises, because UNH_18 par. 18.81, p. 569 divides by the row's
    # non-negative part and defers the alternative formulation to a paper the
    # project does not hold. That was one step too cautious: the scaling factor
    # is defined by Step 7's constraint `p*x - n/x = t`, which at p = 0 is
    # simply linear and gives `x = n/(-t)`. No alternative formulation is
    # needed, and refusing meant refusing real published margins matrices. See
    # OQ-B-07 and run_gras_degenerate.py.
    # Flipping row 6's target also flips 48,580 out of the total, so the margins
    # stop summing to the same figure. That used to be masked -- the degenerate
    # row raised before the iteration began. It is now a separate, named refusal,
    # and the row target has to be made consistent to test the degenerate case
    # at all. Both halves are checked.
    U_neg = U_2006.copy()
    U_neg[6] = -abs(U_2006[6])
    try:
        gras(T_bad, U_neg, V_2006)
        print("    BAD  inconsistent margins were silently accepted")
        all_ok = False
    except MarginImbalanceError:
        print(f"    ok   inconsistent margins -> MarginImbalanceError")
        print(f"         sum u - sum v = {U_neg.sum() - V_2006.sum():,.0f}, far "
              f"beyond what the printed precision allows")

    V_fix = V_2006 * (U_neg.sum() / V_2006.sum())
    res_deg = gras(T_bad, U_neg, V_fix)
    row_hit = abs(float(res_deg.X[6].sum() - U_neg[6]))
    if res_deg.converged and row_hit < 1e-9 and (res_deg.X[6] <= 0).all():
        print(f"    ok   non-positive row, negative target -> SOLVED")
        print(f"         row 6 sums to {res_deg.X[6].sum():.6g} against a target "
              f"of {U_neg[6]:.6g}, still all non-positive")
    else:
        print(f"    BAD  the degenerate row was not solved correctly "
              f"(row deviation {row_hit:.3g})")
        all_ok = False

    print("\n" + "=" * 74)
    if all_ok:
        print("PASS. The update rule and convergence criterion reconstructed from")
        print("UNH_18 par. 18.81, p. 569 reproduce every printed intermediate of")
        print("the Handbook's own iterations 1 and 2, and the converged table")
        print("satisfies the projected row totals exactly.")
        print()
        print("FINDING, not a failure: Box 18.3's printed FINAL table is")
        print("inconsistent with Box 18.3's own printed iterations. Logged as")
        print("OQ-B-08. It does not affect the algorithm, which is what this")
        print("test verifies.")
    else:
        print("FAIL. Mismatch against the Handbook's printed iterations.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
