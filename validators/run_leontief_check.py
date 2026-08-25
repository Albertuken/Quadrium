"""
ID-12, on the user's own table — and the multiplier that is a difference.

WHAT WAS MISSING
-----------------
`identities.id12_leontief` has existed and been verified against published
tables since v1.1. Until 2026-08-25 a `grep` for it in `validation.py`,
`project.py` and `scenarios.py` returned NOTHING: the identity was checked
against other people's tables and never against the user's own.

That is not a missing feature. The report prints "output multipliers by
subsector" and presents them as the result, and a multiplier IS a column sum of
the Leontief inverse. The engine was printing the inverse without ever checking
the inverse existed. The nearest thing it did check was
`check_extreme_coefficients`, which flags an individual coefficient above 1 —
a symptom, not the condition.

FOUR CHECKS, BECAUSE THEY ARE FOUR DIFFERENT KINDS OF STATEMENT
-----------------------------------------------------------------
    productive     rho(A) < 1. The CONDITION, not a residue. Above it the
                   Neumann series diverges and multipliers are undefined.
    identity       max|Ax + y - x|. ACCOUNTING, bounded by the source's own
                   printed precision plus whatever its books are already out by.
    inverse        ||(I-A)L - I||. NUMERICAL, bounded by conditioning times
                   machine epsilon and unrelated to how the publisher rounded.
    non-negative   whether L has negative entries at all.

Holding all four to one tolerance is the mistake this project has now made and
corrected four times.

WHAT THE SWEEP FOUND, AND IT IS THE FOURTH ONE THAT MATTERS
-------------------------------------------------------------
Every table this engine can load is productive and well conditioned —
rho between 0.46 and 0.65, condition number 2 to 4 — so the first three checks
never fire on real data. The fourth does:

    ONS UK 2023 analytical              19 negative cells in L
    Eurostat symmetric ES / PT / IT      0
    INE ES 2022                          0
    supply-use -> model A / C      198 - 623
    supply-use -> model B / D            0

`rho(A) < 1` guarantees a NON-NEGATIVE inverse only for a non-negative A, and
these matrices are not: negatives in an IO table are legitimate (§A.8.1). So a
negative `L[i,j]` is possible, and it says that more final demand for j LOWERS
output of i — which is not what the word multiplier means.

ON THE PROJECT'S OWN FIXTURE THE CHAIN IS ONE CELL LONG
---------------------------------------------------------
The UK table has exactly ONE negative cell in Z: `K64 -> L68A`, financial
services into imputed rents of owner-occupied dwellings, -20,771. It produces
all 19 negatives in L, all of them in the single column `L68A`, whose published
output multiplier of 1.0828 is 1.1705 minus 0.0877.

That is the cell `OQ-D-02` has been asking about for sixty versions. The check
names the column, so a reader distrusts one multiplier rather than 104.

Run:
    python3 validators/run_leontief_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def leontief(Z, X):
    Z, X = np.asarray(Z, float), np.asarray(X, float).ravel()
    with np.errstate(divide="ignore", invalid="ignore"):
        A = np.where(X != 0, Z / X[None, :], 0.0)
    n = len(X)
    return A, np.linalg.inv(np.eye(n) - A)


def main() -> int:
    from quadrium.eurostat import load_iot, load_sut
    from quadrium.io_loader import load_ine_tio, load_uk_analytical_iot
    from quadrium.models import ValidationReport
    from quadrium.validation import _leontief_check

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    D = ROOT / "data" / "eurostat"
    uk = load_uk_analytical_iot(ROOT / "UK_IOAT_2023_domestic_ixi.xlsx")

    # 1 -- the check is wired into what a user actually runs.
    rep = ValidationReport(table_id="t", scenario_id="s")
    _leontief_check(rep, uk.Z, uk.X, uk.Y, 0.0, "", uk.sector_codes)
    names = [c.name for c in rep.checks]
    check("all four checks run on a table the engine loads",
          {"check_leontief_productive", "check_leontief_identity",
           "check_leontief_inverse", "check_leontief_nonnegative"}
          <= set(names),
          ", ".join(n.replace("check_leontief_", "") for n in names))

    # 2 -- the chain on the project's own fixture, cell by cell.
    negZ = np.argwhere(uk.Z < 0)
    A, L = leontief(uk.Z, uk.X)
    bad = np.flatnonzero((L < -1e-9).any(axis=0))
    check("one negative cell in Z produces every negative cell in L",
          len(negZ) == 1
          and uk.sector_codes[negZ[0][1]] == "L68A"
          and [uk.sector_codes[k] for k in bad] == ["L68A"],
          f"{uk.sector_codes[negZ[0][0]]} -> {uk.sector_codes[negZ[0][1]]} = "
          f"{uk.Z[negZ[0][0], negZ[0][1]]:,.0f} gives "
          f"{int((L < -1e-9).sum())} negative cells in L, all in column "
          f"{uk.sector_codes[bad[0]]}")

    col = L[:, bad[0]]
    check("so that column's multiplier is a difference, not a sum",
          abs(col.sum() - (col[col > 0].sum() + col[col < 0].sum())) < 1e-9
          and col[col < 0].sum() < -0.05,
          f"{col.sum():.4f} = {col[col > 0].sum():.4f} − "
          f"{abs(col[col < 0].sum()):.4f}. A reader quoting it is entitled to "
          f"know that, and the check names the column so they distrust one "
          f"multiplier and not {uk.n}")

    # 3 -- the sweep. Every table the engine can load.
    print()
    print(f"    {'table':38s}{'rho(A)':>9}{'cond':>8}{'neg(L)':>9}")
    rows = {}
    rows["ONS UK 2023"] = leontief(uk.Z, uk.X)
    rows["INE ES 2022 total"] = leontief(*(lambda t: (t.Z, t.X))(
        load_ine_tio(ROOT / "data" / "ine" / "cne_tio_22.xlsx", "total")))
    for stem, var in (("naio_10_cp1700_ES_2022", "domestic"),
                      ("naio_10_cp1700_PT_2020", "domestic"),
                      ("naio_10_cp1750_IT_2022", "domestic")):
        t = load_iot(D / f"{stem}.json", var)
        rows[stem.replace("naio_10_", "")] = leontief(t.Z, t.X)
    sut = load_sut(D / "naio_10_cp15_ES_2022.json",
                   D / "naio_10_cp16_ES_2022.json",
                   D / "naio_10_cp1610_ES_2022.json")
    for m in "ABCD":
        t = sut.to_iot(m)
        rows[f"SUT ES 2022 -> model {m}"] = leontief(t.Z, t.X)

    summary = {}
    for name, (A, L) in rows.items():
        rho = float(np.abs(np.linalg.eigvals(A)).max())
        cond = float(np.linalg.cond(np.eye(A.shape[0]) - A))
        neg = int((L < -1e-9).sum())
        summary[name] = (rho, cond, neg)
        print(f"    {name:38s}{rho:>9.4f}{cond:>8.0f}{neg:>9}")

    check("every published table this engine can load is productive",
          all(r < 1.0 for r, _c, _n in summary.values()),
          f"rho runs {min(r for r, _, _ in summary.values()):.2f} to "
          f"{max(r for r, _, _ in summary.values()):.2f}, condition number 2 "
          f"to {max(c for _, c, _ in summary.values()):.0f} — so the first "
          f"three checks never fire on real data, and saying so is part of "
          f"reporting them")

    check("but the fourth does, and it separates the models",
          summary["SUT ES 2022 -> model A"][2] > 100
          and summary["SUT ES 2022 -> model C"][2] > 100
          and summary["SUT ES 2022 -> model B"][2] == 0
          and summary["SUT ES 2022 -> model D"][2] == 0,
          f"models A and C put {summary['SUT ES 2022 -> model A'][2]} and "
          f"{summary['SUT ES 2022 -> model C'][2]} negative cells into the "
          f"inverse where B and D put none — one more argument for B and D, "
          f"of a kind CORE_013 does not make")

    # 4 -- and it catches a system that genuinely is not productive.
    print()
    Zbad = np.array([[60.0, 40.0], [50.0, 70.0]])
    Xbad = np.array([100.0, 100.0])
    Abad, _ = leontief(Zbad, Xbad)
    rho_bad = float(np.abs(np.linalg.eigvals(Abad)).max())
    rep2 = ValidationReport(table_id="t", scenario_id="s")
    _leontief_check(rep2, Zbad, Xbad, np.zeros((2, 1)), 0.0, "", ["a", "b"])
    prod = next(c for c in rep2.checks
                if c.name == "check_leontief_productive")
    check("a system that consumes more than it makes is refused",
          rho_bad > 1.0 and not prod.passed,
          f"rho = {rho_bad:.4f} on a two-sector table whose columns sum to "
          f"1.10 and 1.10 — no amount of tolerance makes that a multiplier, "
          f"and the check is an error rather than a warning for that reason")

    print()
    print("    A multiplier is a column sum of a matrix inverse. Printing one")
    print("    without checking the inverse is the kind of thing that survives")
    print("    precisely because everything around it is careful.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
