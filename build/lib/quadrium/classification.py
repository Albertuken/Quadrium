"""
Is this proposed split a legitimate subdivision, or just a list of codes?

Implements what `library/specs/B_method_cards/M-049` takes from NACE Rev. 2.1:
the hierarchy, the code arithmetic, and the limit on how deep a split can go.

WHAT IT CHECKS, AND WHAT IT DELIBERATELY DOES NOT
-------------------------------------------------
Checks: that the parent's level is splittable, that each child is the parent's
code plus exactly one digit, that children are distinct, and that none repeats
the parent.

Does **not** check that the children EXHAUST the parent. CORE_030 p. 14 requires
that a position's "scope is exhausted by the positions subordinated to it at the
next" more granular level, but confirming it needs the classification's own list
of children — the ~400 pages the package's index says to consult per code and
never to ingest. So the report says `coverage: not checked`, out loud, rather
than implying a check that did not happen. A validator that quietly narrows its
own claim is worse than no validator.

Nor does it translate between classifications. NACE ↔ ISIC ↔ CPA ↔ CNAE ↔ SIC is
`D_open_questions.md` OQ-S-01, still open, still needing CORE_026.

UNRECOGNISED CODES ARE NOT ERRORS
---------------------------------
A table may use codes that are not a classification at all — the project's own
synthetic fixture uses AGR, MAN, HOT. Those are reported as unparsed and the
split proceeds. Refusing them would be this module inventing a rule that no
source states.
"""

from __future__ import annotations

import re

import re
from dataclasses import dataclass, field

# NACE Rev. 2.1 levels, by digit count of the numeric part (CORE_030 p. 13).
_LEVELS = {2: "division", 3: "group", 4: "class"}
_NATIONAL_LEVEL = {5: "national subclass"}

# A code as tables actually write it: an optional section letter, then digits
# with optional dots. "I56", "56", "56.1", "C25.91", "5610" all parse.
_CODE = re.compile(r"^\s*(?P<section>[A-Za-z]{0,2})\s*(?P<digits>[\d.]+)\s*$")


@dataclass(frozen=True)
class Classification:
    """A classification and how deep it goes.

    `max_digits` is 4 for NACE itself and 5 for a national version, which
    CORE_030 p. 15 permits "usually by adding a fifth digit for national
    purposes" provided it still nests.
    """
    name: str = "NACE"
    revision: str = "Rev. 2.1"
    max_digits: int = 4

    @property
    def levels(self) -> dict:
        out = dict(_LEVELS)
        if self.max_digits >= 5:
            out.update(_NATIONAL_LEVEL)
        return out

    def parse(self, code: str) -> str | None:
        """Code as written -> bare digits, or None if it is not a code.

        The section letter is dropped because it is not part of the numeric
        code: CORE_030 p. 13 "The code for the section level is not integrated
        in the NACE code" that identifies division, group and class.
        """
        m = _CODE.match(str(code))
        if not m:
            return None
        digits = m.group("digits").replace(".", "")
        return digits if digits.isdigit() else None

    def level_of(self, code: str) -> str | None:
        d = self.parse(code)
        return self.levels.get(len(d)) if d else None


NACE_REV_2_1 = Classification("NACE", "Rev. 2.1", 4)
# A national version: the UK SIC 2007 and the Spanish CNAE-2009 both nest into
# NACE and both write a section letter in front in published IO tables.
NATIONAL_NACE = Classification("NACE national version", "derived", 5)


@dataclass
class SplitCheck:
    parent: str
    children: list[str]
    classification: Classification | None = None
    parent_level: str | None = None
    parsed: bool = False
    problems: list[str] = field(default_factory=list)
    unchecked: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def summary(self) -> str:
        if not self.parsed:
            return (f"{self.parent} -> {', '.join(self.children)}: codes are not "
                    f"in a recognised classification, so the hierarchy was not "
                    f"checked")
        head = (f"{self.parent} ({self.parent_level}) -> "
                f"{', '.join(self.children)}")
        if self.problems:
            return head + "; " + "; ".join(self.problems)
        return head + f"; hierarchy OK, {', '.join(self.unchecked)}"


