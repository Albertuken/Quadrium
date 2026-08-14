"""
`OQ-B-01`'s residue reframed: the weighted case has no equation because it is
not one.

Since v1.2 this project has treated the weighted / conflicting-data case as a
missing algorithm — UNH_18 ¶18.33, p. 558 says RAS "does not allow the use of
relative reliabilities", assigns the case to KRAS, and writes no equations, and
the entry has been waiting for a source that does. Two more extracted-but-unread
sources say the wait is misconceived.

CORE_004 ¶19.80, p. 630 — rank 1 — describes the same operation:

    "It often involves weighting the relative quality of the various data
    sources, discussing possible reasons for any differences, making decisions
    using informed judgement on which information to use..."

**Weighting relative quality is named, and named as informed judgement.** The SNA
is not withholding a formula; it is describing something that does not have one.
`M-061`'s M-RAS takes the `pinned` half mechanically because a pinned cell is a
fact. The `restricted` half is judgement, and every source that touches it says
so.

AND FULL AUTOMATION WAS TRIED AND GIVEN UP
--------------------------------------------
CORE_021 p. 209 — rank 2, Eurostat's own manual:

    "Statistical offices have tried to develop an integration system that would
    automatically perform most of the balancing work. Eventually, this approach
    was abandoned because the results were rather unpredictable."

This is different in kind from what the library already had. `NSO_AT_01`'s 15
million EUR threshold and CORE_008 ¶5.54, p. 143's hand-made redefinitions say
manual work is *preferred*. This says full automation was **built, run and
abandoned**, and gives the reason.

WHAT EUROSTAT ENDORSES INSTEAD, AND WHY IT MATTERS TO THIS CODEBASE
--------------------------------------------------------------------
Small manual packages, one sector expert each, a simple tool, shared access to
the whole system — and automation confined to the residual: "automatic
procedures can help to eliminate the small discrepancies between supply and
demand. This is often done with the help of proportional corrections."

**Proportional correction of small residuals is `M-020` E3**, the one complete
update rule CORE_012 writes out. It is not GRAS, not SUT-RAS, not an
optimisation. The heavy solvers in `validators/` are projection tools —
they move a base-year table onto another year's margins — and this file checks
that the project's own inventory says so rather than presenting them as balancing
machinery.

A RANK-1 SOURCE ON HOW CONSISTENT PUBLISHED ACCOUNTS ACTUALLY ARE
-------------------------------------------------------------------
CORE_004 ¶19.81, p. 630: "To arrive at full consistency is the ideal, but this is
not the practice." Countries publish different GDP estimates from the production
and expenditure sides. This project refuses a table that does not balance, and
should keep doing so — it consumes published SUTs and IOTs, where the identity is
asserted — but the system those tables sit in does not close, and `OQ-B-02`'s
tolerance question reads differently beside it.

¶19.82, p. 630 gives the triage rule: a discrepancy with "a structural component,
in the sense of being consistently positive or negative" warrants "continued
research". Persistent and one-signed is signal; sign-changing is noise.

Run:
    python3 validators/run_automation_limits.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

EXTRACTED = ROOT / "library" / "extracted"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def _norm(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text())


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    eu = EXTRACTED / "CORE_021_Eurostat2008_CH08_Balancing_Supply_and_Use.txt"
    sna = EXTRACTED / "CORE_004_SNA2025_CH19_Summarizing_Integrating_Balancing.txt"
    if not (eu.exists() and sna.exists()):
        print("extraction(s) absent")
        return 0
    eu_t, sna_t = _norm(eu), _norm(sna)

    check("Eurostat records that full automation was tried and abandoned",
          "abandoned because the results were" in eu_t,
          "CORE_021 p. 209 — built, run and given up, and the reason given is "
          "unpredictability. The library's other two manual-first statements "
          "(NSO_AT_01, CORE_008 ¶5.54, p. 143) say it is preferred; this says "
          "it was attempted")

    for phrase, what in (
            ("split up the supply and use system into smaller parts",
             "small packages"),
            ("sector experts will be responsible", "one expert each"),
            ("as simple in its operation as possible", "a simple tool"),
            ("access to the common database", "shared sight of the whole"),
            ("often done with the help of proportional corrections",
             "automation for the residual only")):
        check(f"  and what replaced it: {what}", phrase in eu_t,
              f'"{phrase}"')

    check("the SNA names weighting by source quality and calls it JUDGEMENT",
          "weighting the relative quality of the various data sources" in sna_t
          and "informed judgement" in sna_t,
          "CORE_004 ¶19.80, p. 630 — so OQ-B-01's residue is not an equation "
          "waiting to be found; M-061 takes the `pinned` half because a pin is "
          "a fact, and `restricted` is where judgement lives")

    check("and states that full consistency is not the practice",
          "To arrive at full consistency is the ideal" in sna_t,
          "CORE_004 ¶19.81, p. 630 — countries publish different GDP estimates "
          "from the production and expenditure sides. This project still "
          "refuses an unbalanced table, because it consumes published SUTs "
          "where the identity is asserted")
    check("with a triage rule for the discrepancy that remains",
          "structural component" in sna_t
          and "consistently positive or negative" in sna_t,
          "CORE_004 ¶19.82, p. 630 — persistent and one-signed warrants "
          "research; sign-changing is noise")

    # The inventory check: are the heavy solvers labelled as projection?
    gras = (ROOT / "src" / "quadrium" / "gras.py").read_text()
    sut_ras = (ROOT / "src" / "quadrium" / "sut_ras.py").read_text()
    check("the project's heavy solvers are labelled as PROJECTION tools",
          "Projecting" in gras or "projecting" in gras.lower(),
          "gras.py cites UNH_18 ch. 18, 'Projecting supply, use and "
          "input-output tables' — which is what Eurostat's account says they "
          "are for. Balancing a current-year table is proportional correction "
          "of small residuals, M-020 E3")
    check("and sut_ras is too",
          "18.86" in sut_ras or "project" in sut_ras.lower(),
          "same chapter")

    print()
    print("    Nothing in the engine changes. What changes is the reading of")
    print("    OQ-B-01's residue: the `restricted` case has no equation because")
    print("    the sources describe it as judgement, not because the literature")
    print("    has a gap that more reading would fill.")
    print()
    print("    Still NOT SPECIFIED: how small 'small discrepancies' is")
    print("    (CORE_021 p. 209 gives no threshold — the same quantity as")
    print("    M-039's handover threshold), and how to weight (CORE_004")
    print("    ¶19.80, p. 630 names the operation and calls it judgement).")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
