"""
Which regions of the European MRIO get Eurostat's employment, and under which
code.

WHY
-----
`mrio_employment` fetches Eurostat's regional employment for a region of the
archive. Measured on 2026-09-11 against Eurostat's 2018 release, 194 of the
archive's 268 regions with data are there under the code the archive uses, and
74 are not. The archive's codes are not one NUTS vintage but four -- Greece
NUTS 2010, France and Poland NUTS 2013 (`run_mrio_nuts_join.py`), Hungary,
Ireland and Lithuania NUTS 2016, Croatia NUTS 2021 (HR02, HR05 and HR06 are
the 2021 split of HR04) -- and Eurostat serves NUTS 2024.

Eurostat publishes a correspondence table for every revision, and each one
says what happened to each code. Where every step is a new code for the SAME
territory, the engine fetches the current code and says so: 26 regions, 21
French and 5 Polish. Greece needs no translation: nineteen of the archive's
labels name another region altogether, and `run_mrio_labels.py` corrects them
before anything is fetched, which leaves Greece on the codes Eurostat serves
and turns the archive's `PL12` into PL91. Where a border moved, the engine
refuses: NL31, NL33, PT16, PT17 and PT18, redrawn in 2024. The United
Kingdom's 33 regions are not in the release at all, and no correspondence can
supply them. So 230 of the 268 get employment from Eurostat.

The engine holds the two lists as constants, `config.MRIO_EUROSTAT_CODE` and
`config.MRIO_REDRAWN`, and never reads these tables at run time. This file
rebuilds both from the published tables and fails if they disagree.

WHAT IS CHECKED
-----------------
- every translated code is reached through new codes for the same territory
  and nothing else, and lands on a code the 2018 release carries;
- every refused region was split or had its border moved, by the tables' own
  account, and its old code carries nothing in the release;
- the release carries no region of the United Kingdom;
- with the archive present, its 268 regions add up: 204 + 26 + 33 + 5.

WHAT IT CANNOT CHECK EVERYWHERE, AND SAYS
-------------------------------------------
The 2010-to-2013 table is `.xls`, read with `xlrd`: a checking dependency and
not an engine one, as in `run_mrio_nuts_join.py`. Without it the Greek codes
are followed from NUTS 2013 on and their 2010 step is not read, and the run
says so rather than passing it. ITH5 had a boundary shift with ITI3 in 2024
that Eurostat records as no NUTS amendment (art. 5(2a) of Regulation
1059/2003); both keep their code and their figures, and the run lists the
change rather than refusing it.

Run:
    python3 validators/run_mrio_eurostat_codes.py
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
NUTS = ROOT / "data" / "nuts"
T1013 = NUTS / "NUTS2010-NUTS2013.xls"
T1316 = NUTS / "NUTS2013-NUTS2016.xlsx"
T1621 = NUTS / "NUTS2021.xlsx"
T2124 = NUTS / "NUTS2021-NUTS2024.xlsx"
RELEASE = ROOT / "data" / "eurostat" / "nama_10r_3empers_ALL_2018.json"
MRIO = ROOT / "data" / "mrio"
FAIL: list[str] = []

# What the tables call a new code for the same territory. Anything else -- a
# boundary shift, a split, a merge -- moves people and output from one region
# to another, and one region's employment over another's output is a
# multiplier of neither.
SAME_TERRITORY = ("recoded", "recoded and relabelled", "code change")

# Exit code 3, not 0. `check.sh` counts it as SKIPPED rather than as a pass:
# this validator opened no file and measured nothing, and a run that says
# "All checks passed" on evidence it never saw is the fault the suite exists
# to catch. It is not a failure -- a tree without the workbook still exits 0.
NOTHING_CHECKED = 3


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def _s(v) -> str:
    return str(v if v is not None else "").strip()


def _xlsx(path, sheet, a, b, ch, header):
    import openpyxl

    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)[sheet]
    rows = [tuple(r) for r in ws.iter_rows(values_only=True)]
    col, text = header
    start = next(i for i, r in enumerate(rows)
                 if len(r) > col and _s(r[col]) == text) + 1
    return [(_s(r[a]), _s(r[b]), _s(r[ch])) for r in rows[start:]
            if len(r) > max(a, b, ch)]


def _xls(path, sheet, a, b, ch):
    try:
        import xlrd
    except ImportError:
        return None
    sh = xlrd.open_workbook(str(path)).sheet_by_name(sheet)
    return [(_s(sh.cell_value(i, a)), _s(sh.cell_value(i, b)),
             _s(sh.cell_value(i, ch))) for i in range(1, sh.nrows)]


def revision(name, main, corr):
    """One revision: the NUTS-2 codes it kept as they were, and what it did to
    the others, from its full listing and its NUTS-2 change sheet."""
    same = {a for a, b, ch in main if len(a) == 4 and a == b and not ch}
    changes = {a: (b, ch) for a, b, ch in corr
               if len(a) == 4 and (ch or b != a)}
    return name, same, changes


def walk(code, revisions):
    """Follow one code through the revisions: (final code, verdict, trail)."""
    trail = []
    for name, same, changes in revisions:
        if code in changes:
            new, ch = changes[code]
            if new and new != code and ch.lower() in SAME_TERRITORY:
                trail.append(f"{code}->{new} in {name} ({ch})")
                code = new
                continue
            if new == code and ch.lower().startswith("name change"):
                continue
            return code, "redrawn", trail + [f"{name}: {ch or 'listed as changed'}"]
        if code in same:
            continue
        return code, "not listed", trail + [f"{name}: not listed"]
    return code, "same territory", trail


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    need = (T1316, T1621, T2124, RELEASE)
    absent = [p.name for p in need if not p.exists()]
    if absent:
        print(f"    -- {', '.join(absent)} absent from this tree.")
        print("\n" + "=" * 78)
        print("Nothing was checked: the correspondence tables or the kept "
              "release are not here.")
        return NOTHING_CHECKED

    try:
        from quadrium.config import MRIO_EUROSTAT_CODE, MRIO_REDRAWN
    except ImportError as exc:
        check("the engine holds its two lists of codes", False, str(exc))
        print(f"\n{len(FAIL)} check(s) FAILED.")
        return 1

    later = [
        revision("NUTS 2016",
                 _xlsx(T1316, "NUTS2013-NUTS2016", 1, 2, 7, (1, "Code 2013")),
                 _xlsx(T1316, "Correspondence NUTS-2", 0, 1, 3,
                       (0, "Code 2013"))),
        revision("NUTS 2021",
                 _xlsx(T1621, "Changes detailed NUTS 2016-2021", 0, 1, 6,
                       (0, "Code 2016")),
                 _xlsx(T1621, "Changes NUTS-2", 0, 1, 3, (0, "Code 2016"))),
        revision("NUTS 2024",
                 _xlsx(T2124, "NUTS2021- NUTS2024", 2, 3, 7, (2, "Code 2021")),
                 _xlsx(T2124, "Changes NUTS-2", 1, 2, 4, (1, "Code 2021"))),
    ]
    main1013 = _xls(T1013, "NUTS2010-NUTS2013", 1, 2, 7) if T1013.exists() \
        else None
    corr1013 = _xls(T1013, "Correspondence NUTS-2", 0, 1, 3) \
        if main1013 is not None else None
    first = (revision("NUTS 2013", main1013, corr1013)
             if main1013 is not None else None)

    from quadrium.eurostat import _Cube

    cube = _Cube(json.loads(RELEASE.read_text()))
    have = {g for g in cube.index["geo"] if len(g) == 4
            and cube.at(nace_r2="TOTAL", geo=g, time="2018") is not None}

    # ---- the translated codes
    wrong, greek_unread = [], []
    for region, geo in sorted(MRIO_EUROSTAT_CODE.items()):
        if region.startswith("EL") and first is None:
            greek_unread.append(region)
            final, verdict, trail = walk(geo, later)
        elif region.startswith("EL"):
            final, verdict, trail = walk(region, [first] + later)
        else:
            final, verdict, trail = walk(region, later)
        if final != geo or verdict != "same territory":
            wrong.append(f"{region}: {verdict}, ends at {final}; "
                         f"{' | '.join(trail)}")
    from collections import Counter
    by_country = Counter(r[:2] for r in MRIO_EUROSTAT_CODE)
    check("every translated code is reached through new codes for the same "
          "territory, and nothing else", not wrong,
          "; ".join(wrong[:3]) if wrong else
          f"{len(MRIO_EUROSTAT_CODE)} codes: "
          + ", ".join(f"{n} {c}" for c, n in sorted(by_country.items()))
          + (f". The NUTS 2010 step of {len(greek_unread)} Greek codes was not "
             f"read here: xlrd is absent from this interpreter, so they were "
             f"followed from their NUTS 2013 code on" if greek_unread else ""))
    missing = sorted(g for g in MRIO_EUROSTAT_CODE.values() if g not in have)
    check("and each lands on a code the 2018 release carries", not missing,
          f"absent: {missing}" if missing else
          "so the figure Eurostat publishes is for the archive's own territory")

    # ---- the refused regions
    not_redrawn = []
    for region in sorted(MRIO_REDRAWN):
        final, verdict, trail = walk(region, later)
        if verdict != "redrawn":
            not_redrawn.append(f"{region}: {verdict}")
    check("every refused region was split or had its border moved, by the "
          "tables' own account", not not_redrawn,
          "; ".join(not_redrawn) if not_redrawn else
          f"{', '.join(sorted(MRIO_REDRAWN))}")
    served = sorted(r for r in MRIO_REDRAWN if r in have)
    check("and under its old code the release carries nothing", not served,
          f"carried: {served}" if served else
          "so there is no figure under that code for the engine to take")

    uk = sorted(g for g in have if g.startswith("UK"))
    check("the release carries no region of the United Kingdom, so no "
          "correspondence can supply one", not uk,
          f"carried: {uk}" if uk else
          f"{len(have)} NUTS-2 codes in the release, none British")

    # ---- the archive's regions, where the archive is here
    try:
        from quadrium.catalogue import _mrio_sources
        codes = sorted(s.source_id.split(":")[-1]
                       for s in _mrio_sources(MRIO)
                       if s.source_id.startswith("mrio:eu2018:"))
    except Exception:                                     # noqa: BLE001
        codes = []
    if not codes:
        print("\n    -- the 2018 archive is absent, so its regions were not "
              "counted; the lists above stand on the tables alone.")
    else:
        own = [c for c in codes if c in have and c not in MRIO_EUROSTAT_CODE]
        translated = [c for c in codes if c in MRIO_EUROSTAT_CODE]
        british = [c for c in codes if c.startswith("UK")]
        redrawn = [c for c in codes if c in MRIO_REDRAWN]
        stray = sorted(set(codes) - set(own) - set(translated)
                       - set(british) - set(redrawn))
        check("every region of the archive is in exactly one class, and none "
              "is left unexplained",
              not stray and len(own) + len(translated) + len(british)
              + len(redrawn) == len(codes),
              f"unexplained: {stray}" if stray else
              f"{len(own)} under their own code, {len(translated)} "
              f"translated, {len(british)} British, {len(redrawn)} redrawn: "
              f"{len(codes)}")
        check("which is 230 of 268 with employment from Eurostat, as the guide "
              "says",
              (len(own), len(translated), len(british), len(redrawn),
               len(codes)) == (204, 26, 33, 5, 268),
              f"{len(own) + len(translated)} of {len(codes)}")
        shifted = []
        for c in own:
            final, verdict, trail = walk(c, later)
            if verdict == "redrawn":
                shifted.append(f"{c} ({trail[-1]})")
        print(f"\n    Taken under their own code although the 2024 table "
              f"lists a change: {'; '.join(shifted) or 'none'}.")

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
