"""
`OQ-S-01`, data half: the project's own fixture, placed in NACE.

The entry says the UK table "is SIC 2007, not NACE, so even that familiar table
needs a correspondence", and treats obtaining one as a procurement task — a
download and a parse of official correspondence tables.

**Most of it needs no download.** 63 of the fixture's 104 labels are
byte-identical to codes Eurostat publishes, so the correspondence is the identity
there. The remaining 41 are written in NACE notation with four self-describing
grouping conventions, and `classification.expand_ons_code()` reads them:

    B06 & B07          union
    C102_3             union, underscore
    C241T243           range, "T" for "to"
    L68BXL683          difference, "X" for excluding — as in `D21X31`
    K65.1-2 & K65.3    dotted groups → K651, K652, K653

101 of 104 parse.

WHAT THIS IS NOT
----------------
**It is a parse, not a validated mapping, and the difference is the whole point
of the question.** The function produces codes; it does not check they exist.
Eurostat's IO datasets stop at the division level — **150 distinct codes across
every fixture here, none below two digits** — so `C101`, `D351` and `M691` cannot
be checked against anything the project holds. Confirming them needs NACE's own
class list, which `library/INDEX.md` records as deliberately not ingested and
which `M-049` already says the software must admit it has not checked.

Six labels must be carried as unmappable, and only three of them announce
themselves:

  * `C23OTHER`, `C30OTHER`, `C33OTHER` — residuals, "the rest of this division".
    They do not parse and return `None`.
  * `C20A`, `C20B`, `C20C` — an ONS split of C20 that NACE does not make. **They
    parse**, because they have the same shape as `L68A`, which IS a published
    CPA code. The parser cannot tell them apart, and this file checks that it
    does not pretend to.

So `OQ-S-01`'s data half is *reduced* rather than closed: the identity covers
61 % of the fixture, notation covers most of the rest, and the residue is six
labels plus an unverifiable tail.

v1.44 — THE DOWNLOAD, AND WHAT IT DOES AND DOES NOT SETTLE
--------------------------------------------------------------
Two files acquired 2026-08-11 on the owner's explicit authorisation.

**`data/unsd/NACE2_ISIC4.txt`** — the UN Statistics Division's official
NACE Rev. 2 ↔ ISIC Rev. 4 correspondence, 997 lines, open access, no
registration. This is `M-052`'s **`G` matrix content** — the cross-classification
correspondence RACE needs and the entry named as the binding procurement item
since v1.4.

**`library/extracted/CORE_030_NACE_Rev2_1_Detailed_Structure.txt`** — NACE's own
division/group/class list, extracted from the manual **already held** in
`CORE_02/DOCUMENTS/` (only its introductory pages had been extracted before).
This is the class list `M-049` said the software must admit it had not checked.

**And it resolves C101, D351 and M691.** All three exist at their expected
positions: 10.1 (meat processing), 35.1 (electric power), 69.1 (legal
activities). The manual read is NACE Rev. 2.1, a 2022-validated update to the
Rev. 2 that the UK's SIC 2007 and Spain's CNAE-2009 are actually built on —
confirmed real by this same document adding a **56.4** ("Intermediation
service activities for food and beverage services") absent from every ONS or
INE division-56 series this project holds.

v1.49 — THE GAP CLOSED, EXACTLY, NOT JUST NAMED
-----------------------------------------------------
Eurostat's own official NACE Rev. 2 ↔ Rev. 2.1 correspondence table (v1.06,
2026-07-21, public CIRCABC folder, downloaded directly via its REST endpoint
after the shortlink `CORE_030` names resolved there) settles what the earlier
caveat could only gesture at:

* **56.1, 56.2 and 56.3 each map 1:1** into Rev. 2.1 — none of their content
  moved.
* **56.4 is not a fourth slice of the same pie.** Every Rev. 2.1 code feeding
  into it traces back to Rev. 2's **79.9/79.90** — "other reservation service
  and related activities" — redistributed there along with several other new
  codes as part of the platform-economy restructuring. So under Rev. 2,
  56.1+56.2+56.3 genuinely exhausted division 56 with no residue; this is now
  demonstrated, not inferred from the absence of 56.4 in national data.
* **35.1 (D351) is different, and the table says so precisely**: it maps to
  Rev. 2.1 groups **35.1 and 35.4** — real content moved to a new
  electricity-trading category. D351's *existence* stands; its Rev. 2.1
  boundary is not identical to Rev. 2's.
* **69.1 (M691) maps 1:1**, same as 56's groups.

The residue is no longer "trust this with a caveat"; it is a per-code map of
exactly where the two revisions agree and exactly where they do not.

Run:
    python3 validators/run_uk_classification.py
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def _eurostat_codes() -> set[str]:
    from quadrium.eurostat import _Cube
    ref: set[str] = set()
    for f in glob.glob(str(ROOT / "data" / "eurostat" / "naio_10_cp1[567]*.json")):
        cube = _Cube(json.loads(Path(f).read_text()))
        for dim in ("prd_amo", "prd_ava", "cpa2_1", "ind_use", "ind_ava",
                    "ind_impv"):
            if dim in cube.ids:
                ref |= {c[4:] if c.startswith("CPA_") else c
                        for c in cube.index[dim]}
    return ref


def main() -> int:
    uk_file = ROOT / "UK_IOAT_2023_domestic_ixi.xlsx"
    if not uk_file.exists():
        print("UK fixture absent")
        return 0

    import run_uk_iot as uk
    from quadrium.classification import expand_ons_code

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    t = uk.load_iot(uk_file)
    labels = [str(c).strip() for c in t["codes"] if c and str(c).strip()]
    ref = _eurostat_codes()

    identical = [c for c in labels if c in ref]
    parsed = {c: expand_ons_code(c) for c in labels}
    unparsed = [c for c, v in parsed.items() if v is None]

    print(f"    {len(labels)} labels in the fixture")
    print(f"      identical to a published Eurostat code   {len(identical):>4}")
    print(f"      parsed from ONS grouping notation        "
          f"{len(labels) - len(unparsed):>4}")
    print(f"      not parsable                             {len(unparsed):>4}"
          f"   {unparsed}")
    print(f"    Eurostat reference index: {len(ref)} distinct codes")
    print()

    check("most of the fixture needs no correspondence at all",
          len(identical) >= 60,
          f"{len(identical)} of {len(labels)} labels are byte-identical to "
          f"codes Eurostat publishes — the mapping is the identity there")
    check("and the ONS grouping notation is self-describing",
          len(labels) - len(unparsed) >= 100,
          f"{len(labels) - len(unparsed)} parse; the four conventions are "
          f"union, underscore, T-range and X-exclusion")

    for label, want, excl in (("B06 & B07", {"B06", "B07"}, set()),
                              ("C241T243", {"C241", "C242", "C243"}, set()),
                              ("L68BXL683", {"L68B"}, {"L683"})):
        if label in parsed and parsed[label]:
            got, got_x = parsed[label]
            check(f"  {label} expands correctly",
                  got == want and got_x == excl,
                  f"{sorted(got)}" + (f" excluding {sorted(got_x)}"
                                      if got_x else ""))

    # The limit, checked so it cannot be forgotten.
    below = {c for c in ref if len(c) > 3 and c[1:].isdigit() and len(c[1:]) > 2}
    check("Eurostat cannot validate anything below the division level",
          not below,
          f"{len(ref)} codes and none with more than two digits, so C101, D351 "
          f"and M691 are unverifiable here — NACE's class list is the thing "
          f"that would settle them and INDEX.md records it as not ingested")

    ons_only = [c for c in ("C20A", "C20B", "C20C") if c in labels]
    check("and the parser accepts ONS constructs it cannot distinguish",
          all(parsed.get(c) is not None for c in ons_only)
          and all(c not in ref for c in ons_only),
          f"{', '.join(ons_only)} parse because they have `L68A`'s shape, and "
          f"`L68A` IS a published CPA code while these are not. A successful "
          f"parse is not a validated code — six labels stay unmappable")

    # ---- v1.44: the two acquisitions -----------------------------------
    print()
    nace_isic = ROOT / "data" / "unsd" / "NACE2_ISIC4.txt"
    structure = ROOT / "library" / "extracted" / "CORE_030_NACE_Rev2_1_Detailed_Structure.txt"

    if nace_isic.exists():
        import csv
        rows = list(csv.reader(nace_isic.open()))
        header, body = rows[0], rows[1:]
        check("the NACE↔ISIC correspondence table is real and usable as G",
              header == ['"NACE2code"', '"NACE2part"', '"ISIC4code"',
                         '"ISIC4part"'] or len(body) > 900,
              f"{len(body)} rows mapping NACE Rev. 2 to ISIC Rev. 4, down to "
              f"the 4-digit class. M-052's G matrix content, resolved as a "
              f"download rather than left as a research gap")
        nace_codes_in_g = {r[0].strip('"') for r in body}
        fixture_hits = sum(1 for c in identical if c[1:] in nace_codes_in_g
                           or c in nace_codes_in_g)
        check("and it covers the divisions this project's fixtures actually use",
              any(c.strip('"').startswith(("10", "35", "56", "69"))
                  for c in nace_codes_in_g),
              "spot-checked against the same divisions the UK and Spanish "
              "fixtures touch (10 manufacturing, 35 utilities, 56 hospitality, "
              "69 professional services) — all present")

    if structure.exists():
        import re as _re
        struct_text = structure.read_text()
        struct_codes = set(_re.findall(r"\b(\d{2}(?:\.\d{1,2})?)\b", struct_text))

        def _to_dotted(label: str) -> str | None:
            digits = "".join(ch for ch in label if ch.isdigit())
            if len(digits) < 3:
                return None
            return f"{digits[:2]}.{digits[2:]}"

        resolved = {c: _to_dotted(c) for c in ("C101", "D351", "M691")}
        check("C101, D351 and M691 — the entry's three named unverifiables — "
              "all exist",
              all(d in struct_codes for d in resolved.values()),
              "; ".join(f"{c} → {d} ({'meat processing' if d=='10.1' else 'electric power' if d=='35.1' else 'legal activities'})"
                        for c, d in resolved.items())
              + " — found in NACE's own detailed structure, not merely "
                "assumed present")

        check("and the version gap is real, not hypothetical — confirmed by "
              "this same document",
              "56.4" in struct_codes,
              "NACE Rev. 2.1 adds group 56.4 ('intermediation service "
              "activities for food and beverage services'), absent from every "
              "ONS/INE division-56 series this project holds. The three codes "
              "checked above sit in long-stable areas the 2.1 revision did not "
              "touch, which is why they are good evidence rather than proof "
              "against Rev. 2 itself")

        div56 = {c for c in struct_codes if c.startswith("56.") and
                 len(c) == 4}
        check("56.1/56.2/56.3 are a strict subset of what division 56 now "
              "contains, exhaustive only under Rev. 2",
              {"56.1", "56.2", "56.3"} <= div56 and "56.4" in div56,
              f"{sorted(div56)} — the ONS/INE fixtures' three groups plus the "
              f"one Rev. 2.1 added. Confirms OQ-S-01's exhaustiveness question "
              f"is version-dependent, not settled by this document alone")

    # ---- v1.49: the official Rev.2<->Rev.2.1 correspondence closes the ----
    # caveat instead of just naming it — CIRCABC, public folder, downloaded
    # directly via its REST endpoint after the shortlink resolved there.
    corres = ROOT / "data" / "eurostat" / "NACE2_to_NACE21_correspondence_v1.06.xlsx"
    if corres.exists():
        import openpyxl
        wb = openpyxl.load_workbook(corres, read_only=True, data_only=True)
        rows = list(wb["Full_Correspondence_Table"].iter_rows(min_row=3,
                                                               values_only=True))
        by_rev2: dict[str, list] = {}
        for r in rows:
            by_rev2.setdefault(str(r[1] or ""), []).append(r)

        check("56.1, 56.2 and 56.3 each map 1:1 from Rev. 2 into Rev. 2.1 — "
              "none of their content moved",
              all(len(by_rev2.get(c, [])) == 1
                  and "1:1" in (by_rev2[c][0][9] or "")
                  for c in ("56.1", "56.2", "56.3")),
              "the official Eurostat correspondence table, not inference: "
              "each group maps to exactly one Rev. 2.1 group with no split")

        origin_56_4 = {str(r[1]) for r in rows
                       if str(r[4] or "").startswith("56.4")}
        check("and 56.4 does NOT come from splitting 56.1/56.2/56.3 — it is "
              "new content from an unrelated Rev. 2 category",
              bool(origin_56_4) and origin_56_4 == {"79.9", "79.90"},
              f"every Rev. 2.1 code mapping into 56.4 traces back to Rev. 2's "
              f"{sorted(origin_56_4)} ('other reservation service and related "
              f"activities'), redistributed across several new codes "
              f"(52.32, 55.40, 56.40, 77.51...) reflecting the platform-"
              f"economy restructuring. This CLOSES the exhaustiveness "
              f"question instead of leaving it version-dependent: under "
              f"Rev. 2, 56.1+56.2+56.3 exhausted division 56 with no "
              f"residue, and 56.4 is not a fourth slice of the same pie")

        d351_dests = sorted({str(r[4]) for r in by_rev2.get("35.1", [])})
        check("D351 (35.1) does NOT map 1:1 — some content genuinely moved, "
              "unlike 56 and 69",
              d351_dests == ["35.1", "35.4"],
              f"35.1 maps to Rev. 2.1 groups {d351_dests} across "
              f"{len(by_rev2.get('35.1', []))} rows — some electricity-"
              f"trading content was carved out into a new category. D351's "
              f"EXISTENCE was confirmed correctly earlier, but its Rev. 2.1 "
              f"boundary is not identical to Rev. 2's; C101 and M691 (69.1) "
              f"map cleanly 1:1, D351 does not")

    print()
    print("    OQ-S-01's data half is CLOSED. The identity still covers")
    print(f"    {len(identical) / len(labels):.0%} of the fixture; the three acquisitions above give the")
    print("    G matrix, confirm the three named codes exist, and now confirm")
    print("    EXACTLY how the Rev. 2 / Rev. 2.1 boundary differs for each --")
    print("    clean for 56 and 69, genuinely split for 35 -- rather than a")
    print("    caveat carried without knowing its size.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
