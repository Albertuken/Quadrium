"""
Almon's procedure against the Eurostat manual's own worked example.

CORE_022 p. 328, Box 11.4 prints two scenarios of a five-product cheese economy
and puts four separate claims on the page. All four are checked here, because
between them they pin the algorithm completely — which matters, since Box 11.7's
subscripts do not survive text extraction and the implementation is therefore a
reconstruction of the prose, not a transcription of the formula.

    1. Model A on scenario A produces no negatives.
    2. A marginal change to the use table -- scenario B, four cells moved by one
       unit -- makes model A produce negatives. The box prints them: -1.67 at
       (Chocolate, Cheese) and -1.67 at (Rennet, Ice Cream).
    3. On scenario A, Almon reproduces model A exactly.
    4. On scenario B, Almon produces the SCENARIO A table, with no negatives,
       and its implied "New use table" is scenario A's use table.

Claim 4 is the one worth understanding. Almon does not preserve the use table;
it preserves the ROW totals and reports what the use table would have to be for
product technology to hold without negatives. In this example the answer is a
table the manual has already shown you, which is why the example was built this
way.

Note what claims 1 and 2 also test, free: the project's own model A, against a
second published example from a different manual than the one it was written
from. `run_handbook_transformations.py` checks it against CORE_013.

Run:
    python3 validators/run_almon_eurostat.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quadrium.transformation import almon, transform  # noqa: E402

FAIL: list[str] = []

# ---------------------------------------------------------------------------
# The fixture -- CORE_022 p. 328, Box 11.4. Products and industries in the same
# order: Cheese, Ice Cream, Chocolate, Rennet, Other.
# ---------------------------------------------------------------------------
V = np.array([[70,  30,   0,  0,   0],          # supply, product x industry
              [20, 180,   0,  0,   0],
              [0,    0, 100,  0,   0],
              [0,    0,   0, 20,   0],
              [0,    0,   0,  0, 535]], float)

U_A = np.array([[0,   0,  0, 0, 0],             # use, scenario A
                [0,   0,  0, 0, 0],
                [4,  36,  0, 0, 0],
                [14,  6,  0, 0, 0],
                [28, 72, 30, 5, 0]], float)

U_B = np.array([[0,   0,  0, 0, 0],             # scenario B: four cells move by 1
                [0,   0,  0, 0, 0],
                [3,  37,  0, 0, 0],
                [15,  5,  0, 0, 0],
                [28, 72, 30, 5, 0]], float)

Y = np.array([[100], [200], [60], [0], [400]], float)
W = np.array([[44, 96, 70, 15, 535]], float)
q, g = V.sum(axis=1), V.sum(axis=0)

# The printed product-by-product tables, p. 328.
IOT_A = np.array([[0,   0,  0, 0, 0],
                  [0,   0,  0, 0, 0],
                  [0,  40,  0, 0, 0],
                  [20,  0,  0, 0, 0],
                  [30, 70, 30, 5, 0]], float)

IOT_B_MODEL_A = np.array([[0,      0,     0, 0, 0],
                          [0,      0,     0, 0, 0],
                          [-1.67, 41.67,  0, 0, 0],
                          [21.67, -1.67,  0, 0, 0],
                          [30,    70,    30, 5, 0]], float)


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def model_a(U):
    return transform("A", V, U, np.zeros_like(U), Y, np.zeros_like(Y),
                     W, g, q).Sd


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 70)

    # 1 and 2 -- the box's model A results, which also re-check the engine's
    # model A against a manual it was not written from.
    a = model_a(U_A)
    check("scenario A, model A reproduces the printed table",
          float(np.abs(a - IOT_A).max()) < 5e-3,
          f"max deviation {np.abs(a - IOT_A).max():.4f}")
    check("and produces no negatives", int((a < -1e-9).sum()) == 0)

    b = model_a(U_B)
    check("scenario B, model A reproduces the printed table",
          float(np.abs(b - IOT_B_MODEL_A).max()) < 5e-3,
          f"max deviation {np.abs(b - IOT_B_MODEL_A).max():.4f} against a table "
          f"printed to two decimals")
    check("and a one-unit change in four use cells creates two negatives",
          int((b < -1e-9).sum()) == 2,
          f"{int((b < -1e-9).sum())} negative(s), most negative {b.min():.2f}")

    # 3 -- Almon agrees with model A where model A is well behaved.
    ra = almon(U_A, V)
    check("scenario A, Almon reproduces model A exactly",
          float(np.abs(ra["Z"] - IOT_A).max()) < 1e-9,
          f"max deviation {np.abs(ra['Z'] - IOT_A).max():.2e}")
    check("and leaves the use table untouched when it need not move it",
          ra["use_table_moved"] < 1e-9,
          f"moved {ra['use_table_moved']:.2e}")

    # 4 -- the substantive claim.
    rb = almon(U_B, V)
    check("scenario B, Almon reaches the scenario A table",
          float(np.abs(rb["Z"] - IOT_A).max()) < 1e-9,
          f"max deviation {np.abs(rb['Z'] - IOT_A).max():.2e}, converged in "
          f"{rb['iterations']} iterations")
    check("with no negatives", rb["n_negatives"] == 0)
    check("row totals are preserved exactly (CORE_022 p. 326)",
          rb["row_total_error"] < 1e-9, f"{rb['row_total_error']:.2e}")
    check("the implied New use table IS scenario A's use table",
          float(np.abs(rb["new_use"] - U_A).max()) < 1e-9,
          f"max deviation {np.abs(rb['new_use'] - U_A).max():.2e} — this is the "
          f"trade Almon makes, and the box was built to show it")
    check("the use table did move, by the one unit that was changed",
          abs(rb["use_table_moved"] - 1.0) < 1e-9,
          f"{rb['use_table_moved']:.4f}")

    # Austria's refinement: a floor other than zero. NSO_AT_01 p. 65.
    floor = np.zeros_like(U_B)
    floor[4, :] = 1.0            # "Other" is consumed by every process
    rf = almon(U_B, V, lower=floor)
    check("a non-zero floor is honoured (NSO_AT_01 p. 65)",
          float(rf["Z"][4].min()) >= 1.0 - 1e-9,
          f"smallest 'Other' input {rf['Z'][4].min():.4f} against a floor of 1.0")
    check("and the floor costs the column totals, which is why RAS follows",
          rf["col_total_error"] > 1e-9,
          f"column totals off by {rf['col_total_error']:.4f} — CORE_022 p. 326 "
          f"and NSO_AT_01 p. 61 both require a RAS pass")

    # ID-13 on integer data, where "preserved" can mean exactly.
    print()
    zero = np.zeros_like(U_A)
    for model in ("A", "B", "C", "D"):
        r = transform(model, V, U_A, zero, Y, np.zeros_like(Y), W, g, q)
        va = float(np.atleast_2d(r.E).sum())
        check(f"ID-13 model {model}: total value added is invariant",
              abs(va - W.sum()) < 1e-9, f"{va:,.4f} against {W.sum():,.4f}")
        if model in ("C", "D"):
            check(f"ID-13 model {model}: the value-added block is untouched",
                  float(np.abs(np.atleast_2d(r.E) - W).max()) < 1e-9)
            check(f"ID-13 model {model}: intermediate column totals hold",
                  float(np.abs(r.Sd.sum(0) - U_A.sum(0)).max()) < 1e-9)
        else:
            check(f"ID-13 model {model}: final use is untouched",
                  float(np.abs(r.Yd - Y).max()) < 1e-9)
            check(f"ID-13 model {model}: intermediate row totals hold",
                  float(np.abs(r.Sd.sum(1) - U_A.sum(1)).max()) < 1e-9)

    print("\n" + "=" * 70)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
