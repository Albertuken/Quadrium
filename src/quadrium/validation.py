"""
The mandatory checks of MVP_0.1 §9.

ONE CHECK IS INVERTED RELATIVE TO THE JUNE SPEC
-----------------------------------------------
The spec's `check_no_negative_Z` treats any negative in Z as an **error** that
stops the run. That is backwards. Negatives are legitimate features of an IO
table, not defects (`library/specs/A_core_accounting_spec.md` §A.8.1), and the
project's own UK fixture — an official, balanced table — has them in five
blocks. A rule that refuses such a table refuses reality.

What the sign census actually determines is the **method**, not the validity:
negatives rule out RAS and select GRAS (`B_method_cards/M-047`). So the check is
recast as `check_sign_structure`, severity `info`, and the selection it drives is
reported. A negative is only an error if it appears somewhere §A.8.1 does not
license — and deciding that is `D_open_questions.md` OQ-B-04, still open, so the
check escalates rather than judging.

Every tolerance below is a PROJECT CHOICE and none is stated by any loaded
source -- with one exception since v1.57, and it is not a source but arithmetic.
`check_margins_attained` judges a SOLVER'S OWN OUTPUT, and a solver handed row
and column totals that do not sum to the same number is being asked for a table
that does not exist; the residual it is left with is derivable from the request
and is not its error. That check now uses the derived floor. The rest judge
relations within one table, where there is no such floor to derive, and stay
project choices (OQ-B-02, closed at v1.57).
"""

from __future__ import annotations

import numpy as np

from .diagnostics import technical_coefficients
from .precision import assertable_tolerance, printed_decimals
from .models import (CellLabel, IOTable, Scenario, ValidationReport,
                     count_label)

# PROJECT CHOICE, all of them. Prefixed so grep finds them.
PROJECT_BALANCE_ABS_TOL = 1e-6
PROJECT_BALANCE_REL_TOL = 1e-9
PROJECT_COEF_MAX = 1.0
PROJECT_UNTOUCHED_ABS_TOL = 1e-8

_CITE_CONV = ("CORE_006 ¶9.51, p. 288 — convergence is necessary, not sufficient")
_CITE_NEG = ("A_core_accounting_spec.md §A.8.1; CORE_012 ¶11.66, pp. 333–334")


def corroborate_keys(keys: dict, new_codes: list[str], keys_used: dict,
                     weights: dict) -> tuple[list[dict], list[dict]]:
    """Compare the split against allocation keys it did NOT use.

    WHY THIS IS UNLIKE EVERY OTHER CHECK IN THIS FILE
    -------------------------------------------------
    The rest of this module asks whether the arithmetic is self-consistent:
    does it balance, did it converge, did the untouched cells stay untouched.
    **All of those pass on an arbitrary allocation key.** They cannot tell a
    good split from a bad one, and a clean validation report should never be
    read as saying they can.

    This asks a different question: does an independent measurement of the same
    subsectors agree? If the analyst registered turnover, value added and
    employment but drove the split with turnover alone, the other two are free
    evidence about the composition the split implies. The gap between them is
    an error bar, and it is the only externally grounded number this engine can
    produce.

    Nothing needs configuring. Any key registered for these subsectors and not
    used to drive a block is compared automatically -- registering a key you do
    not use is, in effect, asking for it to be checked.

    A WEAK KEY CANNOT CORROBORATE ANYTHING, AND THIS WAS LEARNED THE HARD WAY
    -------------------------------------------------------------------------
    The first version compared against every unused key regardless of strength.
    Run on the UK pilot it immediately reported that the employment-driven
    scenario was better supported than the ABS-turnover one -- the opposite of
    the truth -- because the largest "disagreement" in every scenario was
    against a leftover ILLUSTRATIVE key that had been left registered. An
    invented number was silently deciding which result to believe, dressed as
    external validation. That is precisely the failure this project exists to
    prevent, reproduced by the very check meant to catch it (2026-08-10).

    A key the analyst marked `weak` is, by their own declaration, not a
    measurement. It is skipped, and skipped keys are RETURNED rather than
    dropped, so the report can say what was left out and why.

    Returns `(records, skipped)`. `max_abs_gap` is the largest relative
    difference between the share the split gave a subsector and the share the
    unused key measures for it.
    """
    driving = set(keys_used.values())
    out: list[dict] = []
    skipped: list[dict] = []
    for key_id, key in sorted(keys.items()):
        if key_id in driving:
            continue
        if list(key.new_sector_codes) != list(new_codes):
            continue                       # a key belonging to another split
        strength = getattr(key.strength, "value", str(key.strength))
        if strength == "weak":
            skipped.append({"key_id": key_id, "strength": strength,
                            "source": key.source,
                            "reason": "declared weak — a proxy its own author "
                                      "calls a last resort cannot be evidence "
                                      "about anything else"})
            continue
        # Compare against the weights of the block this key claims to describe,
        # falling back to output -- which is what the engine itself falls back
        # to when a block has no key of its own.
        block = key.applies_to if key.applies_to in weights else "output"
        rows, worst = [], 0.0
        for code, a, m in zip(new_codes, weights[block], key.weights):
            gap = (a - m) / m if m else float("nan")
            if gap == gap:
                worst = max(worst, abs(gap))
            rows.append({"code": code, "implied": float(a),
                         "measured": float(m), "gap": float(gap)})
        out.append({
            "key_id": key_id,
            "compared_against_block": block,
            "source": key.source,
            "source_year": key.source_year,
            "strength": strength,
            "rows": rows,
            "max_abs_gap": worst,
        })
    return out, skipped


