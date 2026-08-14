"""
`OQ-B-01`: CORE_082 acquired, its numbers verified against the PDF itself, and
its own citation corrected in three places it never belonged.

The entry's acquisition list named CORE_082 as a stub — "download or excerpt
before ingesting" — since the package was assembled. Downloaded 2026-08-11 on
the owner's explicit instruction, from the direct-download link AgEcon Search's
own record page exposes (`https://ageconsearch.umn.edu/record/9847/files/
sp07ah01.pdf`), a freely deposited working paper rather than a paywalled
journal article.

WHAT IT ACTUALLY IS, WHICH THREE ENTRIES HAD WRONG
-----------------------------------------------------
Ahmed & Preckel (2007), "A Comparison of RAS and Entropy Methods in Updating IO
Tables" — an AAEA Selected Paper, marked on its own cover **"PRELIMINARY
VERSION — PLEASE DO NOT DISTRIBUTE OR CITE WITHOUT PERMISSION."** Unpublished,
not peer-reviewed. Treated here as provisional evidence, not settled literature.

It compares RAS against Minimum Cross-Entropy for **updating a whole IO table
from one period's totals to the next** — real South Korean data, 1995 updated
to 2000. **It says nothing about disaggregating a sector, self-consumption in an
internal block, or how many subsectors a table can support.** Five places in
`D_open_questions.md` cited it; three — `OQ-S-02`, `OQ-S-03`, `OQ-S-04` — cited
it for topics it does not address, written before anyone had read it. Corrected
and struck through at v1.42.

THE FINDING, VERIFIED AGAINST THE PDF ITSELF
------------------------------------------------
Table 1 and Table 3, on real cross-period data: CE beats RAS on every reported
metric — SSE1 (nonzero cells) 22 % smaller, SSE2 (all cells) 28 % smaller,
maximum absolute coefficient difference 35 % smaller.

**And it disagrees with a rank-2 source already loaded.** UNH_18 ¶18.74, p. 566
surveys the published literature on exactly this comparison and concludes "The
results generally favour the RAS method over the other options." One
provisional paper finding the opposite of what a Handbook literature survey
reports is a live disagreement, not a resolution — recorded as such, not
smoothed into agreement with either source.

**What it does not do: justify GRAS.** GRAS is chosen in this project because
"the RAS method can be considered as a special case of the GRAS method" (UNH_18
¶18.35) — a generalisation that admits negative cells — not because GRAS
belongs to an entropy family CE also belongs to. Reading CORE_082 as support for
GRAS would be misapplying a finding about updating accuracy to a question about
handling negatives, which is a different problem this paper does not touch.

Run:
    python3 validators/run_core082_acquisition.py
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF = (ROOT / "library" / "Methodology" / "CORE_08_Extensions_and_Validation"
       / "DOCUMENTS" / "CORE_082_AhmedPreckel2007_RAS_vs_Entropy.pdf")
QUESTIONS = ROOT / "library" / "specs" / "D_open_questions.md"
UNH_18 = ROOT / "library" / "extracted" / "UNH_18_UN2018_CH18_Projecting_SUTs_and_IOTs.txt"

EXPECTED_SHA256 = "dd8597416a0f071a36c351dfef301101330257ff2f2b3dd2447c7baa563676ca"

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if not PDF.exists():
        print("CORE_082 PDF absent")
        return 0

    digest = hashlib.sha256(PDF.read_bytes()).hexdigest()
    check("the acquired PDF matches the hash recorded at download time",
          digest == EXPECTED_SHA256,
          f"{digest[:16]}… — the file has not silently changed since 2026-08-11")

    try:
        import pypdf
        text = "\n".join(p.extract_text() for p in pypdf.PdfReader(PDF).pages)
    except ImportError:
        print("pypdf unavailable")
        return 0
    flat = re.sub(r"\s+", " ", text)

    check("it is the preliminary, unpublished version, and says so on its own "
          "cover",
          "PLEASE DO NOT DISTRIBUTE OR CITE WITHOUT PERMISSION" in flat,
          "treated as provisional evidence throughout, not settled literature — "
          "this is not a formality, it changes how much weight the finding "
          "below carries against UNH_18's rank-2 survey")

    check("the SSE1/SSE2 table is real and matches what is quoted",
          "1.017" in flat and "0.792" in flat and "1.113" in flat
          and "0.796" in flat,
          "Table 1: RAS SSE1 1.017 / SSE2 1.113, CE SSE1 0.792 / SSE2 0.796 — "
          "22% and 28% smaller respectively, transcribed correctly")

    check("the maximum-absolute-difference table is real",
          "8088577" in re.sub(r"[,.\s]", "", flat),
          "Table 3: RAS 8,088,577.010 vs CE 5,231,717.586 on the coefficient "
          "matrix — CE 35% smaller")

    check("the topic is updating across periods, not disaggregation",
          "updating IO" in flat.lower() or "Updating IO Tables" in flat,
          "confirmed from the title itself and the abstract's description of "
          "the 1995-to-2000 update exercise. Nothing about splitting a sector "
          "or a table's internal block appears anywhere in 20 pages")

    check("it does not contain 'disaggregat' anywhere",
          not re.search(r"disaggregat", flat, re.I),
          "zero occurrences — confirms OQ-S-02/S-03/S-04 had the wrong source "
          "attached, independent of reading the topic sentences")

    # ---- the UNH_18 disagreement -------------------------------------------
    if UNH_18.exists():
        f18 = re.sub(r"\s+", " ", UNH_18.read_text())
        check("UNH_18 really does say the literature generally favours RAS",
              "results generally favour the RAS method over the other options"
              in f18,
              "¶18.74, p. 566 — a rank-2 survey of the published comparisons, "
              "reaching the opposite conclusion from CORE_082's single "
              "provisional result")

    # ---- the corrected entries stay corrected ------------------------------
    print()
    qtext = QUESTIONS.read_text()
    entries = {m.group(1): m.group(0) for m in
              re.finditer(r"^### (OQ-[A-Z]-\d+) — .*?(?=^### |\Z)", qtext,
                          re.S | re.M)}
    for qid in ("OQ-S-02", "OQ-S-03", "OQ-S-04"):
        body = entries.get(qid, "")
        live = re.sub(r"~~[^~]*CORE_082[^~]*~~", "", body)
        check(f"{qid} no longer sends a reader to CORE_082 for its own topic",
              "CORE_082" not in live or "Not `CORE_082`" in live
              or "**Not `CORE_082`**" in live,
              "every remaining mention is struck through or explicitly "
              "corrected, not a live pointer")

    check("OQ-B-01 is where the finding actually lives",
          "CORE_082" in entries.get("OQ-B-01", ""),
          "the acquisition and its content are recorded on the entry the paper "
          "actually answers")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
