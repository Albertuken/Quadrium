"""
A three-block table divided, written, read back, and still three blocks.

WHY THIS WAS WRITTEN
----------------------
`run_table_composition.py` exists because four times in three days a code path
rebuilt an `IOTable` and the fields that ride on it did not come along: the
satellite account, the type II closure. `region_codes` was the fifth, and it
was invisible for a month because until `mrio_scope: with_rest` there was one
construction in the engine that set it and nothing downstream that could
receive it. A field nobody reads cannot be seen to be lost.

Dividing a sector of a three-block table is the operation that pays for it, and
it is the documented route: the table's own notes say a sector code names the
region's own block, so a split of `G-I` divides ES51's G-I. Before 2026-09-12
the result of that split had no regional axis at all, and the file it was
written to had nowhere to put one.

WHAT IS CHECKED, ON THE REAL ARCHIVE
--------------------------------------
ES51 with the rest of Spain and the rest of the archive, 2018:

1. the split keeps the three blocks, and the two new subsectors are in ES51's,
   which is the claim the table's notes make;
2. the blocks come out UNEQUAL -- eleven sectors against ten -- and both
   identities still close, because a divided interregional table is what this
   is and the object holds it;
3. the table survives a round trip through the interchange format: the axis
   comes back, each block keeps its own labels, and a satellite account comes
   back unit by unit;
4. what the round trip does NOT carry is stated rather than lost:
   `interregional` is the leakage measured on the archive, not a fact about
   the file, and a table read from disk does not claim it.

WHAT WOULD HAVE HAPPENED WITHOUT 3
------------------------------------
The interchange format keys labels and satellite rows by SECTOR CODE, and
three blocks repeat the same ten codes. Written and read back, an employment
account came back with the rest of the archive's figures sitting in the
region's own block -- the same numbers, in the wrong place, with no error:
the coverage check counted ten codes out of ten and passed. That is measured
here rather than described, on the fixture in `tests/test_engine.py`.

Run:
    python3 validators/run_regional_roundtrip.py
"""
from __future__ import annotations

import sys
import tempfile
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MRIO = ROOT / "data" / "mrio"
REGION = "ES51"
FAIL: list[str] = []

