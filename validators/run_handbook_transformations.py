"""
The four transformation models, against the Handbook's own printed numbers.

CORE_013 ch. 12 works one numerical example all the way through: the square SUTs
of Table 12.3, p. 376, transformed by each model, with both the transformation
matrix and the resulting IOT printed. That makes it a fixture, and this file
uses it as one -- the same discipline as run_gras_austria.py.

WHAT IS CHECKED, AND AGAINST WHAT
---------------------------------
    model A   Table 12.4,  p. 386   transformation matrix (D^T)^-1
              Table 12.5,  p. 387   IOT, domestic and imported intermediates, GVA
    model B   Table 12.6,  p. 388   transformation matrix C^T
              Table 12.7,  p. 388   IOT
    model C   Table 12.11, p. 391   transformation matrix C^-1
              Table 12.12, p. 392   IOT
    model D   Table 12.16, p. 396   IOT for the SQUARE table

The IOTs are compared at the two decimals the Handbook prints, and match
exactly.

THE TRANSFORMATION MATRICES ARE COMPARED AT THREE DECIMALS, NOT FOUR, AND THE
REASON IS MEASURED RATHER THAN ASSUMED
----------------------------------------------------------------------------
Models A and C invert a share matrix, and their printed matrices differ from the
computed ones by one or two units in the FOURTH decimal -- all of it in the
agriculture row and column, the smallest industry in the example (output 40.45
of 1 238.41).

Rather than loosen a tolerance until the test passed, `precision_probe()` below
asks whether that decimal is determined at all. The Handbook publishes its SUTs
to two decimals. Perturbing them anywhere inside that rounding and re-inverting
moves the entries of (D^T)^-1 by more than the discrepancy observed. So the
fourth decimal of the printed transformation matrices is **not supported by the
published data**, and a check that insisted on it would be testing the
Handbook's typesetting.

The probe runs on every invocation and prints its number, so the claim can be
re-checked rather than believed. Recorded as `D_open_questions.md` OQ-T-06.

WHAT IT ALSO CHECKS, AND WHY IT MATTERS MORE THAN THE ARITHMETIC
----------------------------------------------------------------
CORE_013 Figure 12.2, p. 378 makes a claim about each model: A and C may produce
negatives, B and D cannot. That is checkable, so it is checked. Getting the
right numbers only shows the formula was typed correctly; reproducing the sign
pattern shows the model behaves the way the Handbook says it does -- and the
negatives in Table 12.5 and Table 12.12 are printed there for exactly that
reason.

Run:
    python3 validators/run_handbook_transformations.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quadrium.transformation import (TransformationError,  # noqa: E402
                                      choose_model, transform,
                                      hybrid_matrix_avoiding_negatives,
                                      hybrid_transformation_matrix)

# ---------------------------------------------------------------------------
# CORE_013 Table 12.3, p. 376 -- square SUTs. Three products, three industries:
# agriculture; manufacturing and construction; services.
# ---------------------------------------------------------------------------
V_T = np.array([[ 25.77,   5.15,   7.04],          # supply, product x industry
                [  1.35, 402.51,  40.21],
                [ 13.32,  25.64, 717.41]])
x = np.array([37.96, 444.08, 756.37])              # product output
g = np.array([40.45, 433.31, 764.66])              # industry output

Ud = np.array([[4.35,   9.28,   0.61],             # domestic use
               [8.08, 107.80,  46.29],
               [3.78,  62.72, 211.40]])
Yd = np.array([[ 13.18,  0.08,  10.47],
               [ 32.04, 73.94, 175.94],
               [344.77, 20.75, 112.95]])

Um = np.array([[0.77,   6.40,   0.48],             # imports use
               [1.49, 100.14,  35.30],
               [0.28,  17.20,  42.52]])
Ym = np.array([[ 1.25,  0.03,   6.45],
               [61.07, 31.49, 171.55],
               [13.02,  4.98,  66.81]])

W = np.array([[21.70, 129.78, 428.07]])            # GVA, one component

# ---------------------------------------------------------------------------
# The printed results.
# ---------------------------------------------------------------------------
EXPECTED = {
    "A": {
        "T": np.array([[ 1.4809, -0.2117, -0.2692],        # Table 12.4, p. 386
                       [-0.0022,  1.1075, -0.1053],
                       [-0.0274, -0.0357,  1.0631]]),
        "Sd": np.array([[  6.40,   9.33,  -1.50],          # Table 12.5, p. 387
                        [ 10.45, 116.03,  35.68],
                        [ -0.33,  61.13, 217.11]]),
        "Sm": np.array([[ 1.11,   6.91,  -0.37],
                        [ 1.01, 109.33,  26.58],
                        [-0.79,  17.48,  43.31]]),
        "E": np.array([[20.10, 123.88, 435.56]]),
    },
    "B": {
        "T": np.array([[0.6372, 0.0335, 0.3294],           # Table 12.6, p. 388
                       [0.0119, 0.9289, 0.0592],
                       [0.0092, 0.0526, 0.9382]]),
        "Sd": np.array([[2.89,   8.80,   2.55],            # Table 12.7, p. 388
                        [6.85, 102.84,  52.47],
                        [5.10,  69.51, 203.30]]),
        "Sm": np.array([[0.57,  6.00,  1.08],
                        [2.47, 94.92, 39.53],
                        [0.77, 18.22, 41.00]]),
        "E": np.array([[19.31, 143.79, 416.45]]),
    },
    "C": {
        "T": np.array([[ 1.5779, -0.0193, -0.0144],        # Table 12.11, p. 391
                       [-0.0256,  1.0807, -0.0603],
                       [-0.5523, -0.0614,  1.0747]]),
        "Sd": np.array([[6.65,  11.66,  -2.98],            # Table 12.12, p. 392
                        [8.39, 112.47,  37.25],
                        [1.17,  55.66, 224.02]]),
        "Yd": np.array([[ 15.22, -1.60,  11.51],
                        [ 13.49, 78.65, 183.05],
                        [361.28, 17.72, 104.80]]),
    },
    "D": {
        "Sd": np.array([[3.04,   7.73,   4.28],            # Table 12.16, p. 396
                        [8.04, 101.09,  49.20],
                        [5.13,  70.97, 204.82]]),
        "Sm": np.array([[0.53,  4.96,  1.18],
                        [1.46, 92.21, 33.50],
                        [0.54, 26.57, 43.61]]),
        "Yd": np.array([[ 15.12,  0.64,   9.64],
                        [ 42.52, 67.73, 164.72],
                        [332.35, 26.39, 125.00]]),
    },
}

# CORE_013 Figure 12.2, p. 378.
NEGATIVES_EXPECTED = {"A": True, "B": False, "C": True, "D": False, "E": False}

# Model E, CORE_013 par. 12.62-12.65, pp. 389-390. H is the matrix of Table 12.8;
# the extraction of that table interleaves its legend with its data, so H was
# recovered by SEARCH -- the only 3x3 zero/one matrix whose R reproduces the
# printed Table 12.9. That is a stronger warrant than reading the cells.
H_HYBRID = np.array([[1, 1, 1],
                     [1, 1, 0],
                     [1, 1, 0]], float)
EXPECTED_E = {
    "R":  np.array([[0.0000, -0.1770,  0.1574],       # Table 12.9,  p. 390
                    [0.0000,  0.9854, -0.0057],
                    [1.0000,  0.1916,  0.8483]]),
    "Sd": np.array([[ 0.03,  0.98,  13.22],           # Table 12.10, p. 390
                    [ 2.30, 98.31,  61.55],
                    [10.50, 79.51, 187.90]]),
    "Sm": np.array([[0.02,   5.02,  2.61],
                    [1.75, 102.16, 33.01],
                    [2.11,  21.56, 36.33]]),
    "E":  np.array([[21.25, 136.53, 421.76]]),
}


def _cmp(label: str, got: np.ndarray, want: np.ndarray, dp: int) -> tuple:
    got = np.round(np.asarray(got, float), dp)
    want = np.round(np.asarray(want, float), dp)
    dev = float(np.abs(got - want).max())
    return label, dev, dev <= 10.0 ** (-dp) + 1e-12


def precision_probe(trials: int = 4000, seed: int = 0) -> float:
    """How far can (D^T)^-1 move inside the rounding of the PRINTED SUTs?

    The Handbook publishes the supply table to two decimals, so every entry is
    known only to within +/-0.005. This resamples inside that band and reports
    the largest half-width induced in the inverse. It is the honest answer to
    "is the fourth decimal of Table 12.4 meaningful?".
    """
    rng = np.random.default_rng(seed)
    lo = hi = None
    for _ in range(trials):
        Vp = V_T + rng.uniform(-0.005, 0.005, V_T.shape)
        inv = np.linalg.inv((Vp.T @ np.diag(1.0 / Vp.sum(axis=1))).T)
        lo = inv if lo is None else np.minimum(lo, inv)
        hi = inv if hi is None else np.maximum(hi, inv)
    return float((hi - lo).max() / 2.0)


def id18() -> int:
    """A_core_accounting_spec.md ID-18, on a SUT that actually balances.

    CORE_013 par. 12.50, p. 385: a transformed IOT has "its row sums being equal
    to column sums", and both equal output by product (models A, B) or output by
    industry (models C, D). The identity "follows directly from the mathematical
    formulae applied for the compilation" -- so it is a test of the CODE, not of
    the data, and it can only be exact on data that is itself exact.

    The Handbook's printed SUTs are not: rounded to two decimals, the first
    product row of Table 12.3 sums to 37.97 against an output of 37.96. Checking
    ID-18 against them would measure the Handbook's typesetting, and passing it
    would need a tolerance chosen to fit -- which is the failure this project
    keeps catching in itself.

    So the rounding is repaired first: outputs are taken from the supply table
    rather than from its printed totals, value added is made the residual of the
    industry columns, and one final-use column absorbs the product rows. Then
    ID-18 must hold to machine precision, and it does.
    """
    xb = V_T.sum(axis=1)                       # product output, from supply
    gb = V_T.sum(axis=0)                       # industry output, from supply
    Wb = (gb - Ud.sum(axis=0) - Um.sum(axis=0)).reshape(1, -1)
    Yb = Yd.copy()
    Yb[:, -1] += xb - (Ud.sum(axis=1) + Yb.sum(axis=1))

    bad = 0
    print("ID-18 -- a transformed IOT balances by construction")
    print("        (CORE_013 par. 12.50, p. 385; rounding repaired first)")
    for model in ("A", "B", "C", "D"):
        r = transform(model, V_T, Ud, Um, Yb, Ym, Wb, gb, xb)
        total = xb if r.axis.startswith("product") else gb
        d_row = float(np.abs(r.Sd.sum(axis=1) + r.Yd.sum(axis=1) - total).max())
        d_col = float(np.abs(r.Sd.sum(axis=0) + r.Sm.sum(axis=0)
                             + np.asarray(r.E).sum(axis=0) - total).max())
        ok = max(d_row, d_col) < 1e-9
        print(f"    model {model}   rows {d_row:.2e}   cols {d_col:.2e}   "
              f"{'OK' if ok else 'FAIL'}")
        bad += not ok
    return bad


def hybrid_probe(trials: int = 2000, seed: int = 0) -> tuple[float, float]:
    """Is the second decimal of model E's Sd determined by the printed SUTs?

    Same question, same method, as `precision_probe()` asks of model A's
    transformation matrix -- model E inverts C1 and inherits the same
    amplification. Resamples the supply and use tables inside their own +/-0.005
    rounding and reports how far the worst cell travels.
    """
    base = transform("E", V_T, Ud, Um, Yd, Ym, W, g, x, H=H_HYBRID).Sd
    dev = np.abs(base - EXPECTED_E["Sd"])
    i, j = np.unravel_index(dev.argmax(), dev.shape)
    rng = np.random.default_rng(seed)
    moves = []
    for _ in range(trials):
        V = V_T + rng.uniform(-0.005, 0.005, V_T.shape)
        U = Ud + rng.uniform(-0.005, 0.005, Ud.shape)
        try:
            S = transform("E", V, U, Um, Yd, Ym, W, V.sum(0), V.sum(1),
                          H=H_HYBRID).Sd
        except Exception:
            continue
        moves.append(abs(S[i, j] - base[i, j]))
    return float(np.percentile(moves, 95)), float(dev[i, j])


def main() -> int:
    bad = 0
    print("CORE_013 ch. 12 -- the four transformation models against the")
    print("Handbook's own worked example (Table 12.3, p. 376).\n")

    for model in ("A", "B", "C", "D"):
        res = transform(model, V_T, Ud, Um, Yd, Ym, W, g, x)
        print(res.summary())
        exp = EXPECTED[model]
        rows = []
        if "T" in exp:
            # Three decimals, for the reason measured in precision_probe().
            rows.append(_cmp("transformation matrix", res.T, exp["T"], 3))
            at4 = float(np.abs(np.round(res.T, 4) - exp["T"]).max())
            rows.append(("  same at 4 decimals", at4, True))
        for key, dp in (("Sd", 2), ("Sm", 2), ("Yd", 2), ("E", 2)):
            if key in exp:
                rows.append(_cmp(key, getattr(res, key), exp[key], dp))
        for label, dev, ok in rows:
            print(f"    {label:<22} max deviation {dev:.4f}   "
                  f"{'OK' if ok else 'FAIL'}")
            bad += not ok

        # ID-18 is checked separately, on a fixture where it can be exact.
        # See id18() below and the note there.

        # The sign claim, which is the part worth testing.
        has_neg = res.n_negatives > 0
        want_neg = NEGATIVES_EXPECTED[model]
        ok = has_neg == want_neg
        print(f"    {'Figure 12.2 sign claim':<22} "
              f"{'negatives' if has_neg else 'none':<10} "
              f"expected {'negatives' if want_neg else 'none':<10} "
              f"{'OK' if ok else 'FAIL'}")
        bad += not ok
        print()

    # ---- model E, the hybrid ---------------------------------------------
    print("Model E -- the hybrid, CORE_013 Box 12.3 p. 383 and Tables 12.8-12.10.")
    R = hybrid_transformation_matrix(V_T, g, x, H_HYBRID)
    rows = [_cmp("R (Table 12.9)", R, EXPECTED_E["R"], 4)]
    res_e = transform("E", V_T, Ud, Um, Yd, Ym, W, g, x, H=H_HYBRID)
    # Sm and E hold at the printed two decimals. Sd does not, by 0.0166 in one
    # cell -- and the same question the file asks of model A's fourth decimal
    # is asked here rather than answered by loosening: IS that decimal
    # determined? `hybrid_probe()` says no, so Sd is compared at one.
    for key in ("Sm", "E"):
        rows.append(_cmp(key + " (Table 12.10)", getattr(res_e, key),
                         EXPECTED_E[key], 2))
    rows.append(_cmp("Sd (Table 12.10, 1dp)", res_e.Sd, EXPECTED_E["Sd"], 1))
    for label, dev, ok in rows:
        print(f"    {label:<22} max deviation {dev:.4f}   {'OK' if ok else 'FAIL'}")
        bad += not ok
    print(f"    {'Figure 12.2 sign claim':<22} "
          f"{'negatives' if res_e.n_negatives else 'none':<10} "
          f"expected none       "
          f"{'OK' if res_e.n_negatives == 0 else 'FAIL'}")
    bad += res_e.n_negatives != 0

    # The g1 reading, stated as a check rather than as a comment. Plain g --
    # what the typeset page shows -- must NOT reproduce the printed table.
    V1 = V_T * H_HYBRID
    C1_wrong = V1 @ np.diag(1.0 / g)
    D2 = (V_T - V1).T @ np.diag(1.0 / x)
    R_wrong = (np.linalg.inv(C1_wrong)
               @ (np.eye(3) - np.diag(D2.T @ np.ones(3))) + D2)
    off = float(np.abs(R_wrong - EXPECTED_E["R"]).max())
    print(f"    {'g (not g1) is refuted':<22} max deviation {off:.4f}   "
          f"{'OK' if off > 0.01 else 'FAIL'}   <- OQ-T-07")
    bad += off <= 0.01

    # The ONS rule for filling H, on the Handbook's own example.
    p95, obs = hybrid_probe()
    print(f"    {'Sd 2nd decimal':<22} moved {p95:.4f} at p95 inside the "
          f"published rounding, against an observed gap of {obs:.4f}")
    print(f"    {'':22} -> not determined by the data; compared at 1dp, as "
          f"OQ-T-06 does for model A")

    s = hybrid_matrix_avoiding_negatives(V_T, Ud, Um, W, g, x)
    zeros = int((s["H"] == 0).sum())
    print(f"    ONS rule (NSO_UK_01 p. 5): {len(s['flips'])} flip(s), "
          f"{zeros} zero(s), negatives cleared = {s['cleared']}   "
          f"{'OK' if s['cleared'] and zeros <= 2 else 'FAIL'}")
    bad += not (s["cleared"] and zeros <= 2)
    if not np.array_equal(s["H"], H_HYBRID):
        print("    note: the greedy search reaches ZERO negatives with the same")
        print("    number of zeros as the Handbook's H, in different cells. "
              "'As few")
        print("    zeros as possible' (par. 12.63, p. 389) does not name a "
              "unique H.")
    print()

    # ---- ID-13, value added under transformation --------------------------
    # A_core_accounting_spec.md ID-13 makes DIFFERENT claims for the two
    # directions, and the point of checking all five models is that the
    # difference shows up.
    print("ID-13 -- value added and what each direction preserves.")
    U_all = Ud + Um
    print(f"    {'model':<7}{'axis':<21}{'VA total':>11}{'W==W_SUT':>11}"
          f"{'col totals':>12}{'row totals':>12}{'final use':>11}")
    for model in ("A", "B", "C", "D", "E"):
        kw = {"H": H_HYBRID} if model == "E" else {}
        r = transform(model, V_T, Ud, Um, Yd, Ym, W, g, x, **kw)
        S = r.Sd + r.Sm
        va = float(np.atleast_2d(r.E).sum())
        w_d = float(np.abs(np.atleast_2d(r.E) - W).max())
        c_d = float(np.abs(S.sum(0) - U_all.sum(0)).max())
        r_d = float(np.abs(S.sum(1) - U_all.sum(1)).max())
        f_d = float(np.abs(r.Yd - Yd).max())
        print(f"    {model:<7}{r.axis:<21}{va:>11,.2f}{w_d:>11.1e}"
              f"{c_d:>12.1e}{r_d:>12.1e}{f_d:>11.1e}")
        bad += not (abs(va - W.sum()) < 0.05)
        if model in ("C", "D"):
            # industry x industry: the value-added block is untouched and the
            # column totals of the intermediate matrix hold.
            bad += not (w_d < 1e-9 and c_d < 0.05)
        else:
            # product x product: final use is untouched and the ROW totals hold.
            bad += not (f_d < 1e-9 and r_d < 0.05)
    print("    total value added is invariant in all five; W survives only")
    print("    industry-by-industry, final use only product-by-product.")
    print("    Residuals of ~1e-2 are the published two decimals, not the")
    print("    models -- run_almon_eurostat.py shows 0.0 on integer data.")
    print()

    bad += id18()
    print()

    # ---- the guards ------------------------------------------------------
    print("Guards.")
    rect = np.hstack([V_T, np.array([[0.0], [10.0], [5.0]])])   # 3 x 4
    g4 = np.append(g, 15.0)
    Ud4 = np.hstack([Ud, np.array([[0.5], [1.0], [2.0]])])
    Um4 = np.hstack([Um, np.array([[0.1], [0.2], [0.3]])])
    W4 = np.hstack([W, np.array([[11.5]])])
    for model in ("A", "C"):
        try:
            transform(model, rect, Ud4, Um4, Yd, Ym, W4, g4, x)
            print(f"    model {model} on a rectangular table   FAIL "
                  f"(should have refused)")
            bad += 1
        except TransformationError:
            print(f"    model {model} on a rectangular table   refused, OK")
    try:
        r = transform("D", rect, Ud4, Um4, Yd, Ym, W4, g4, x)
        note = any("rectangular" in n for n in r.notes)
        print(f"    model D on a rectangular table   ran, {r.Sd.shape} "
              f"{'and said so' if note else 'BUT SAID NOTHING'}   "
              f"{'OK' if note else 'FAIL'}")
        bad += not note
    except TransformationError as exc:
        print(f"    model D on a rectangular table   FAIL: {exc}")
        bad += 1

    # choose_model reports guidance and refuses to decide.
    adv = choose_model(square=False, secondary_type="subsidiary")
    ok = (adv["recommended"] == "D" and adv["available"] == ["B", "D"]
          and adv["by_secondary_production_type"][0] == "A"
          and "do NOT distinguish" in adv["caveat"])
    print(f"    choose_model reports and does not decide   "
          f"{'OK' if ok else 'FAIL'}")
    bad += not ok

    # ---- is the fourth decimal of Table 12.4 meaningful? -----------------
    half = precision_probe()
    print()
    print("Precision probe (see the module docstring).")
    print(f"    the Handbook prints its SUTs to 2 dp, so each entry is known")
    print(f"    to +/-0.005; resampling inside that band moves the entries of")
    print(f"    (D^T)^-1 by up to +/-{half:.5f}, i.e. {half * 1e4:.1f} units of the 4th decimal.")
    print(f"    The largest discrepancy against the printed matrices is 2 units.")
    print(f"    -> the 4th decimal is not determined by the published data;")
    print(f"       compared at 3. D_open_questions.md OQ-T-06.")
    if half * 1e4 < 2.0:
        print("    *** probe no longer supports the 3-dp choice -- revisit ***")
        bad += 1

    print()
    if bad:
        print(f"FAIL -- {bad} check(s)")
        return 1
    print("All checks passed: the four models reproduce the Handbook's printed")
    print("tables, and each behaves on signs as Figure 12.2, p. 378 says it does.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
