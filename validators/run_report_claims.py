"""
Every number the report tells a user, against the validator it cites.

THE GAP THIS FILLS, NAMED BY THE FILE NEXT DOOR
-------------------------------------------------
`run_docs_current.py` audits the countable half of the documentation and says so
in its own output: *"What this cannot check is prose. A sentence that was true
when written and is false now will pass here."*

The report is prose, and it is the only prose a user actually reads. It carries
about forty figures — how much a split costs, what a real key is worth, what
balancing gives back — and every one of them comes from a validator that
measured it. When the evidence base widened this week those measurements moved,
and the report had to be chased by hand each time. It was chased imperfectly:
six figures sat stale in the user's report for hours before the next pass caught
them.

WHAT IS CHECKED
-----------------
Each numeric claim in `reporting.py` is paired with the validator cited nearest
to it, and the number must appear in that validator's source.

**The tolerance is the report's own printed precision.** A claim of `1.2` is met
by anything from 1.15 to 1.25; a claim of `27.4` by 27.35 to 27.45. That is
`precision.assertable_tolerance`'s rule — half of the last printed digit —
applied to prose instead of to a table, and it is what keeps a rounding
difference from reading as a contradiction. Matching the strings instead would
fail on 3 of 8 sample pairs purely for writing `pp` where the validator writes
`points`.

AND THE PATHS, WHICH IS WHERE THE FIRST DEFECT WAS
----------------------------------------------------
The report cites validators by path, and this file runs in BOTH trees: the
private one keeps them under `validators/`, the public one — where a
user actually runs the engine — under `validators/`. One citation had the
private prefix hard-coded, so the path it handed a public user did not exist.
Fifteen others used two other spellings. All twenty now use the one form that
resolves in both.

WHAT THIS DOES NOT SHOW
-------------------------
That a claim and its validator agree does **not** make either right. What
establishes the figures is the validators themselves, run against tables the
offices published. This catches drift between what was measured and what is
told, which is a narrower and more mundane failure — and the one that actually
happened, five times in five days.

Run:
    python3 validators/run_report_claims.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

REPORTING = ROOT / "src" / "quadrium" / "reporting.py"
VDIR = Path(__file__).resolve().parent
FAIL: list[str] = []

# Numbers that are not measurements: cut points, alphas, section numbers and the
# like, plus the years and paragraph references that belong to the sources.
NOT_A_MEASUREMENT = re.compile(r"^(0|1|2|3|4|5|18|19|20|65|89|100|1000)$")

CITE = re.compile(r"`validators/(run_[a-z_0-9]+\.py)`")
# A claim is a number the report emphasises or qualifies: bolded, a percentage,
# an "N of M", or a correlation.
CLAIM = re.compile(
    r"\*\*([0-9][0-9.,]*)\s*%?\*\*"
    r"|([0-9]+\.[0-9]+)\s*(?:%|points|pp)"
    r"|([0-9]+)\s+of\s+([0-9]+)"
    r"|r\s*=\s*([+-]?[0-9]+\.[0-9]+)")


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}"
          + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def printed_tolerance(text: str) -> float:
    """Half of the last digit the claim actually prints.

    The same rule `precision.assertable_tolerance` applies to a published table,
    applied to a sentence: a number written to one decimal asserts nothing
    finer than 0.05 either side of itself.
    """
    body = text.replace(",", "")
    return 0.5 * 10 ** -(len(body.split(".")[1]) if "." in body else 0)


def numbers_in(text: str) -> list[float]:
    out = []
    for m in re.finditer(r"[0-9]+(?:\.[0-9]+)?", text.replace(",", "")):
        try:
            out.append(float(m.group()))
        except ValueError:
            pass
    return out


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    check("the report module is where this expects it",
          REPORTING.exists(), str(REPORTING.relative_to(ROOT)))
    if not REPORTING.exists():
        return 1
    lines = REPORTING.read_text().splitlines()

    # 1 -- every cited path must resolve in THIS tree, whichever tree it is.
    cited = sorted({m for line in lines for m in CITE.findall(line)})
    missing = [c for c in cited if not (VDIR / c).exists()]
    print()
    print(f"    {len(cited)} distinct validators cited, in "
          f"{VDIR.relative_to(ROOT)}")
    check("every validator the report points a user at exists here",
          not missing,
          f"all {len(cited)} resolve" if not missing
          else f"missing: {', '.join(missing)}")

    # THE NEEDLE CANNOT BE A LITERAL THE SYNC REWRITES.
    #
    # `sync_public.py` rewrites the private tree's `library/` + `validators/`
    # into the public tree's `validators/` in everything it copies, INCLUDING
    # validator source. Written as a literal, this test became
    # `if "validators/" in line` in the public tree and failed against all 22
    # legitimate citations. The rewrite is right when the string is a path
    # being USED -- `run_p2_sweep.py` spells one out and is translated
    # correctly -- and wrong when it is a path being SEARCHED FOR. Assembled
    # from parts, it survives the copy.
    private_prefix = "library" + "/" + "validators/"
    stale_prefix = [i + 1 for i, line in enumerate(lines)
                    if private_prefix in line]
    check("no citation assumes the private tree's layout",
          not stale_prefix,
          f"the public tree keeps validators one level up, so a citation "
          f"carrying the private prefix hands a user a path that does not "
          f"exist: line(s) {stale_prefix}"
          if stale_prefix else
          f"none of the {len(cited)} carries it, checked in "
          f"{VDIR.relative_to(ROOT)}")

    # 2 -- pair each claim with the validator cited nearest below it, since the
    #      report states a figure and then names its source.
    pairs, uncited = [], []
    for i, line in enumerate(lines):
        # ONLY WHAT REACHES THE USER. The report is built from string literals;
        # everything else in the module is commentary, and this was scanning it
        # too -- pulling numbers out of comments about the pilot's history and
        # reporting them as uncited claims. A line counts when it is a string
        # literal, which for this file means it starts with a quote.
        stripped = line.strip()
        if not (stripped.startswith('"') or stripped.startswith('f"')
                or stripped.startswith("'") or stripped.startswith("f'")):
            continue
        found = [m for m in CLAIM.finditer(line)]
        if not found:
            continue
        # EVERY validator named nearby, not the first one below. A section of
        # the report states several figures and cites several sources, in no
        # fixed order -- taking the nearest citation below attributed the size
        # screen's numbers to the carry-over study simply because that citation
        # came first in the sentence. A claim counts as supported if ANY source
        # the section names still carries it.
        near = set()
        for j in range(max(0, i - 8), min(i + 30, len(lines))):
            near.update(CITE.findall(lines[j]))
        cite = sorted(near) or None
        for m in found:
            raw = next(g for g in m.groups() if g)
            if NOT_A_MEASUREMENT.match(raw.replace(",", "")):
                continue
            if m.group(3) and m.group(4):        # "N of M" -- check the pair
                raw = f"{m.group(3)} of {m.group(4)}"
            (pairs if cite else uncited).append((i + 1, raw, cite))

    print()
    print(f"    {len(pairs)} claim(s) with a cited validator, "
          f"{len(uncited)} without")
    check("most of what the report asserts names what measured it",
          len(pairs) > len(uncited),
          f"{len(pairs)} cited against {len(uncited)} not. An uncited figure "
          f"is not wrong, but nothing here can tell whether it has drifted")

    # 3 -- the substance
    bad = []
    for lineno, raw, cites in pairs:
        ok = False
        for c in cites:
            src = (VDIR / c).read_text()
            if " of " in raw:
                a, b = raw.split(" of ")
                ok = (raw in src) or (f"{a} of {b}" in src.replace(",", ""))
            else:
                want = float(raw.replace(",", ""))
                tol = printed_tolerance(raw)
                ok = any(abs(v - want) <= tol for v in numbers_in(src))
            if ok:
                break
        if not ok:
            bad.append((lineno, raw, ", ".join(cites)))

    print()
    for lineno, raw, cite in bad:
        print(f"    reporting.py:{lineno}  '{raw}'  not found in {cite}")
    check("every cited claim still appears in the validator that made it",
          not bad,
          f"{len(pairs)} checked at their own printed precision"
          if not bad else
          f"{len(bad)} of {len(pairs)} have drifted — the report is telling a "
          f"user a number its own source no longer produces")

    if uncited:
        print()
        print("    figures with no validator named in their section:")
        for lineno, raw, _ in uncited[:12]:
            print(f"      reporting.py:{lineno}  '{raw}'")
        if len(uncited) > 12:
            print(f"      … and {len(uncited) - 12} more")

    print()
    print("    Agreement is not correctness. The validators are what establish")
    print("    these figures; this only catches the report drifting away from")
    print("    them, which is the failure that actually kept happening.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