def validate_original(table: IOTable) -> ValidationReport:
    """Must pass before anything else runs (spec §5 step 2)."""
    rep = ValidationReport(table_id=table.table_id, scenario_id="__original__")

    row_dev = np.max(np.abs(table.Z.sum(axis=1) + table.Y.sum(axis=1) - table.X))
    col_dev = np.max(np.abs(table.Z.sum(axis=0) + table.VA.sum(axis=0) - table.X))

    # THE TOLERANCE IS DERIVED FROM THE TABLE, NOT CHOSEN.
    #
    # This check used `abs + rel * max|X|`, which is a statement about the
    # magnitude of the biggest sector and says nothing about how precisely the
    # publisher printed anything. `OQ-B-02` closed at v1.57 on the opposite
    # rule: a table published to `d` decimals states each cell as a stand-in
    # for a figure in a band of width `10^-d`, so an identity summing `n` such
    # cells cannot be checked more tightly than `0.5*10^-d*n`, and below that
    # line "balanced" and "not balanced" are the same observation. `precision`
    # has computed it since v1.10 and `eurostat._rounding_tol` has used it; the
    # gate every table must pass through never adopted it.
    #
    # What that cost, measured on 2026-08-25 over the four Eurostat symmetric
    # tables the project can load:
    #
    #     ES 2020   max dev 0.1        old tol 1.5e-04   FAIL      floor 3.65
    #     ES 2021   max dev 5.8e-11    old tol 1.6e-04   pass      floor 3.75
    #     ES 2022   max dev 2.9e-11    old tol 1.8e-04   pass      floor 3.65
    #     PT 2020   max dev 0.09       old tol 2.6e-05   FAIL      floor 0.37
    #
    # Two of four refused, on residues one to two orders of magnitude INSIDE
    # what the publishers' own rounding can produce. Portugal prints two
    # decimals and Spain one, from the same dataset under the same regulation,
    # and 2020 differs from 2022 for the same country. The run stops at this
    # check, so a first-time user of an ordinary published table was told their
    # table does not balance -- and it does.
    #
    # The floor never goes below PROJECT_BALANCE_ABS_TOL, which is what catches
    # a genuinely broken load: a dropped final-demand column moves a row by
    # thousands, not by hundredths.
    values = np.concatenate([table.Z.ravel(), table.Y.ravel(),
                             table.VA.ravel(), table.X.ravel()])
    n_row = table.n + table.Y.shape[1] + 1      # Z row + Y row + X
    n_col = table.n + table.VA.shape[0] + 1     # Z column + VA column + X
    tol_row = max(PROJECT_BALANCE_ABS_TOL, assertable_tolerance(values, n_row))
    tol_col = max(PROJECT_BALANCE_ABS_TOL, assertable_tolerance(values, n_col))
    d = printed_decimals(values)
    basis = (f"derived from this source's own {d}-decimal precision over "
             f"{n_row} terms (OQ-B-02: 0.5·10^-d·n)" if d is not None else
             "derived from float64 accumulation over the terms summed — this "
             "source does not round")
    rep.add("check_original_balance",
            bool(row_dev <= tol_row and col_dev <= tol_col),
            f"row balance max dev {row_dev:.3g} against {tol_row:.3g}, column "
            f"balance max dev {col_dev:.3g} against {tol_col:.3g} — {basis}",
            "error", "ID-11 / ID-02, A_core_accounting_spec.md §A.6; "
                     "D_open_questions.md OQ-B-02")

    neg = _negative_census(table)
    rep.add("check_sign_structure", True,
            (f"{neg['total']} negative cell(s): "
             + (", ".join(f"{k}={v}" for k, v in neg["by_block"].items())
                if neg["total"] else "none")
             + ". Negatives are legitimate and select GRAS over RAS; they are "
               "not an error."),
            "info", _CITE_NEG)

    if np.any(np.abs(table.X) < 1e-12):
        zeros = [table.sector_codes[i]
                 for i in np.flatnonzero(np.abs(table.X) < 1e-12)]
        rep.add("check_zero_output", False,
                f"sectors with zero output: {', '.join(zeros)} — usually a "
                f"loading error, not a legitimate case", "warning")
    else:
        rep.add("check_zero_output", True, "all sectors have non-zero output",
                "info")
    return rep


