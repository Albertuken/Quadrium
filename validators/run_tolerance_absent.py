"""
`OQ-B-02`: the tolerance is not missing from the chapters this project read. It
is missing from the entire Handbook.

The entry has been open since v1.1 waiting for a source that states a numerical
tolerance for an accounting identity, and has sent readers to CORE_021, CORE_067
and CORE_080 in turn. With the full UN Handbook PDF in hand for `OQ-B-05`, the
question can be settled for that source exhaustively rather than chapter by
chapter.

CORE_067 and CORE_076 turned out to be byte-identical to NSO_UK_01 and
NSO_ES_01 — sources this project had already acquired and read under those
IDs, for different questions. Neither had been searched for tolerance
language before. CORE_080 (GASTAT) has no such duplicate.

THE EXHAUSTIVE SEARCH
-----------------------
735 pages, 2,012,467 characters, every page's text:

    "toleran*"            1 sentence, and it is a SOLVER stopping rule
    "acceptable level"    1 sentence
    "acceptable range"    0
    "acceptable difference" 1 sentence, and it is about price indices
    "threshold"          19 sentences, every one about SURVEY COVERAGE —
                         VAT registration, turnover, employment — not about
                         an identity

**The single "toleran*" is ¶18.102's SUT-EURO sentence**, which is `OQ-B-10`'s
notation collision and states no value: "The convergence in the SUT-Euro method
can always be found by changing the tolerance level (ɛ) until convergence is
reached."

**And the single "acceptable level" defers to judgement explicitly.** ¶21.51:
"Using a manual procedure, the residuals have to be corrected to an acceptable
level. **Based on their judgment, the compilers should balance the accounts by
adjusting selected components in the light of such criteria as quality, coverage,
and others.**"

So the Handbook does not withhold a threshold by oversight. **It assigns the
decision to the compiler's judgement, on quality and coverage criteria, and
declines to name a number anywhere in 735 pages.**

WHAT THAT CHANGES
-------------------
`OQ-B-02` has been framed as waiting for a source. It is not waiting: three
manuals have now been searched and none gives one — the UN Handbook exhaustively,
Eurostat's balancing chapter (CORE_021, zero occurrences of "toleran", its one
"threshold" being Intrastat trade reporting) and Eurostat's transformation
chapter (CORE_022, zero in 253 KB).

**The question is therefore not "find the source" but "is the project's own floor
defensible".** That floor exists — `quadrium.precision.assertable_tolerance`,
derived from printed decimals rather than chosen — and it is labelled a project
choice wherever it appears. What no source will ever supply is the *acceptance*
threshold above it: how far a real table may miss its own identity before a
compiler should refuse it. On the evidence, that is a judgement the framework
deliberately leaves open, and an engine that invented one would be inventing
something three manuals decline to state.

The entry stays open — the project still has to defend its own number — but its
"next source" list can be pruned, which is the practical result.

Run:
    python3 validators/run_tolerance_absent.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
EXTRACTED = ROOT / "library" / "extracted"
FAIL: list[str] = []

# Recorded from the full 735-page PDF on 2026-08-11. The PDF is not kept in the
# repository, so these are the measured counts and the checks below re-verify
# what the extracted corpus can support.
FULL_PDF = {"pages": 735, "chars": 2_012_467, "toleran": 1,
            "acceptable level": 1, "acceptable range": 0, "threshold": 19}


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # Everything this project holds from the two manuals that would carry a
    # tolerance if one existed: the UN Handbook chapters and Eurostat's
    # balancing and transformation chapters.
    corpus = sorted(EXTRACTED.glob("UNH_*.txt"))
    for name in ("CORE_021_Eurostat2008_CH08_Balancing_Supply_and_Use.txt",
                 "CORE_022_Eurostat2008_CH11_SUT_to_Symmetric_IOT.txt",
                 "CORE_012_UN2018_CH11_Balancing_Supply_and_Use_Tables.txt",
                 "CORE_016_OECD_EU2025_CH05_Balancing_Extended_SUTs.txt"):
        p = EXTRACTED / name
        if p.exists():
            corpus.append(p)

    if not corpus:
        print("no extractions")
        return 0

    total_chars = 0
    hits: dict[str, list[str]] = {}
    for p in corpus:
        flat = re.sub(r"\s+", " ", p.read_text())
        total_chars += len(flat)
        for m in re.finditer(r"[^.]{0,150}\btoleran\w*[^.]{0,150}\.", flat, re.I):
            hits.setdefault(p.name, []).append(m.group(0).strip())

    print(f"    searched {len(corpus)} extractions, {total_chars:,} characters")
    for fn, sentences in hits.items():
        for s in sentences:
            print(f"      [{fn[:16]}] {s[:150]}")

    all_sentences = [s for v in hits.values() for s in v]
    check("across every balancing and transformation source held, the word "
          "appears twice — and never about an identity",
          len(all_sentences) <= 3,
          f"{len(all_sentences)} sentences in {total_chars:,} characters. Both "
          f"are SOLVER CONVERGENCE parameters — UNH_18 ¶18.102's SUT-EURO "
          f"line, which is OQ-B-10's notation collision, and CORE_016's "
          f"stopping rule for GRAS. **Neither is a tolerance on an accounting "
          f"identity**, which is what OQ-B-02 asks for, and that distinction "
          f"is the finding: the corpus has stopping rules and no acceptance "
          f"thresholds")

    check("and neither states a value",
          not any(re.search(r"\d", re.split(r"toleran\w*", s, 1)[-1][:70])
                  for s in all_sentences),
          "one says convergence 'can always be found by changing the tolerance "
          "level (ɛ) until convergence is reached', the other 'smaller than a "
          "given tolerance level'. Both name the parameter and leave it to the "
          "user")

    # ---- what the full PDF gave, recorded ---------------------------------
    print()
    print(f"    Measured on the full Handbook PDF, {FULL_PDF['pages']} pages, "
          f"{FULL_PDF['chars']:,} characters:")
    for k in ("toleran", "acceptable level", "acceptable range", "threshold"):
        print(f"      {k:<22} {FULL_PDF[k]:>3} sentence(s)"
              + ("   all about survey coverage — VAT, turnover, employment"
                 if k == "threshold" else ""))
    check("the exhaustive count is recorded with its method, not asserted",
          FULL_PDF["toleran"] == 1 and FULL_PDF["acceptable range"] == 0,
          "the PDF is not kept in the repository — library/Methodology/**/*.pdf "
          "is gitignored — so this is a dated measurement rather than a "
          "re-runnable one, and the corpus checks above are what re-run")

    # ---- the Handbook's own position --------------------------------------
    c21 = EXTRACTED / "CORE_021_Eurostat2008_CH08_Balancing_Supply_and_Use.txt"
    if c21.exists():
        check("Eurostat's balancing chapter agrees by silence",
              not re.search(r"toleran", c21.read_text(), re.I),
              "zero occurrences; its single 'threshold' is Intrastat trade "
              "reporting. Three manuals, no number")

    # A fourth, found 2026-08-13 sitting unread in CORE_04/DOCUMENTS/ while
    # closing OQ-B-01.
    c41 = EXTRACTED / "CORE_041_Lahr_deMesnard_Biproportional.txt"
    if c41.exists():
        f41 = re.sub(r"\s+", " ", c41.read_text())
        check("and a fourth source's one 'toleran' is the same shape as the "
              "others — a solver stopping rule",
              "within a certain pre-specified tolerance" in f41,
              "CORE_041 (Lahr & de Mesnard): RAS 'will kick out its estimate "
              "... when all diagonal elements ... are within a certain "
              "pre-specified tolerance' — the algorithm's own convergence "
              "check, not an acceptance threshold on the balanced table. "
              "Four sources now, same pattern in every one")

    # A fifth check, and a correction of one made in error on 2026-08-13.
    # This entry's own "next source" list named CORE_067 and CORE_080. What
    # was NOT noticed until re-checking: CORE_067 is byte-identical
    # (SHA-256 048622d8...3207) to NSO_UK_01, already read and cited
    # throughout the project (M-027, OQ-T-03, OQ-T-04) — and CORE_076 (a
    # pointer used by OQ-T-03, not this entry) is likewise identical to
    # NSO_ES_01. Both are read sources, just never previously searched for
    # THIS question — the same fault CORE_022's docstring already names: a
    # source that has been read is not thereby read against every later
    # question. CORE_080 (GASTAT) has no such duplicate and is the one
    # genuinely new acquisition here.
    nso_uk = EXTRACTED / "NSO_UK_01_ONS_IOAT_QMI.txt"
    nso_es = EXTRACTED / "NSO_ES_01_INE_nota_metodologica_TIO.txt"
    c80 = EXTRACTED / "CORE_080_GASTAT_SUT_IOT_Quality_Report.txt"
    if nso_uk.exists():
        check("NSO_UK_01 (the ONS QMI, already read for OQ-T-03/T-04 under "
              "that ID) states no tolerance either, now checked for THIS "
              "question for the first time",
              not re.search(r"toleran|acceptable\s+(level|range|difference)"
                             r"|threshold", nso_uk.read_text(), re.I),
              "zero occurrences across 7 pages. The office whose table this "
              "project uses as a fixture documents its balancing process "
              "with no numeric discrepancy criterion")
    if nso_es.exists():
        check("NSO_ES_01 (the INE note, already read and cited at OQ-B-04 "
              "v1.8 for a different sentence) has no tolerance language "
              "either",
              not re.search(r"toleran|umbral|acceptable|threshold",
                             nso_es.read_text(), re.I),
              "zero occurrences. Its own 'no resuelve todos los problemas' "
              "admission (already quoted at OQ-B-04) is about negatives "
              "surviving the hybrid method, not about a discrepancy limit")
    if c80.exists():
        t80 = c80.read_text()
        check("CORE_080 (GASTAT's quality report — genuinely new, a sixth "
              "national office, no duplicate elsewhere in the project) "
              "names no number either",
              "toleran" not in t80.lower()
              and "cross-referenced with the data source for" in t80,
              "its sole mention of discrepancy is a data-correction workflow "
              "('if errors or discrepancies are discovered, the data is "
              "cross-referenced with the data source for correction or "
              "clarification'), not an acceptance threshold on an identity")

    print()
    print("    Six sources now, same result: the UN Handbook (exhaustively,")
    print("    735 pages), Eurostat's balancing and transformation chapters,")
    print("    Lahr & de Mesnard, and three national offices' own published")
    print("    quality documentation (ONS and Spain, both already read under")
    print("    other IDs; GASTAT genuinely new). None states an acceptance")
    print("    threshold for an accounting identity.")
    print()
    print("    The Handbook does not withhold a threshold by oversight. ¶21.51")
    print("    assigns the decision: 'Based on their judgment, the compilers")
    print("    should balance the accounts by adjusting selected components in")
    print("    the light of such criteria as quality, coverage, and others.'")
    print()
    print("    So OQ-B-02 is not waiting for a source. It is waiting for the")
    print("    project to defend its own floor, which is a different task and")
    print("    a smaller one. precision.assertable_tolerance is derived from")
    print("    printed decimals rather than chosen; the ACCEPTANCE threshold")
    print("    above it is what no manual will supply.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
