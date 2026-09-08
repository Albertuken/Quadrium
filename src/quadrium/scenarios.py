"""
Orchestration: run the full flow of MVP_0.1 §5 for one scenario, or for several
and compare them.

Since the multi-sector extension a scenario carries a LIST of `SplitSpec`, each
with its own allocation keys and input profiles. Splitting one sector is the
case where that list has one element, not a separate code path.

No step mutates the original IOTable.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from . import diagnostics
from .balancing import balance, solver_margin_tolerance
from .disaggregation import (DisaggregationError, feasibility,
                             split_satellites, split_sectors,
                             targets)
from .precision import assertable_tolerance
from .models import (CellLabel, DisaggregationResult, IOTable, Scenario,
                     SplitSpec)
from .reaggregation import reaggregate, reaggregation_error
from .validation import (corroborate_keys, validate_original,
                         validate_scenario)

PROJECT_MOVED_CELL_ABS_TOL = 1e-9   # PROJECT CHOICE: "did this cell move?"


class ScenarioInfeasible(RuntimeError):
    """The scenario's own numbers cannot describe an economy.

    Distinct from a solver failure, and the distinction matters: nothing about
    the algorithm or its tolerances can fix this. The proxies chosen for
    different blocks imply a state that does not exist.
    """

    def __init__(self, scenario_id: str, explanation: str, detail: str):
        # The DETAIL belongs in the message, not only on the object. It used to
        # be held back for the report, so anyone who hit this at a prompt or in
        # a traceback saw only "the allocation keys imply an impossible
        # economy" -- true, unactionable, and the opposite of what every other
        # error in this project does (found 2026-08-10, using it in anger).
        # The detail names the subsector, the amount and the way out; it is the
        # entire value of the check.
        super().__init__(f"{scenario_id}: {explanation}\n\n{detail}")
        self.scenario_id = scenario_id
        self.explanation = explanation
        self.detail = detail


def _profile_exceeds_headroom(split: dict, diag: dict) -> bool:
    """The one infeasibility this engine can name before it happens.

    `OQ-B-17` option 4, implemented 2026-09-01 on the owner's decision. A
    profiled split whose internal headroom is already negative is refused with
    certainty -- measured, 37 of 37 in `run_input_profiles_backtest.py` -- so
    dying downstream as a generic "impossible economy" tells the analyst less
    than the engine knows. Naming it changes nothing for the splits that
    survive, which is where OQ-B-17's real finding lives; this is a better
    diagnosis of the same refusal, not a fix for it.
    """
    hp = diag.get("headroom_pct")
    return bool(split.get("profiled")) and hp is not None and hp == hp and hp < 0


def _explain_infeasible(table: IOTable, split: dict, diag: dict) -> list[str]:
    """Say which subsector does not fit, and against which of its own budgets."""
    p = split["original_index"]
    w, codes = split["weights"], split["new_codes"]
    lines = []
    for code, side, value in diag["problems"]:
        a = codes.index(code)
        if side == "sells":
            lines.append(
                f"- **{code}** (from `{split['sector_code']}`) is left needing "
                f"to sell {value:,.2f} to its sibling subsectors, which cannot "
                f"be negative. It is assigned {w['output'][a]:.1%} of the "
                f"sector's output but {w['final_demand'][a]:.1%} of its final "
                f"demand and {w['intermediate_rows'][a]:.1%} of its sales to "
                f"other industries — more outlets than it has production.")
        else:
            lines.append(
                f"- **{code}** (from `{split['sector_code']}`) is left needing "
                f"to buy {value:,.2f} from its sibling subsectors, which cannot "
                f"be negative. It is assigned {w['output'][a]:.1%} of the "
                f"sector's output but {w['value_added'][a]:.1%} of its value "
                f"added and {w['intermediate_cols'][a]:.1%} of its purchases "
                f"from other industries — more inputs than its output can "
                f"absorb.")
    X_p, Y_p = float(table.X[p]), float(table.Y[p].sum())
    VA_p = float(table.VA[:, p].sum())
    lines.append(
        f"\n  `{split['sector_code']}`'s own ratios are the budget its "
        f"subsectors must fit inside: of an output of {X_p:,.0f}, "
        f"{100*Y_p/X_p:.1f} % goes to final demand, {100*VA_p/X_p:.1f} % is "
        f"value added, and only {100*diag['z_pp']/X_p:.2f} % is trade within "
        f"the sector itself.")
    if _profile_exceeds_headroom(split, diag):
        lines.insert(0, (
            f"- **This profile asks `{split['sector_code']}`'s internal block "
            f"for more than it has.** Its headroom is "
            f"{diag['headroom_pct']:.2f} % — already negative before the "
            f"profiles are applied — so no weighting of them can fit. Soften "
            f"the input profiles for this split, or drop them and accept that "
            f"the subsectors inherit the parent's purchasing pattern, which "
            f"the report will say outright."))
    return lines


def check_feasible(table: IOTable, seed: dict, tr, tc,
                   scenario: Scenario) -> dict:
    """Reject weights that describe no possible economy, before the solver runs.

    Checked at the INTERNAL-BLOCK level, per split, which is where the
    constraint really binds. Testing only `tr > 0` misses the case where a
    subsector's total intermediate sales are positive but smaller than what the
    proportional split already commits it to selling outside its group.

    The cause is almost always multi-proxy splitting (MVP_0.1 §7), or an input
    profile more aggressive than the sector's internal trade can absorb.
    """
    per_split, problems = {}, []
    for split in seed["splits"]:
        diag = feasibility(table, seed, split, tr, tc)
        per_split[split["sector_code"]] = diag
        if not diag["feasible"]:
            problems += _explain_infeasible(table, split, diag)

    if problems:
        profiled_cause = any(
            _profile_exceeds_headroom(sp, per_split[sp["sector_code"]])
            for sp in seed["splits"])
        raise ScenarioInfeasible(
            scenario.scenario_id,
            "an input profile asks for more internal trade than the sector has"
            if profiled_cause else
            "the allocation keys imply an impossible economy",
            "\n".join(problems)
            + "\n\nThis is not a solver tolerance issue and no tolerance will "
              "fix it. Either use one key for output and final demand, move "
              "the keys closer together, or soften the input profiles. The "
              "totals always reconcile — each internal block sums to its "
              "parent's own diagonal whatever weights are used — so what fails "
              "is the sign of an individual subsector, not the accounting.")
    return per_split


def run_scenario(table: IOTable, splits: list[SplitSpec], scenario: Scenario,
                 keys: dict) -> DisaggregationResult:
    """Steps 5a–5j of the spec, for one scenario and any number of splits."""
    seed = split_sectors(table, splits, scenario, keys)
    tr, tc = targets(seed["Y"], seed["VA"], seed["X"])
    feas = check_feasible(table, seed, tr, tc, scenario)

    # ------------------------------------------------------------------
    # Balance each split's INTERNAL BLOCK ONLY, never the whole matrix.
    #
    # Proportional splitting already satisfies every other margin exactly: the
    # k cells of an untouched row sum to the original Z[i, p] because the shares
    # sum to 1, and symmetrically down the columns. The only constraint the seed
    # violates is each set of new subsectors' own totals, and only because of
    # the self-consumption damping alpha on the internal diagonal (§6.3).
    #
    # Balancing the full matrix would let the solver move cells copied verbatim
    # from the original, breaking the Reaggregation Guarantee of §8 — which is a
    # test, not a diagnostic. Pinning the untouched block instead would need
    # predefined interior cells, which GRAS does not accept (UNH_18 ¶18.81,
    # p. 569); TRAS and KRAS do, and no loaded source specifies either
    # (D_open_questions.md OQ-B-01).
    #
    # The internal blocks of different splits are DISJOINT — each occupies the
    # rows and columns of its own subsectors only — and splitting B preserves
    # A's row and column totals, so they can be balanced independently and in
    # any order.
    # ------------------------------------------------------------------
    Zs = seed["Z"]
    Z_bal = Zs.copy()
    n = len(seed["codes"])
    infos = {}

    # THE BOUND THE SOLVER JUDGES ITS MARGINS BY, computed here because only
    # here is it known what they were built from.
    #
    # Each internal margin below is a target minus a sum across the other `n-k`
    # sectors, so it inherits the rounding of order `n` published cells — not
    # of the one or two numbers it ends up as. `gras` cannot see that, and
    # inferring it from the margins themselves bounds the wrong quantity: the
    # weights introduce decimals the publisher never printed.
    source_values = np.concatenate(
        [table.Z.ravel(), table.Y.ravel(), table.VA.ravel(), table.X.ravel()])

    for split in seed["splits"]:
        pos = split["positions"]
        off = [i for i in range(n) if i not in pos]
        itr = tr[pos] - Z_bal[np.ix_(pos, off)].sum(axis=1)
        itc = tc[pos] - Z_bal[np.ix_(off, pos)].sum(axis=0)
        Z_int, info = balance(Z_bal[np.ix_(pos, pos)], itr, itc,
                              method=scenario.balancing_method,
                              tol=scenario.balancing_tolerance,
                              max_iter=scenario.balancing_max_iter,
                              locked_cells=scenario.locked_cells or None,
                              margin_floor=assertable_tolerance(
                                  source_values,
                                  (len(itr) + len(itc)) * table.n))
        Z_bal[np.ix_(pos, pos)] = Z_int
        infos[split["sector_code"]] = info

    # One combined view, for the validators and the report. Margin deviations
    # are measured against the WHOLE table, not the sub-blocks -- and so, for the
    # same reason, is the tolerance they are judged by: `tr` and `tc` are what
    # this scenario asked for, and if they do not sum to the same number no
    # table satisfies both and part of the deviation is theirs (OQ-B-02 v1.57).
    first = next(iter(infos.values()))
    combined = {
        "method": first["method"],
        "reason": first["reason"],
        "converged": all(i["converged"] for i in infos.values()),
        "iterations": max(i["iterations"] for i in infos.values()),
        "solver_step": max(i["solver_step"] for i in infos.values()),
        "tolerance": scenario.balancing_tolerance,
        "scope": f"internal block of each of {len(infos)} split(s)",
        "iterations_per_split": {k: v["iterations"] for k, v in infos.items()},
        "margin_imbalance": float(tr.sum() - tc.sum()),
        "margin_tolerance": float(solver_margin_tolerance(tr, tc)),
        "n_negative_seed": int((Zs < 0).sum()),
        "n_negative_result": int((Z_bal < 0).sum()),
        "sign_changes": int(np.count_nonzero(np.sign(Z_bal) != np.sign(Zs))),
        "max_row_dev": float(np.max(np.abs(Z_bal.sum(axis=1) - tr))),
        "max_col_dev": float(np.max(np.abs(Z_bal.sum(axis=0) - tc))),
    }
    if combined["n_negative_seed"]:
        combined["reason"] = (
            f"{combined['n_negative_seed']} negative cell(s) in the expanded "
            f"table; RAS is undefined there (CORE_012 Box 11.3, p. 345)")

    # Provenance: anything the solver moved becomes BALANCED_ADJUSTMENT. A
    # copied cell that did not move stays OBSERVED — that is the point of
    # tracking this at all.
    #
    # A PINNED CELL THE SOLVER MOVED USED TO KEEP ITS PIN LABEL, AND THE LABEL
    # WAS A LIE. `user_constraints` writes a value and marks the cell
    # USER_CONSTRAINT, which the report renders "OBSERVED (analyst-pinned)".
    # Nothing protected it: `locked_cells` is a separate mechanism, and GRAS
    # refuses locks outright because UNH_18 ¶18.81, p. 569 gives it row and
    # column totals only. So on any table with negatives — the normal case,
    # the reason GRAS is selected at all — a pin inside the internal block is
    # unprotectable. Reproduced 2026-08-10: asked for 99.0, got 0.3734, and the
    # cell still reported itself as the analyst's own value.
    #
    # It is now relabelled to what it actually is, and the override is recorded
    # so the report can say it out loud. Silently keeping the pin label was the
    # worst silence in the engine: not an absent warning but a false statement.
    prov = seed["provenance"].copy()
    moved = np.abs(Z_bal - Zs) > PROJECT_MOVED_CELL_ABS_TOL
    overridden = []
    for i, j in zip(*np.where(moved)):
        if prov[i, j] is CellLabel.USER_CONSTRAINT:
            overridden.append({
                "cell": f"{seed['codes'][i]},{seed['codes'][j]}",
                "index": [int(i), int(j)],
                "requested": float(Zs[i, j]),
                "actual": float(Z_bal[i, j]),
                "moved_by": float(Z_bal[i, j] - Zs[i, j])})
        prov[i, j] = CellLabel.BALANCED_ADJUSTMENT

    Z_reagg = reaggregate(Z_bal, seed["mapping"], table.n)
    split_indices = [s["original_index"] for s in seed["splits"]]
    reagg = reaggregation_error(table.Z, Z_reagg, split_indices)

    # How far the SOURCE fails to close its own books, measured on the table
    # that came in. Zero for the UK, the INE and Spain 2022; 0.09 for Portugal
    # 2020, which prints two decimals. Nothing downstream can be held tighter.
    source_residue = float(max(
        np.abs(table.Z.sum(1) + table.Y.sum(1) - table.X).max(),
        np.abs(table.Z.sum(0) + table.VA.sum(0) - table.X).max()))
    rep = validate_scenario(table, scenario, seed, Z_bal, combined, reagg,
                            prov, overridden, keys,
                            source_residue=source_residue)

    expanded = IOTable(
        table_id=f"{table.table_id}::{scenario.scenario_id}",
        country=table.country, year=table.year, unit=table.unit,
        classification=table.classification,
        sector_codes=seed["codes"], sector_labels=seed["labels"],
        Z=Z_bal, Y=seed["Y"], Y_labels=table.Y_labels,
        VA=seed["VA"], VA_labels=table.VA_labels, X=seed["X"],
        source=f"{table.source} (disaggregated, scenario {scenario.scenario_id})",
        notes="; ".join(f"{s['sector_code']} split into "
                        f"{', '.join(s['new_codes'])}" for s in seed["splits"]),
        # The result carries its own provenance and its parent's ancestry, so
        # that exporting it and reading it back loses neither. `prov` here is
        # post-balancing: it holds the BALANCED cells the solver moved as well
        # as the ESTIMATED ones the key produced.
        provenance=prov,
        lineage=list(table.lineage) + [
            f"{table.table_id} -> {table.table_id}::{scenario.scenario_id}: "
            + "; ".join(f"{s['sector_code']} into {', '.join(s['new_codes'])}"
                        for s in seed["splits"])])

    # Satellite accounts follow their sectors. Done before `diag` is filled so
    # the effects below are computed on the SPLIT accounts and not the parent's.
    sat = split_satellites(table, seed, seed["splits"])
    if sat:
        expanded.satellites = sat["satellites"]

    diag = diagnostics.compute(Z_bal, seed["X"])

    # Type II, when the workbook asked for it. Computed on the SPLIT table, so
    # the subsectors get their own income coefficients -- which, like the
    # satellite accounts, they inherit from the parent unless a key said
    # otherwise, and the report says so.
    expanded.type_ii = dict(table.type_ii)
    if expanded.type_ii:
        va_idx = [list(expanded.VA_labels).index(r)
                  for r in expanded.type_ii["income_rows"]]
        y_idx = list(expanded.Y_labels).index(expanded.type_ii["household"])
        income = expanded.VA[va_idx, :].sum(axis=0)
        diag["type_ii"] = {
            **diagnostics.type_ii_multipliers(
                diag["A"], income, expanded.Y[:, y_idx], seed["X"]),
            "income_rows": list(expanded.type_ii["income_rows"]),
            "household": expanded.type_ii["household"]}

    if expanded.satellites:
        diag["satellites"] = {
            name: {**diagnostics.satellite_effects(s.values, seed["X"],
                                                   diag["L"]),
                   "unit": s.unit, "source": s.source,
                   "source_year": s.source_year,
                   "estimated": [c for c, o in zip(seed["codes"], s.origin)
                                 if o == "estimated"]}
            for name, s in expanded.satellites.items()}
        diag["equal_intensity_assumed"] = sat["equal_intensity_assumed"]
    diag["balance_info"] = combined
    diag["reaggregation"] = reagg
    diag["user_constraints_overridden"] = overridden
    diag["splits"] = []
    for split in seed["splits"]:
        f = feas[split["sector_code"]]
        _corr = corroborate_keys(keys, split["new_codes"],
                                 split["keys_used"], split["weights"])
        diag["splits"].append({
            "sector_code": split["sector_code"],
            "sector_label": table.sector_labels[split["original_index"]],
            "new_codes": split["new_codes"],
            "positions": split["positions"],
            "keys_used": split["keys_used"],
            "keys_inherited": split.get("keys_inherited", {}),
            "va_rows": split.get("va_rows", {}),
            "profile_shift": split.get("profile_shift"),
            "profile_provenance": split.get("profile_provenance"),
            "key_meta": {k: {
                "strength": getattr(keys[k].strength, "value",
                                    str(keys[k].strength)),
                "source": keys[k].source,
                "source_year": keys[k].source_year}
                for k in set(split["keys_used"].values())},
            "weights": {k: v.tolist() for k, v in split["weights"].items()},
            "original_diagonal": split["original_diagonal"],
            "internal_block_share_pct": split["internal_block_share_pct"],
            "input_structure": diagnostics.input_structure_divergence(
                diag["A"], split["positions"], split["new_codes"],
                profiled=split["profiled"]),
            "code_check": split["code_check"].summary(),
            "code_check_ok": split["code_check"].ok,
            "code_check_unchecked": list(split["code_check"].unchecked),
            "headroom_pct": f["headroom_pct"],
            "tightest_internal_total": f["tightest_internal_total"],
            "parent_diagonal": f["z_pp"],
            "iterations": infos[split["sector_code"]]["iterations"],
            # Free external evidence: every registered key this scenario did
            # NOT drive a block with is compared against the split it produced.
            "corroboration": _corr[0], "corroboration_skipped": _corr[1],
            # Machine-readable scope. The report says this in prose; a consumer
            # reading max_abs_gap out of the JSON had no way to know what the
            # number does not cover.
            "corroboration_covers": (
                "subsector shares only — input profiles are present and no key "
                "backs a purchasing pattern, so the differentiated multipliers "
                "are NOT covered by these gaps"
                if split.get("profiled") else
                "subsector shares, which is everything this split varies"),
        })

    return DisaggregationResult(
        scenario_id=scenario.scenario_id, table=expanded, provenance=prov,
        mapping=seed["mapping"], splits=diag["splits"], report=rep,
        seed_Z=Zs, diagnostics=diag)


def run_project(table: IOTable, splits: list[SplitSpec],
                scenarios: list[Scenario], keys: dict,
                *, key_alternatives_on: bool = False):
    """Validate the original table, then run every scenario and compare.

    `key_alternatives_on` re-runs the split under every other registered key
    (`OQ-E-02`). It is OFF by default and the default is not timidity: it costs
    one full run per candidate key, so a project with eight of them takes nine
    times as long. Wired in unconditionally on 2026-09-06 it turned a four
    minute validator suite into one still running at thirty-five, which is how
    the cost stopped being an estimate.
    """
    original = validate_original(table)
    if not original.passed:
        failed = [c.name for c in original.checks
                  if not c.passed and c.severity == "error"]
        raise ValueError(
            f"the original table failed validation and the run stops here "
            f"(MVP_0.1 §5 step 2): {', '.join(failed)}\n"
            + original.to_markdown())

    results, infeasible = [], []
    for s in scenarios:
        try:
            results.append(run_scenario(table, splits, s, keys))
        except ScenarioInfeasible as exc:
            # A scenario that describes no possible economy is a finding about
            # the proxies, not a crash. Record it and carry on with the rest.
            infeasible.append({"scenario_id": exc.scenario_id,
                               "explanation": exc.explanation,
                               "detail": exc.detail})

    if not results:
        raise ValueError(
            "every scenario was infeasible; nothing to report.\n"
            + "\n\n".join(f"{i['scenario_id']}: {i['explanation']}\n{i['detail']}"
                          for i in infeasible))

    all_new = [c for s in results[0].splits for c in s["new_codes"]]
    all_pos = [p for s in results[0].splits for p in s["positions"]]
    mult = {r.scenario_id: r.diagnostics["multipliers"][all_pos] for r in results}
    comparison = diagnostics.compare_scenarios(mult, all_new)
    driver, spread = diagnostics.variation_driver(
        {r.scenario_id: r.table.Z for r in results},
        results[0].table.sector_codes)

    # OQ-E-02, and only when asked. Computed on the FIRST scenario alone, and
    # said so rather than left to be inferred: what a key decides is the SIZE
    # of each subsector, which is the same question in every scenario, and
    # running it once per scenario would multiply an already large cost for an
    # answer that barely moves.
    alternatives = (key_alternatives(table, splits, scenarios[0], keys, results[0])
                   if key_alternatives_on else None)

    return results, {"original_report": original, "original_table": table,
                     "comparison": comparison,
                     "driver": driver, "driver_spread": spread,
                     "infeasible": infeasible,
                     "key_alternatives": alternatives,
                     "key_alternatives_scenario": (results[0].scenario_id
                                                  if alternatives else None)}


# ---------------------------------------------------------------------------
# Key sensitivity -- OQ-E-02
# ---------------------------------------------------------------------------

def key_alternatives(table: IOTable, splits: list[SplitSpec],
                    scenario: Scenario, keys: dict,
                    actual: DisaggregationResult) -> dict:
    """What the split would have been under each of the other registered keys.

    WHY THIS EXISTS
    ----------------
    `corroborate_keys` already compares the SHARES an unused key implies
    against the shares the split produced. That is the composition, and it is
    not what anybody publishes. What gets published is the multiplier, and
    until now nothing in this engine said how far the multiplier moves when the
    proxy changes.

    The engine already treats this as the honest way to present a result --
    across SCENARIOS. `compare_scenarios` computes the spread and the guide
    calls it *"the honest measure of how much your answer depends on your own
    choices"*. A choice of allocation key is a choice of exactly that kind, and
    it was the one variable exempt from the treatment.

    Opened as `OQ-E-02` by the owner on 2026-09-06, after running the engine
    himself and finding that the workbook demands a proxy and never says where
    to get one, still less what turns on the answer.

    WHAT COUNTS AS A CANDIDATE, AND WHY THE RULE IS THE ENGINE'S OWN
    -----------------------------------------------------------------
    A key registered for exactly these subsectors, declared for the `output`
    block, and not already driving. Driving the whole split from an output key
    is not a new liberty: `_block_key` already falls back to the output key for
    every block that has none of its own, so a candidate run is the engine's
    existing default behaviour with one substitution.

    WEAK KEYS ARE INCLUDED HERE, AND ARE EXCLUDED FROM CORROBORATION
    -----------------------------------------------------------------
    Deliberately different, and the difference is the point. `corroborate_keys`
    skips a weak key because a number its own author calls a last resort cannot
    be EVIDENCE about anything. This is not evidence: it is a statement of what
    the answer would have been. A weak key that moves the multiplier by thirty
    per cent is worth seeing precisely because it is weak, and its strength
    travels with it so nothing here reads as endorsement.

    WHAT THIS DOES NOT DO
    ----------------------
    It does not rank them, and `OQ-E-03` records why at length. Briefly: on
    `examples/es_hosteleria.py`, the one split in this project where the INE
    publishes the truth, the key an economist would pick on conceptual grounds
    was the third worst of seven and the best was the loosest match of all. An
    engine that ranked by plausibility would have chosen wrong and called it
    founded.

    THE MULTIPLIER DOES NOT MOVE, AND THE PROJECT ALREADY KNEW
    -----------------------------------------------------------
    The first run of this returned a multiplier spread of **0.00 %** across
    eight keys whose weights for accommodation ran from 10.54 % to 55.19 % -- a
    factor of five in the size of a subsector, and not one decimal of movement.

    That is not news here. `library/validators/run_key_sensitivity.py` measured
    it long before, on the UK fixture, and states it in as many words: the
    weight scales `Z_ij` and `X_j` together and cancels in `a_ij = Z_ij / X_j`,
    so *"a perturbation study would have reported a spread of zero and been
    mistaken for a finding about robustness"*. That warning is why the levels
    are carried here rather than the multiplier alone -- had it not existed the
    zero would have shipped as a robustness figure.

    So both are carried: `multiplier_gap`, which in an unprofiled split is zero
    by construction and is labelled as such, and `level_gap` -- the subsector
    OUTPUTS, which is what the key actually decides and where the disagreement
    between proxies is enormous.

    Returns `{sector_code: {...}}` per split, carrying for each candidate its
    identity, weights, multipliers, subsector levels, and both gaps against the
    run that actually happened.
    """
    by_code = {s["sector_code"]: s for s in actual.splits}
    out: dict = {}

    for spec in splits:
        got = by_code.get(spec.sector_code)
        if got is None:
            continue
        driving = set(got["keys_used"].values())
        actual_mult = actual.diagnostics["multipliers"][got["positions"]]
        actual_lvl = actual.table.X[got["positions"]]

        runs, skipped = [], []
        for key_id, key in sorted(keys.items()):
            if key_id in driving:
                continue
            if list(key.new_sector_codes) != list(spec.new_codes):
                continue                   # a key belonging to another split
            if key.applies_to != "output":
                # A key declared for one block cannot be made to drive the
                # whole split without contradicting its author. Named rather
                # than dropped, because a candidate that silently disappears
                # is indistinguishable from one that was never registered.
                skipped.append({
                    "key_id": key_id, "applies_to": key.applies_to,
                    "source": key.source,
                    "reason": f"declared for the {key.applies_to!r} block "
                              f"only, so it cannot drive the whole split"})
                continue

            variant = [
                replace(s, keys_by_block={**s.keys_by_block, "output": key_id},
                        va_row_keys={}, va_residual_row=None)
                if s.sector_code == spec.sector_code else s
                for s in splits]
            try:
                alt = run_scenario(table, variant, scenario, keys)
            except (ScenarioInfeasible, DisaggregationError) as exc:
                # A key that describes no possible economy is a finding about
                # that key, and one the user should see BEFORE choosing it.
                skipped.append({
                    "key_id": key_id, "source": key.source,
                    "reason": f"the split is infeasible under this key: {exc}"})
                continue

            alt_split = next(s for s in alt.splits
                             if s["sector_code"] == spec.sector_code)
            alt_mult = alt.diagnostics["multipliers"][alt_split["positions"]]
            alt_lvl = alt.table.X[alt_split["positions"]]
            gaps = [float((a - b) / b) if b else float("nan")
                    for a, b in zip(alt_mult, actual_mult)]
            lvl_gaps = [float((a - b) / b) if b else float("nan")
                        for a, b in zip(alt_lvl, actual_lvl)]
            finite = [abs(g) for g in gaps if g == g]
            finite_lvl = [abs(g) for g in lvl_gaps if g == g]
            runs.append({
                "key_id": key_id,
                "source": key.source,
                "source_year": key.source_year,
                "strength": getattr(key.strength, "value", str(key.strength)),
                "weights": [float(w) for w in key.weights],
                "multipliers": [float(m) for m in alt_mult],
                "multiplier_gap": gaps,
                "max_abs_multiplier_gap": max(finite) if finite else float("nan"),
                "levels": [float(x) for x in alt_lvl],
                "level_gap": lvl_gaps,
                "max_abs_level_gap": (max(finite_lvl) if finite_lvl
                                      else float("nan")),
            })

        out[spec.sector_code] = {
            "new_codes": list(spec.new_codes),
            "driving": sorted(driving),
            "actual_multipliers": [float(m) for m in actual_mult],
            "actual_levels": [float(x) for x in actual_lvl],
            "runs": runs,
            "skipped": skipped,
            # The two numbers a reader wants first, and they answer different
            # questions. Computed over the actual run AND every candidate,
            # because the actual one is a candidate too -- it was just chosen
            # first.
            "multiplier_spread_pct": _spread_pct(
                [[float(m) for m in actual_mult]]
                + [r["multipliers"] for r in runs]),
            "level_spread_pct": _spread_pct(
                [[float(x) for x in actual_lvl]]
                + [r["levels"] for r in runs]),
            # Said here rather than left to the reader. An unprofiled split
            # gives every subsector a scaled copy of the parent's input
            # structure and the scale cancels out of a_ij = Z_ij / X_j, so the
            # multiplier CANNOT move whatever the key says -- established by
            # run_key_sensitivity.py, not by this. A zero there is arithmetic,
            # not agreement, and a reader who takes it for agreement has been
            # misled by this engine.
            "multiplier_invariant_by_construction": not got.get("profiled"),
        }
    return out


def _spread_pct(sets: list[list[float]]) -> float:
    """Widest disagreement between any two runs, as a percentage.

    Per subsector, the range across runs over the smallest of them; the worst
    subsector is reported. Relative rather than absolute because a multiplier
    of 1.3 and one of 2.6 are not comparable in points.
    """
    if len(sets) < 2:
        return 0.0
    worst = 0.0
    for col in zip(*sets):
        lo, hi = min(col), max(col)
        if lo > 0:
            worst = max(worst, (hi - lo) / lo * 100.0)
    return worst
