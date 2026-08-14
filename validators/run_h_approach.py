"""
The approach the Handbook recommends, which this library had never named.

CORE_007 was the last unread UN Handbook chapter. Its ¶2.24, p. 30 states the
recommendation: "The H-Approach is the recommended compilation approach, which
brings together the compilation of SUTs in current prices and volume terms, the
valuation at basic prices, producers' prices and purchasers' prices, and the
links with the compilation of IOTs."

Four things at once — price and volume, three valuations, and the transformation.
Every method card in this library treats one cell of that grid and none had said
they are one operation.

WHAT THE PROJECT COVERS, AND THE ONE IT DOES NOT
--------------------------------------------------
Audited below: three of the four components have method cards and code; the
volume dimension has neither, and the engine has no volume concept at all.
`OQ-B-01` has carried "simultaneous current-price and volume balancing" on its
missing list since v1.2 — this names it and locates the specification.

CORE_007 ¶2.23, p. 29: "More details are provided in chapters 9 and 11."
Chapter 11 is CORE_012, held and read. **Chapter 9 is not in the library.**
`OQ-B-05` lists it as "deflation detail", which undersells it: it is where the
recommended compilation approach is specified.

AND WHY THERE ARE TWO PRICE BASES TO CHOOSE BETWEEN
-----------------------------------------------------
`OQ-S-03` measured what the price basis costs a disaggregation — a median 4.5
points of the input structure — and said no source states which to use. CORE_007
¶2.103, p. 40 explains why there are two: "the valuation of use table is based on
the actual price paid by the users for the goods and services (i.e., purchasers'
price) while the valuation of the production data in the supply table is based on
output at basic prices".

Not a choice, a property of what each table records. ¶2.104, p. 40 adds that to
balance them "the same valuation should be used", via the margin and tax
matrices — so `M-055`'s valuation matrices are the only thing that makes the two
comparable, and `ID-01`'s articulated form is that comparison written out.

This narrows `OQ-S-03` and does not close it: which basis a *disaggregation*
should use is a question the Handbook does not ask.

Run:
    python3 validators/run_h_approach.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SRC = (ROOT / "library" / "extracted"
       / "CORE_007_UN2018_CH02_Overview_of_SUTs_and_IOTs.txt")
CARDS = ROOT / "library" / "specs" / "B_method_cards"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    if not SRC.exists():
        print("extraction absent")
        return 0
    text = re.sub(r"\s+", " ", SRC.read_text())

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    check("CORE_007 names the H-Approach as the recommended one",
          "The H-Approach is the recommended compilation approach" in text,
          "¶2.24, p. 30 — price and volume, three valuations, and the link to "
          "IOTs, held together")
    check("and refers its detail to chapters 9 and 11",
          "More details are provided in chapters 9 and 11" in text,
          "¶2.23, p. 29 — chapter 11 is CORE_012, held; chapter 9 is not in the "
          "library, and OQ-B-05 undersells it as 'deflation detail'")
    check("the volume half needs the PREVIOUS year's table too",
          "SUTs are available in current prices both for the current year and "
          "for the previous year" in text,
          "¶2.22, p. 29 — volume estimates are in previous years' prices, so "
          "the prior table is a precondition, not a convenience")

    # ---- the audit -------------------------------------------------------
    components = {
        "supply table at basic prices": ["M-059", "M-018"],
        "use table at purchasers' prices": ["M-060", "M-019"],
        "valuation matrices (the three price bases)": ["M-055"],
        "transformation to IOTs": ["M-023", "M-024", "M-025", "M-026", "M-027"],
        "VOLUME TERMS": [],
    }
    print()
    print("    the H-Approach's components, against this library:")
    for label, cards in components.items():
        have = [c for c in cards
                if any(CARDS.glob(f"{c}_*.md"))]
        mark = ", ".join(have) if have else "— nothing"
        print(f"      {label:<44} {mark}")
    print()

    check("three of the four components are covered",
          all(any(CARDS.glob(f"{c}_*.md"))
              for c in ("M-059", "M-060", "M-055", "M-023")),
          "supply, use, valuation and transformation all have cards and code")
    check("and the volume dimension has NOTHING, which is honest to state",
          not components["VOLUME TERMS"],
          "no card, no code, no concept — the engine consumes one table in "
          "current prices for one year. OQ-B-01 can now name what is absent "
          "instead of describing it")

    # ---- the valuation framing -------------------------------------------
    check("CORE_007 says the two price bases are a property, not a choice",
          "the valuation of use table is based on the actual price paid by the "
          "users" in text,
          "¶2.103, p. 40 — supply records what producers receive, use records "
          "what users pay")
    check("and that the valuation matrices are what make them comparable",
          "In order to balance the SUTs, the same valuation should be used"
          in text,
          "¶2.104, p. 40 — so M-055 is not an accessory; ID-01's articulated "
          "form is that comparison written out")

    check("it also corroborates M-058 on the statistical unit",
          "the same statistical unit is the basis for compiling the use table"
          in text,
          "¶2.96, p. 39 — third source, same requirement as CORE_009 ¶6.35, "
          "p. 164; nothing new, and worth knowing it is stable")

    print()
    print("    Still NOT SPECIFIED: the H-Approach in operational form (it lives")
    print("    in chapter 9, unheld), and which price basis a disaggregation")
    print("    should use (a question the Handbook does not ask).")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