# Exit 3, as `run_eu_mrio_wide.py` does: the archive is 33 MB and gitignored,
# and a validator that opened no file must not report a pass.
NOTHING_CHECKED = 3


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if not ((MRIO / "_mrio2018_cache.npz").exists()
            or (MRIO / "MRIO_2018_272regions.xlsx").exists()):
        print("    -- the 2018 archive is absent (33 MB, gitignored). The URL "
              "and SHA-256 are in data/mrio/_provenance.json.")
        print("\n" + "=" * 78)
        print("Nothing was checked: the archive is not in this tree.")
        return NOTHING_CHECKED

    from quadrium.export import write_interchange_xlsx
    from quadrium.io_loader import load_eu_mrio_wide, load_io_table
    from quadrium.models import (AllocationKey, ProxyStrength, Satellite,
                                 Scenario, SplitSpec)
    from quadrium.scenarios import run_scenario

    t = load_eu_mrio_wide(MRIO, REGION, 2018)
    S = len(t.sector_codes) // 3
    blocks = t.regions
    print(f"    {REGION} 2018, three blocks: {', '.join(blocks)}, "
          f"{S} sectors each")
    print()

    # An account whose every unit differs, so a lookup by sector code alone
    # cannot come back right by coincidence.
    t.satellites["jobs"] = Satellite(
        name="jobs", unit="persons (fixture, not Eurostat's)",
        values=[1000.0 + i for i in range(t.n)],
        source="a fixture of this validator, so the round trip has something "
               "to carry", source_year=2018)

    key = AllocationKey(
        key_id="k", applies_to="output", new_sector_codes=["GI1", "GI2"],
        raw_values=[70.0, 30.0], source="a fixture of this validator",
        source_year=2018, strength=ProxyStrength.WEAK)
    res = run_scenario(
        t, [SplitSpec("G-I", ["GI1", "GI2"], ["Trade and transport",
                                              "Accommodation and food"])],
        Scenario(scenario_id="S1", label="split", description="one sector",
                 keys_by_block={"output": "k"}), {"k": key})
    out = res.table
    rc = list(out.region_codes or [])

    check("a split of the region's sector keeps the three blocks",
          out.regions == blocks and len(rc) == out.n,
          f"{out.n_regions} block(s) over {out.n} units")
    check("and the subsectors are in the region's own block, which is what "
          "the table's notes promise",
          bool(rc) and rc[out.index_of("GI1")] == REGION
          and rc[out.index_of("GI2")] == REGION,
          f"GI1 is unit {out.index_of('GI1')} of {out.n}, in "
          f"{rc[out.index_of('GI1')] if rc else 'no region'}")
    check("the blocks are unequal now, and the object holds that",
          bool(rc) and rc.count(REGION) == S + 1
          and rc.count(blocks[2]) == S,
          f"{rc.count(REGION)} sectors in {REGION}, {rc.count(blocks[2])} in "
          f"{blocks[2]}")
    check("and both identities still close on the divided table",
          bool(np.allclose(out.Z.sum(1) + out.Y.sum(1), out.X, rtol=0, atol=1e-6))
          and bool(np.allclose(out.Z.sum(0) + out.VA.sum(0), out.X,
                               rtol=0, atol=1e-6)),
          f"max |row| {np.abs(out.Z.sum(1) + out.Y.sum(1) - out.X).max():.2e}, "
          f"max |col| {np.abs(out.Z.sum(0) + out.VA.sum(0) - out.X).max():.2e}")

    tmp = Path(tempfile.mkdtemp(prefix="quadrium_regional_roundtrip_"))
    path = write_interchange_xlsx(
        out, tmp / f"{REGION}_split.xlsx",
        derived_from="a three-block table with one sector divided.")
    back = load_io_table(path)

    check("written and read again, the table knows its regions",
          back.regions == blocks and list(back.region_codes or []) == rc,
          f"came back as {back.regions or 'no regional axis'}")
    check("every block keeps its own labels, not the last block's",
          back.sector_labels == out.sector_labels,
          f"{sum(a != b for a, b in zip(back.sector_labels, out.sector_labels))}"
          f" of {out.n} differ")
    check("and the account comes back unit by unit",
          np.allclose(back.satellites["jobs"].values,
                      out.satellites["jobs"].values),
          f"{back.satellites['jobs'].values[:2]} … against "
          f"{out.satellites['jobs'].values[:2]} …")
    # NOT bit-for-bit, and the reason is the format rather than the engine.
    # `run_export_roundtrip.py` requires exact equality and gets it, on a
    # fixture whose cells are two-digit numbers. These are the archive's, seven
    # digits before the point, and a spreadsheet holds about sixteen
    # significant digits: 3,107,471.4074966107 is written 3,107,471.407496611
    # and comes back one unit of the last place away. Asking for exactness
    # here would be asking the file format for a digit it does not have.
    worst = max(float(np.abs(back.Z - out.Z).max()),
                float(np.abs(back.X - out.X).max()))
    scale = max(float(np.abs(out.Z).max()), float(np.abs(out.X).max()))
    check("the numbers survive the round trip to the last digit a spreadsheet "
          "holds",
          worst <= 1e-15 * scale,
          f"worst {worst:.2e} on cells up to {scale:,.0f} — "
          f"{worst / scale:.1e} relative, one unit in the sixteenth "
          f"significant digit")
    check("and what a file cannot claim, it does not: the archive's leakage "
          "is not read back as if it were in the file",
          not (back.interregional or {}),
          "`interregional` is measured on the whole archive; a table read "
          "from disk has no archive to measure")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: " + ", ".join(FAIL))
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
