"""
Test SUT-RAS against the Handbook's own worked example.

Fixture: UNH_18 Box 18.2, p. 568 (Austria 2005 SUT at basic prices, four
products, three industries). Expected values: Box 18.5, p. 574, which prints
iterations 1, 2, 3 and 20 with their `dev r_d` and `dev r_m` columns, plus the
projected 2006 SUT.

Same design as `run_gras_austria.py`, and the same lesson from OQ-B-08: the
Handbook's printed ITERATIONS are trustworthy and its printed FINAL table need
not be. Level A is the gate; level B reports.

TWO FIXTURE POINTS THAT ARE DERIVED, NOT READ
---------------------------------------------
1. `u` for an industry column is that industry's output MINUS its GVA. The
   chapter lists both as required inputs (¶18.84, p. 571) and never states the
   subtraction. Verified: it recovers Box 18.5's printed s(1) exactly.
2. The imported "Trade to business services" row of Box 18.2's use table is
   extracted as "1 249 395 645" -- three values for five columns. The two
   readings differ in whether 395 sits in Services or in Domestic demand.
   Resolved arithmetically against Box 18.5's own printed `p_s` row, which is a
   column sum of exactly this matrix: only [1, 249, 395, 0, 0] reproduces
   [4159, 116520, 107129, 239907, 120803]. The alternative misses two columns by
   395. No PDF page was needed for this.

Usage:
    python3 run_sut_ras_austria.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quadrium.sut_ras import imports_and_taxes, sut_ras  # noqa: E402

PRODUCTS = ["Agriculture", "Manuf. and const.", "Trade to busin. services",
            "Other services"]
INDUSTRIES = ["Agriculture", "Manuf. and const.", "Services"]
COLS = ["Agriculture", "Manuf. and const.", "Services", "Dom. demand", "Exports"]

# --------------------------------------------------------------------------
# Base year 2005 — UNH_18 Box 18.2, p. 568
# --------------------------------------------------------------------------

# d: domestic intermediate and final use, 4 products x 5 columns
Pd = np.array([
    [1784,  2777,   340,   1448,    477],
    [ 987, 37706, 20218,  43014,  74550],
    [ 301,  9761,  5668,  27221,   6924],
    [ 452, 18475, 57943, 118725,  18546],
], float)
Nd = np.zeros_like(Pd)

# m: imported use, 4 products, PLUS the taxes-less-subsidies row (par. 18.84,
# p. 571: "adjusted to account separately for taxes less subsidies on products")
Pm = np.array([
    [115,   980,   141,    920,     53],
    [480, 42057,  8228,  28991,  17557],
    [  1,   249,   395,      0,      0],
    [ 39,  3491,  9476,   1373,   2579],
    [  0,  1024,  4720,  18215,    117],
], float)
Nm = np.zeros_like(Pm)
Nm[4, 0] = 93.0        # the single negative: taxes less subsidies, agriculture

# v: supply table transposed, 3 industries x 4 products
Pv = np.array([
    [6826,    725,     2,    249],
    [   0, 172430,  4433,   4345],
    [   0,   3320, 45440, 209547],
], float)
Nv = np.zeros_like(Pv)

# Base-year imports by product, plus base-year total taxes less subsidies
M_BASE = np.array([2209, 97313, 645, 16958, 23983], float)

# --------------------------------------------------------------------------
# Projection year 2006 targets — UNH_18 Box 18.2, p. 568
# --------------------------------------------------------------------------

X_2006 = np.array([8367, 200582, 273485], float)          # industry outputs
GVA_2006 = np.array([3990, 68902, 159769], float)
FINAL_USE_2006 = np.array([249844, 134709], float)        # dom. demand, exports
U_2006 = np.concatenate([X_2006 - GVA_2006, FINAL_USE_2006])
MT_2006 = 127602.0 + 24290.0                              # imports + taxes

# --------------------------------------------------------------------------
# Expected values — UNH_18 Box 18.5, p. 574, as printed
# --------------------------------------------------------------------------

EXPECTED = {
    1: {"p_d": [6826, 176475, 49875, 214141],
        "n_d": [6826, 176475, 49875, 214141],
        "rd": [1, 1, 1, 1], "rm": [1, 1, 1, 1, 1],
        "p_v": [7802, 181208, 258307], "rv": [1.072, 1.107, 1.059],
        "p_s": [4159, 116520, 107129, 239907, 120803], "n_s": [93, 0, 0, 0, 0],
        "s": [1.07325, 1.13011, 1.06149, 1.04142, 1.11511], "r": 1.07642},
    2: {"p_d": [7454, 193060, 53440, 227193],
        "n_d": [7320, 195158, 53019, 226936],
        "rd": [0.991, 1.005, 0.996, 0.999],
        "rm": [0.996, 0.992, 0.995, 0.997, 1.012],
        "p_v": [7860, 180298, 258588], "rv": [1.064, 1.112, 1.058],
        "p_s": [4142, 116292, 107142, 239927, 121011], "n_s": [92, 0, 0, 0, 0],
        "s": [1.077, 1.132, 1.061, 1.041, 1.113], "r": 1.072,
        "dev_rd": [-0.0090, 0.0054, -0.0039, -0.0006],
        "dev_rm": [-0.0042, -0.0085, -0.0053, -0.0027]},
    3: {"p_d": [7466, 192998, 53447, 227183],
        "n_d": [7266, 196111, 52992, 226718],
        "rd": [0.987, 1.008, 0.996, 0.999],
        "rm": [0.993, 0.989, 0.992, 0.995, 1.010],
        "p_v": [7890, 179857, 258690], "rv": [1.060, 1.115, 1.057],
        "p_s": [4135, 116255, 107114, 239858, 121145], "n_s": [92, 0, 0, 0, 0],
        "s": [1.079, 1.133, 1.062, 1.042, 1.112], "r": 1.069,
        "dev_rd": [-0.0045, 0.0026, -0.0003, -0.0005],
        "dev_rm": [-0.0026, -0.0023, -0.0024, -0.0021]},
    20: {"p_d": [7474, 192875, 53457, 227261],
         "n_d": [7215, 197079, 52977, 226557],
         "rd": [0.982, 1.011, 0.995, 0.998],
         "rm": [0.991, 0.987, 0.990, 0.993, 1.008],
         "p_v": [7916, 179386, 258803], "rv": [1.057, 1.118, 1.057],
         "p_s": [4129, 116222, 107080, 239778, 121292], "n_s": [92, 0, 0, 0, 0],
         "s": [1.081, 1.133, 1.062, 1.042, 1.111], "r": 1.067},
}

# The projected 2006 SUT, Box 18.5, p. 574.
EXPECTED_FD = np.array([
    [1894,  3091,   355,   1482,    520],
    [1078, 43184, 21704,  45306,  83694],
    [ 324, 11009,  5992,  28236,   7655],
    [ 488, 20900, 61438, 123517,  20566],
], float)
EXPECTED_FM = np.array([
    [123,  1100,   148,    950,     58],
    [512, 47021,  8622,  29808,  19241],
    [  1,   279,   415,      0,      0],
    [ 42,  3927,  9990,   1420,   2844],
    [-85,  1169,  5051,  19125,    131],
], float)
EXPECTED_FV = np.array([
    [7343,    758,     2,    264],
    [   0, 190737,  4979,   4866],
    [   0,   3471, 48235, 221779],
], float)


def _cmp(label, got, want, tol):
    got, want = np.asarray(got, float), np.asarray(want, float)
    dev = float(np.max(np.abs(got - want)))
    ok = dev <= tol
    print(f"    {'ok ' if ok else 'BAD'}  {label:<10s} max|dev| = {dev:.4g}")
    if not ok:
        for i, (g, w) in enumerate(zip(got.ravel(), want.ravel())):
            if abs(g - w) > tol:
                print(f"           [{i}] got {g:.6g}  printed {w:.6g}")
    return ok


def main() -> int:
    print("SUT-RAS against the Handbook's own worked example")
    print("UNH_18 Box 18.2, p. 568 (fixture) and Box 18.5, p. 574 (expected)")
    print("=" * 74)

    print("\nDerived fixture inputs (not read off the page)")
    print(f"    u = industry output - GVA, then final uses")
    print(f"      = {np.array2string(U_2006, precision=0)}")
    print(f"    MT = imports 127602 + taxes 24290 = {MT_2006:.0f}")
    print(f"    m  = {np.array2string(M_BASE, precision=0)}   "
          f"(base-year imports by product, plus base-year taxes)")

    all_ok = True
    res = sut_ras(Pd, Nd, Pm, Nm, Pv, Nv, M_BASE, X_2006, U_2006, MT_2006)

    # Box 18.5 prints iteration 20, which this implementation reaches its own
    # stopping rule before. eps=0 forces exactly 20 recorded iterations so the
    # printed row can be compared at all.
    trace = sut_ras(Pd, Nd, Pm, Nm, Pv, Nv, M_BASE, X_2006, U_2006, MT_2006,
                    eps=0.0, max_iter=20)

    print(f"\nA. Iteration-by-iteration against Box 18.5, p. 574")
    for k, want in EXPECTED.items():
        h = trace.history[k - 1]
        print(f"  Iteration {k}")
        all_ok &= _cmp("p_d", h["p_d"], want["p_d"], 0.5)
        all_ok &= _cmp("n_d", h["n_d"], want["n_d"], 0.5)
        all_ok &= _cmp("r_d", h["rd"], want["rd"], 0.0005)
        all_ok &= _cmp("r_m", h["rm"], want["rm"], 0.0005)
        all_ok &= _cmp("p_v", h["p_v"], want["p_v"], 0.5)
        all_ok &= _cmp("r_v", h["rv"], want["rv"], 0.0005)
        all_ok &= _cmp("p_s", h["p_s"], want["p_s"], 0.5)
        all_ok &= _cmp("n_s", h["n_s"], want["n_s"], 0.5)
        # s(1) is printed to five decimals, later iterations to three.
        all_ok &= _cmp("s", h["s"], want["s"], 0.000005 if k == 1 else 0.0005)
        all_ok &= _cmp("r", [h["r"]], [want["r"]],
                       0.000005 if k == 1 else 0.0005)
        if "dev_rd" in want:
            all_ok &= _cmp("dev r_d", h["dev_rd"], want["dev_rd"], 0.00005)
            all_ok &= _cmp("dev r_m", h["dev_rm"][:4], want["dev_rm"], 0.00005)

    print(f"\nB. Converged system")
    print(f"    {res}".replace("\n", "\n    "))

    Fd, Fm, Fv = res.Fd, res.Fm, res.Fv
    print(f"\n    Constraint satisfaction (par. 18.38, p. 559: supply and use")
    print(f"    must match for BOTH products and industries)")
    prod_use = Fd.sum(axis=1) + Fm[:len(PRODUCTS)].sum(axis=1)
    prod_sup = Fv.sum(axis=0) + imports_and_taxes(res, M_BASE)[:len(PRODUCTS)]
    print(f"        max |product supply - product use| = "
          f"{np.max(np.abs(prod_sup - prod_use)):.3e}")
    print(f"        max |industry output - x|          = "
          f"{np.max(np.abs(Fv.sum(axis=1) - X_2006)):.3e}")
    col = Fd.sum(axis=0) + Fm.sum(axis=0)
    print(f"        max |use column total - u|         = "
          f"{np.max(np.abs(col - U_2006)):.3e}")
    lhs = imports_and_taxes(res, M_BASE)
    print(f"        Step 6, the two 'equivalent expressions' agree to "
          f"{np.max(np.abs(lhs - Fm.sum(axis=1))):.3e}")
    print(f"        total imports + taxes = {lhs.sum():.1f}  vs MT = {MT_2006:.0f}")

    print(f"\n    Against Box 18.5's printed projected SUT")
    for label, got, want in (("use, domestic", Fd, EXPECTED_FD),
                             ("use, imports", Fm, EXPECTED_FM),
                             ("supply", Fv, EXPECTED_FV)):
        d = float(np.max(np.abs(got - want)))
        print(f"        {'ok ' if d <= 1.0 else 'off'}  {label:<14s} "
              f"max|cell - printed| = {d:.4g}")

    print(f"\n    Sign and zero structure")
    signed_in = np.concatenate([(Pd - Nd).ravel(), (Pm - Nm).ravel(),
                                (Pv - Nv).ravel()])
    signed_out = np.concatenate([Fd.ravel(), Fm.ravel(), Fv.ravel()])
    changes = int(np.count_nonzero(np.sign(signed_in) != np.sign(signed_out)))
    print(f"        sign changes vs the 2005 base SUT : {changes}"
          f"   (sign preserving, as GRAS -- par. 18.35, p. 558)")
    print(f"        taxes row, agriculture            : {Fm[4, 0]:.1f}"
          f"   (was -93.0; still negative)")

    print("\n" + "=" * 74)
    if all_ok:
        print("PASS. The SUT-RAS equations of UNH_18 par. 18.86, pp. 571-573")
        print("reproduce every printed intermediate of the Handbook's own")
        print("iterations 1, 2, 3 and 20 -- p_d, n_d, r_d, r_m, p_v, r_v, p_s,")
        print("n_s, s, r, and the printed deviation columns.")
        print()
        print("M-045 is now verified to the same standard as M-044.")
    else:
        print("FAIL. Mismatch against the Handbook's printed iterations.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
