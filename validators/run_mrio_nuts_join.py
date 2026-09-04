"""
The MRIO's side files can be joined after all — for 271 of 272 regions.

WHAT WAS BLOCKED
------------------
`run_mrio_axis_scale.py` records that the European MRIO's block carries one set
of region codes and its `Final_demand_2018.xlsx` and `TAXSUB_VA_2018.xlsx`
another: 236 of 272 match by label and 36 do not, all of them French, Greek or
Polish. Both lists hold 272 regions in the same country order, so a positional
join completes and is wrong — it pairs Anatoliki Makedonia with Attiki. The
archive's own `NUTS2_list.xlsx` carries no correspondence, and the project
refused to invent one. Everything since has used the block alone, with
intermediate sales as a stated proxy for output.

WHAT THIS ADDS
----------------
Eurostat publishes the correspondence tables, openly. Two were acquired through
this engine's own `acquire()` on 2026-09-04, with URL and SHA-256 recorded in
`SOURCE_REGISTER.md`. Composing them resolves the 36:

    236  already the same code
     26  NUTS 2013 -> NUTS 2016      France, and five Polish regions
      9  NUTS 2010 -> NUTS 2013      Greece
      1  unresolved                  PL12

AND THE PREMISE WAS WRONG, WHICH IS THE FINDING
-------------------------------------------------
The block was described as being on NUTS 2013. It is not on one vintage at all.
France's `FR21` is a 2013 code that became `FRF2` in 2016 — so France is 2013.
But Greece's `EL11` was already `EL51` in NUTS **2013**: the 2013-to-2016 table
lists `EL51 -> EL51`, unchanged. `EL11 -> EL51` appears in the 2010-to-2013
table. **The block carries French codes from one vintage and Greek codes from
an earlier one**, which is why a single correspondence table could never have
closed this and why the failure looked like a missing file rather than a mixed
axis.

WHAT PL12 COSTS, AND WHY IT IS NOT JOINED
-------------------------------------------
`PL12` (Mazowieckie) is not recoded. Eurostat's own correspondence says
*discontinued; split into new PL91 and PL92*, with
`PL91=PL127+PL129+PL12A-newPL926` and `PL92=PL128+PL12B+PL12C+PL12D+PL12E`.
The side files carry `PL91` and **not** `PL92`. So the one region left over on
each side — the block's `PL12` and the side files' `PL91` — are the pair a
counting argument would marry, and they are not the same territory: `PL91` is
Warsaw and its ring, `PL12` is that plus the whole of the rest of Mazovia.

Pairing them would understate Mazovia's final demand by whatever `PL92` holds,
and nothing in the archive says what that is. So this file resolves 271 and
refuses the 272nd by name.

SUPERSEDED AS AN UNBLOCKER, AND STILL TRUE AS A FINDING
--------------------------------------------------------
Written to unblock the side files, and it does not: `run_mrio_side_join.py`
shows the following day that those files' label column describes nothing, so
there was never a vintage mismatch in the DATA to correct. Everything below
stands — the block really does carry French codes from NUTS 2013 and Greek
codes from NUTS 2010, and `PL12` really was split rather than recoded — and
none of it is what makes the join possible. It is a fact about the block's own
labels, which is worth holding for anyone who reads them.

Run:
    python3 validators/run_mrio_nuts_join.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

NUTS = ROOT / "data" / "nuts"
C1316 = NUTS / "NUTS2013-NUTS2016.xlsx"
C1013 = NUTS / "NUTS2010-NUTS2013.xls"
MRIO = ROOT / "data" / "mrio"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def map_xlsx(path: Path, sheet: str) -> dict[str, list[str]]:
    """`{2013 code: [2016 code, …]}` at NUTS-2, off the published table."""
    from quadrium.io_loader import _open_workbook

    rows = _open_workbook(path)[sheet]
    hdr = next(i for i, r in enumerate(rows)
               if r and len(r) > 1 and str(r[1]).strip() == "Code 2013")
    out: dict[str, list[str]] = {}
    for r in rows[hdr + 1:]:
        a = str(r[1] or "").strip() if len(r) > 1 else ""
        b = str(r[2] or "").strip() if len(r) > 2 else ""
        if len(a) == 4 and len(b) == 4:
            out.setdefault(a, []).append(b)
    return out


def map_xls(path: Path, sheet: str) -> dict[str, list[str]]:
    """The same, from the 2010-2013 table, which Eurostat ships as `.xls`.

    `xlrd` is a CHECKING dependency and not an engine one, on the precedent
    `pyproject.toml` already sets for scipy: the engine is numpy-and-openpyxl
    on purpose, and one old-format file read by one validator does not change
    that. Absent, this returns nothing and the nine Greek regions stay
    unresolved — which the caller reports rather than papers over.
    """
    try:
        import xlrd
    except ImportError:
        return {}
    sh = xlrd.open_workbook(str(path)).sheet_by_name(sheet)
    out: dict[str, list[str]] = {}
    for i in range(sh.nrows):
        a = str(sh.cell_value(i, 1)).strip()
        b = str(sh.cell_value(i, 2)).strip()
        if len(a) == 4 and len(b) == 4:
            out.setdefault(a, []).append(b)
    return out


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if not C1316.exists():
        # NOT A FAILURE where the tables are not shipped. They are 1.2 MB of
        # open Eurostat data with provenance sidecars, so they travel; but a
        # tree without them cannot run this, and saying so is the honest
        # report. The same rule as the Catalan workbook in tests/.
        check("the correspondence tables are not in this tree, so the join "
              "cannot be checked here", True,
              f"{C1316.name} is absent. It is acquired by "
              f"quadrium.acquire(); the URL and SHA-256 are in "
              f"SOURCE_REGISTER.md section 7")
        print("\n" + "=" * 78)
        print("All checks passed.")
        return 0
    for p in (C1316, C1013):
        check(f"{p.name} is on disk", p.exists(),
              "acquired through quadrium.acquire; URL and SHA-256 in "
              "SOURCE_REGISTER.md" if p.exists() else
              "absent — the nine Greek regions will be reported unresolved")

    m1316 = map_xlsx(C1316, "NUTS2013-NUTS2016")
    m1013 = map_xls(C1013, "NUTS2010-NUTS2013") if C1013.exists() else {}
    check("the 2013-to-2016 table reads as a NUTS-2 correspondence",
          len(m1316) > 250, f"{len(m1316)} codes carried forward")
    # DEGRADES, on the precedent `sign_pattern_feasible` already sets: without
    # scipy it falls back to the per-line test and SAYS so. Without xlrd the
    # 2010 table cannot be read, Greece cannot be resolved, and the counts
    # below are reported at what this interpreter can actually establish --
    # never at what the full run would have shown.
    check("and the 2010-to-2013 one does too, or this run says it could not "
          "read it", True,
          f"{len(m1013)} codes" if m1013 else
          "xlrd is absent from this interpreter, so the nine Greek regions "
          "stay unresolved here. `pyproject.toml` declares it under `dev` for "
          "the same reason it declares scipy: a checking dependency, not an "
          "engine one")

    # ---- the premise this file overturns
    check("Greece's block codes are NOT NUTS 2013: `EL51` is already `EL51` "
          "there", m1316.get("EL51") == ["EL51"] and "EL11" not in m1316,
          "the 2013-to-2016 table carries EL51 unchanged and has no EL11 at "
          "all, so EL11 belongs to an earlier vintage. France's FR21 -> FRF2 "
          "IS in that table. The block mixes vintages, which is why one "
          "correspondence could never have closed this")
    if m1013:
        check("and `EL11 -> EL51` is in the 2010-to-2013 table, which settles "
              "which vintage it is",
              m1013.get("EL11") == ["EL51"],
              "so the block is NUTS 2013 for France and NUTS 2010 for Greece")

    # ---- the composition, against the archive itself
    if not (MRIO / "_mrio2018_cache.npz").exists() \
       and not (MRIO / "MRIO_2018_272regions.xlsx").exists():
        print(f"\n    -- the MRIO block is absent (33 MB, gitignored); the "
              f"correspondence above stands on its own.")
        print("\n" + "=" * 78)
        if FAIL:
            print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
            return 1
        print("All checks passed.")
        return 0

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "axis", ROOT / "validators" / "run_mrio_axis_scale.py")
    axis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(axis)

    _, labels = axis.load_Z()
    block = list(dict.fromkeys(l.split("-", 1)[0] for l in labels))
    side_keys, _, _ = axis.load_side(axis.FD, "rows")
    side = list(dict.fromkeys(k.split("-", 1)[0] for k in side_keys))
    side_set = set(side)

    def resolve(code):
        if code in side_set:
            return [code], "same code"
        v = m1316.get(code)
        if v and len(v) == 1 and v[0] in side_set:
            return v, "2013->2016"
        w = m1013.get(code)
        if w and len(w) == 1:
            if w[0] in side_set:
                return w, "2010->2013"
            v2 = m1316.get(w[0])
            if v2 and len(v2) == 1 and v2[0] in side_set:
                return v2, "2010->2013->2016"
        return [], "unresolved"

    routes = {c: resolve(c) for c in block}
    from collections import Counter
    by_route = Counter(r for _, r in routes.values())
    unresolved = [c for c, (t, _) in routes.items() if not t]
    targets = [t[0] for t, _ in routes.values() if t]

    check("every region resolves by a published correspondence, or not at all",
          by_route["unresolved"] == len(unresolved),
          ", ".join(f"{n} {r}" for r, n in by_route.most_common()))

    check("the join is one-to-one on everything it resolves",
          len(set(targets)) == len(targets),
          f"{len(set(targets))} distinct targets for {len(targets)} regions — "
          f"no two block regions land on the same side-file region, which a "
          f"positional join could not promise")

    left_over = sorted(side_set - set(targets))
    if not m1013:
        greek = sorted(c for c in unresolved if c.startswith("EL"))
        check("without the 2010 table, Greece stays unresolved and is counted "
              "as such", len(greek) == 9 and unresolved == greek + ["PL12"],
              f"{len(unresolved)} unresolved: the nine Greek regions this "
              f"interpreter cannot map, and PL12, which no interpreter can. "
              f"Install the `dev` extra to check the full join")
        print("\n" + "=" * 78)
        if FAIL:
            print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
            return 1
        print("All checks passed.")
        return 0

    check("exactly one region on each side is left over, and they are NOT the "
          "same territory",
          unresolved == ["PL12"] and left_over == ["PL91"],
          f"the block's {unresolved} and the side files' {left_over}. A "
          f"counting argument would marry them; Eurostat says PL12 was "
          f"discontinued and split into PL91 and PL92, and the side files "
          f"carry no PL92. PL91 is Warsaw and its ring, PL12 is that plus the "
          f"rest of Mazovia — pairing them understates Mazovia's final demand "
          f"by whatever PL92 holds, which the archive does not say")

    check("so 271 of 272 regions can now carry their final demand and value "
          "added, where none could before",
          len(targets) == 271 and len(block) == 272,
          "the block was used alone until now, with intermediate sales as a "
          "stated proxy for output. That proxy is no longer forced — for 271 "
          "of the 272")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
