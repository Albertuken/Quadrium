"""
Supply-use tables as an input to the engine, and the choice that makes them one.

WHAT WAS UNREACHABLE
---------------------
The four transformation models of CORE_013 Figure 12.2, p. 378 have been
implemented and verified against the chapter's own printed tables since v1.5.
`eurostat.load_sut` has built supply-use pairs since v1.3. And `TABLE_KINDS`
listed five ways into the engine, none of which was a supply-use pair — so
everything above was reachable from Python and from nowhere a user goes.

That is the third time this project has found the same shape: built, verified,
and not wired up. The Eurostat download was the first, the interchange format
the second.

WHY IT IS WORTH MORE THAN THE OTHER TWO
-----------------------------------------
Supply and use tables are what statistical offices publish first, most often,
and for the most years. Measured against Eurostat's own catalogue for Spain on
2026-08-25:

    naio_10_cp1700   symmetric IOT     22 years   1990-2023
    naio_10_cp15     supply            35 years   1990-2024
    naio_10_cp16     use               35 years   1990-2024

Thirteen more years, and the most recent year exists ONLY as a supply-use pair.

THE PART THAT IS A DECISION, NOT A CONVERSION
-----------------------------------------------
A supply-use pair is what the data is collected as. A symmetric table is what an
assumption about secondary production turns it into, and the four assumptions
are not interchangeable: `run_model_choice.py` measured model A's negatives
spanning a factor of fourteen between France and the Netherlands. So
`eurostat_model` is a configuration key, the report names the model that
produced the table, and taking the default is reported as a default taken.

WHAT THE SPLIT NEEDED, AND WHERE IT CAME FROM
-----------------------------------------------
The transformation needs use at BASIC prices split into domestic and imported.
`naio_10_cp16` is at purchasers' prices and undivided. `naio_10_cp1610` is at
basic prices with a `stk_flow` dimension of TOTAL / DOM / IMP, so the split is
READ. That matters: deriving it would impose the import-proportionality
assumption — every user of a product imports the same share of it — which is an
economic hypothesis and not bookkeeping.

Run:
    python3 validators/run_sut_to_iot.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "eurostat"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def files(geo: str, year: int = 2022) -> tuple:
    return (DATA / f"naio_10_cp15_{geo}_{year}.json",
            DATA / f"naio_10_cp16_{geo}_{year}.json",
            DATA / f"naio_10_cp1610_{geo}_{year}.json")


def main() -> int:
    from quadrium.eurostat import load_sut
    from quadrium.models import CellLabel, label_mask
    from quadrium.precision import assertable_tolerance, printed_decimals
    from quadrium.transformation import MODELS

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # 1 -- a pair without the basic-price file loads, and refuses to transform.
    sup, use, basic = files("ES")
    plain = load_sut(sup, use)
    check("a pair without the basic-price file still loads",
          not plain.transformable and plain.V.shape == (65, 65),
          "every supply-use identity still holds on it; what it cannot do is "
          "become a symmetric table")
    try:
        plain.to_iot("D")
        refused = ""
    except ValueError as exc:
        refused = str(exc)
    check("and says why, rather than deriving the split",
          "import-proportionality" in refused,
          "deriving it would assume every user of a product imports the same "
          "share of it — an economic hypothesis, not bookkeeping")

    # 2 -- with it, the blocks reconstitute what the pair already knew.
    #      `load_sut` refuses the file otherwise, so reaching here IS the check.
    full = load_sut(sup, use, basic)
    check("the domestic/imported split is read and cross-checked on load",
          full.transformable,
          f"U_dom {full.U_domestic.sum():,.0f} + U_imp "
          f"{full.U_imported.sum():,.0f} on {full.V.shape[0]} products; "
          f"load_sut refuses a file whose blocks do not rebuild q, imports "
          f"and g")

    # 3 -- all four models, on two countries, with their identities measured.
    print()
    print(f"    {'':4s}{'model':<30}{'sectors':>8}{'row dev':>10}"
          f"{'col dev':>10}{'neg(Z)':>8}")
    results = {}
    for geo in ("ES", "AT"):
        s = load_sut(*files(geo))
        vals = np.concatenate([s.V.ravel(), s.U.ravel(), s.q, s.g])
        # The bound is the source's own precision over the terms each identity
        # sums -- Spain prints one decimal and Austria two, from one dataset.
        tol = assertable_tolerance(vals, s.V.shape[0] + s.Y.shape[1] + 1)
        print(f"    {geo}  (published to {printed_decimals(vals)} decimal(s), "
              f"identities allowed {tol:.3g})")
        for m in "ABCD":
            t = s.to_iot(m)
            row = float(np.abs(t.Z.sum(1) + t.Y.sum(1) - t.X).max())
            col = float(np.abs(t.Z.sum(0) + t.VA.sum(0) - t.X).max())
            neg = int((t.Z < 0).sum())
            results[(geo, m)] = (t, row, col, neg, tol)
            print(f"    {'':4s}{m + '  ' + MODELS[m][0]:<30}{t.n:>8}"
                  f"{row:>10.4f}{col:>10.4f}{neg:>8}")

    # A TRANSFORMED CELL IS NOT A PUBLISHED FIGURE, so `0.5*10^-d*n` is the
    # wrong bound for it. It is a weighted sum of many published cells, and
    # model A inverts a matrix on the way. `run_rounding_amplification.py`
    # measured that on four economies: model A amplifies rounding four to ten
    # times more than model D, and 33x between Austria's smallest and largest
    # industries. Holding a transformed table to the summation floor asked it
    # to be more exact than its own arithmetic permits, and Austria's model A
    # duly failed it at 110%.
    #
    # What IS assertable is that the residue is negligible against the table,
    # and that its size follows the amplification already measured.
    rel = {(g, m): max(r, c) / abs(t.X.sum())
           for (g, m), (t, r, c, _n, _tol) in results.items()}
    worst = max(rel.items(), key=lambda kv: kv[1])
    check("no model leaves a residue that matters against the table",
          worst[1] < 1e-6,
          f"the worst is {worst[0][0]}/{worst[0][1]} at {worst[1]:.1e} of "
          f"total output — Spain closes exactly at one decimal, Austria to "
          f"hundredths at two")
    # Spain's residues are float64 noise, not zero -- the same distinction the
    # export round trip had to learn. `< 1e-12 of output` is the noise floor.
    es_noise = max(rel[("ES", m)] for m in "ABCD")
    check("and the residue is larger under the model that inverts",
          rel[("AT", "A")] > rel[("AT", "D")] and es_noise < 1e-12,
          f"Austria: A {rel[('AT', 'A')]:.1e} against D "
          f"{rel[('AT', 'D')]:.1e}. `run_rounding_amplification.py` measured "
          f"model A amplifying four to ten times more than D on four "
          f"economies; this is the same effect showing up in the identity "
          f"residue, and it is an argument for D beyond the ones CORE_013 "
          f"gives. Spain, which prints one decimal, closes to "
          f"{es_noise:.0e} of output under every model — float64 noise")

    # 4 -- and the models disagree, which is the point of naming one.
    negs = {m: results[("ES", m)][3] for m in "ABCD"}
    check("A and C produce negatives where B and D cannot",
          negs["A"] > 0 and negs["C"] > 0 and negs["B"] == 0 and negs["D"] == 0,
          f"Spain: A {negs['A']}, C {negs['C']}, B {negs['B']}, D {negs['D']} "
          f"— CORE_013 Figure 12.2, p. 378 says exactly this, and it is "
          f"observed here rather than assumed")

    a, d = results[("ES", "A")][0], results[("ES", "D")][0]
    spread = float(np.abs(a.Z - d.Z).max())
    check("and the same data gives materially different tables",
          spread > 1.0,
          f"the widest cell differs by {spread:,.0f} {a.unit} between models A "
          f"and D on identical inputs. Which is right is not a question the "
          f"data answers, which is why `eurostat_model` is a key and not a "
          f"default nobody sees")

    # 5 -- what the result claims to be.
    print()
    t = results[("ES", "D")][0]
    check("every cell of the result is labelled BALANCED, not OBSERVED",
          label_mask(t.provenance, CellLabel.BALANCED_ADJUSTMENT).all(),
          f"all {t.n ** 2} of them: no symmetric flow was ever observed, "
          f"because no such observation exists")
    check("and the table carries the model in its lineage",
          len(t.lineage) == 1 and "model D" in t.lineage[0],
          t.lineage[0])
    check("the imported block becomes value added marked NOT value added",
          t.VA_labels[0].endswith("(not value added)")
          and t.VA_labels[1].endswith("(not value added)"),
          f"{t.VA_labels[0]}; {t.VA_labels[1]} — the same convention the ONS "
          f"and INE loaders use, so the column identity closes the same way "
          f"everywhere")

    # 6 -- the sector with no output at all.
    dropped = set(load_sut(*files("ES")).activity_codes) - set(t.sector_codes)
    check("a sector with no output is dropped and named",
          dropped == {"U"} and "U" in (t.notes or ""),
          "U, extraterritorial organisations, is published with zero output; "
          "every model divides by output, so it has no technology to describe")

    # 7 -- end to end, the way a configuration does it.
    from quadrium.config import build_config
    cfg = build_config(
        {"project_id": "sut", "table_kind": "eurostat_sut",
         "eurostat_geo": "ES", "eurostat_year": 2022, "eurostat_model": "D",
         "table_path": str(DATA), "title": "t"},
        {"splits": [{"sector_code": "I", "new_code": c, "new_label": c,
                     "key_id": "k"} for c in ("I55", "I56")],
         "keys": [{"key_id": "k", "new_sector_code": c, "value": v,
                   "source": "synthetic", "source_year": 2022,
                   "strength": "weak"}
                  for c, v in (("I55", 22.0), ("I56", 78.0))],
         "scenarios": [{"scenario_id": "S1", "label": "S1"}],
         "profiles": []},
        base_dir=ROOT, offline=True)
    check("a configuration workbook can name a supply-use system",
          cfg["table"].n == 64 and "model-D" in cfg["table"].table_id,
          f"{cfg['table'].table_id} — three files, one transformation, and a "
          f"table the rest of the engine treats like any other")

    print()
    print("    Built, verified, and unreachable is the third instance of one")
    print("    shape in this project. It is worth looking for a fourth.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
