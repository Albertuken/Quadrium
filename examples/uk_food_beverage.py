"""
Split a sector of the REAL UK Input-Output Analytical Table.

Target: I56, "Food And Beverage Service Activities", GBP 94,810 million, one of
104 industries in the ONS 2023 analytical IOT (domestic use, basic prices).

WHAT IS REAL HERE AND WHAT IS NOT — read this before quoting any number.

REAL: the table, and the SIZE split. S1 is driven by ONS Annual Business Survey
TURNOVER for SIC 56.1/56.2/56.3 — United Kingdom, 2023, the table's own year,
published at exactly the detail needed. Strength STRONG: turnover is the closest
published variable to output, and the two agree on the sector total to 0.8 %
(ABS 94,081 against the table's 94,810) from independent surveys. S2 repeats the
split on BRES employment, kept so the cost of a weaker proxy can be measured.

CORROBORATED, which nothing else here is. aGVA, purchases and employment are
registered as keys but do NOT drive the split, so the engine compares the result
against all three automatically and prints the gap in report.md. Largest
disagreement 9.9 %, on event catering. Every other check in this project asks
whether the arithmetic is self-consistent and passes on any key; this one asks
whether a separate survey agrees, and it partly does not.

WHAT THIS FILE DELIBERATELY DOES NOT DO: differentiate the subsectors' input
structures. Doing so needs purchasing profiles that nothing measures, and it
would put the report's most quotable numbers — different multipliers per
subsector — on invented ground. The capability exists and is demonstrated in
examples/uk_hospitality.py. See INFORME_PILOTO.md §4 for why this sector is the
worst possible place to use it.

What IS real and IS the point of this script: the table, its 129 legitimate
negative entries, its balance to 1e-10, and the fact that the whole pipeline —
load, validate, split, balance with GRAS, reaggregate, diagnose — runs on it
unchanged from the synthetic example.

Run:
    python3 examples/uk_food_beverage.py
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

SECTOR = "I56"
NEW_CODES = ["I561", "I562", "I563"]
NEW_LABELS = ["Restaurants and mobile food service",
              "Event catering and other food service",
              "Beverage serving activities"]

# NO INPUT PROFILES HERE, AND THAT IS THE DECISION, NOT AN OMISSION.
#
# A profile is a purchasing intensity the analyst types. Nothing measures one,
# no allocation key backs one, and the corroboration in this run validates
# SIZES only. A profiled scenario therefore produces the most quotable numbers
# in the whole report -- differentiated multipliers -- with nothing behind them.
#
# Worse here than elsewhere: CORE_013 par. B12.14, p. 422 names restaurants
# (ISIC 561) and bars (ISIC 563) as the case where separate input structures
# CANNOT be distinguished from the accounts, because both services are supplied
# together. A profiled split of exactly this sector asserts the one thing a
# rank-2 source says is not establishable.
#
# This file is the pilot -- a real estimate on a real table. The profile
# capability is demonstrated in examples/uk_hospitality.py, which is a
# capability demonstration and says so.



# SIC 2007 group -> the 5-digit classes it contains. Complete by construction:
# group 56.1 holds only class 56.10, split into these three subclasses; 56.2
# holds 56.21 and 56.29; 56.3 holds only 56.30, split into two.
_SIC56 = {"I561": ("56101", "56102", "56103"),
          "I562": ("56210", "56290"),
          "I563": ("56301", "56302")}

BRES_CSV = ROOT / "data" / "ons" / "bres_sic56_gb_2022_2024.csv"
BRES_YEAR = 2023             # matches the table's own reference year
BRES_STATUS = "Employment"   # employees PLUS working proprietors


def bres_employment(year: int = BRES_YEAR, status: str = BRES_STATUS) -> list[int]:
    """Real employment by SIC 56.1 / 56.2 / 56.3, from the saved BRES extract.

    Read from disk rather than hard-coded, so the number in the run and the
    number in the file are the same object. Retrieved from the NOMIS API,
    dataset NM_189_1, on 2026-08-09; query and checksum in `data/ons/README.md`.

    "Employment" rather than "Employees" is deliberate: it includes working
    proprietors, and an input-output table's output covers production by
    unincorporated businesses too. Here that is not a rounding difference --
    it is about 47,000 people in 2023.
    """
    import csv
    totals = {k: 0 for k in _SIC56}
    seen = set()
    with open(BRES_CSV, newline="") as fh:
        for row in csv.DictReader(fh):
            if row["DATE_NAME"] != str(year) or \
               row["EMPLOYMENT_STATUS_NAME"] != status:
                continue
            code = row["INDUSTRY_CODE"]
            for group, classes in _SIC56.items():
                if code in classes:
                    totals[group] += int(float(row["OBS_VALUE"]))
                    seen.add(code)
    missing = {c for cs in _SIC56.values() for c in cs} - seen
    if missing:
        raise SystemExit(
            f"BRES extract is missing SIC class(es) {sorted(missing)} for "
            f"{year}/{status}. A group total built from an incomplete set of "
            f"classes would be wrong in a way nothing downstream can detect.")
    return [totals[c] for c in NEW_CODES]


ABS_CSV = ROOT / "data" / "ons" / "abs_sic56_uk_2019_2024.csv"
ABS_YEAR = 2023
# SIC group -> our subsector code. The ABS publishes 56.1/56.2/56.3 directly,
# so unlike BRES no aggregation from 5-digit classes is needed.
_ABS_GROUP = {"56.1": "I561", "56.2": "I562", "56.3": "I563"}


def abs_variable(column: str, year: int = ABS_YEAR) -> list[float]:
    """A variable from the ONS Annual Business Survey, by SIC 56.1/56.2/56.3.

    `column` is a header of `data/ons/abs_sic56_uk_2019_2024.csv` --
    TURNOVER_GBPM or AGVA_BASIC_PRICES_GBPM.

    The published SIC 56 total is used as a CHECK, not as an input: if the three
    groups do not sum to it, the extract has lost something and the run stops.
    ONS suppresses nothing at this level, so a mismatch means a parsing error.
    """
    import csv
    vals, total = {}, None
    with open(ABS_CSV, newline="") as fh:
        for row in csv.DictReader(fh):
            if int(row["YEAR"]) != year:
                continue
            if row["SIC"] in _ABS_GROUP:
                vals[_ABS_GROUP[row["SIC"]]] = float(row[column])
            elif row["SIC"] == "56":
                total = float(row[column])
    if len(vals) != 3 or total is None:
        raise SystemExit(f"ABS extract incomplete for {year}/{column}")
    if abs(sum(vals.values()) - total) > 0.5:
        raise SystemExit(
            f"ABS {column} {year}: the three groups sum to {sum(vals.values()):,.0f} "
            f"but the published SIC 56 total is {total:,.0f}. Something was lost "
            f"in parsing; a key built from this would be silently wrong.")
    return [vals[c] for c in NEW_CODES]


ABS_SOURCE = (
    "ONS Annual Business Survey, 'Non-financial business economy, UK: Sections "
    "A to S', Table 13 Section I, released 2026-05-26, retrieved 2026-08-09. "
    "United Kingdom, SIC 56.1/56.2/56.3 published directly at 3-digit level.")

BRES_SOURCE = (
    "ONS Business Register and Employment Survey (BRES), employment including "
    "working proprietors, Great Britain, via NOMIS dataset NM_189_1, retrieved "
    "2026-08-09. GREAT BRITAIN, not UK: Northern Ireland is surveyed separately "
    "by NISRA and is excluded from these shares.")


def build_keys() -> dict:
    keys = [
        # Output: ABS turnover. Closest published variable to the thing being
        # split, and the total corroborates the table -- ABS turnover for SIC 56
        # in 2023 is 94,081 against the IOT's output of 94,810, a gap of 0.8 %
        # between two independent ONS products.
        AllocationKey(key_id="key_turnover_abs_2023", applies_to="output",
                      new_sector_codes=NEW_CODES,
                      raw_values=abs_variable("TURNOVER_GBPM"),
                      source=ABS_SOURCE, source_year=ABS_YEAR,
                      strength=ProxyStrength.STRONG),
        # Value added: ABS approximate GVA, which is published AT BASIC PRICES
        # and so matches both the concept and the valuation of the block it
        # splits. Using turnover here would carry the alcohol duty inside
        # beverage serving's sales into a basic-price block.
        # aGVA and purchases are REGISTERED BUT NOT USED AS KEYS, and that is a
        # finding rather than an oversight. Imposing all three at once is
        # infeasible and the engine refuses: catering earns 16.4 % of the
        # sector's value added on 15.0 % of its output, and with only 1.39 % of
        # output traded inside the sector there is no room to absorb the
        # difference. Three share vectors measured in the ABS's accounting
        # frame over-determine one column identity in the IOT's frame.
        #
        # So turnover drives the split -- it is closest to output and its total
        # corroborates the table to 0.8 % -- and these two are used to CHECK the
        # result instead. See `corroborate()`.
        AllocationKey(key_id="key_agva_abs_2023", applies_to="value_added",
                      new_sector_codes=NEW_CODES,
                      raw_values=abs_variable("AGVA_BASIC_PRICES_GBPM"),
                      source=ABS_SOURCE, source_year=ABS_YEAR,
                      strength=ProxyStrength.STRONG),
        # What each subsector BUYS, splitting the intermediate columns. Without
        # this the run is INFEASIBLE and the engine says so: catering earns 16.4
        # % of the sector's value added on 15.0 % of its output, so splitting
        # its purchases proportionally to output hands it more inputs than its
        # output can absorb, and the internal block would have to go negative to
        # absorb the difference. That is not a defect in the data -- it is event
        # catering genuinely being more value-added-intensive (53.0 % against a
        # sector average of 48.3 %) -- and the answer is to split purchases by
        # purchases rather than to blunt the other two keys.
        AllocationKey(key_id="key_purchases_abs_2023",
                      applies_to="intermediate_cols",
                      new_sector_codes=NEW_CODES,
                      raw_values=abs_variable("PURCHASES_GBPM"),
                      source=ABS_SOURCE, source_year=ABS_YEAR,
                      strength=ProxyStrength.STRONG),
        AllocationKey(key_id="key_employment_bres_2023", applies_to="output",
                      new_sector_codes=NEW_CODES,
                      raw_values=bres_employment(),
                      source=BRES_SOURCE, source_year=BRES_YEAR,
                      strength=ProxyStrength.MEDIUM),
    ]
    return {k.key_id: k for k in keys}


def build_scenarios() -> list[Scenario]:
    return [
        Scenario(scenario_id="S1_abs", label="ABS turnover + aGVA (real)",
                 description="Output, final demand and the intermediate blocks "
                             "split by ABS turnover; value added split by ABS "
                             "approximate GVA at basic prices. Each block takes "
                             "the published variable that matches it.",
                 keys_by_block={"output": "key_turnover_abs_2023"}),
        Scenario(scenario_id="S2_employment", label="BRES employment (real)",
                 description="The same split driven by employment instead. Kept "
                             "to measure what the equal-productivity assumption "
                             "costs: restaurants turn over GBP 43.9k per worker "
                             "against 49.2k in catering and 48.2k in bars.",
                 keys_by_block={"output": "key_employment_bres_2023"}),
    ]


def main() -> int:
    table = load_uk_analytical_iot(ROOT / "UK_IOAT_2023_domestic_ixi.xlsx")
    p = table.index_of(SECTOR)

    print(f"Loaded {table.table_id}: {table.n} industries, {table.unit}")
    print(f"  reference year {table.year} (from the Menu sheet, not the filename)")
    print(f"  balance: rows {np.abs(table.Z.sum(1)+table.Y.sum(1)-table.X).max():.2e}"
          f"  cols {np.abs(table.Z.sum(0)+table.VA.sum(0)-table.X).max():.2e}")
    print(f"  negatives: Z={int((table.Z<0).sum())} Y={int((table.Y<0).sum())} "
          f"VA={int((table.VA<0).sum())}  <- a non-negative solver cannot "
          f"reproduce this table")
    print(f"  splitting [{p}] {SECTOR} {table.sector_labels[p]!r}, "
          f"output {table.X[p]:,.0f}")
    print(f"  its own diagonal Z[{SECTOR},{SECTOR}] = {table.Z[p, p]:,.1f}")

    ledger = AssumptionLedger(project_id="uk_food_beverage")
    ledger.add(Assumption(
        assumption_id="A-01",
        description="Every subsector inherits the parent's input structure. "
                    "That is the method's limit, not a choice: with one "
                    "allocation key the weight cancels in a_ij = Z_ij / X_j, so "
                    "all three subsectors necessarily share the parent's "
                    "multiplier. Differentiating them would need purchasing "
                    "profiles that no published source provides.",
        applies_to="the multipliers of every subsector",
        source="Sizes: " + ABS_SOURCE + " || Structures: NOT ESTIMATED. "
               "CORE_013 par. B12.14, p. 422 holds that for restaurants and "
               "bars specifically the separate input structures cannot be "
               "distinguished from the accounts.",
        validated_by="sizes: ABS, corroborated against ABS aGVA and purchases "
                     "(largest gap 9.9 %). structures: NOT ATTEMPTED",
        confidence=ProxyStrength.STRONG,
        impact_on_results="the subsector multipliers are the parent's, and "
                          "should be quoted as such"))
    ledger.add(Assumption(
        assumption_id="A-03",
        description="One key splits every block, so each subsector inherits the "
                    "parent's composition. ABS measured the true composition "
                    "separately and it differs: value added by up to 8.9 % and "
                    "purchases by up to 9.9 %, both on event catering. The "
                    "sizes are right; the composition is approximate.",
        applies_to="all blocks of S1_abs and S2_employment",
        source=ABS_SOURCE,
        validated_by="MEASURED, not assumed — see corroborate() in this file",
        confidence=ProxyStrength.MEDIUM,
        impact_on_results="up to 10 % on a subsector's value added and "
                          "intermediate purchases; none on its size"))
    ledger.add(Assumption(
        assumption_id="A-04",
        description="Splitting output, value added and purchases by three "
                    "separate ABS variables at once is INFEASIBLE and was "
                    "refused by the engine, not chosen against. Catering earns "
                    "16.4 % of the sector's value added on 15.0 % of its "
                    "output, and only 1.39 % of output is traded inside the "
                    "sector, so nothing can absorb the difference.",
        applies_to="the choice of a single driving key",
        source="engine feasibility check, src/quadrium/scenarios.py",
        validated_by="the run stops rather than returning a number",
        confidence=ProxyStrength.STRONG,
        impact_on_results="decides the configuration; see A-03 for what it "
                          "costs"))
    ledger.add(Assumption(
        assumption_id="A-02",
        description="Balancing uses GRAS. The table carries 129 legitimate "
                    "negative entries, so RAS is undefined on it.",
        applies_to="balancing",
        source="CORE_012 Box 11.3, p. 345; UNH_18 par. 18.35, p. 558",
        validated_by="verified against the UN Handbook's own worked example",
        confidence=ProxyStrength.STRONG,
        impact_on_results="decisive"))

    project = IOProject(
        project_id="uk_food_beverage", table=table,
        splits=[SplitSpec(SECTOR, NEW_CODES, NEW_LABELS)],
        scenarios=build_scenarios(), keys=build_keys(), ledger=ledger,
        title=f"UK {SECTOR} — {table.sector_labels[p]} — sector split",
        source_file=ROOT / "UK_IOAT_2023_domestic_ixi.xlsx", root=ROOT / "outputs",
        preamble="> **Sizes are real; structures are the parent's.** The table "
                 "is the ONS 2023 analytical IOT and the size split uses real "
                 "ABS turnover for SIC 56.1/56.2/56.3. Deliberately, "
                 "no attempt is made to differentiate the subsectors' input "
                 "structures, so all three carry the parent's multiplier. See "
                 "the assumption ledger, and `INFORME_PILOTO.md` §4 for why.")
    project.run().write()

    print()
    print(project.summary())
    print(f"\nProject folder: {project.dir}")
    return 0 if all(r.report.passed for r in project.results) else 1


if __name__ == "__main__":
    sys.exit(main())
