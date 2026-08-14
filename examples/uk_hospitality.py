"""
Divide TWO sectors of the real UK table in one run.

  I55  Accommodation                    ->  hotels / other accommodation
  I56  Food and beverage service        ->  restaurants / catering / bars

Two sectors that trade with each other, split with different keys and different
input profiles, in a single scenario. That is the point of the multi-sector
extension: "split hotels by bedspaces and restaurants by employment" is an
ordinary request, and forcing one key set on both would be wrong.

⚠ THE PROXIES AND PROFILES ARE ILLUSTRATIVE, NOT REAL DATA.
Doing this properly needs ONS Business Register and Employment Survey or Annual
Business Survey figures by SIC 55.1/55.2/55.3 and 56.1/56.2/56.3. The table is
real; the split is not.

Run:
    python3 examples/uk_hospitality.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quadrium.io_loader import load_uk_analytical_iot  # noqa: E402
from quadrium.models import (AllocationKey, Assumption,  # noqa: E402
                              AssumptionLedger, ProxyStrength, Scenario,
                              SplitSpec)
from quadrium.project import IOProject  # noqa: E402

_ILLUSTRATIVE = ("ILLUSTRATIVE, NOT REAL DATA — replace with ONS BRES/ABS by "
                 "SIC 55.x and 56.x")
ALCOHOL = "C1101T1106 & C12"


def build_keys() -> dict:
    keys = [
        # I55 — accommodation
        AllocationKey(key_id="k55_bedspaces", applies_to="output",
                      new_sector_codes=["I551", "I559"],
                      raw_values=[820_000, 260_000],
                      source=_ILLUSTRATIVE, source_year=2023,
                      strength=ProxyStrength.WEAK),
        # I56 — food and beverage service
        AllocationKey(key_id="k56_employment", applies_to="output",
                      new_sector_codes=["I561", "I562", "I563"],
                      raw_values=[720_000, 120_000, 380_000],
                      source=_ILLUSTRATIVE, source_year=2023,
                      strength=ProxyStrength.WEAK),
        AllocationKey(key_id="k56_turnover", applies_to="output",
                      new_sector_codes=["I561", "I562", "I563"],
                      raw_values=[58_000, 9_500, 27_000],
                      source=_ILLUSTRATIVE, source_year=2023,
                      strength=ProxyStrength.WEAK),
    ]
    return {k.key_id: k for k in keys}


PROFILES = {
    # hotels: premises-heavy and cleaning-heavy; other accommodation less so
    "I551": {"L68BXL683": 1.30, "N81": 1.25},
    "I559": {"L68BXL683": 0.55, "N81": 0.70},
    # restaurants buy food, bars buy drink, caterers buy through wholesale
    "I561": {"C101": 1.35, "C102_3": 1.30, "C107": 1.15, "C108": 1.25,
             ALCOHOL: 0.55, "C1107": 0.85},
    "I562": {"C101": 1.20, "C108": 1.20, "G46": 1.30,
             "L68BXL683": 0.35, ALCOHOL: 0.70},
    "I563": {ALCOHOL: 2.10, "C1107": 1.45, "C101": 0.45, "C102_3": 0.35,
             "C107": 0.55, "C108": 0.50, "L68BXL683": 1.25},
}


def build_splits() -> list[SplitSpec]:
    """The two splits. Each names its own allocation key.

    Input profiles are NOT set here: they live on the scenario, which is a
    shared pool across splits. That is what lets one scenario run these same
    two splits "plain" and another run them "profiled".
    """
    return [
        SplitSpec("I55", ["I551", "I559"],
                  ["Hotels and similar accommodation", "Other accommodation"],
                  keys_by_block={"output": "k55_bedspaces"}),
        SplitSpec("I56", ["I561", "I562", "I563"],
                  ["Restaurants and mobile food service",
                   "Event catering and other food service",
                   "Beverage serving activities"],
                  keys_by_block={"output": "k56_employment"}),
    ]


def main() -> int:
    table = load_uk_analytical_iot(ROOT / "UK_IOAT_2023_domestic_ixi.xlsx")
    print(f"Loaded {table.table_id}: {table.n} industries")
    for code in ("I55", "I56"):
        i = table.index_of(code)
        print(f"  {code}: {table.sector_labels[i].strip()[:44]:44s} "
              f"output {table.X[i]:>9,.0f}  own diagonal {table.Z[i, i]:>8,.1f}")
    i55, i56 = table.index_of("I55"), table.index_of("I56")
    print(f"  they trade with each other: I55->I56 {table.Z[i55, i56]:,.1f}, "
          f"I56->I55 {table.Z[i56, i55]:,.1f}")

    ledger = AssumptionLedger(project_id="uk_hospitality")
    ledger.add(Assumption(
        assumption_id="A-01",
        description="Every allocation weight and every input intensity in this "
                    "run is illustrative. No figure here estimates the UK "
                    "economy.",
        applies_to="all splits", source=_ILLUSTRATIVE,
        validated_by="NOT VALIDATED", confidence=ProxyStrength.WEAK,
        impact_on_results="total"))
    ledger.add(Assumption(
        assumption_id="A-02",
        description="Two sectors are divided in one run. Their internal blocks "
                    "are disjoint and each split preserves the other's row and "
                    "column totals, so they are balanced independently and the "
                    "result does not depend on the order.",
        applies_to="multi-sector splitting",
        source="Project derivation; asserted in tests/test_engine.py",
        validated_by="regression test", confidence=ProxyStrength.STRONG,
        impact_on_results="none — it is why the procedure is well defined"))

    project = IOProject(
        project_id="uk_hospitality", table=table, splits=build_splits(),
        scenarios=[
            Scenario(scenario_id="S1_plain", label="Size only",
                     description="Both sectors split by size; no input "
                                 "profiles, so every subsector inherits its "
                                 "parent's purchasing pattern."),
            Scenario(scenario_id="S2_profiled",
                     label="Differentiated input structures",
                     description="Hotels buy premises and cleaning; bars buy "
                                 "drink; caterers buy through wholesale.",
                     input_profiles=PROFILES),
        ],
        keys=build_keys(), ledger=ledger,
        title="UK hospitality — two sectors divided in one run",
        source_file=ROOT / "UK_IOAT_2023_domestic_ixi.xlsx", root=ROOT / "outputs",
        preamble="> **Illustrative proxies and profiles.** The ONS table is "
                 "real; the split is not. See the assumption ledger.")
    project.run().write()

    print()
    for res in project.results:
        b, r = res.diagnostics["balance_info"], res.report
        print(f"  {res.scenario_id:<13s} {b['method']:<5s} conv={b['converged']} "
              f"iters={b['iterations_per_split']} "
              f"reagg={r.reaggregation_error_pct:.1e} % "
              f"signchg={b['sign_changes']} "
              f"-> {'PASS' if r.passed else 'FAIL'} ({r.n_warnings} warn)")
    print(f"\n  sectors after the split: {project.results[0].table.n} "
          f"(from {table.n})")
    print(f"\nProject folder: {project.dir}")
    return 0 if all(r.report.passed for r in project.results) else 1


if __name__ == "__main__":
    sys.exit(main())
