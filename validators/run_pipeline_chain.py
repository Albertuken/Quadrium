"""
The whole chain, once: regionalise, write, read back, split, and see what survives.

WHY A CHAIN AND NOT MORE UNIT CHECKS
--------------------------------------
Every link in this engine is checked on its own. The chain was not, and running
it end to end on 2026-09-01 found two defects in the first five minutes, both of
the same kind and both invisible to any test of a single step:

1. **`--regionalise` returned a table whose every cell claimed to be an
   observation.** `IOTable.provenance is None` means "a publisher's table, as
   far as this system can tell", and the regionalised table set none — so a
   split of it would have inherited a matrix of estimates wearing the status of
   measurements.

2. **And the file boundary erased it anyway.** The `Provenance` sheet, which the
   loader reads back, was written by `write_xlsx` and not by the interchange
   writer, so only a disaggregation ever got one. Written ESTIMATED on 4,096
   cells, read back OBSERVED on all 4,096.

The second is the failure `IOTable.provenance`'s own docstring calls "the one
thing an audit trail may not do" — reset at the file boundary. It had been true
of every table this engine produced by any route other than a split.

WHAT THIS CHECKS
------------------
That the estimates stay estimates through four boundaries: the constructor, the
file, the loader, and a second derivation on top. And that the **measured cost**
of the regionalisation is still attached after the split, because a caveat that
survives one step and not two is worse than none — it disappears exactly when
the result has travelled far enough for someone to have forgotten it.

Run:
    python3 validators/run_pipeline_chain.py
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

ES = ROOT / "data" / "ine" / "cne_tio_21.xlsx"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    warnings.filterwarnings("ignore")
    from quadrium import diagnostics
    from quadrium.export import write_interchange_xlsx
    from quadrium.io_loader import load_ine_tio, load_io_table
    from quadrium.models import AllocationKey, ProxyStrength, Scenario, SplitSpec
    from quadrium.project import IOProject
    from quadrium.regionalise import regionalise

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    check("a national table to start the chain from", ES.exists(), ES.name)
    if not ES.exists():
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="quadrium_chain_"))
    try:
        # ---- 1. regionalise
        national = load_ine_tio(ES, variant="interior")
        rng = np.random.default_rng(11)
        share = np.clip(0.20 * np.exp(rng.normal(0, 0.5, national.n)), 0.02, 0.85)
        A_nat = np.nan_to_num(
            diagnostics.technical_coefficients(national.Z, national.X))
        r = regionalise(A_nat, national.X * share, national.X,
                        method="FLQ", delta=0.25)
        region = r.to_table(
            sector_codes=national.sector_codes,
            sector_labels=national.sector_labels, country="ES-region",
            year=national.year, unit=national.unit,
            classification=national.classification)

        counts = region.provenance_counts()
        check("the regionalised table says every cell of it is an estimate",
              region.derived and counts.get("ESTIMATED") == region.n ** 2
              and counts.get("OBSERVED", 0) == 0,
              f"{counts}. It is A^N scaled by a quotient, so not one cell is an "
              f"observation; the first version of to_table() left provenance "
              f"None, which claims the opposite")

        d = diagnostics.compute(region.Z, region.X)
        check("and it is a table the engine can actually work with",
              d["spectral_radius"] < 1.0 and int((d["L"] < 0).sum()) == 0,
              f"spectral radius {d['spectral_radius']:.4f}, no negative cell in "
              f"the Leontief inverse, mean multiplier "
              f"{d['multipliers'].mean():.4f}")

        # ---- 2. write it, and read it back
        path = tmp / "region.xlsx"
        write_interchange_xlsx(region, path, derived_from="chain test")
        back = load_io_table(path)
        check("the estimates survive the file boundary",
              back.derived
              and back.provenance_counts() == region.provenance_counts(),
              f"{back.provenance_counts()} after a round trip. Until the "
              f"Provenance sheet moved into the interchange writer this came "
              f"back {region.n ** 2} OBSERVED — the audit trail resetting at "
              f"the file boundary, which is what the field exists to prevent")

        check("and so does what the table is",
              back.lineage and any("regionalised" in line for line in back.lineage),
              f"{len(back.lineage)} lines of lineage survive, the first being "
              f"{back.lineage[0][:60]!r}")

        # ---- 3. split a sector of it
        code = back.sector_codes[35]
        key = AllocationKey(
            key_id="k", applies_to="output",
            new_sector_codes=[f"{code}a", f"{code}b"], raw_values=[60.0, 40.0],
            source="chain test fixture", source_year=2021,
            strength=ProxyStrength.WEAK)
        run = IOProject(
            project_id="chain", table=back, keys={"k": key},
            splits=[SplitSpec(code, [f"{code}a", f"{code}b"], ["A", "B"])],
            scenarios=[Scenario(scenario_id="S", label="x",
                                keys_by_block={"output": "k"})]).run()
        out = run.results[0].table

        check("a sector of the region can be split, and the result still "
              "declares itself derived",
              out.n == back.n + 1 and out.derived
              and out.provenance_counts().get("OBSERVED", 0) == 0,
              f"{out.n} sectors, {out.provenance_counts()}. Nothing in this "
              f"table was ever measured and nothing in it claims to be")

        # ---- 4. and the cost of the first step is still attached
        lineage = "\n".join(out.lineage)
        check("the measured cost of the regionalisation survives the split",
              "28.3" in lineage and "2.2 points" in lineage
              and "6.9 % to 20.0 %" in lineage,
              "the three caveats are still on the table after a second "
              "derivation. A warning that survives one step and not two "
              "disappears exactly when the result has travelled far enough for "
              "someone to have forgotten it")

        check("and the second step is recorded on top of the first, not "
              "instead of it",
              any("regionalised" in line for line in out.lineage)
              and any("->" in line and code in line for line in out.lineage),
              f"{len(out.lineage)} lines: the regionalisation, its caveats, and "
              f"{[line for line in out.lineage if '->' in line][0][:56]!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
