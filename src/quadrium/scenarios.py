"""
Orchestration: run the full flow of MVP_0.1 §5 for one scenario, or for several
and compare them.

Since the multi-sector extension a scenario carries a LIST of `SplitSpec`, each
with its own allocation keys and input profiles. Splitting one sector is the
case where that list has one element, not a separate code path.

No step mutates the original IOTable.
"""

from __future__ import annotations

import numpy as np

from . import diagnostics
from .balancing import balance, solver_margin_tolerance
from .disaggregation import feasibility, split_sectors, targets
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
        raise ScenarioInfeasible(
            scenario.scenario_id,
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

    for split in seed["splits"]:
        pos = split["positions"]
        off = [i for i in range(n) if i not in pos]
        itr = tr[pos] - Z_bal[np.ix_(pos, off)].sum(axis=1)
        itc = tc[pos] - Z_bal[np.ix_(off, pos)].sum(axis=0)
        Z_int, info = balance(Z_bal[np.ix_(pos, pos)], itr, itc,
                              method=scenario.balancing_method,
                              tol=scenario.balancing_tolerance,
                              max_iter=scenario.balancing_max_iter,
                              locked_cells=scenario.locked_cells or None)
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

    rep = validate_scenario(table, scenario, seed, Z_bal, combined, reagg,
                            prov, overridden, keys)

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

    diag = diagnostics.compute(Z_bal, seed["X"])
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
                scenarios: list[Scenario], keys: dict):
    """Validate the original table, then run every scenario and compare."""
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

    return results, {"original_report": original, "original_table": table,
                     "comparison": comparison,
                     "driver": driver, "driver_spread": spread,
                     "infeasible": infeasible}
