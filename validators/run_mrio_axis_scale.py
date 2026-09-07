"""
The regional axis on 272 real regions, and what the cross-hauling floor becomes there.

TWO THINGS THAT WERE ONLY TESTED SMALL
----------------------------------------
**The axis.** `IOTable` grew a regional axis at v1.81 on the argument that an
IRIO is an ordinary table whose sectors are (region, sector) pairs. Until now the
only thing exercising it was a synthetic 6 x 6 in the unit tests. The European
MRIO's 2018 table is 272 NUTS-2 regions by 10 sectors — **2,720 x 2,720**,
59 MB of doubles — and it is laid out exactly as the axis requires, region-major
with labels like `AT11-A`, `AT11-B-E`, `AT11-F`. If the design is right it should
load without special-casing and slice without copying.

**The floor.** `run_lq_crosshauling_structure.py` proved that CILQ cross-hauls at
least `S - R` commodities whatever the data, and that the bound is exact for two
regions: 8 of 10, 62 of 64. That was measured in one regime only — many sectors,
few regions. Here `S = 10` and `R = 272`, so `S - R` is negative and the bound
says nothing. What replaces it is not a guess: a region imports commodity `i`
unless `i` is that region's SLQ-argmax, so

    regions importing i  =  R - (regions where i is the argmax)

exactly, and a commodity is cross-hauled whenever two or more regions import it.
With 272 regions and 10 commodities every commodity is argmax somewhere at most,
and short of one commodity dominating 271 regions, **all ten are cross-hauled**.
The floor does not weaken at scale; it saturates.

THE SIDE FILES CANNOT BE JOINED, AND THAT IS THE THIRD FINDING
----------------------------------------------------------------
`MRIO_2018_272regions.xlsx` runs region-major. `Final_demand_2018.xlsx` and
`TAXSUB_VA_2018.xlsx` run sector-major, which alone would only need a
permutation. But they are also on a **different NUTS vintage**: the block
carries 2013 codes (`EL11`, `FR21`, `PL11`) and the side files 2016 codes
(`EL51`, `FRB0`, `PL71`). 236 of the 272 regions match by label; the other 36
are France, Greece and Poland, exactly the countries recoded between the two.

Both files hold 272 regions in the same country order, so a **positional join
within each country looks safe and is not**: it pairs the block's `EL11`
(Anatoliki Makedonia) with the side files' `EL30` (Attiki), because each list is
sorted under its own coding. The counts agree, the join completes, and the
result is wrong. The archive's `NUTS2_list.xlsx` does not carry the
correspondence — its two `geo` columns are identical on all 268 of its rows —
and this project does not invent one.

**Resolved on 2026-09-04, and the premise above is half wrong.** Eurostat's
published correspondence tables were acquired and composed in
`run_mrio_nuts_join.py`: 271 of the 272 regions join one to one. The block is
not on NUTS 2013 — it is 2013 for France and **2010 for Greece**, which is why
one table could never have closed it and why the failure looked like a missing
file rather than a mixed axis. The 272nd, `PL12`, stays refused: it was split
into `PL91` and `PL92` and the side files carry only `PL91`. What follows still
uses the block alone, which is correct for what it tests — the quotient's
structure — and is no longer forced.

**And on 2026-09-04 the join stopped needing the correspondence at all.**
`run_mrio_side_join.py` establishes that the side files' data is in the BLOCK's
region-major order while their label column is printed sector-major: the labels
do not describe their own rows. Joining by label gives a log-correlation of
**-0.08** with the block's intermediate sales, puts output below intermediate
sales in **875 of 2,360** units, and spreads government consumption flat across
all ten sectors; joining row `i` to row `i` gives **+0.88**, 123 of 2,720, and
puts government consumption in `O-Q` and `R-U` where it belongs. The refusal
recorded above was right on what it knew — it refused to assume — and what
changed it is evidence rather than a decision.

So the block is used alone. Regional sectoral activity is measured as **total
intermediate sales**, `Z.sum(axis=1)`, and that is a stated proxy for output: an
SLQ is a ratio of shares, so a consistent proxy is admissible where the real
output vector cannot be formed.

**Settled on 2026-09-04, and the bet was half won.** `run_mrio_real_output.py`
attaches the published output vector and repeats the measurement. The
conclusion below holds — all ten commodities cross-hauled either way — and
**nothing per-region does**: the two measures name the same specialising sector
for only 160 of 272 regions, and construction goes from 49 regions to 22 while
real estate goes from 29 to 5. The proxy was admissible for exactly the claim
this file makes and for no statement about a named region. Everything below is a statement about the
quotient's structure, which is what it was written to test.

Run:
    python3 validators/run_mrio_axis_scale.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

MRIO = ROOT / "data" / "mrio" / "MRIO_2018_272regions.xlsx"
FD = ROOT / "data" / "mrio" / "Final_demand_2018.xlsx"
VA = ROOT / "data" / "mrio" / "TAXSUB_VA_2018.xlsx"
CACHE = ROOT / "data" / "mrio" / "_mrio2018_cache.npz"
FAIL: list[str] = []

# Exit code 3, not 0. `check.sh` counts it as SKIPPED rather than as a pass:
# this validator opened no file and measured nothing, and a run that says
# "All checks passed" on evidence it never saw is the fault the suite exists
# to catch. It is not a failure -- a tree without the workbook still exits 0.
NOTHING_CHECKED = 3


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def load_Z():
    """The 2,720 x 2,720 block, cached because the workbook takes 30 s to parse.

    The cache is gitignored and rebuilt from the workbook whenever it is
    missing, so it is an optimisation and never a source of truth.
    """
    import openpyxl

    if CACHE.exists():
        d = np.load(CACHE, allow_pickle=False)
        return d["Z"], [str(x) for x in d["labels"]]
    sh = openpyxl.load_workbook(MRIO, read_only=True, data_only=True)["Sheet1"]
    it = sh.iter_rows(values_only=True)
    labels = [str(x) for x in next(it)[1:]]
    idx, rows = [], []
    for r in it:
        idx.append(str(r[0]))
        rows.append([0.0 if c is None else float(c) for c in r[1:]])
    if idx != labels:
        raise ValueError("the MRIO's row and column labels differ")
    Z = np.asarray(rows, dtype=np.float64)
    np.savez_compressed(CACHE, Z=Z, labels=np.array(labels))
    return Z, labels


def load_side(path, orientation):
    """Final demand (rows are units) or VA (columns are units), by label."""
    import openpyxl

    rows = list(openpyxl.load_workbook(path, read_only=True,
                                       data_only=True)["Sheet1"]
                .iter_rows(values_only=True))
    if orientation == "rows":
        head = [str(c) for c in rows[0][1:]]
        keys = [str(r[0]) for r in rows[1:]]
        M = np.array([[0.0 if c is None else float(c) for c in r[1:]]
                      for r in rows[1:]], float)
    else:
        head = [str(r[0]) for r in rows[1:]]
        keys = [str(c) for c in rows[0][1:]]
        M = np.array([[0.0 if c is None else float(c) for c in r[1:]]
                      for r in rows[1:]], float).T
    return keys, head, M


def main() -> int:
    warnings.filterwarnings("ignore")
    from quadrium.models import IOTable

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if not (MRIO.exists() or CACHE.exists()):
        print(f"    -- {MRIO.name} absent; it is 33 MB and gitignored. The URL")
        print( "       and SHA-256 of the archive are in data/mrio/_provenance.json.")
        print("\n" + "=" * 78)
        print("Nothing was checked: data/mrio/MRIO_2018_272regions.xlsx "
              "is absent.")
        return NOTHING_CHECKED

    Z, labels = load_Z()
    check("the interregional block loads at full size",
          Z.shape == (2720, 2720),
          f"{Z.shape[0]:,} x {Z.shape[1]:,}, {Z.nbytes / 1e6:.0f} MB of doubles, "
          f"summing to {Z.sum():,.0f}")

    # A label is REGION-SECTOR, but sector codes themselves contain hyphens
    # (B-E, G-I, O-Q, R-U), so split on the FIRST hyphen only.
    regions = [l.split("-", 1)[0] for l in labels]
    sectors = [l.split("-", 1)[1] for l in labels]
    S = len(dict.fromkeys(sectors))
    R = len(dict.fromkeys(regions))
    check("and it is laid out region-major, as the axis requires",
          R * S == len(labels) and sectors[:S] == sectors[S:2 * S],
          f"{R} regions x {S} sectors = {len(labels):,}; the first two regions "
          f"carry the same sectors in the same order")

    # ---- why the side files are not used
    if FD.exists():
        fd_keys, _, _ = load_side(FD, "rows")
        fd_reg = list(dict.fromkeys(k.split("-", 1)[0] for k in fd_keys))
        blk_reg = list(dict.fromkeys(regions))
        common = set(fd_reg) & set(blk_reg)
        countries_ok = all(a[:2] == b[:2] for a, b in zip(blk_reg, fd_reg))
        # The countries whose CODES differ, not merely their position: Finland
        # appears in both lists under the same codes but at different offsets,
        # and calling that a recoding would be wrong.
        offenders = sorted({r[:2] for r in set(blk_reg) ^ set(fd_reg)})
        check("the side files are on a different NUTS vintage, so they are not "
              "joined",
              len(common) < len(blk_reg) and countries_ok,
              f"{len(common)} of {len(blk_reg)} regions match by label; the "
              f"rest are {', '.join(offenders)} — recoded between NUTS 2013 and "
              f"2016. The country ORDER matches, which is what makes a "
              f"positional join tempting: it would pair the block's "
              f"{[a for a, b in zip(blk_reg, fd_reg) if a != b][0]} with the "
              f"side files' {[b for a, b in zip(blk_reg, fd_reg) if a != b][0]}, "
              f"two different regions. NUTS2_list.xlsx does not carry the "
              f"correspondence and this project does not invent one")

    # The table is closed with residual final demand and value added columns.
    # That is a construction for exercising the axis at scale, not an economic
    # claim: it makes the identities hold by definition, and nothing below
    # reads Y or VA.
    Y = (Z.sum(1) * 0.25)[:, None]
    X = Z.sum(1) + Y.sum(1)
    V = (X - Z.sum(0))[None, :]

    table = IOTable(
        table_id="EUR_MRIO_2018", country="EU+", year=2018,
        unit="million EUR", classification="NACE level 1, NUTS-2",
        # The sector code is the SECTOR, not the label: `region_codes` carries
        # the other half. Passing the full 'AT11-A' here is what the axis
        # exists to make unnecessary, and IOTable refuses it — the first run of
        # this file did exactly that and was told so.
        sector_codes=list(sectors), sector_labels=list(labels),
        Z=Z, Y=Y, Y_labels=["final demand (residual, for closure)"],
        VA=V, VA_labels=["value added (residual, for closure)"],
        X=X, source="Zenodo 7875024, MRIO_2018_272regions.xlsx",
        region_codes=regions)

    check("it constructs as an IOTable, with the axis and both identities",
          table.n == 2720 and table.n_regions == R
          and table.sectors_per_region == S,
          f"{table.n:,} rows, {table.n_regions} regions, "
          f"{table.sectors_per_region} sectors each. No new type was needed and "
          f"__post_init__ accepted the layout")

    a, b = table.regions[0], table.regions[1]
    blk = table.block(a, b)
    check("blocks slice without copying, at this size",
          blk.shape == (S, S) and np.shares_memory(blk, table.Z)
          and np.array_equal(table.intraregional(a), Z[:S, :S]),
          f"{a}->{b} is {blk.shape[0]}x{blk.shape[1]} and shares memory with "
          f"the {Z.nbytes / 1e6:.0f} MB array rather than owning any. The "
          f"blocks partition Z, so one pass over all {R * R:,} of them costs "
          f"nothing extra; a copying implementation would allocate another "
          f"{Z.nbytes / 1e6:.0f} MB per pass, and a regionalisation sweeps them "
          f"repeatedly")

    # ---- the floor, at the other end of the regime
    print()
    # Activity = total intermediate sales, the stated proxy. NOT
    # table.regional_output(), which here is the residual closure above.
    sales = Z.sum(axis=1)
    per = np.array([sales[i * S:(i + 1) * S] for i in range(R)])        # R x S
    Xr = per.sum(axis=1)
    nat = per.sum(0)
    with np.errstate(divide="ignore", invalid="ignore"):
        slq = (per / Xr[:, None]) / (nat / nat.sum())
    slq = np.where(np.isfinite(slq), slq, 0.0)
    argmax = slq.argmax(axis=1)
    importing = np.array([R - int((argmax == i).sum()) for i in range(S)])
    hauled = int((importing >= 2).sum())

    print(f"    {'sectors':<34}{S:>8}")
    print(f"    {'regions':<34}{R:>8}")
    print(f"    {'the S - R floor':<34}{max(S - R, 0):>8}   (vacuous here)")
    print(f"    {'commodities cross-hauled':<34}{hauled:>8} of {S}")
    print(f"    {'regions importing the least-imported':<34}{importing.min():>8}")

    check("the identity that generates the floor still holds cell by cell",
          all(importing[i] == R - int((argmax == i).sum()) for i in range(S)),
          "regions importing i = R minus the regions where i is the SLQ-argmax, "
          "which is what the floor was derived from in the first place")

    check("and at 272 regions the floor saturates rather than weakening",
          hauled == S,
          f"all {S} commodities are cross-hauled, the least-imported still "
          f"imported by {importing.min()} of {R} regions. S - R stops binding "
          f"because everything is above it, not because the effect goes away — "
          f"which is the opposite of what a vacuous bound usually means")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
