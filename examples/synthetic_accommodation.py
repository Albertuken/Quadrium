"""
MVP 0.1 pilot: split "Accommodation & food services" into four subsectors.

Synthetic, country-agnostic table (MVP_0.1 §0), built so that it balances
exactly and so that it contains the kinds of negative entries a real table has.
That last point is deliberate and is the whole reason the June spec's choice of
RAS had to change:

  * Z[OTH, ACC] = -8   — a negative intermediate cell, of the kind a
    fixed-industry-sales transformation produces (CORE_005 ¶36.61, p. 1019;
    A_core_accounting_spec.md §A.8.1)
  * inventories negative for AGR and OTH — withdrawals exceeding additions
    (CORE_003 Table 15.8, p. 499)
  * net taxes on production negative for AGR — a net subsidy position
    (CORE_003 ¶15.93, p. 495)

Run:
    python3 examples/synthetic_accommodation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quadrium.models import (AllocationKey, Assumption, AssumptionLedger,
                              IOTable, ProxyStrength, Scenario, SplitSpec)
from quadrium.project import IOProject



def build_table() -> IOTable:
    codes = ["AGR", "MAN", "ACC", "TRA", "OTH"]
    labels = ["Agriculture", "Manufacturing",
              "Accommodation & food services", "Transport", "Other services"]

    Z = np.array([
        [20, 180,  60,  5,  15],
        [35, 420, 110, 60, 140],
        [ 2,  18,  12,  6,  25],
        [ 8,  55,  20, 40,  35],
        [25, 150,  -8, 30, 220],      # legitimate negative
    ], float)

    Y = np.array([                    # HH, GFCF, Inventories, Exports
        [ 90,  10, -12,  40],
        [380, 260,  25, 500],
        [300,   5,   0,  60],
        [120,  20,   0,  90],
        [700, 120,  -5, 150],
    ], float)

    VA = np.array([                   # Compensation, Net taxes, Gross op. surplus
        [150, 620, 140, 150, 600],
        [-18,  35,  12,   8,  22],
        [186, 452,  82,  89, 325],
    ], float)

    X = Z.sum(axis=1) + Y.sum(axis=1)
    return IOTable(
        table_id="SYNTH-ACC-2024", country="Synthetica", year=2024,
        unit="million EUR, current prices, basic prices",
        classification="NACE Rev.2 (illustrative)",
        sector_codes=codes, sector_labels=labels,
        Z=Z, Y=Y, Y_labels=["HH consumption", "GFCF", "Inventories", "Exports"],
        VA=VA, VA_labels=["Compensation of employees",
                          "Taxes less subsidies on production",
                          "Gross operating surplus"],
        X=X, source="Synthetic example, IO Model Foundry MVP 0.1",
        notes="Contains legitimate negatives by design; see module docstring.")


def build_keys() -> dict:
    new_codes = ["HOT", "CAM", "RES", "FBS"]
    emp = AllocationKey(
        key_id="key_employment", applies_to="output",
        new_sector_codes=new_codes, raw_values=[12500, 1800, 34200, 9100],
        source="National Statistics Office, Annual Tourism Survey",
        source_year=2022, strength=ProxyStrength.STRONG)
    gva = AllocationKey(
        key_id="key_gva", applies_to="value_added",
        new_sector_codes=new_codes, raw_values=[15200, 1500, 30100, 7800],
        source="National Statistics Office, Structural Business Statistics",
        source_year=2022, strength=ProxyStrength.STRONG)
    turnover = AllocationKey(
        key_id="key_turnover", applies_to="output",
        new_sector_codes=new_codes, raw_values=[18900, 2100, 41500, 11200],
        source="Sector association report",
        source_year=2021, strength=ProxyStrength.WEAK)
    # NOTE the years. The table is 2024 and these proxies are 2022 and 2021,
    # deliberately: a proxy almost always lags the table it splits, and this is
    # the only fixture in the repo where `check_key_vintage` fires. Aligning
    # them would make the example less realistic and silence the one warning
    # that demonstrates the check works. tests/test_engine.py asserts the gap.
    return {k.key_id: k for k in (emp, gva, turnover)}


def build_scenarios() -> list[Scenario]:
    return [
        Scenario(scenario_id="S1_employment", label="Employment",
                 description="Everything split by employment.",
                 keys_by_block={"output": "key_employment"}),
        Scenario(scenario_id="S2_gva", label="Gross value added",
                 description="Everything split by GVA.",
                 keys_by_block={"output": "key_gva"}),
        Scenario(scenario_id="S3_mixed", label="Mixed",
                 description="Output and intermediates by employment, value "
                             "added by GVA, final demand by turnover.",
                 keys_by_block={"output": "key_employment",
                                "value_added": "key_gva",
                                "final_demand": "key_turnover"}),
    ]


def main() -> int:
    table = build_table()
    keys = build_keys()
    scenarios = build_scenarios()
    new_codes = ["HOT", "CAM", "RES", "FBS"]
    new_labels = ["Hotels", "Camping", "Restaurants", "Food & beverage services"]

    ledger = AssumptionLedger(project_id="synthetic_accommodation")
    ledger.add(Assumption(
        assumption_id="A-01",
        description="The internal block among the four new subsectors is "
                    "estimated by double proportionality, with a 0.5 damping "
                    "factor on self-consumption.",
        applies_to="Z internal block",
        source="MVP_0.1 §6.3 — project convention, no methodological source",
        validated_by="pending analyst review",
        confidence=ProxyStrength.WEAK,
        impact_on_results="high — it is the only part of the table with no "
                          "observation behind it",
        discarded_alternative="Allocate the whole original diagonal to "
                              "self-consumption",
        discard_reason="Would assert zero trade among subsectors, which is "
                       "less plausible than proportionality for hospitality"))
    ledger.add(Assumption(
        assumption_id="A-02",
        description="Balancing uses GRAS rather than the RAS of the June spec.",
        applies_to="balancing",
        source="CORE_012 Box 11.3, p. 345; UNH_18 par. 18.35, p. 558",
        validated_by="verified against the UN Handbook's own worked example",
        confidence=ProxyStrength.STRONG,
        impact_on_results="decisive — RAS is undefined on this table, which "
                          "has a legitimate negative intermediate cell"))

    project = IOProject(
        project_id="synthetic_accommodation", table=table,
        splits=[SplitSpec("ACC", new_codes, new_labels)],
        scenarios=scenarios, keys=keys, ledger=ledger,
        title="Accommodation & food services — sector split",
        root=Path(__file__).resolve().parents[1] / "outputs")
    project.run().write()

    print(f"Original table: {table.n} sectors, "
          f"{int((table.Z < 0).sum())} negative cell(s) in Z")
    print(project.summary())
    print(f"\nProject folder: {project.dir}")
    return 0 if all(r.report.passed for r in project.results) else 1


if __name__ == "__main__":
    sys.exit(main())
