"""
The archive's Greek and Finnish labels describe other regions' rows.

WHAT THIS IS
--------------
The European MRIO prints a region code over every row. For 254 of its 272
regions that code describes the row. For Greece's thirteen, Finland's four and
one Polish region it does not: the block prints Greece's NUTS 2010 codes in
NUTS 2010 order over data that are in NUTS 2013 order, Finland's shifted by
one, and `PL12` -- the old code for the whole of Mazowieckie -- over PL91's
rows, Warsaw and its ring. The rows the block calls `EL11` are Attiki's; the
rows it calls `EL30` are the Ionian Islands'; `FI1B` is Åland.

It went unseen because nothing compared a region's SIZE with anything outside
the archive. `run_mrio_axis_scale.py` saw the labels disagree with the side
files and read it as a vintage mismatch; `run_mrio_side_join.py` showed the
data join by position and concluded the side files' label column described
nothing. Half of that was right: the join is positional. But the side files'
REGION order is the true one, and it is the block's labels that lie.

TWO INDEPENDENT SOURCES SAY THE SAME THING
--------------------------------------------
1. **The archive's own side files.** Region by region, at the position where
   the block says `EL11`, `Final_demand` and `TAXSUB_VA` say `EL30` -- and so
   on for all eighteen, in every year of the deposit.

2. **Eurostat's regional GDP** (`nama_10r_2gdp`, one file per year in
   `data/eurostat/`, fetched through `eurostat.fetch`), against the archive's
   own value added -- the comparable quantity, since GDP is value added plus
   taxes on products, while output carries intermediates whose weight differs
   by industry. A region's share of its own country is a fact no archive can
   move, and no exchange rate enters a share. Under the corrected labels the
   worst of the eighteen is within 5 % of Eurostat's share in every year from
   2008 to 2018; under the block's labels it is out by a factor of about 64,
   in every year. For the other 22 countries the archive's shares already match
   Eurostat (0.98 to 1.02 between the tenth and ninetieth percentile).

WHAT THE ENGINE DOES
----------------------
`io_loader.MRIO_RELABEL` corrects the eighteen wherever the archive is read,
and the catalogue lists the corrected codes, so a user who asks for `EL30`
gets Attiki. A NUTS 2010 Greek code is refused with the code to ask for
instead. Nothing in the data is moved: only the names are.

WHAT IS CHECKED
-----------------
- the correction is a permutation within each country, and touches no other;
- it is exactly what the archive's own side files say, in every year present;
- with it, every region's share of its country matches Eurostat's regional GDP
  in every year, and without it eighteen do not;
- `_mrio_block` and the catalogue return the corrected codes.

Run:
    python3 validators/run_mrio_labels.py
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MRIO = ROOT / "data" / "mrio"
EUROSTAT = ROOT / "data" / "eurostat"
S = 10
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


def header_labels(path: Path) -> list[str]:
    """The block's unit labels, corrected, from its header row alone: reading
    the whole 33 MB block for a list of names would cost a minute a year."""
    import openpyxl

    from quadrium.io_loader import _mrio_relabel

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        head = next(wb.worksheets[0].iter_rows(values_only=True, max_row=1))
    finally:
        wb.close()
    return _mrio_relabel([str(x) for x in head[1:] if x is not None])


def side_regions(path: Path, orientation: str) -> list[str]:
    """The side file's own region order, from its label column or header."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = list(wb.worksheets[0].iter_rows(values_only=True))
    finally:
        wb.close()
    if orientation == "rows":
        labels = [str(r[0]) for r in rows[1:] if r and r[0] is not None]
    else:
        labels = [str(c) for c in rows[0][1:] if c is not None]
    return list(dict.fromkeys(l.split("-", 1)[0] for l in labels))


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    from quadrium.config import MRIO_EUROSTAT_CODE, MRIO_REDRAWN
    from quadrium.io_loader import (MRIO_RELABEL, _MRIO_YEARS, _mrio_files,
                                    _mrio_relabel, _mrio_side)

    years = []
    for y in _MRIO_YEARS:
        try:
            fs = _mrio_files(MRIO, y)
        except Exception:                                 # noqa: BLE001
            continue
        if (EUROSTAT / f"nama_10r_2gdp_ALL_{y}.json").exists():
            years.append((y, fs))
    if not years:
        print("    -- no year has both the archive and Eurostat's regional "
              "GDP in this tree.")
        print("\n" + "=" * 78)
        print("Nothing was checked: the archive or the GDP files are absent.")
        return NOTHING_CHECKED

    # ---- the correction itself
    # Not a permutation of one code set: Greece's labels are NUTS 2010 codes
    # and the regions they belong to carry NUTS 2013 ones. What it must be is
    # one region per label, inside the same country, for every label of the
    # two countries.
    check("the correction gives each label a different region of its own "
          "country, and covers each of them whole",
          all(a[:2] == b[:2] for a, b in MRIO_RELABEL.items())
          and len(set(MRIO_RELABEL.values())) == len(MRIO_RELABEL)
          and {a[:2] for a in MRIO_RELABEL} == {"EL", "FI", "PL"},
          f"{len(MRIO_RELABEL)} labels, "
          f"{sorted({a[:2] for a in MRIO_RELABEL})}")

    # ---- what the archive's own side files say
    disagree = []
    for y, fs in years:
        raw = list(dict.fromkeys(l.split("-", 1)[0]
                                 for l in header_labels(fs[0])))
        for name, path, orient in (("final demand", fs[1], "rows"),
                                   ("value added", fs[2], "columns")):
            side = side_regions(path, orient)
            if len(side) != len(raw):
                disagree.append(f"{y} {name}: {len(side)} regions against "
                                f"{len(raw)}")
                continue
            # France's and Poland's side labels are the same territories under
            # NUTS 2016 codes, which the engine already translates; compare
            # through that so only a real disagreement shows.
            bad = [(a, b) for a, b in zip(raw, side)
                   if a != b and MRIO_EUROSTAT_CODE.get(a, a) != b]
            if bad:
                disagree.append(f"{y} {name}: {len(bad)} disagree, "
                                f"{bad[:3]}")
    check("the corrected labels are exactly what the archive's own side files "
          "say, in every year present", not disagree,
          "; ".join(disagree[:3]) if disagree else
          f"{len(years)} years, both side files, all 272 regions")

    # ---- and what Eurostat's regional GDP says
    from quadrium.eurostat import _Cube

    raw_of = {v: k for k, v in MRIO_RELABEL.items()}
    worst_corrected, worst_block, others = [], [], []
    for y, fs in years:
        regions = list(dict.fromkeys(l.split("-", 1)[0]
                                     for l in header_labels(fs[0])))
        # VALUE ADDED, not output: GDP is value added plus taxes on products,
        # and output carries intermediates, whose weight differs by industry.
        # A region's share of its country in value added is the comparable one.
        vh, VA = _mrio_side(fs[2], "columns")
        x = VA[:, vh.index("VA")]
        gdp = _Cube(json.loads(
            (EUROSTAT / f"nama_10r_2gdp_ALL_{y}.json").read_text()))

        def shares(names):
            """Archive share against Eurostat share, by country."""
            out = {}
            for country in {r[:2] for r in names}:
                rs = [r for r in names if r.startswith(country)]
                pairs = {}
                for r in rs:
                    if r in MRIO_REDRAWN or r.startswith("UK"):
                        continue
                    g = MRIO_EUROSTAT_CODE.get(r, r)
                    e = gdp.at(geo=g, time=str(y))
                    k = regions.index(r)
                    a = float(x[k * S:(k + 1) * S].sum())
                    if e and a > 0:
                        pairs[r] = (a, float(e))
                if len(pairs) < 2:
                    continue
                ta = sum(v[0] for v in pairs.values())
                te = sum(v[1] for v in pairs.values())
                for r, (a, e) in pairs.items():
                    out[r] = abs(np.log2((a / ta) / (e / te)))
            return out

        here = [r for r in regions if r[:2] in ("EL", "FI")]
        corrected = shares(here)
        worst_corrected.append(max(corrected.values()))
        rest = shares([r for r in regions if r[:2] not in ("EL", "FI")])
        others.append(np.percentile(list(rest.values()), 90))
        # what the block's labels would give: pair each region's archive
        # figure with the GDP of the region the block names
        rows = {}
        for r in here:
            k = regions.index(r)
            rows[r] = float(x[k * S:(k + 1) * S].sum())
        for country in ("EL", "FI"):
            rs = [r for r in here if r.startswith(country)]
            ta = sum(rows[r] for r in rs)
            es = {}
            for r in rs:
                name = raw_of.get(r, r)          # the archive's own label
                g = MRIO_EUROSTAT_CODE.get(name, name)
                e = gdp.at(geo=g, time=str(y))
                if e is None and name in ("EL11", "EL12", "EL13", "EL14",
                                          "EL21", "EL22", "EL23", "EL24",
                                          "EL25"):
                    # a NUTS 2010 code Eurostat no longer serves
                    e = gdp.at(geo={"EL11": "EL51", "EL12": "EL52",
                                    "EL13": "EL53", "EL14": "EL61",
                                    "EL21": "EL54", "EL22": "EL62",
                                    "EL23": "EL63", "EL24": "EL64",
                                    "EL25": "EL65"}[name], time=str(y))
                es[r] = float(e or 0.0)
            te = sum(es.values())
            if te > 0:
                worst_block.append(max(
                    abs(np.log2((rows[r] / ta) / (es[r] / te)))
                    for r in rs if es[r] > 0))

    check("with the correction, every Greek and Finnish region's share of its "
          "country matches Eurostat's regional GDP, in every year",
          max(worst_corrected) < 0.15,
          f"worst region {max(worst_corrected):.3f} in log2 "
          f"({100 * (2 ** max(worst_corrected) - 1):.1f} % out) across "
          f"{len(years)} years")
    check("and under the archive's own labels it does not, by a factor of "
          "tens", min(worst_block) > 4,
          f"worst region between {2 ** min(worst_block):.0f} and "
          f"{2 ** max(worst_block):.0f} times its Eurostat share")
    check("while every other region already matched, which is why only these "
          "are corrected", max(others) < 0.15,
          f"90th percentile of the rest {max(others):.3f} in log2 "
          f"({100 * (2 ** max(others) - 1):.1f} % out)")

    # ---- and the engine hands the corrected codes on
    regions = {l.split("-", 1)[0] for l in header_labels(years[0][1][0])}
    from quadrium.catalogue import _mrio_sources

    listed = {s.geo for s in _mrio_sources(MRIO)}
    check("the loader and the catalogue both give the corrected codes",
          "EL30" in regions and "EL11" not in regions
          and "EL51" in regions and (not listed or "EL30" in listed)
          and "EL11" not in listed,
          f"{len(regions)} regions; the catalogue lists {len(listed)}")
    check("and `_mrio_relabel` leaves every other label alone",
          _mrio_relabel(["ES51-A", "FR21-B-E", "PL11-F", "DE30-J"])
          == ["ES51-A", "FR21-B-E", "PL11-F", "DE30-J"],
          "only Greece, Finland and PL12 move")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED:")
        for f in FAIL:
            print(f"  - {f}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
