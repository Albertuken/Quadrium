"""Telling a reader which of the report's references they can actually follow.

THE PROBLEM
-------------
This engine cites its sources, and that is most of what makes its output worth
reading: `CORE_012 ¶11.66, pp. 333-334` sends you to a published manual, on a
page whose text the project has verified carries the sentence. Those are good.

Mixed in with them are references of a different kind — `MVP_0.1 §6.3`,
`A_core_accounting_spec.md §A.8.1`, `OQ-B-02` — which point into this project's
own research record. That record is not distributed and is not going to be: it
quotes copyrighted chapters at length. For the author they are useful shorthand.
For anybody else they are dead ends in the middle of an explanation, and there
were **40 of them** in strings the engine can print.

WHY THE FIX IS A FOOTNOTE AND NOT FORTY EDITS
-----------------------------------------------
Rewriting each string would work once and then rot: the next refusal message
written in a hurry puts another one back, and nothing would notice. So the
marking happens at the **rendering boundary** — where a report or an error
becomes text a user sees — and it is driven by matching, not by a list someone
maintains. A reference invented tomorrow is covered the day it is written.

And it is a footnote rather than an inline annotation because these references
appear many times in one document. Forty inline disclaimers would be noise; one
paragraph at the foot says the same thing once and leaves the prose readable.

WHAT IS NOT MARKED
--------------------
`CORE_nnn`, `UNH_nn`, `SNA_25`, `NSO_*` and `ID-nn` are published sources and
identities defined in the public specification. They stay exactly as they are.
"""
from __future__ import annotations

import re

# The project's own record: a numbered open question, one of the specification
# documents, or the MVP note. Deliberately narrow -- it must not catch CORE_012
# or ID-11, which a reader CAN follow.
INTERNAL = re.compile(
    r"\bOQ-[A-Z]-\d{1,3}\b"
    r"|\bMVP_0\.\d+\b"
    r"|\b[A-Z]_[a-z_]+\.md\b"          # A_core_accounting_spec.md, D_open_questions.md
    r"|\bB_method_cards/[A-Z]-\d+\b"
    r"|\bINFORME_PILOTO(?:_ES)?\.md\b")

MARKER = "*Not every reference here is one you can follow.*"


def internal_refs(text: str) -> list[str]:
    """Every reference to the project's own record, in order of first sight."""
    seen: dict[str, None] = {}
    for m in INTERNAL.finditer(text or ""):
        seen.setdefault(m.group(0), None)
    return list(seen)


def footnote(refs: list[str]) -> str:
    """One paragraph naming them and saying where they do and do not lead."""
    shown = ", ".join(f"`{r}`" for r in refs[:8])
    more = f" and {len(refs) - 8} more" if len(refs) > 8 else ""
    return (
        f"---\n\n{MARKER} {shown}{more} point into this project's own research "
        f"record — its open questions, its accounting specification and its "
        f"method cards. That record is **not** distributed with the software, "
        f"because it quotes copyrighted manuals at length; `PROVENANCE.md` says "
        f"so and why. Everything cited as `CORE_nnn`, `UNH_nn` or `SNA_25` is a "
        f"published source, given by paragraph and page, and every one of those "
        f"page citations is verified against the source's own text before it "
        f"ships. The identities `ID-nn` are defined in the public "
        f"specification.")


def annotate(text: str) -> str:
    """Append the footnote to a rendered document, once, if it needs one.

    Idempotent: a document that already carries the marker is returned
    unchanged, so nesting a report inside a larger one cannot stack notes.
    """
    if not text or MARKER in text:
        return text
    refs = internal_refs(text)
    return f"{text}\n\n{footnote(refs)}" if refs else text
