"""
The type II closure, in the engine rather than in a validator — and what it may not say.

WHY A SECOND FILE ON TYPE II
------------------------------
`run_type_ii_multipliers.py` settled the METHOD: it extracted `UNH_20` chapter
20, established that ¶20.90 eq. (45) and ¶20.94 eq. (46) are normative rather
than observed practice, reproduced Box 20.4's German example inside the bound an
integer-printed table supports, and measured the closure three ways on the UK
table. That work stands; nothing here repeats it.

What it did NOT do is put the closure where a user can reach it. It lived in a
validator, which means the engine could measure an induced effect and no
workbook could ask for one. This checks the feature: the arithmetic in
`diagnostics`, the two refusals in `config`, and the paragraph in the report
that stops the numbers being read the way the source does not support.

THE ONE THING THE FEATURE MUST NOT DO
---------------------------------------
Present a ranking. ¶20.88 names the income concept -- wages and salaries -- and
says nothing about what to divide the consumption column by when household
consumption is not funded by wages alone, which on the UK table it is not: the
column sums to 0.892 of wage income.

Closed three ways, the economy-wide uplift barely moves -- 1.573, 1.614, 1.612 --
and **the spread between industries nearly halves**, 1.02-3.10 against 1.20-2.31.
So the aggregate is firm and the order is not, and a report that prints a type II
column without saying so has published the half the Handbook does not support.
"""
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FIXTURE = ROOT / "UK_IOAT_2023_domestic_ixi.xlsx"
FAIL = []
NOTHING_CHECKED = 3


def check(label, ok, detail=""):
    print(f"  [{'ok' if ok else 'FAIL'}] {label}")
    if detail:
        print(f"         {detail}")
    if not ok:
        FAIL.append(label)


def main():
    if not FIXTURE.exists():
        print(f"    -- {FIXTURE.name} is absent.")
        print("\n" + "=" * 78)
        print("Nothing checked here.")
        return NOTHING_CHECKED

    from quadrium.config import ConfigError, _type_ii_spec
    from quadrium.diagnostics import compute, type_ii_multipliers
    from quadrium.io_loader import load_uk_analytical_iot
    from quadrium.models import Scenario, SplitSpec
    from quadrium.reporting import scenario_section
    from quadrium.scenarios import run_scenario

    t = load_uk_analytical_iot(FIXTURE)
    X = np.asarray(t.X, float)
    d = compute(np.asarray(t.Z, float), X)
    wages = np.asarray(t.VA, float)[list(t.VA_labels).index(
        "Compensation of employees")]
    hh = np.asarray(t.Y, float)[:, list(t.Y_labels).index("P3 S14")]
    live = X > 0

    # 1 -- the arithmetic reproduces what the method validator measured.
    r = type_ii_multipliers(d["A"], wages, hh, X)
    m1, m2 = d["multipliers"][live], r["multipliers"][live]
    check("every multiplier grows, because closing adds a channel and removes "
          "none",
          bool((m2 >= m1 - 1e-9).all()),
          f"mean ratio {(m2 / m1).mean():.3f}")
    check("and the engine reproduces the figure the method validator measured",
          abs((m2 / m1).mean() - 1.573) < 0.002,
          f"{(m2 / m1).mean():.4f} against 1.573 — the same table closed the "
          f"same way, computed by two independent pieces of code")
    check("the closure it used is reported and not left implicit",
          abs(r["propensity"] - 0.892) < 0.002,
          f"propensity {r['propensity']:.3f} — household consumption is 89 % "
          f"of wage income here, so the normalisation is a live choice and "
          f"paragraph 20.88 does not make it")

    # 2 -- a closure on nothing is refused rather than returning type I.
    try:
        type_ii_multipliers(d["A"], np.zeros_like(wages), hh, X)
        check("closing on rows that sum to zero is refused", False,
              "it returned numbers")
    except ValueError as exc:
        check("closing on rows that sum to zero is refused",
              "no loop to close" in str(exc),
              "it would return the type I multipliers unchanged, which reads "
              "as a finding about an economy where spending does not "
              "circulate")

    # 3 -- the workbook's two refusals, which are about naming the wrong row.
    for meta, want, why in (
            ({"type_ii_income_rows": "Compensation of employees"},
             "BOTH", "income that is never spent is half a loop"),
            ({"type_ii_income_rows": "Wages",
              "type_ii_household_column": "P3 S14"},
             "does not have", "closing on the wrong row does not fail"),
            ({"type_ii_income_rows": "Compensation of employees",
              "type_ii_household_column": "nope"},
             "does not have", "nor does spending the wrong column")):
        try:
            _type_ii_spec(meta, t)
            check(f"refused: {why}", False, "it was accepted")
        except ConfigError as exc:
            check(f"refused: {why}", want in str(exc), str(exc)[:90])
    check("and a workbook that asks for neither gets no closure",
          _type_ii_spec({}, t) == {},
          "type II is opt-in; a table without the keys is type I and says so "
          "by saying nothing")

    # 4 -- through a real run, and into the report.
    t.type_ii = _type_ii_spec(
        {"type_ii_income_rows": "Compensation of employees",
         "type_ii_household_column": "P3 S14"}, t)
    from quadrium.models import AllocationKey, ProxyStrength
    keys = {"k": AllocationKey(
        key_id="k", applies_to="output",
        new_sector_codes=["I561", "I562", "I563"],
        raw_values=[720000.0, 120000.0, 380000.0],
        source="illustrative", source_year=2023,
        strength=ProxyStrength.WEAK)}
    res = run_scenario(
        t, [SplitSpec("I56", ["I561", "I562", "I563"],
                      ["a", "b", "c"], keys_by_block={"output": "k"})],
        Scenario(scenario_id="S1", label="size only", description="base"),
        keys)
    check("a run carries the closure through the split",
          "type_ii" in res.diagnostics
          and len(res.diagnostics["type_ii"]["multipliers"]) == res.table.n,
          "the split changes neither axis, so the labels carry forward")

    md = scenario_section(res)
    check("the report prints type I beside type II, not type II alone",
          "| type I | type II |" in md.replace("Subsector | ", ""),
          "a type II column on its own invites the comparison the source "
          "does not support")
    check("and says the aggregate is solid while the ranking is not",
          "aggregate uplift is solid" in md and "do not read the order" in md,
          "1.573 / 1.614 / 1.612 against a spread that nearly halves")
    check("and states the closure the numbers came from",
          "of the income you named" in md and "0.892" in md,
          "which normalisation produced these figures, since 20.88 does not "
          "choose one")
    check("and warns that the subsectors inherit the parent's income "
          "coefficient",
          "inherit the parent's income coefficient" in md,
          "the split divided value added by the allocation key, so nothing "
          "says one subsector pays more wages per unit of output")

    print()
    print("    The uplift is a result. The order between subsectors is a")
    print("    choice the Handbook declines to make, and the report has to")
    print("    say which of the two the reader is looking at.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
