"""
Splitting a table this engine already split — and what that costs the audit.

WHAT WAS MISSING
-----------------
An analyst divides hospitality, looks at the result, and wants to divide food
manufacturing too. Until 2026-08-25 there was no way to do it except redo both
splits in one run: the exporter wrote `Z`, `FinalDemand`, `ValueAdded` and
`Output` as one sheet per block, laid out for a person, and the loader reads
the interchange format, laid out for a loader. **Quadrium could not read
Quadrium.** `docs/GUIDE.md` had no answer for the question and said so.

The exporter now writes both layouts into the same workbook, from the same
arrays in the same function, so they cannot disagree.

THE PART THAT IS NOT PLUMBING
-------------------------------
Reading the numbers back is easy. Reading back **what they are** is the point.

A disaggregated table balances exactly as well as a published one — the
identities hold to 1e-10 either way — so nothing in the figures reveals that
two thirds of its intermediate cells came from an allocation key rather than
from a survey. Load it as an ordinary table and the audit trail resets to
zero: the second run stamps every cell it does not touch `OBSERVED`, and by
the third generation a table of pure inference reports itself as pure
measurement.

So the `Provenance` sheet is read back too, and `split_sectors` now seeds from
the incoming provenance instead of from `OBSERVED`. The counterfactual below
measures what that is worth: the same second split, run on the same numbers
with the provenance withheld, and the difference is how many cells would have
been promoted from estimate to observation by a round trip through a file.

WHAT IS CHECKED
----------------
Two generations on the four-sector fixture of `run_interchange_roundtrip.py`.
Generation 1 divides B, is written to disk, and is read back. Generation 2
divides C in the reloaded table. Then: the numbers survive the round trip
exactly, the provenance survives it, no cell is promoted, both generations
reaggregate, and the lineage reads oldest-first with one line per split.

Run:
    python3 validators/run_export_roundtrip.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def split_once(table, sector, new_codes, labels, scenario_id, root, weights):
    """Run one scenario dividing `sector`, and return the DisaggregationResult."""
    from quadrium.models import (AllocationKey, Assumption, AssumptionLedger,
                                 ProxyStrength, Scenario, SplitSpec)
    from quadrium.project import IOProject

    key = AllocationKey(
        key_id=f"k{sector}", applies_to="output", new_sector_codes=new_codes,
        raw_values=list(weights),
        source="Synthetic proxy — run_export_roundtrip.py",
        source_year=table.year, strength=ProxyStrength.MEDIUM)
    ledger = AssumptionLedger(project_id=f"gen_{scenario_id}")
    ledger.add(Assumption(
        assumption_id="A-01",
        description="Synthetic weights. This checks the software, not an "
                    "economy.",
        applies_to=sector, source="run_export_roundtrip.py",
        validated_by="nothing — the fixture is invented",
        confidence=ProxyStrength.WEAK,
        impact_on_results="total"))
    project = IOProject(
        project_id=f"gen_{scenario_id}", table=table,
        splits=[SplitSpec(sector_code=sector, new_codes=new_codes,
                          new_labels=labels,
                          keys_by_block={"output": key.key_id})],
        scenarios=[Scenario(scenario_id=scenario_id, label=scenario_id,
                            description="")],
        keys={key.key_id: key}, ledger=ledger,
        title=f"generation {scenario_id}", source_file="—", root=root)
    project.run().write()
    return project, project.results[0]


def reaggregate(Z, mapping, n_old):
    """Sum an expanded Z back onto the original sector positions."""
    out = np.zeros((n_old, n_old))
    for i, oi in enumerate(mapping):
        for j, oj in enumerate(mapping):
            out[oi, oj] += Z[i, j]
    return out


def main() -> int:
    from quadrium.io_loader import load_io_table
    from quadrium.models import CellLabel, label_mask
    import run_interchange_roundtrip as fixture

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        original = load_io_table(fixture.write_table(tmp / "ruritania.xlsx"))
        check("the fixture starts with no provenance and no ancestry",
              original.provenance is None and original.lineage == []
              and not original.derived,
              "a table from a publisher is the start of a lineage, not a step "
              "in one")

        # ---- generation 1 -------------------------------------------------
        p1, g1 = split_once(original, "B", ["B1", "B2"],
                            ["Heavy manufacturing", "Light manufacturing"],
                            "S1", tmp / "out1", [0.7, 0.3])
        xlsx = p1.dir / "scenarios" / "S1" / "table_disaggregated.xlsx"
        check("the exported workbook carries both layouts",
              xlsx.exists(),
              "one sheet per block for a person, plus `table` and `metadata` "
              "for the loader — written together, from the same arrays")

        back = load_io_table(xlsx)
        worst = max(float(np.abs(a - b).max()) for a, b in
                    ((back.Z, g1.table.Z), (back.Y, g1.table.Y),
                     (back.VA, g1.table.VA), (back.X, g1.table.X)))
        # WHAT THIS IS ACTUALLY TESTING, and it is not bit-identity.
        #
        # The failure it exists to catch is a workbook written at the DISPLAY
        # precision -- the sheets carry `number_format = "#,##0.00"` -- which
        # would reload two decimals out, of order 5e-3. What it must tolerate
        # is the last bit of a float64 surviving a trip through openpyxl's
        # serialiser, which is not guaranteed to be exact.
        #
        # `worst == 0.0` conflated the two. It held on macOS and failed in CI
        # on Linux at 8.88e-16, one ULP on a value near 4 — the first thing
        # continuous integration found, on its first run, which is the whole
        # argument for having it. The bound below sits eleven orders of
        # magnitude below the defect and a few ULP above the noise.
        scale = max(float(np.abs(g1.table.Z).max()),
                    float(np.abs(g1.table.X).max()), 1.0)
        bound = 16 * float(np.finfo(float).eps) * scale
        check("every number survives the round trip to the last bit",
              worst <= bound,
              f"Z, Y, VA and Output reload to {worst:.3g}, against a bound of "
              f"{bound:.3g} — full precision, not the two decimals the sheets "
              f"are FORMATTED to, which would be out by ~5e-3")
        check("and so do the codes and the labels",
              back.sector_codes == g1.table.sector_codes
              and back.sector_labels == g1.table.sector_labels,
              f"{back.sector_codes}")

        same = int((np.asarray(back.provenance) ==
                    np.asarray(g1.table.provenance)).sum())
        check("the provenance survives it too", same == back.n * back.n,
              f"all {same} cells reload with the status they were written "
              f"with: {back.provenance_counts()}")
        check("the reloaded table knows it is not a publication",
              back.derived and "NOT A PUBLICATION" in (back.notes or ""),
              f"{len(back.lineage)} lineage line: {back.lineage[0][:58]}…")

        # ---- generation 2, on the reloaded table --------------------------
        p2, g2 = split_once(back, "C", ["C1", "C2"],
                            ["Market services", "Non-market services"],
                            "S2", tmp / "out2", [0.6, 0.4])
        check("a second sector of an already-split table can be divided",
              g2.table.sector_codes == ["A", "B1", "B2", "C1", "C2", "D"]
              and g2.report.passed,
              "six sectors from four, in two runs and two files, each of them "
              "balanced and validated on its own")

        # ---- the part that is not plumbing --------------------------------
        prov1 = np.asarray(back.provenance)
        prov2 = np.asarray(g2.table.provenance)
        promoted = [(i, j) for i in range(g2.table.n) for j in range(g2.table.n)
                    if prov2[i, j] == CellLabel.OBSERVED
                    and prov1[g2.mapping[i], g2.mapping[j]] != CellLabel.OBSERVED]
        check("no cell is promoted from estimate to observation", not promoted,
              f"{len(promoted)} promotions across {g2.table.n ** 2} cells")

        # The counterfactual: the same split with the provenance withheld.
        import dataclasses
        blind = dataclasses.replace(back, provenance=None)
        _, g2b = split_once(blind, "C", ["C1", "C2"],
                            ["Market services", "Non-market services"],
                            "S2b", tmp / "out2b", [0.6, 0.4])
        obs_kept = int(label_mask(prov2, CellLabel.OBSERVED).sum())
        obs_blind = int(label_mask(g2b.table.provenance,
                                   CellLabel.OBSERVED).sum())
        check("and withholding the provenance would have promoted many",
              obs_blind > obs_kept,
              f"{obs_blind} cells would call themselves observations against "
              f"{obs_kept} that are — {obs_blind - obs_kept} of 36 laundered "
              f"by one trip through a file, on a table this small")

        check("the numbers are identical either way, which is the point",
              float(np.abs(g2.table.Z - g2b.table.Z).max()) == 0.0,
              "the blind run computes exactly the same table. What it loses is "
              "not accuracy, it is the record of what the accuracy rests on")

        # ---- both generations still reaggregate ---------------------------
        r1 = reaggregate(back.Z, g1.mapping, original.n)
        r2 = reaggregate(g2.table.Z, g2.mapping, back.n)
        d1 = float(np.abs(r1 - original.Z).max())
        d2 = float(np.abs(r2 - back.Z).max())
        check("each generation reaggregates onto the one before it",
              max(d1, d2) < 1e-9,
              f"generation 1 back to the published table: {d1:.2e}; "
              f"generation 2 back to generation 1: {d2:.2e}")

        r_all = reaggregate(reaggregate(g2.table.Z, g2.mapping, back.n),
                            g1.mapping, original.n)
        d_all = float(np.abs(r_all - original.Z).max())
        check("and the chain reaggregates the whole way home",
              d_all < 1e-9,
              f"six sectors summed back to four across two files: {d_all:.2e}")

        # ---- the ancestry -------------------------------------------------
        final = load_io_table(p2.dir / "scenarios" / "S2" /
                              "table_disaggregated.xlsx")
        check("the lineage reads oldest first, one line per split",
              len(final.lineage) == 2
              and "B into B1, B2" in final.lineage[0]
              and "C into C1, C2" in final.lineage[1],
              " | ".join(x.split(":")[-1].strip() for x in final.lineage))
        check("and it does not double its newest step each time round",
              len(set(final.lineage)) == 2,
              "`derived_from` restates the last line for a human reader, and "
              "is read back only when there is no lineage row at all")

    print()
    print("    A result that cannot be read back is a dead end, and a result")
    print("    read back without its provenance is worse than one: it is a")
    print("    table of inference that reports itself as measurement.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
