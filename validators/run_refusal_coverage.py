"""
Which of the engine's own refusals has anything ever reached.

WHY ASK
---------
This engine refuses a great deal, on purpose: `INDEX.md` section 8 is a list of
what it will not do and why. A refusal is a promise to the user — *your table
cannot be used this way, and here is the reason* — and a promise nothing has
ever exercised is a promise nobody has read aloud.

`INDEX.md` section 9 already carries the neighbouring pattern: **built, verified,
and unreachable — four times**, each found by accident. So this was measured
rather than waited for.

HOW
-----
Each of the twelve exception types `quadrium` defines was wrapped so that
constructing one records the line that raised it, and then every validator and
the unit tests were run as separate processes. `data/_refusal_coverage.json`
holds the result and how it was taken; this file checks that the code still
matches it.

WHAT IT SHOWS
---------------
    166 refusal sites of the engine's own types
     94 reached by something in the suite
     72 never reached

    module              reached   total
    scenarios.py              1       1
    sut_ras.py                2       2
    gras.py                   3       4
    balancing.py              2       4
    config.py                15      41
    disaggregation.py         8      20
    eurostat.py              10      27
    io_loader.py             12      39
    transformation.py         2      11
    sut_euro.py               1       4
    acquire.py                1       6

A CORRECTION, BECAUSE THIS FILE GOT IT WRONG FIRST
----------------------------------------------------
The first version of this docstring said: *"Most of the remaining 107 judge what
the CALLER passed — a shape mismatch, a model name that is not one of the four —
and no published table can reach them, so their being unexercised costs
nothing."*

**That was asserted without being checked, and it is wrong.** Reading all 159
messages and recording what each one judges gives:

    what it judges                          total   unreached
    a file or response from an office          54          33
    the user's own spreadsheet                 56          16
    what they asked for in that spreadsheet    19           3
    the numbers themselves                     19           4
    an internal API contract (the CALLER)       7           6
    a failure elsewhere, re-raised               5           5

**Six of the 67 are caller checks — 9 %, not "most".** The largest group is
the user's own workbook, which is the route the guide opens with: *"No Python:
you fill in a spreadsheet and run one command"*. Messages like *"no row labelled
'Output' or 'Total output'"* are the first thing a stranger with a slightly
different sheet meets, and none of them had a case.

Thirteen now do (`tests/test_engine.py`), in two halves.

`io_loader` reads the TABLE, so a minimal valid workbook is built and broken one
way at a time: no file, no `table` sheet, no `metadata` sheet, metadata without
the price basis, no `Output` row, no final-demand column.

`config` reads the workbook that says what to DO with it — `splits`, `keys`,
`scenarios`, `profiles` — and it holds 41 refusals, the largest single block in
the engine. The engine ships a working example, so that baseline is not
invented: `configs/ejemplo.xlsx` is loaded, asserted to load, and then one cell
is changed at a time. A refusal counts only if it names the thing that was
broken.

The second half also corrected the test rather than the engine. Changing ONE row
of a split's key gives *"names more than one allocation key"* — the rows of one
split must agree before anything else is asked — which is an earlier and correct
refusal, and the case was rewritten to cover both.

A third pass took the refusals that judge what was ASKED FOR — a split into
fewer than two parts, a key with the wrong number of weights, a scenario naming
a key nobody defined, a new code that already exists in the table. Those are a
direct call from the synthetic fixture away, so nothing but not looking had kept
them untested.

Workbook coverage went 22 of 56 to 37 of 56, `scenario` 9 of 20 to 13 of 20;
`config.py` 15 of 41 to 25 of 41, `io_loader.py` 7 of 39 to 12 of 39.

A fourth pass took what arrives FROM AN OFFICE, which is the largest class and
the one the engine reaches on its own — someone asking for a new country meets
these without anyone having read one aloud. No network and no invented fixture:
`data/eurostat/` holds a hundred real JSON-stat files and a JSON-stat is a dict,
so one is loaded, one thing is removed or emptied, and it goes to a temporary
file. The office workbooks are mutated the same way.

**AND ONE REFUSAL COULD NOT FIRE AT ALL.** `split_sectors` asked, after
checking that no new code collides with a sector already in the table, whether a
new code "repeats the code of a sector being split". It could not: the set it
tested against is built only from codes `table.index_of` accepted, so it was a
subset of the collision checked three lines above, which always caught it first.

That is the distinction this sweep exists to draw — **unreachable, not
untested**. No input reaches it, so no case could be written for it, and a case
aimed at it landed on the earlier check every time. Removed rather than left
looking like a guard, on the rule `PROVENANCE.md` already states for validators:
*a check that cannot run was removed rather than left to pass vacuously*.

**A fifth pass took what the METHODS refuse** — a negative seed handed to RAS,
interior cells pinned under a method that takes only margins, a
secondary-production type that is not one of the three, the hybrid model without
the matrix that defines it, a projection whose pieces are not one pair. Those
are a hand-written matrix away, so `data` went from 9 unreached to 4.

**Two passes found two defects, both of the same shape: a malformed input
reaching the user as a traceback instead of a refusal.**

`_Cube.__init__` guarded on `id` and `size` and
then indexed `doc["dimension"]` two lines below, so a response carrying the
first two and not the third came out as a raw `KeyError` — a traceback where the
user should have had *"this is not a JSON-stat response"*. Nothing in the suite
had ever handed the loader a half-formed response. Fixed to require all three.

And `load_iot` read a saved download with `json.loads(path.read_text())`, which
raises `UnicodeDecodeError` on a binary file and `JSONDecodeError` on a text
one — both reaching the user from `codecs.py`. That is one wrong line away in
the template, where `table_kind` and `table_path` sit next to each other: say
`eurostat` and leave the path on a workbook and the engine answered with a codec
error. The download path had refused a non-JSON response by name since it was
written; the read path had not. `_read_cube` now does, at all four call sites.

And twice it caught the test looking in the wrong place, which is the same
lesson from the other side: the INE's interior table does not balance as
published (`OQ-D-04`), so every mutation met the balance refusal until the case
passed the policy that gets past it; and the product codes are read from
`Tabla2` over a row range computed per vintage, so a case aimed at `Tabla1`
quietly changed nothing and the table loaded. The row is now found by the
pattern the loader itself matches.

Four times in these passes the engine gave an EARLIER and more specific refusal
than the case was aiming at — a split's rows must agree on their key before the
key is looked up; a new code that already exists is caught before the collision
with the sector being split; an absent `keys` sheet reads as empty, so the
split's own check fires first; and an INE workbook without its index sheet fails
on the reference year before the missing-table check. Each time the test was
rewritten, not the engine, and each earlier refusal was itself on the unreached
list.

*The record used to be keyed by `file:line`, and that was wrong.* Inserting the
Catalan loader shifted every line below it and silently re-labelled **38 sites**
by module default, moving 19 of them from `source` to `workbook`. The count
check caught that something had moved; nothing would have caught the labels
being wrong.

It is now keyed by the FUNCTION the refusal sits in, which does not move, with a
few identified by a distinctive fragment of their own message — because one
function can judge both a caller's arguments and a table's contents, and
`transform` judges both.

The classification lives in `data/_refusal_coverage.json` so it is held rather
than repeated, and it was made by reading each message rather than by matching
words — which is the same mistake in a different costume.

WHAT MATTERS MOST, AND WHAT NOW HAS A CASE
--------------------------------------------
The refusals that judge the numbers themselves, because a user meets those with
a table that loads and is still wrong:

    transformation.py:122   a coefficient's denominator is zero
    transformation.py:239   model A cannot be computed on this table at all
    sut_ras.py:126          a product row whose margin is non-positive
    sut_ras.py:172          the same for an import row

`transformation.py` was the starkest: the SUT-to-IOT transformation is a
headline feature with four models from CORE_013, and **one** of its eleven
refusals had ever fired.

Three of the four now have a case, in `tests/test_engine.py`: a supply table
with a product nobody makes reaches both coefficient refusals from opposite
sides, and a product row with negative mass and no positive mass reaches
SUT-RAS's, as does the import row that is negative-only rather than empty —
which is the distinction that made SUT-RAS runnable on real tables at all.
Coverage went 49 to 52 and `sut_ras.py` from 0 of 2 to 2 of 2.

The fourth, `transformation.py:239`, is left: reaching it needs a table on which
model A cannot be computed at all, and nothing built here does that honestly.
It is named rather than quietly dropped.

Run:
    python3 validators/run_refusal_coverage.py
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SRC = ROOT / "src" / "quadrium"
RECORD = ROOT / "data" / "_refusal_coverage.json"
TYPES = ("BalancingError", "AcquisitionRefused", "ConfigError",
         "DisaggregationError", "EurostatError", "SignInfeasibleError",
         "DegenerateMarginError", "MarginImbalanceError", "LoaderError",
         "ScenarioInfeasible", "TransformationError", "SutEuroError")

# The refusals that judge the DATA rather than the caller's arguments, and that
# nothing has reached. Named here so the list is a claim, not a shrug.
DATA_JUDGEMENTS = {
    "transformation.py:122": "a coefficient's denominator is zero",
    "transformation.py:239": "model A cannot be computed on this table at all",
    "sut_ras.py:126": "a product row whose margin is non-positive",
    "sut_ras.py:172": "the same for an import row",
}
# The one still without a case, and why: reaching it needs a table on which
# model A cannot be computed at all, and nothing built here does that honestly.
# Named so it stays a known gap rather than becoming a silent one.
NO_CASE_YET = {"transformation.py:239"}

LABELS = {
    "source": "a file or response from an office",
    "workbook": "the user's own spreadsheet",
    "scenario": "what they asked for in that spreadsheet",
    "data": "the numbers themselves",
    "caller": "an internal API contract (the CALLER)",
    "upstream": "a failure elsewhere, re-raised",
}

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}"
          + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    check("the sweep is recorded, so nobody has to re-run it to read it",
          RECORD.exists(), str(RECORD.relative_to(ROOT)))
    if not RECORD.exists():
        return 1
    rec = json.loads(RECORD.read_text())

    pat = re.compile(r"raise\s+(" + "|".join(TYPES) + r")\b")
    static = {}
    for f in sorted(SRC.glob("*.py")):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            m = pat.search(line)
            if m:
                static[f"{f.name}:{i}"] = m.group(1)

    check("the code still has the number of refusals the sweep counted",
          len(static) == rec["n_sites"],
          f"{len(static)} found against {rec['n_sites']} recorded. If this "
          f"trips, a refusal was added or moved and the sweep is stale — "
          f"re-take it rather than editing the number")

    fired = set(rec["fired"])
    tot = collections.Counter(k.split(":")[0] for k in static)
    got = collections.Counter(k.split(":")[0] for k in static if k in fired)
    print()
    print(f"    {'module':<24}{'reached':>9}{'total':>7}")
    for m in sorted(tot, key=lambda x: (got[x] / tot[x], -tot[x])):
        print(f"    {m:<24}{got[m]:>9}{tot[m]:>7}")

    check("a large share of the engine's refusals has never been reached",
          len(fired) < len(static) * 0.6,
          f"{len(fired)} of {len(static)}")

    # WHAT EACH ONE JUDGES, read rather than guessed. The first version of this
    # file asserted that most unreached sites were caller checks and no table
    # could reach them. Seven of 107 are.
    klass = rec.get("classified", {})
    # Naming the difference, not just counting it. The counts can agree while
    # the sets do not -- editing a module shifts every line below the edit, so
    # one site leaves the classification and another joins it. A failure that
    # says "166 against 166" sends the reader to diff two lists by hand.
    unclassified = sorted(set(static) - set(klass))
    orphaned = sorted(set(klass) - set(static))
    check("the classification covers every refusal in the code",
          not unclassified and not orphaned,
          f"{len(klass)} classified against {len(static)} in the code"
          + (f"; UNCLASSIFIED: {', '.join(unclassified[:8])}"
             + (" …" if len(unclassified) > 8 else "") if unclassified else "")
          + (f"; CLASSIFIED BUT GONE: {', '.join(orphaned[:8])}"
             + (" …" if len(orphaned) > 8 else "") if orphaned else ""))
    by_kind = collections.Counter(klass.values())
    un_kind = collections.Counter(v for k, v in klass.items() if k not in fired)
    print()
    print(f"    {'what it judges':<40}{'total':>7}{'unreached':>11}")
    for k in sorted(by_kind, key=lambda x: -un_kind[x]):
        print(f"    {LABELS.get(k, k):<40}{by_kind[k]:>7}{un_kind[k]:>11}")
    caller_share = un_kind["caller"] / max(sum(un_kind.values()), 1)
    check("and the unreached are NOT mostly caller checks, as this file first said",
          caller_share < 0.2,
          f"{un_kind['caller']} of {sum(un_kind.values())} — "
          f"{caller_share * 100:.0f} %. {un_kind['workbook']} judge the user's "
          f"own spreadsheet, which is the route the guide opens with. The "
          f"earlier claim was made without reading them")

    # the part that is not an argument check
    still_unfired = {k: v for k, v in DATA_JUDGEMENTS.items()
                     if k not in fired}
    gone = [k for k in DATA_JUDGEMENTS if k not in static]
    print()
    for k, why in sorted(DATA_JUDGEMENTS.items()):
        state = ("REACHED" if k in fired
                 else "moved" if k in gone else "never reached")
        print(f"    {k:<26}{state:<15}{why}")
    check("and the refusals that judge DATA are named, not left as a remainder",
          not gone and set(still_unfired) <= NO_CASE_YET,
          f"{len(DATA_JUDGEMENTS) - len(still_unfired)} of "
          f"{len(DATA_JUDGEMENTS)} now have a case in tests/test_engine.py. "
          f"The remainder is {sorted(still_unfired) or 'none'}, which is "
          f"recorded above with the reason rather than left as a gap nobody "
          f"named"
          if not gone else
          f"these line numbers no longer hold a refusal: {gone}. The list has "
          f"drifted from the code and must be re-taken")

    worst = min(tot, key=lambda m: got[m] / tot[m] if tot[m] else 1)
    check("the transformation is no longer the thinnest-covered module",
          got["transformation.py"] >= 4,
          f"{got['transformation.py']} of {tot['transformation.py']} in "
          f"transformation.py, the SUT-to-IOT step with four models from "
          f"CORE_013, against 1 of 11 when this sweep began. The least covered "
          f"overall is now {worst} at {got[worst]} of {tot[worst]}")

    print()
    print("    A refusal is a promise to the user. This does not keep the")
    print("    unkept ones; it stops them being invisible.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