def _negative_census(table: IOTable) -> dict:
    by_block = {}
    for name, arr in (("Z", table.Z), ("Y", table.Y), ("VA", table.VA)):
        c = int((arr < 0).sum())
        if c:
            by_block[name] = c
    return {"total": sum(by_block.values()), "by_block": by_block}


def key_vintages(table: IOTable, seed: dict, keys: dict) -> list[dict]:
    """Every key actually used to drive a block, against the table's own year.

    Kept separate from the check so the report can print the whole table
    whether or not the check passed.
    """
    out = []
    for split in seed["splits"]:
        for block, key_id in split["keys_used"].items():
            k = (keys or {}).get(key_id)
            if k is None:
                continue
            out.append({
                "sector": split["sector_code"], "block": block,
                "key_id": key_id, "source_year": int(k.source_year),
                "table_year": int(table.year),
                "gap": k.vintage_gap(table.year),
                "inherited": bool(split.get("keys_inherited", {}).get(block)),
                "vintage": getattr(k, "vintage", None)})
        # A profile carries a year too, now that it carries anything at all
        # (OQ-B-13). A purchasing pattern measured in a different year makes the
        # same assumption a stale key does, and used to be invisible for the
        # simpler reason that a profile was a bare dict.
        pv = split.get("profile_provenance")
        if pv and pv.get("source_year") is not None:
            out.append({
                "sector": split["sector_code"], "block": "input profile",
                "key_id": "(profile)", "source_year": int(pv["source_year"]),
                "table_year": int(table.year),
                "gap": int(pv["source_year"]) - int(table.year),
                "inherited": False, "vintage": None})
    return out


