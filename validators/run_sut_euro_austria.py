"""
SUT-EURO against the Handbook's own worked example — `M-046`, Box 18.7, pp. 578–579.

WHY THIS WAS THE LAST ONE
--------------------------
UNH_18 specifies three methods. GRAS was implemented at v1.2 and SUT-RAS at
v1.9; SUT-EURO waited because ¶18.95, p. 576 builds its consistency step on the
fixed product sales structure model and states it **by reference only** — "see
model D in Eurostat, 2008, p. 351". The project could not follow that reference.
`OQ-T-01` closed at v1.5 when CORE_013 ¶12.74, p. 393 gave model D as `T = D`,
and `M-046` has been implementable and unimplemented ever since. `INDEX.md` §7
named it as the next piece of engine work on 2026-08-14; this is it.

THE FIXTURE, AND WHERE IT COMES FROM
--------------------------------------
Box 18.7 prints the growth rates, the market shares and tables 3 to 9 for
iterations 1 and 2 — but **not the base-year table they are applied to**.
¶18.101, p. 577 says the run is measured "against the official SUT for 2006, as
in Box 18.2", so the base is Box 18.2's Austrian 2005 SUT, which this project
already holds in `run_sut_ras_austria.py`.

Box 18.2 has **four** products and three industries. SUT-EURO is square only
(¶18.102, p. 577), so the two service products are collapsed into one — the same
collapse `OQ-B-08` found the chapter performing silently between the two halves
of Box 18.2 itself. The collapse is done here in the open, and it is verified
rather than assumed: with it, **all seven growth rates the box prints follow
from the base table** to four decimals, which is the check that the base is
right. Without it they do not.

ONE FIGURE THE BOX DOES NOT PRINT AND THE ARITHMETIC RECOVERS
---------------------------------------------------------------
Base-year GVA is not in Box 18.2 either; it falls out as output minus inputs.
Doing that gives agriculture **3 736** only if the taxes-less-subsidies entry
for agriculture is **−93** — the single negative of the whole fixture, which
`run_sut_ras_austria.py` carries separately as `Nm[4, 0]`. Treat it as zero and
the implied growth rate misses the printed 1.0680 by a fifth of a point. The
negative is load-bearing.

WHAT IS VERIFIED
-----------------
Iteration 1 reproduces **exactly**, at the unit the box prints: both scalings,
their average, the step-1 inconsistency the chapter reports without repairing,
the model-D outputs, the consistent table and every figure of table 9(1).
Iteration 2 reproduces to a few units in 200,000 — the residue of the box
printing its growth rates to four decimals.

Run:
    python3 validators/run_sut_euro_austria.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quadrium.sut_euro import (SutEuroError, correction_factor,  # noqa: E402
                               sut_euro)

FAIL: list[str] = []

PRODUCTS = ["Agriculture", "Manuf. and const.", "Services"]

# --------------------------------------------------------------------------
# Base year 2005 — UNH_18 Box 18.2, p. 568, with the two service products
# collapsed so the pair is square. Columns: 3 industries, dom. demand, exports.
# --------------------------------------------------------------------------
UD0 = np.array([
    [1784,  2777,   340,   1448,    477],
    [ 987, 37706, 20218,  43014,  74550],
    [ 753, 28236, 63611, 145946,  25470],      # 301+452, 9761+18475, …
], float)
UM0 = np.array([
    [115,   980,   141,    920,     53],
    [480, 42057,  8228,  28991,  17557],
    [ 40,  3740,  9871,   1373,   2579],       # 1+39, 249+3491, …
], float)
TLS0 = np.array([-93, 1024, 4720, 18215, 117], float)   # −93: see the docstring
V0 = np.array([
    [6826,    725,    251],
    [   0, 172430,   8778],
    [   0,   3320, 254987],
], float)

# Projection year 2006 targets — Box 18.2, p. 568 and Box 18.7 table 2, p. 578.
VA_2006 = np.array([3990, 68902, 159769], float)
FINAL_USE_2006 = np.array([249844, 134709], float)
TLS_2006 = 24290.0
IMPORTS_2006 = 127602.0

# --------------------------------------------------------------------------
# Box 18.7, pp. 578–579, as printed
# --------------------------------------------------------------------------
T5_1_DOM = np.array([                       # table 5 (1), domestic block
    [1905,  2962,   361,   1527,    521],
    [1053, 40162, 21451,  45306,  81269],
    [ 800, 29958, 67226, 153115,  27660],
], float)
T5_1_TLS = np.array([-97, 1064, 4884, 18709, 124], float)
T5_1_COLTOT = np.array([8328, 192858, 273003], float)
X_1 = np.array([8351, 194527, 273058], float)          # after model D
T7_1_DOM_ROW0 = np.array([1911, 2987, 361, 1527, 521], float)
T7_1_GVA = np.array([4001, 69498, 159801], float)
T9_1_ACTUAL = np.array([1.0680, 1.0651, 1.0568, 1.0414, 1.1151, 1.0595,
                        1.0128, 1.0895])
T9_1_PROJECTED = np.array([1.0709, 1.0744, 1.0570, 1.0488, 1.0891, 1.0624,
                           1.0297, 1.0688])
T9_1_DEV = np.array([0.9973, 0.9914, 0.9998, 0.9930, 1.0238, 0.9973,
                     0.9836, 1.0193])
T9_1_CORRECTION = np.array([0.9969, 0.9913, 0.9997, 0.9928, 1.0219, 0.9969,
                            0.9844, 1.0181])
GDP_SUPPLY_SIDE_1 = 257346.0            # ¶18.94, p. 576
GDP_USE_SIDE_1 = 258432.0               # ¶18.94, p. 576


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def one_iteration(max_iter: int):
    return sut_euro(UD0, UM0, TLS0, V0, va_target=VA_2006,
                    final_use_target=FINAL_USE_2006, tls_target=TLS_2006,
                    imports_target=IMPORTS_2006, max_iter=max_iter,
                    stop_pct=0.0)          # never stop early: we want iteration 1


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # ---- (E1), which needed no implementation and is a unit test ------------
    got = correction_factor(T9_1_DEV)
    check("(E1) reproduces every correction factor Box 18.7 table 9 prints",
          np.max(np.abs(got - T9_1_CORRECTION)) < 2e-4,
          f"worst {np.max(np.abs(got - T9_1_CORRECTION)):.1e} over 8 columns, "
          f"including the two that only the recovered MINUS branch can give")

    # ---- the base table is right, judged by the rates it implies ------------
    base_va = V0.sum(1) - (UD0[:, :3].sum(0) + UM0[:, :3].sum(0) + TLS0[:3])
    implied = np.array([
        *(VA_2006 / base_va),
        FINAL_USE_2006[0] / (UD0[:, 3].sum() + UM0[:, 3].sum() + TLS0[3]),
        FINAL_USE_2006[1] / (UD0[:, 4].sum() + UM0[:, 4].sum() + TLS0[4]),
        VA_2006.sum() / base_va.sum(),
        TLS_2006 / TLS0.sum(),
        IMPORTS_2006 / UM0.sum()])
    check("all seven growth rates the box prints follow from the base table",
          np.max(np.abs(implied - T9_1_ACTUAL)) < 5e-5,
          f"worst {np.max(np.abs(implied - T9_1_ACTUAL)):.1e}; base GVA comes "
          f"out {base_va.round(0).tolist()} and agriculture is 3 736 only "
          f"because the taxes entry is −93")

    r = one_iteration(max_iter=1)

    # ---- step 1: the average table, printed in full -------------------------
    check("table 5 (1) reproduces cell by cell, domestic block",
          np.max(np.abs(r.step1.Ud - T5_1_DOM)) < 0.6,
          f"worst {np.max(np.abs(r.step1.Ud - T5_1_DOM)):.2f} over 15 cells")
    check("and its taxes row, negative included",
          np.max(np.abs(r.step1.tls - T5_1_TLS)) < 0.6,
          f"{r.step1.tls.round(0).tolist()} against "
          f"{T5_1_TLS.astype(int).tolist()}")
    col_tot = (r.step1.Ud[:, :3].sum(0) + r.step1.Um[:, :3].sum(0)
               + r.step1.tls[:3] + r.step1.gva)
    check("and the column totals that do not yet balance",
          np.max(np.abs(col_tot - T5_1_COLTOT)) < 0.6,
          f"{col_tot.round(0).tolist()} against {T5_1_COLTOT.astype(int).tolist()}")

    # ---- the inconsistency the chapter reports and does not repair ----------
    check("the step-1 GDP disagreement is reproduced, both sides",
          abs(r.step1.gdp_supply_side - GDP_SUPPLY_SIDE_1) < 1.0
          and abs(r.step1.gdp_use_side - GDP_USE_SIDE_1) < 1.0,
          f"use side {r.step1.gdp_use_side:,.0f} against supply side "
          f"{r.step1.gdp_supply_side:,.0f} — ¶18.94, p. 576 prints "
          f"{GDP_USE_SIDE_1:,.0f} and {GDP_SUPPLY_SIDE_1:,.0f}. Reproducing "
          f"the DISAGREEMENT is a sharper test of step 1 than reproducing a "
          f"balanced table")

    # ---- step 2: model D --------------------------------------------------
    check("model D returns the consistent industry outputs the box prints",
          np.max(np.abs(r.x - X_1)) < 0.6,
          f"{r.x.round(0).tolist()} against {X_1.astype(int).tolist()}")
    check("and the consistent table 7 (1) follows from them",
          np.max(np.abs(r.Ud[0] - T7_1_DOM_ROW0)) < 0.6
          and np.max(np.abs(r.gva - T7_1_GVA)) < 0.6,
          f"row 1 {r.Ud[0].round(0).tolist()}, GVA {r.gva.round(0).tolist()} "
          f"against {T7_1_GVA.astype(int).tolist()}")
    check("supply equals use after step 2, which it did not before",
          np.max(np.abs(r.V.sum(1) - r.x)) < 1e-6
          and np.max(np.abs(r.V.sum(0) - r.Ud.sum(1))) < 1e-6,
          "column sums of the supply table are the industry outputs and its "
          "row sums are the domestic product uses — the identities hold only "
          "after the model-D step (¶18.95, p. 576)")

    # ---- table 9 (1): the method's own quality statement --------------------
    dev = np.array([r.deviations[k] for k in
                    ("va[0]", "va[1]", "va[2]", "final_use[0]",
                     "final_use[1]", "va_total", "tls", "imports")])
    check("table 9 (1) reproduces: the deviation of every aggregate",
          np.max(np.abs(dev - T9_1_DEV)) < 5e-4,
          f"worst {np.max(np.abs(dev - T9_1_DEV)):.1e} over the eight columns")

    print()
    print(f"    {'aggregate':<22}{'actual':>9}{'projected':>11}"
          f"{'dev':>9}{'printed dev':>13}")
    names = ["VA agriculture", "VA manuf. and const.", "VA services",
             "domestic demand", "exports", "total value added",
             "taxes less subsidies", "imports"]
    for nm, a, pr, d, pd_ in zip(names, T9_1_ACTUAL, T9_1_PROJECTED, dev,
                                 T9_1_DEV):
        print(f"    {nm:<22}{a:>9.4f}{pr:>11.4f}{d:>9.4f}{pd_:>13.4f}")

    # ---- iteration 2, where the two printed iterations stop agreeing ---------
    r2 = sut_euro(UD0, UM0, TLS0, V0, va_target=VA_2006,
                  final_use_target=FINAL_USE_2006, tls_target=TLS_2006,
                  imports_target=IMPORTS_2006, max_iter=2, stop_pct=0.0)
    dom2 = np.array([1899, 2944, 361, 1519, 526], float)
    imp2 = np.array([124, 1050, 151, 976, 59], float)
    tls2 = np.array([-96, 1051, 4846, 18496, 125], float)
    gva2 = np.array([3962, 68311, 159695], float)
    check("iteration 2 reproduces the domestic block and the taxes row exactly",
          np.max(np.abs(r2.step1.Ud[0] - dom2)) < 0.6
          and np.max(np.abs(r2.step1.tls - tls2)) < 0.6,
          f"row 1 {r2.step1.Ud[0].round(0).tolist()} and taxes "
          f"{r2.step1.tls.round(0).tolist()}, both as printed")
    check("and the GVA row, which is what pins down the recursion",
          np.max(np.abs(r2.step1.gva - gva2)) < 0.6,
          f"{r2.step1.gva.round(0).tolist()} against "
          f"{gva2.astype(int).tolist()} — the column scaling takes each "
          f"industry's own corrected rate and the row scaling the corrected "
          f"total, which the chapter states nowhere and these three figures "
          f"determine")
    check("the imported block is the one thing that does not reproduce exactly",
          np.max(np.abs(r2.step1.Um[0] - imp2)) < 2.5,
          f"{r2.step1.Um[0].round(0).tolist()} against "
          f"{imp2.astype(int).tolist()}, worst "
          f"{np.max(np.abs(r2.step1.Um[0] - imp2)):.1f} on 1 050. ¶18.93, "
          f"p. 576 gives the domestic rates to the imports only 'as starting "
          f"values' and never says how they diverge; this is the closest of the "
          f"four readings tried, and it is an inference, not a reading")

    # ---- and it converges ---------------------------------------------------
    run = sut_euro(UD0, UM0, TLS0, V0, va_target=VA_2006,
                   final_use_target=FINAL_USE_2006, tls_target=TLS_2006,
                   imports_target=IMPORTS_2006)
    worst = max(abs(v - 1.0) for v in run.deviations.values()) * 100
    print()
    print(f"    {run}")
    check("the loop converges on Box 18.8's own 1 per cent rule",
          run.converged and worst < 1.0,
          f"{run.iterations} iterations, worst deviation {worst:.3f} % — "
          f"¶18.101, p. 577 reports a fiftieth-iteration run and Box 18.8, "
          f"p. 580 would have stopped at 1 %, which the chapter never "
          f"reconciles (`M-046` LIMITATIONS)")
    check("and the converged pair still balances",
          np.max(np.abs(run.V.sum(1) - run.x)) < 1e-6,
          "supply column sums equal industry outputs")

    # ---- the guard the chapter states as a hard constraint ------------------
    try:
        sut_euro(UD0[:, :4], UM0[:, :4], TLS0[:4], V0[:, :2],
                 va_target=VA_2006, final_use_target=FINAL_USE_2006[:1],
                 tls_target=TLS_2006, imports_target=IMPORTS_2006)
        check("a rectangular pair is refused", False, "it was ACCEPTED")
    except SutEuroError as exc:
        check("a rectangular pair is refused", True, str(exc).split(".")[0][:96])

    print()
    print("    NOT claimed: that this is the only reading of ¶18.92's scaling.")
    print("    The chapter gives (E1) in closed form and describes the rest in")
    print("    prose; what is implemented reproduces iteration 1 exactly and")
    print("    iteration 2 to a few units in 200,000, which is the most a")
    print("    reader can ask of prose plus four printed decimals.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
