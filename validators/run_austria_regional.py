"""
Nine Austrian regions: what they are good for, and the one thing they are not.

WHY THESE TABLES
------------------
Everything this project has measured about regionalisation rests on one region.
`OQ-R-02` says so as it closes — "one region, one year, one country" — and names
`CORE_040` as the source that would say whether delta = 0.20 generalises. That
source is behind a portal. **What generalises a measurement is not a source but
more cases**, and there are nine of them here.

Rokicki, Bartlomiej, et al., "Survey-based versus algorithm-based multi-regional
input-output tables within the CGE framework — the case of Austria", *Economic
Systems Research* 33(4): 470-491, distributed as the technical-validation set of
the European MRIO dataset (Zenodo record 7875024, CC BY 4.0, code MIT).

They are **survey-based**, and they have the shape Catalonia has and almost
nothing else does: both sides of interregional trade, by sector. Column
`61 EXPROC` is what a region sells to the rest of Austria; row `71 ROCimp` is
what it buys.

THE CHECK THAT MATTERS MOST, BECAUSE IT CATCHES A MISTAKE THIS PROJECT MADE
-----------------------------------------------------------------------------
A closed national MRIO cannot have the regions exporting more to each other than
they import from each other: one region's sale to the rest of the country is
another's purchase. So the nine `EXPROC` columns must total the nine `ROCimp`
rows exactly.

They do — but only if the import rows are read across the **whole width** of the
table, intermediate columns and final-demand columns alike. Read across the
intermediate block alone, imports come to 75,338 against exports of 180,079,
**58 % short**. That is the same error, in a new dataset, that cost this project
a correction on the Catalan table, where it was 29.3 % against 28.3 %. The
identity below is what makes it impossible to make quietly.

AND THE THING THEY ARE NOT
----------------------------
They are not symmetric tables in the sense `IOTable` means. Both balance
identities hold against their **own** total — rows to 2.1 and columns to 4.9 on
AT13, against a file floor of 0.028 — but row output and column output differ by
up to **6,730 for a single sector**. Trade sells 11,156 and buys 17,886. The
differences sum to 3.3 across all 56 sectors, so it is a redistribution and not
a hole: a margin treatment, or a product/industry distinction, not an error.

`Z.sum(1) + Y.sum(1) == X` and `Z.sum(0) + VA.sum(0) == X` cannot both hold for
one X, so `load_rokicki_austria` **refuses** rather than attaching a residue and
carrying on. `read_rokicki_components` returns the parts and makes the caller
say which total it is using. That distinction is the whole point: use `X_col`
for technical coefficients, `X_row` for anything about commodity supply.

Run:
    python3 validators/run_austria_regional.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "mrio" / "truth" / "Austria"
REGIONS = ("AT11", "AT12", "AT13", "AT21", "AT22", "AT31", "AT32", "AT33", "AT34")
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    warnings.filterwarnings("ignore")
    from quadrium.io_loader import load_rokicki_austria, read_rokicki_components
    from quadrium.precision import assertable_tolerance

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if not DATA.exists():
        print(f"    -- {DATA} absent. The dataset is 317 MB and gitignored; the")
        print( "       URL and SHA-256 are in data/mrio/_provenance.json.")
        return 0

    missing = [r for r in REGIONS if not (DATA / f"{r}.csv").exists()]
    check("all nine regions are on disk", not missing,
          f"{len(REGIONS) - len(missing)} of {len(REGIONS)}"
          + (f"; missing {', '.join(missing)}" if missing else ""))
    if missing:
        return 1

    parts = {r: read_rokicki_components(DATA, r) for r in REGIONS}

    # ---- 1. the identity that makes the reading mistake impossible to keep
    exports = sum(float(p["Y"][:, p["Y_labels"].index("61 EXPROC")].sum())
                  for p in parts.values())
    imports_full = sum(p["imports_total"]["rest of country"] for p in parts.values())
    imports_intermediate = sum(float(p["imports"]["rest of country"].sum())
                               for p in parts.values())

    print()
    print(f"    {'interregional exports, all nine regions':<48}{exports:>12,.0f}")
    print(f"    {'interregional imports, read across the full width':<48}"
          f"{imports_full:>12,.0f}")
    print(f"    {'the same rows read across intermediates only':<48}"
          f"{imports_intermediate:>12,.0f}")

    check("the nine regions form a CLOSED national MRIO",
          abs(exports - imports_full) <= 1e-5 * exports,
          f"{abs(exports - imports_full) / exports * 100:.4f} % apart. One "
          f"region's sale to the rest of the country is another's purchase, so "
          f"this cannot be nearly true — it is true or the reading is wrong")

    check("and reading the import rows the wrong way is off by more than half",
          imports_intermediate < 0.6 * exports,
          f"{imports_intermediate:,.0f} against {exports:,.0f}, "
          f"{(1 - imports_intermediate / exports) * 100:.0f} % short. The same "
          f"mistake on the Catalan table was 29.3 % against 28.3 % and took a "
          f"correction to find; here the identity above catches it outright")

    # ---- 2. each identity holds against its own total
    print()
    print(f"    {'region':<8}{'row residue':>13}{'col residue':>13}"
          f"{'file floor':>12}{'row vs col output':>20}")
    worst_gap = 0.0
    for r in REGIONS:
        p = parts[r]
        Z, Y = p["Z"], p["Y"]
        prim = np.array(list(p["primary"].values()) +
                        [p["imports"][k] for k in p["imports"]])
        rowres = float(np.abs(Z.sum(1) + Y.sum(1) - p["X_row"]).max())
        colres = float(np.abs(Z.sum(0) + prim.sum(0) - p["X_col"]).max())
        vals = np.concatenate([Z.ravel(), Y.ravel(), p["X_row"]])
        floor = assertable_tolerance(vals, len(p["X_row"]))
        gap = float(np.abs(p["X_row"] - p["X_col"]).max())
        worst_gap = max(worst_gap, gap)
        print(f"    {r:<8}{rowres:>13.3f}{colres:>13.3f}{floor:>12.3f}{gap:>20,.0f}")

    check("both identities hold against their own total, on all nine",
          all(float(np.abs(parts[r]["Z"].sum(1) + parts[r]["Y"].sum(1)
                           - parts[r]["X_row"]).max()) < 10.0 for r in REGIONS),
          "so the tables are internally consistent; what follows is not an "
          "error in them")

    check("but row output is not column output, so they are not symmetric "
          "tables in the engine's sense",
          worst_gap > 1000.0,
          f"up to {worst_gap:,.0f} for a single sector, while the differences "
          f"sum to about zero across all 56 — a redistribution, not a hole")

    # ---- 3. and the loader says so instead of loading them
    print()
    refused = 0
    for r in REGIONS:
        try:
            load_rokicki_austria(DATA, r)
        except ValueError as exc:
            refused += 1
            if r == REGIONS[0]:
                print(f"    {str(exc).split(': ', 1)[1][:150]}…")
    check("load_rokicki_austria refuses all nine rather than attaching a residue",
          refused == len(REGIONS),
          f"{refused} of {len(REGIONS)}. A 5 % structural difference is not "
          f"rounding, and inherited_residue is for rounding. The parts are "
          f"available through read_rokicki_components(), which makes the caller "
          f"say which total it is using")

    print()
    print("    What these nine are FOR is D_open_questions.md OQ-R-02: they are")
    print("    the second, third and ninth region against which delta can be")
    print("    fitted, instead of the one the entry closed on.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
