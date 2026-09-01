"""
The report tells a reader which of its references they can actually follow.

THE DEFECT THIS CLOSES
------------------------
Quadrium's reports cite their sources by paragraph and page, and that is most of
what makes them worth reading. Mixed in were references of a different kind —
`MVP_0.1 §6.3`, `A_core_accounting_spec.md §A.8.1`, `OQ-B-02` — pointing into a
research record that is **not distributed** and is not going to be, because it
quotes copyrighted chapters at length.

Forty of them lived in strings the engine can print, across fourteen modules.
For the author they are shorthand. For anyone else they are dead ends in the
middle of an explanation, and nothing told the reader which was which.

WHY THE FIX IS AT THE BOUNDARY
--------------------------------
Rewriting forty strings works once and then rots: the next refusal message
written in a hurry puts another one back. So `references.annotate()` runs where
a document becomes text a user sees, and it is driven by **matching**, not by a
list somebody maintains — a reference invented tomorrow is covered the day it is
written. The footnote goes at the true end of the document, which is after the
assumption ledger and not where `build_report` returns; annotating earlier put
it in the middle, which is how the first attempt was found to be wrong.

WHAT THIS FILE CHECKS
-----------------------
That a real report carries the note when it needs one. That the pattern does not
over-reach — `CORE_012`, `UNH_18`, `SNA_25` and `ID-11` are published or public
and must pass through untouched, and a footnote that disclaimed them would be
worse than none. And that a document with nothing internal in it gets no
footnote, because a note about an absent problem is noise.

Run:
    python3 validators/run_internal_refs.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
FAIL: list[str] = []

# Must be recognised as internal.
INTERNAL_CASES = [
    "see OQ-B-02 for the derivation",
    "MVP_0.1 §6.3 — project convention",
    "A_core_accounting_spec.md §A.8.1",
    "D_open_questions.md OQ-S-05 v1.57",
    "B_method_cards/M-049 records what was not checked",
    "INFORME_PILOTO.md §4 for why",
]
# Must NOT be: these are published, or defined in the public specification.
PUBLIC_CASES = [
    "CORE_012 ¶11.66, pp. 333-334",
    "UNH_18 par. 18.81, p. 569",
    "SNA_25 ch. 15",
    "NSO_UK_01 table 2",
    "identity ID-11 holds to 1e-9",
    "CORE_006 ¶9.51, p. 288",
    "the ONS analytical table, 2023",
]


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    warnings.filterwarnings("ignore")
    from quadrium import references

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # ---- the pattern, in both directions
    missed = [c for c in INTERNAL_CASES if not references.internal_refs(c)]
    check("every reference into the project's own record is recognised",
          not missed, f"{len(INTERNAL_CASES)} forms, all matched" if not missed
          else f"missed: {missed}")

    caught = [c for c in PUBLIC_CASES if references.internal_refs(c)]
    check("and no published source is mistaken for one",
          not caught,
          f"{len(PUBLIC_CASES)} published citations pass through untouched"
          if not caught else
          f"WRONGLY FLAGGED: {caught} — a footnote disclaiming a manual a "
          f"reader CAN open is worse than no footnote")

    # ---- the footnote is added, once, and only when needed
    plain = "This report cites CORE_012 ¶11.66, p. 333 and nothing else."
    check("a document with nothing internal in it gets no footnote",
          references.annotate(plain) == plain,
          "unchanged — a note about an absent problem is noise")

    dirty = "The floor is derived rather than sourced; see OQ-B-02."
    once = references.annotate(dirty)
    twice = references.annotate(once)
    check("a document that needs one gets exactly one, however often it is "
          "annotated",
          references.MARKER in once and once == twice
          and once.count(references.MARKER) == 1,
          "idempotent, so nesting a report inside a larger one cannot stack "
          "notes")

    # ---- and a REAL report, which is the thing that was wrong
    print()
    run = ROOT / "outputs" / "uk_food_beverage" / "report.md"
    if not run.exists():
        run = ROOT.parent / "Quadrium" / "outputs" / "uk_food_beverage" / "report.md"
    if not run.exists():
        print("    -- no published run to read; regenerate it with")
        print("       python3 examples/uk_food_beverage.py")
        return 1 if FAIL else 0

    text = run.read_text()
    refs = references.internal_refs(text)
    check("the published run still carries references into the private record",
          bool(refs),
          f"{len(refs)} distinct: {', '.join(refs[:6])}"
          f"{' …' if len(refs) > 6 else ''}. They are not removed — the report "
          f"is verbatim output and the author uses them")

    check("and it says so, at the end rather than in the middle",
          references.MARKER in text
          and text.index(references.MARKER) > len(text) * 0.9,
          f"the note sits at {text.index(references.MARKER) / len(text) * 100:.0f} % "
          f"through the document. The first attempt annotated where "
          f"build_report returns, which is before the assumption ledger is "
          f"appended, and put the note in the middle")

    check("the note names what a reader CAN follow, not only what they cannot",
          "CORE_nnn" in text and "verified against the source" in text
          and "PROVENANCE.md" in text,
          "it distinguishes the published citations from the internal ones and "
          "says where the rule is written down")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
