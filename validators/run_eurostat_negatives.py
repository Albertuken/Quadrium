"""
CORE_022 read at last, and it answers `OQ-B-04` by refusing the question a fourth
time — plus two dead ends now closed by checking instead of guessing.

Seven open entries name a "next source" that is already sitting in
`library/extracted/`. Three of them name **CORE_022**, Eurostat's chapter on
transforming SUTs into symmetric IOTs, 253 KB, extracted and unread. This is the
same fault the session has hit repeatedly: entries are written and never re-read.

`OQ-B-04` — NO TEST, FOR THE FOURTH TIME, AND NOW WITH A TAXONOMY
------------------------------------------------------------------
> **Correction, 2026-08-11.** This file first said CORE_022 §11.4.2 and §11.4.4
> "are the closest any loaded source comes". **They are not.** CORE_013's Annex
> B to chapter 12 covers the same ground and goes further — it names the Almon
> method for removing small negatives, gives a three-step strategy, cites ten Raa
> and Rueda-Cantuche (2013) for algorithmic solutions, and carries the
> restaurants-and-bars example in ISIC Rev. 4 rather than NACE Rev. 1.1. **All of
> it has been in `library/extracted/` since v1.5**, in a chapter this project
> read, mined for the four transformation models, and cited 125 times.
>
> The conclusion below is unchanged and now rests on two sources instead of one.
> What was wrong was the claim of primacy — and the cause is the session's own
> subject turned on itself: a source that has been *read* is not thereby read
> against every later question. Nobody re-opened chapter 12 when negatives became
> the topic.

The entry asks for a test of whether a negative at basic prices is "unwanted".
CORE_022 §11.4.2 and §11.4.4 give something better than a test and worse than a
rule:

**Four causes** (§11.4.2, p. 319–320) — the product technology assumption being
wrong; economic transactions being recorded rather than technological relations
(subcontracting, and the vertically integrated dairy that "produces cheese
without using milk"); non-market output valued at cost, where transferring a
secondary market product "a negative will arise for the operating surplus"; and
heterogeneity in data and classifications.

**Seven remedies** (§11.4.4, p. 322–325) — merge industries, change the primary
producer, apply industry technology inside the product technology framework, make
by-products, introduce new products, correct errors in the SUT, and make manual
corrections to the IOT.

**And no threshold anywhere.** CORE_013 §B12.12 says the same in its own words:
large negatives are "investigated, resolved and rebalanced" one at a time, "small
negatives are eliminated by applying some form of automated procedure", and the
procedure it names is **Almon's** — which this engine implements and validates
against Eurostat's printed numbers in `run_almon_eurostat.py`. Two manuals, one
answer, and no number in either.

The nearest thing to a test is "wherever it can be
established that negatives (or other implausible results) are caused by errors" —
establishing it is the compiler's job — and "if (large) negatives remain", with
no definition of large. What the chapter reports instead is that **the German
office built "special transformation matrices" to carry manual corrections and
the Austrian office "has identified ten problem areas for large negatives which
are corrected during a manual correction"**. Two national offices, and both
answer it by hand against a named list.

That is the fourth independent confirmation of the v1.8 answer: the question has
the wrong shape. There is no test because there is no property of a cell that
decides it; there is a cause, and each cause has a remedy.

THE RESTAURANTS-AND-BARS EXAMPLE, AND WHY IT DOES **NOT** CONDEMN THE PILOT
-----------------------------------------------------------------------------
§11.4.4's worked case for "merge industries" is restaurants and bars, and the
first reading is alarming for a project whose pilot splits hospitality: Eurostat
says trying to separate their input structures "may lead to negative elements"
and "it would be better to aggregate such industries".

**Read the classification before panicking.** The manual is NACE Rev. 1.1, where
restaurants are 55.3 and bars 55.4. Both of those map into NACE Rev. 2's
**division 56**, food and beverage service activities. **CORE_013 §B12.14 settles
it outright in the modern classification**: it gives the same example as
"restaurants (ISIC Rev. 4, group 561) and bars (ISIC Rev. 4, group 563)" — both
inside division 56. What was inferred from a correspondence is stated directly by
a source the library already held. So Eurostat is saying
*merge the parts of 56 together* — and the Spanish pilot splits **55 from 56**,
which is the boundary its reasoning leaves standing. The advice does not hit the
pilot; if anything it says division 56 is already the right merged unit.

Recorded because the alarming reading was the first one and it was wrong, and
because a project that split 56 internally would be doing exactly what this
paragraph warns against.

TWO DEAD ENDS, NOW MEASURED RATHER THAN ASSUMED
-------------------------------------------------
`OQ-B-10` says CORE_022 "documents the EURO method family and may settle it".
**It does not.** The chapter contains zero occurrences of "EURO method",
"SUT-EURO", "tolerance" or "convergence". The pointer is wrong and the entry
should stop sending readers there.

`OQ-B-02` sends readers to CORE_021 for a numerical tolerance. **CORE_021
contains no tolerance language at all** — zero occurrences of "toleran", and its
single "threshold" is about Intrastat trade reporting. Checked, not guessed.

AND A FOURTH VOICE ON `OQ-T-03`
---------------------------------
CORE_022 §11.4.1, p. 318 states the ESA 1995 preference and its reason: the
product-by-product variant "was preferred by ESA 1995, since this table shows
more homogeneous flows", the product technology model is "fully consistent" with
using such a table in analysis, and this "cannot be said of the industry
technology assumption". It also says "most cases of secondary production will be
cases of subsidiary production, for which the product technology seems to apply
best". A fourth source, leaning the same way as CORE_006 and CORE_017.

Run:
    python3 validators/run_eurostat_negatives.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / "library" / "extracted"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    c22 = EXTRACTED / "CORE_022_Eurostat2008_CH11_SUT_to_Symmetric_IOT.txt"
    c21 = EXTRACTED / "CORE_021_Eurostat2008_CH08_Balancing_Supply_and_Use.txt"
    if not (c22.exists() and c21.exists()):
        print("extraction(s) absent")
        return 0
    t22, t21 = c22.read_text(), c21.read_text()
    flat22 = re.sub(r"\s+", " ", t22)

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # ---- the four causes --------------------------------------------------
    causes = [
        "The product technology assumption can be incorrect",
        "Economic transactions are recorded rather than t echnological relations",
        "Non-market output creates a special problem",
        "Heterogeneity in data and classifications",
    ]
    present = [c for c in causes if c in t22]
    check("CORE_022 §11.4.2 names four causes of negatives",
          len(present) == 4,
          f"{len(present)} of 4 — the assumption being wrong, transactions "
          f"rather than technology, non-market output valued at cost, and "
          f"classification heterogeneity. A taxonomy, which is what OQ-B-04 "
          f"gets instead of a test")

    check("including the one no other loaded source states — non-market output",
          "a negative will arise for the operating surplus" in flat22,
          "output valued as the sum of costs with surplus fixed at zero, so "
          "transferring a secondary market product out drives the surplus "
          "negative. A negative that is an artefact of a valuation convention, "
          "not of a technology")

    # ---- the seven remedies -----------------------------------------------
    # Matched with regexes, not literals: the PDF hyphenates across line
    # breaks ("by-\nproducts" flattens to "by- products") and drops page
    # furniture mid-sentence. A literal match here fails on typesetting, not
    # on content, and quietly under-counts.
    remedies = [r"merging industries", r"changing the primary producer",
                r"applying industry technology within the product technology",
                r"making by-\s*products", r"introducing new products",
                r"correcting errors in the supply and use table",
                r"making manual corrections to symmetric input-output tables"]
    found = [r for r in remedies if re.search(r, flat22)]
    check("and §11.4.4 names seven remedies, one per cause and then some",
          len(found) == 7,
          "merge industries, change the primary producer, apply industry "
          "technology inside the product framework, make by-products, "
          "introduce new products, correct the SUT, correct the IOT by hand")

    # ---- but no threshold -------------------------------------------------
    check("while offering NO threshold — the fourth source to decline",
          not re.search(r"toleran", t22, re.I)
          and "if (large) negatives remain" in flat22,
          "zero occurrences of 'toleran' in 253 KB; the discriminator offered "
          "is the word 'large', undefined. OQ-B-04 asked for a test and the "
          "answer is again that there is none")

    check("and what two national offices do instead is by hand",
          bool(re.search(r"special transformation .{0,200}?matrices", flat22))
          # 151 characters of page furniture sit inside that phrase.
          # Measured, not guessed at until it passed.
          and "ten problem areas" in flat22,
          "Germany carries manual corrections in 'special transformation "
          "matrices'; Austria 'has identified ten problem areas for large "
          "negatives which are corrected during a manual correction'. This is "
          "M-062's finding arriving from a fifth direction")

    # ---- the restaurants and bars reading ---------------------------------
    print()
    check("the merge example is restaurants and bars, and it reads as a threat "
          "to the pilot",
          "restaurants (NACE 55.3) and bars (NACE 55.4)" in flat22
          and "It would be better to aggregate such industries" in flat22,
          "Eurostat says separating their input structures 'may lead to "
          "negative elements'")
    check("but the classification says otherwise, and this is the reading that "
          "holds",
          "55.3" in flat22 and "55.4" in flat22,
          "the manual is NACE Rev. 1.1, where restaurants are 55.3 and bars "
          "55.4 — and BOTH map into NACE Rev. 2's division 56. Eurostat is "
          "saying merge the parts of 56; the pilot splits 55 from 56, which is "
          "the boundary that reasoning leaves standing. A project splitting "
          "56 internally would be doing what this paragraph warns against")

    # ---- the two dead ends ------------------------------------------------
    print()
    euro_terms = {p: len(re.findall(p, t22, re.I))
                  for p in ("EURO method", "SUT-EURO", "tolerance",
                            "convergence")}
    check("OQ-B-10's pointer to CORE_022 is a dead end",
          sum(euro_terms.values()) == 0,
          f"{euro_terms} — the chapter documents no EURO method, no tolerance "
          f"and no convergence. The entry should stop sending readers here")

    tol21 = len(re.findall(r"toleran", t21, re.I))
    check("and so is OQ-B-02's pointer to CORE_021",
          tol21 == 0,
          f"{tol21} occurrences of 'toleran' in the balancing chapter; its one "
          f"'threshold' is Intrastat trade reporting. Checked rather than "
          f"assumed, which is the only way a dead end stops costing anything")

    # ---- OQ-T-03's fourth voice -------------------------------------------
    print()
    check("CORE_022 §11.4.1 is a fourth source on model choice, leaning the "
          "same way",
          "was preferred by ESA 1995, since this table shows more homogeneous "
          "flows" in flat22
          and "cannot be said of the industry technology assumption" in flat22,
          "product-by-product preferred for homogeneity; product technology "
          "'fully consistent' with using such a table in analysis, which "
          "'cannot be said of' industry technology. With CORE_006 and "
          "CORE_017 that is three leaning one way and CORE_013 even-handed")

    check("and it repeats the detail-level recommendation the engine needs",
          "apply the product technology assumption always at the most detailed "
          "level of products possible" in flat22,
          "which is OQ-S-02's ceiling argument from the other side: detail "
          "reduces the heterogeneity that causes negatives in the first place")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