def validate_scenario(table: IOTable, scenario: Scenario, seed: dict,
                      Z_balanced: np.ndarray, balance_info: dict,
                      reagg: dict, provenance: np.ndarray,
                      overridden: list | None = None,
                      keys: dict | None = None,
                      source_residue: float = 0.0) -> ValidationReport:
    """All post-disaggregation checks (spec §9).

    `source_residue` is how far the ORIGINAL table fails to close its own
    accounting identities — measured, not assumed, and zero for a source that
    closes exactly. Two checks below add it to their tolerance, because neither
    can be met more tightly than the source itself manages:

      * the expanded table cannot attain targets derived from a table whose own
        row and column totals disagree, any more closely than they disagree;
      * the reaggregated table cannot reproduce an original that does not
        balance, once the margins have been squared to make it solvable at all.

    On Spain 2022, the UK and the INE fixtures this is 0.0 and nothing moves.
    On Portugal 2020 it is 0.09, which is exactly the deviation the expanded
    table was being failed for.
    """
    rep = ValidationReport(table_id=table.table_id,
                           scenario_id=scenario.scenario_id)
    rep.method_used = balance_info["method"]
    rep.method_reason = balance_info["reason"]
    rep.solver_converged = balance_info["converged"]
    rep.solver_iterations = balance_info["iterations"]

    # --- proxy coverage, across every split
    bad = [f"{s['sector_code']}/{b}" for s in seed["splits"]
           for b, w in s["weights"].items() if np.any(np.asarray(w) <= 0)]
    rep.add("check_proxy_coverage", not bad,
            f"every subsector of every split has a positive proxy in every "
            f"block ({len(seed['splits'])} split(s))" if not bad
            else f"non-positive weights: {', '.join(bad)}",
            "error")

    # --- key vintage against the table's own reference year
    #
    # `source_year` was stored, printed and exported from the first version and
    # compared with `table.year` by nothing. A 2019 proxy driving a 2022 table
    # produced no warning anywhere.
    #
    # The check reports the gap; it does not judge it, because the size of the
    # error a gap causes is not a function of the gap. Measured on one source,
    # the Spanish structural business survey, for the same two subsectors:
    # between 2018 and 2019 the output share moved 0.6 points and employment did
    # not move at all, while between 2019 and 2020 output moved 11.9 points and
    # value added 21.0. A year is nothing or it is everything depending on
    # whether a break falls inside it, and the engine cannot see breaks. The
    # analyst can. So: state the gap, state the volatility where the key knows
    # it, and warn.
    vint = key_vintages(table, seed, keys or {})
    stale = [v for v in vint if v["gap"] != 0]
    if not vint:
        detail = ("no key metadata was passed to the validator, so no key "
                  "vintage could be checked against the table's year")
    elif not stale:
        detail = (f"all {len(vint)} key(s) and profile(s) are measured in "
                  f"{table.year}, the table's own reference year")
    else:
        worst = max(stale, key=lambda v: abs(v["gap"]))
        moves = [v["vintage"]["max_yoy_share_move_pp"] for v in stale
                 if v.get("vintage")
                 and v["vintage"].get("max_yoy_share_move_pp") is not None]
        detail = (
            f"{len(stale)} of {len(vint)} key(s)/profile(s) do not come from "
            f"{table.year}: worst is `{worst['key_id']}` on "
            f"{worst['sector']}/{worst['block']}, measured in "
            f"{worst['source_year']} ({worst['gap']:+d} year(s)). A gap is not "
            f"an error and its cost is not proportional to its size — it "
            f"depends on whether the structure moved, which this engine cannot "
            f"see."
            + (f" Largest year-on-year share move in the series behind these "
               f"keys: {max(moves):.1f} pp." if moves else
               " None of these keys carries a multi-year series, so there is "
               "no evidence here about how much its share moves."))
    rep.add("check_key_vintage", not stale, detail, "warning")

    # --- keys read out of a report rather than a dataset (OQ-B-14, closed at
    #     v1.57 on the owner's decision that the engine may do this).
    #
    # WARNING severity for using one — a report figure is very often the only
    # figure there is, which is why the capability exists. ERROR severity for
    # one that was never checked against the document it cites: an unverified
    # quotation is a number wearing a source's name, and it reaches the reader
    # looking exactly like a figure from a dataset.
    from_report = [v for v in vint
                   if (v.get("vintage") or {}).get("method") == "report"]
    unverified = [v for v in from_report
                  if not (v["vintage"] or {}).get("verified")]
    if from_report:
        cites = ", ".join(
            f"`{v['key_id']}` = {v['vintage']['source_id']} "
            f"p. {'/'.join(str(p) for p in v['vintage']['pages'])}"
            for v in from_report)
        rep.add("check_report_sourced_keys", not unverified,
                (f"{len(from_report)} key(s) were read out of a report rather "
                 f"than a dataset: {cites}. Each carries the page and the "
                 f"verbatim sentence its figure came from"
                 + (f". **{len(unverified)} of them was never checked against "
                    f"the document** — "
                    + ", ".join(f"`{v['key_id']}`" for v in unverified)
                    + ". Pass a verifier to `key_from_report`."
                    if unverified else
                    ", and every quote was verified against the source text.")),
                "error" if unverified else "warning")

    # --- solver convergence
    rep.add("check_solver_convergence", bool(balance_info["converged"]),
            f"{balance_info['method']} {'converged' if balance_info['converged'] else 'DID NOT converge'} "
            f"in {balance_info['iterations']} iterations "
            f"(step {balance_info['solver_step']:.3g}, tolerance "
            f"{balance_info['tolerance']:.3g}, PROJECT CHOICE)",
            "warning", _CITE_CONV)

    # --- margins actually hit
    #
    # JUDGED AGAINST THE FLOOR THE TARGETS THEMSELVES IMPOSE, NOT A CONSTANT.
    # This check compared against a bare `1e-6` and printed `margin_imbalance`
    # in the same breath without ever reading it. When that imbalance is
    # non-zero the row totals and the column totals do not sum to the same
    # number, so NO table satisfies both: the residual is the constraints' and
    # not the solver's, it is bounded below by `|sum(u) - sum(v)| / (m + n)`,
    # and no amount of iterating removes it. On the Handbook's own Austrian
    # fixture -- margins published summing to 866,987.032 against 866,987.000 --
    # a flat 1e-6 rejects a GRAS result that reproduces the chapter's printed
    # iterations, by a factor of 10,092. `library/validators/
    # run_tolerance_engine.py`, `D_open_questions.md` OQ-B-02 v1.57.
    #
    # `margin_tolerance` is computed by `balance()`, which is the only place
    # holding the targets, and it never goes below `PROJECT_BALANCE_ABS_TOL`.
    # So this loosens only where the request itself makes the tighter number
    # unreachable, and only by as much as the request forces. The fallback keeps
    # a `balance_info` built before v1.57 readable.
    worst = max(balance_info["max_row_dev"], balance_info["max_col_dev"])
    tol = balance_info.get("margin_tolerance", PROJECT_BALANCE_ABS_TOL)
    tol = tol + max(0.0, float(source_residue))
    imbalance = balance_info["margin_imbalance"]
    rep.add("check_margins_attained", bool(worst <= tol),
            f"max deviation from target row/column totals {worst:.3g} against "
            f"a tolerance of {tol:.3g}; margin imbalance sum(rows)-sum(cols) = "
            f"{imbalance:.3g}"
            + ("" if not imbalance else
               " — the targets are inconsistent, so no table satisfies both "
               "and part of that deviation cannot be solved away")
            + ("" if not source_residue else
               f". {source_residue:.3g} of the tolerance is the source's own "
               f"unclosed identities, which the targets inherit"),
            "error", "OQ-B-02 v1.57; quadrium.precision.infeasibility_floor")

    # --- reaggregation guarantee
    untouched = reagg.get("untouched_max_abs_error", float("nan"))
    rep.add("check_reaggregation_untouched", bool(untouched <= PROJECT_UNTOUCHED_ABS_TOL),
            f"cells involving no split sector reproduce the original to "
            f"{untouched:.3g} (must be ~0: they were copied, not estimated)",
            "error")
    pct = reagg["max_pct_error"]
    rep.reaggregation_error_pct = pct
    shown = "not computable" if pct is None else f"{pct:.3g} %"
    # A RELATIVE CRITERION AND AN ABSOLUTE ESCAPE. The percentage is the sharp
    # test and stays the primary one: on a source that closes, reaggregation is
    # exact and this reads 0. But a percentage on a small cell is a brutal
    # measure once the margins have had to be squared — a move of 0.015 on a
    # cell of 100 is 0.015 %, ten thousand times the project tolerance, while
    # the whole table is off by 0.035 in 350,000. So a run also passes when its
    # WORST ABSOLUTE cell error is inside what the source's own books are out
    # by. For a source that closes, that allowance is zero.
    abs_err = reagg.get("max_abs_error", float("inf"))
    allowance = max(0.0, float(source_residue)) + PROJECT_UNTOUCHED_ABS_TOL
    by_pct = pct is not None and pct <= scenario.reaggregation_tolerance_pct
    by_abs = abs_err <= allowance
    rep.add("check_reaggregation", bool(by_pct or by_abs),
            f"max reaggregation error {shown} against a tolerance of "
            f"{scenario.reaggregation_tolerance_pct:g} % (PROJECT CHOICE); "
            f"grand total off by {reagg['total_abs_error']:.3g}"
            + ("" if by_pct or not source_residue else
               f". Passed on the absolute test instead: worst cell off by "
               f"{abs_err:.3g}, inside the {allowance:.3g} this source's own "
               f"identities are out by"),
            "error")

    # --- sign structure preserved
    rep.add("check_sign_preserved", balance_info["sign_changes"] == 0,
            f"{balance_info['sign_changes']} cell(s) changed sign during "
            f"balancing; {balance_info['n_negative_result']} negative(s) in the "
            f"result against {balance_info['n_negative_seed']} in the seed",
            "error", "UNH_18 ¶18.35, p. 558 — GRAS is sign preserving")

    # --- extreme technical coefficients
    A = technical_coefficients(Z_balanced, seed["X"])
    finite = A[np.isfinite(A)]
    n_extreme = int(np.sum(finite > PROJECT_COEF_MAX))
    rep.add("check_extreme_coefficients", n_extreme == 0,
            f"{n_extreme} technical coefficient(s) above "
            f"{PROJECT_COEF_MAX:g} (PROJECT CHOICE); max = "
            f"{finite.max():.3g}, min = {finite.min():.3g}",
            "warning")

    # --- internal block weight, informational by design
    parts = ", ".join(f"{s['sector_code']} {s['internal_block_share_pct']:.2f} %"
                      for s in seed["splits"])
    rep.add("check_internal_block_share", True,
            f"estimated internal block(s) as a share of the absolute value of "
            f"the whole intermediate matrix: {parts}. This is the least certain "
            f"part of the result and is labelled PROXY_ESTIMATED throughout",
            "info", "MVP_0.1 §6.3 — double-proportionality hypothesis")

    # --- zero rows / columns after balancing
    #
    # Named, and separated into pre-existing and newly created. A zero row in a
    # real table is usually legitimate — UK L68A, owner-occupiers' housing, has
    # no intermediate sales because imputed rent goes entirely to household
    # final consumption, and T97, households as employers, has neither sales nor
    # purchases because it is pure labour. A zero that BALANCING created is a
    # different animal and is the one worth investigating.
    codes = seed["codes"]
    zr = np.flatnonzero(np.abs(Z_balanced.sum(axis=1)) < 1e-12)
    zc = np.flatnonzero(np.abs(Z_balanced.sum(axis=0)) < 1e-12)
    was_zr = set(np.flatnonzero(np.abs(seed["Z"].sum(axis=1)) < 1e-12).tolist())
    was_zc = set(np.flatnonzero(np.abs(seed["Z"].sum(axis=0)) < 1e-12).tolist())
    new_zeros = ([f"row {codes[i]}" for i in zr if i not in was_zr]
                 + [f"col {codes[j]}" for j in zc if j not in was_zc])
    pre = ([f"row {codes[i]}" for i in zr if i in was_zr]
           + [f"col {codes[j]}" for j in zc if j in was_zc])
    detail = (f"{len(new_zeros)} zero row/column(s) created by balancing"
              + (f": {', '.join(new_zeros)}" if new_zeros else ""))
    if pre:
        detail += (f". {len(pre)} were already zero in the seed and are not "
                   f"attributable to the solver: {', '.join(pre)}")
    rep.add("check_zero_row_col", not new_zeros, detail, "warning")

    # --- provenance completeness
    n_obs = count_label(provenance, CellLabel.OBSERVED)
    n_est = count_label(provenance, CellLabel.PROXY_ESTIMATED)
    n_bal = count_label(provenance, CellLabel.BALANCED_ADJUSTMENT)
    over = overridden or []
    rep.add("check_user_constraints_held", not over,
            (f"{len(over)} pinned cell(s) were moved by the solver and now hold "
             f"its value, not yours: "
             + "; ".join(f"{o['cell']} asked {o['requested']:,.4g} holds "
                         f"{o['actual']:,.4g}" for o in over[:4])
             + ("" if len(over) <= 4 else f" and {len(over)-4} more")
             if over else
             "every analyst-pinned cell still holds the value it was given"),
            "warning" if over else "info",
            "UNH_18 ¶18.81, p. 569 — GRAS accepts row and column totals only")
    n_usr = count_label(provenance, CellLabel.USER_CONSTRAINT)
    total = provenance.size
    rep.add("check_provenance_complete", n_obs + n_est + n_bal + n_usr == total,
            f"{n_obs} observed, {n_est} proxy-estimated, {n_bal} "
            f"balanced-adjustment, {n_usr} user-constrained, of {total} cells",
            "error", "MVP_0.1 §2.6; A_core_accounting_spec.md §A.1")
    return rep