def check_split(parent: str, children: list[str],
                classification: Classification | None = None) -> SplitCheck:
    """Validate a proposed subdivision against the classification's own rules."""
    cls = classification or NATIONAL_NACE
    chk = SplitCheck(parent=parent, children=list(children), classification=cls)

    p = cls.parse(parent)
    kids = {c: cls.parse(c) for c in children}
    if p is None or any(v is None for v in kids.values()):
        chk.unchecked.append("codes not parsed as a classification")
        return chk
    chk.parsed = True

    chk.parent_level = cls.levels.get(len(p))
    if chk.parent_level is None:
        chk.problems.append(
            f"a {len(p)}-digit code is not a level of {cls.name} {cls.revision} "
            f"(levels: {', '.join(f'{k} digits = {v}' for k, v in sorted(cls.levels.items()))})")
        return chk
    if len(p) >= cls.max_digits:
        chk.problems.append(
            f"{parent} is already at the deepest level {cls.name} "
            f"{cls.revision} defines ({chk.parent_level}); splitting it further "
            f"is outside the classification. A national version may add one "
            f"more digit (CORE_030 p. 15), but the table must say so")
        return chk

    seen = set()
    # Over the LIST, not the dict: `kids` is keyed by code, so a repeated code
    # collapses into one entry and the duplicate check never fires. Found by
    # testing the duplicate case rather than by reading.
    for code in children:
        d = kids[code]
        if d == p:
            chk.problems.append(f"{code} repeats the parent code")
            continue
        if d in seen:
            chk.problems.append(f"{code} is listed twice")
            continue
        seen.add(d)
        if not d.startswith(p):
            chk.problems.append(
                f"{code} is not inside {parent}: a child's code is the "
                f"parent's plus one digit")
        elif len(d) != len(p) + 1:
            deeper = cls.levels.get(len(d), f"{len(d)} digits")
            chk.problems.append(
                f"{code} is a {deeper}, but {parent} is a {chk.parent_level}: "
                f"the hierarchy is not skippable, a {chk.parent_level} splits "
                f"into {cls.levels.get(len(p) + 1, 'the next level')}")

    if len(children) > 9:
        chk.problems.append(
            f"{len(children)} children, but a level is one digit, so at most 9 "
            f"are available")

    # Said out loud, every time. See the module docstring.
    chk.unchecked.append("coverage not checked: whether these children exhaust "
                         "the parent needs the classification's own list of "
                         "positions, which this project does not hold "
                         "(OQ-S-01)")
    nec = [c for c, d in kids.items() if d and d.endswith("9")]
    if nec:
        chk.unchecked.append(
            f"{', '.join(nec)} ends in 9, which in NACE marks an 'n.e.c.' "
            f"residual (CORE_030 p. 14); check it is meant as the catch-all")
    return chk

# ---------------------------------------------------------------------------
# ONS grouping notation -> NACE codes.  OQ-S-01, data half.
# ---------------------------------------------------------------------------

_ONS_ATOM = re.compile(r"^[A-Z]\d{2,4}[A-Z]?$")


def expand_ons_code(label: str) -> tuple[set[str], set[str]] | None:
    """The NACE codes an ONS IOAT column label covers, and the ones it excludes.

    `OQ-S-01` says the project's own UK fixture is "SIC 2007, not NACE, so even
    that familiar table needs a correspondence". Most of it needs none: **63 of
    the 104 labels are byte-identical to codes Eurostat publishes**, so the
    correspondence is the identity there. The rest are written in NACE notation
    with four grouping conventions, all self-describing:

        `B06 & B07`         union, ampersand or comma
        `C102_3`            union, underscore -- C102 and C103
        `C241T243`          range, "T" for "to"
        `L68BXL683`         difference, "X" for "excluding" -- as in `D21X31`
        `K65.1-2 & K65.3`   dotted groups, expanded to K651, K652, K653

    Returns `(covered, excluded)`, or `None` for a label this cannot parse.

    WHAT THIS DOES *NOT* DO, AND IT IS THE HALF THAT MATTERS.
    It does not verify that the codes it produces EXIST. Eurostat's IO datasets
    stop at the division level -- 150 distinct codes across every fixture here,
    none below two digits -- so `C101`, `D351` and `M691` cannot be checked
    against anything the project holds. Confirming them needs NACE's own class
    list, which `library/INDEX.md` records as deliberately not ingested and
    which `M-049` already says the software must admit it has not checked.

    So the output is a PARSE, not a validated mapping, and the distinction has
    teeth. **Three labels do not parse at all** -- `C23OTHER`, `C30OTHER`,
    `C33OTHER`, residuals meaning "the rest of this division" -- and return
    `None`. **Three more parse and should not be trusted**: `C20A`, `C20B` and
    `C20C` have the same shape as `L68A`, which IS a published CPA code, so this
    function accepts them; they are in fact an ONS split of C20 that NACE does
    not make. The parser cannot tell the two apart, because telling them apart
    requires the class list it does not have.

    Do not read a successful parse as a validated code. Carry the six as
    unmappable.
    """
    s = str(label).replace("&", ",").replace(" ", "")
    if not s:
        return None
    if "X" in s[1:]:
        head, _, tail = s.partition("X")
        covered, excluded = _ons_atoms(head), _ons_atoms(tail)
        return (covered, excluded) if covered and excluded else None
    out: set[str] = set()
    for part in s.split(","):
        if not part:
            continue
        atoms = _ons_atoms(part)
        if atoms is None:
            return None
        out |= atoms
    return (out, set()) if out else None


def _ons_atoms(part: str) -> set[str] | None:
    if "T" in part[1:]:
        m = re.match(r"^([A-Z])(\d+)T(\d+)$", part)
        if not m:
            return None
        letter, lo, hi = m.groups()
        if len(lo) != len(hi):
            return None
        return {f"{letter}{n}" for n in range(int(lo), int(hi) + 1)}
    if "_" in part:
        m = re.match(r"^([A-Z])(\d+)_(\d+)$", part)
        if not m:
            return None
        letter, lo, hi = m.groups()
        hi = lo[:len(lo) - len(hi)] + hi
        return {f"{letter}{lo}", f"{letter}{hi}"}
    if "." in part:
        m = re.match(r"^([A-Z]\d+)\.(\d)(?:-(\d))?$", part)
        if not m:
            return None
        base, lo, hi = m.groups()
        return {f"{base}{n}" for n in range(int(lo), int(hi or lo) + 1)}
    return {part} if _ONS_ATOM.match(part) else None
