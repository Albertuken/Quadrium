"""
Deterministic validators for the accounting identities in
library/specs/A_core_accounting_spec.md (identities ID-01 … ID-14).

Design rules, from the ingestion protocol:
  * this module performs numerical checks only; it never selects a method,
    never repairs data, and never relabels a value's status;
  * every identity carries its citation, so a failure can be traced to a
    source paragraph rather than to an opinion;
  * tolerances are a PROJECT CHOICE. The loaded CORE sources specify none, and
    six of them have now been asked (OQ-B-02, closed at v1.57). One threshold
    here is nevertheless NOT a choice: a solver's output is judged against the
    floor its own constraints impose, which is arithmetic on what the caller
    asked for rather than an opinion. See `solver_margins_attained` below.

Sources available when this was written: CORE_003 (SNA 2025 ch. 15),
CORE_005 (SNA 2025 ch. 36), CORE_006 (ESA 2010 ch. 9). Nothing else.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# The derived floors live in the engine package, not here: they are arithmetic
# on a source's own stated precision and on a solver's own constraints, and they
# are used by `quadrium.eurostat` and `quadrium.validation` as well. This
# module is on `library/validators/`, which is not on the path when the engine
# imports it, hence the insert -- the same one `run_tolerance_engine.py` makes.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from quadrium.precision import infeasibility_floor  # noqa: E402

# ---------------------------------------------------------------------------
# Tolerances — PROJECT CHOICE, not specified by any loaded CORE source.
#
# CHECKED AGAIN AT THE UNH_18 INGESTION, AND STILL A PROJECT CHOICE.
# UNH_18 par. 18.81, p. 569 does state a threshold -- "less than a certain
# threshold (for example 10-8)" -- and it is NOT this one. That epsilon is a
# convergence test on GRAS's column scaling factors: dimensionless multipliers
# near 1, measuring whether an ITERATION has stopped moving. ABS_TOL and REL_TOL
# are residuals in the table's own currency unit, measuring whether an ACCOUNTING
# IDENTITY holds. A solver can converge to a table that violates ID-01 -- which
# is exactly why CORE_006 par. 9.51, p. 288 says convergence is necessary and not
# sufficient. Copying 1e-8 in here would be a category error.
#
# The sourced solver threshold lives in gras.py as GRAS_EPS, separately named,
# with its citation and its caveat attached, and NOTHING BELOW TOUCHES IT: the
# v1.57 change here judges a residual in currency units, GRAS_EPS stops an
# iteration on a dimensionless multiplier, and the whole point of the paragraph
# above is that the two are different quantities. See D_open_questions.md
# OQ-B-02 (CLOSED at v1.57) and OQ-B-06 (CLOSED at v1.57 — UNH_18 states its own
# epsilon twice, an order of magnitude apart, and both figures are right about
# different things).
#
# WHAT v1.10 ESTABLISHED, AND WHY THESE TWO CONSTANTS SURVIVE ANYWAY
# ------------------------------------------------------------------
# `ABS_TOL = 1e-6` is right for four of the project's five fixtures and it is
# right BY ACCIDENT: the founding fixture is the ONS table, which is published
# UNROUNDED. A flat absolute tolerance in currency units is very nearly correct
# for a source that does not round and wrong for every source that does. The
# Italian Eurostat table is published to two decimals and its row identity is
# out by 0.08 -- correctly published, and rejected by this constant.
#
# `quadrium.precision.assertable_tolerance()` derives the FLOOR from the
# source's own printed precision: an identity over `n` cells rounded to `d`
# decimals cannot be checked tighter than `0.5*10^-d*n`. That is not a project
# choice -- it is arithmetic on what the publisher stated -- and no acceptance
# criterion may go below it. See `run_tolerance_from_precision.py`.
#
# IT DOES NOT REPLACE THESE CONSTANTS, because it answers a different question.
# The floor says what is DETECTABLE against a published source. ABS_TOL says
# what this project ACCEPTS in an object it computed itself, where the values
# are unrounded float64 and no publisher's rounding is involved. Both are needed
# and they must not share a constant -- the same separation the handover
# threshold already required (`M-039`).
#
# WHAT v1.57 ESTABLISHED, AND WHY THE OTHER HALF IS NOW A DERIVED FLOOR TOO
# --------------------------------------------------------------------------
# The sentence above -- "ABS_TOL says what this project ACCEPTS in an object it
# computed itself" -- was measured, and it was wrong in exactly the place it
# claimed to be safe. An object the engine computed is a SOLVER'S OUTPUT, and a
# solver asked to hit row totals `u` and column totals `v` is being asked for a
# table whose cells sum to `sum(u)` AND to `sum(v)`. When those differ no such
# table exists, the residual is the CONSTRAINTS' and not the solver's, it cannot
# be driven out, and it is bounded below by `|sum(u) - sum(v)| / (m + n)` --
# `quadrium.precision.infeasibility_floor`, added at v1.57.
#
# The project's own GRAS fixture is that case. UNH_18 Box 18.2, p. 568 publishes
# margins summing to 866,987.032 against 866,987.000, so GRAS meets the rows to
# 1.5e-11 and misses a column total by 1.01e-02 -- the 0.032, redistributed;
# the signed column residuals sum to it exactly. `ABS_TOL = 1e-6` calls that
# verified-correct result a failure by a factor of 10,092.
#
# So the symmetry with v1.10 is uncomfortable and worth stating plainly: on
# published tables this constant was right BY ACCIDENT, because the founding
# fixture is unrounded; on solver output it was wrong BY ACCIDENT, because the
# founding fixture's constraints were never checked for consistency. Both halves
# are floors derived from the problem in front of you.
#
# WHAT ABS_TOL / REL_TOL STILL COVER, WHICH IS MOST OF THIS FILE
# ---------------------------------------------------------------
# Every identity below states an accounting relation among cells of ONE table.
# There is no `u` and no `v`, nothing is being asked for that may not exist, and
# no floor can be derived because there is no infeasibility to derive it from.
# ABS_TOL and REL_TOL judge those, they remain a PROJECT CHOICE, and they keep
# the label. `solver_margins_attained()` is the only check here with a solver's
# targets in hand, and it is the only one that uses the floor.
# ---------------------------------------------------------------------------

ABS_TOL = 1e-6      # absolute, in the table's own unit (e.g. GBP million)
REL_TOL = 1e-9      # relative to the magnitude of the row/column being tested

# How far above its OWN derived floor a solver's residual may sit and still be
# accepted. PROJECT CHOICE, like the two above -- a floor is what is achievable,
# never an acceptance criterion, and `precision.py` says so itself -- but unlike
# them it is dimensionless, so it is a choice about slack rather than a choice
# about pounds, and the project's two v1.57 measurements bound it from both
# sides. Converged GRAS on the Handbook's own fixture sits at 2.5x its floor and
# the same run stopped after one iteration at 169,566x (`run_tolerance_engine`);
# published tables that balance sit within 0.26x of theirs and the two that do
# not miss by 37.5x and 1252x (`run_tolerance_population`). Any factor in
# [2.5, 37.5] classifies every observation the project holds identically. 10 is
# inside that band on both counts and is the figure `run_tolerance_engine.py`
# already uses to say a run "is at the floor its constraints impose".
FLOOR_SLACK = 10.0


@dataclass
class Result:
    identity: str
    name: str
    citation: str
    passed: bool
    max_abs_dev: float
    n_violations: int
    detail: str = ""
    info: dict = field(default_factory=dict)

    def __str__(self) -> str:
        mark = "PASS" if self.passed else "FAIL"
        s = (f"[{mark}] {self.identity}  {self.name}\n"
             f"        max|dev| = {self.max_abs_dev:.6g}   violations = {self.n_violations}\n"
             f"        {self.citation}")
        if self.detail:
            s += f"\n        {self.detail}"
        return s


def _close(a, b, abs_tol=ABS_TOL, rel_tol=REL_TOL):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    dev = np.abs(a - b)
    scale = np.maximum(np.abs(a), np.abs(b))
    ok = dev <= (abs_tol + rel_tol * scale)
    return ok, dev


# ---------------------------------------------------------------------------
# Solver output — judged against the floor its own constraints impose
# ---------------------------------------------------------------------------

_CITE_SOLVER = ("derived, not sourced: D_open_questions.md OQ-B-02 v1.57; "
                "UNH_18 par. 18.81, p. 569 (GRAS is given row and column "
                "totals and nothing else); CORE_006 par. 9.51, p. 288")


def solver_margin_tolerance(u, v) -> float:
    """The residual a solver's output may be held to, given the totals it was asked for.

    `ABS_TOL` governs until the request is provably unsatisfiable by more than
    `ABS_TOL`; from there `FLOOR_SLACK * infeasibility_floor(u, v)` does. So
    this only ever LOOSENS, only when the totals asked for cannot both be met,
    and only by as much as that makes unavoidable. It is deliberately not a
    replacement of `ABS_TOL`: the v1.10 finding is that swapping one flat
    constant for another trades an accident for an accident, and where the
    constraints ARE satisfiable a solver has no excuse and `ABS_TOL` is exactly
    the project choice that still applies.

    WHY THE GATE IS ON `|sum(u) - sum(v)| / (m + n)` AND NOT ON THE FLOOR
    ---------------------------------------------------------------------
    `infeasibility_floor` returns the larger of the infeasibility bound and
    `assertable_tolerance` of the margins, and the second term is right where it
    was built for -- the UNH_18 fixture, whose margins are TRANSCRIBED PUBLISHED
    FIGURES printed to three decimals, so their own rounding floor of 0.004
    legitimately beats the 0.00246 infeasibility bound.

    It is wrong for margins the engine computed. `printed_decimals` reads whole
    numbers as "published to 0 decimals" -- it cannot distinguish a rounded
    figure from an exact one -- so a toy fixture with integer totals gets a
    rounding floor of `0.5 * n` and a tolerance of 10. Measured on this
    project's own test suite before the gate existed: **a tolerance of 10 where
    the solver achieved 3.6e-15**, on a table whose totals are of order 10. The
    check would have passed anything.

    So the floor is consulted only once the request is DEMONSTRABLY
    unsatisfiable -- and `|sum(u) - sum(v)|` is the demonstration, needing no
    guess about whether a number was rounded. Past that point the floor's own
    reasoning applies in full, rounding term included, because the margins that
    are inconsistent enough to open this gate are the published ones.
    """
    u = np.asarray(u, float).ravel()
    v = np.asarray(v, float).ravel()
    both = np.concatenate([u, v])
    scale = float(np.abs(both).max()) if both.size else 1.0
    flat = ABS_TOL + REL_TOL * scale

    infeasible_by = abs(float(u.sum()) - float(v.sum())) / (u.size + v.size)
    if infeasible_by <= flat:
        return flat
    return max(flat, FLOOR_SLACK * infeasibility_floor(u, v))


def solver_margins_attained(X, target_row_sums, target_col_sums,
                            label: str = "balanced table") -> Result:
    """Did the solver hit the totals it was given, as closely as they permit?

    NOT AN ACCOUNTING IDENTITY, AND KEPT SEPARATE FROM THEM ON PURPOSE
    ------------------------------------------------------------------
    Every other check in this file states a relation the SOURCES require of a
    table (ID-01 … ID-19), and each carries the paragraph that requires it. This
    one asks whether a computation did what it was asked, which no source
    speaks to; its threshold is derived from the request itself rather than
    cited, and mixing the two would let a solver's slack pass for an accounting
    statement. Hence the `SOLVER` code rather than an `ID-` number.

    A residual here is reported against three numbers, because which one binds
    is the whole finding: the observed deviation, the floor `|sum(u) - sum(v)| /
    (m + n)` below which NO table can go, and the tolerance actually applied.
    When the targets are inconsistent the solver is not free to do better, and
    calling that a failure is calling arithmetic a bug -- which is what
    `ABS_TOL = 1e-6` did to this project's own verified GRAS result, by a factor
    of 10,092 (`run_tolerance_engine.py`).

    Rows and columns are counted separately because a solver may meet one set
    exactly and carry the whole inconsistency into the other: GRAS does exactly
    that, meeting the rows to 1.5e-11 on the fixture above. The tighter
    row-exact bound `|sum(u) - sum(v)| / n` is reported for that reason and is
    NOT used to judge -- which margin absorbs the gap is the solver's business.
    """
    X = np.asarray(X, float)
    u = np.asarray(target_row_sums, float).ravel()
    v = np.asarray(target_col_sums, float).ravel()
    floor = infeasibility_floor(u, v)
    tol = solver_margin_tolerance(u, v)
    gap = float(u.sum() - v.sum())

    row_dev = np.abs(X.sum(axis=1) - u)
    col_dev = np.abs(X.sum(axis=0) - v)
    worst = float(max(row_dev.max(), col_dev.max()))
    viol = int((row_dev > tol).sum() + (col_dev > tol).sum())

    detail = (f"max|row dev|={row_dev.max():.6g}  "
              f"max|col dev|={col_dev.max():.6g}  "
              f"tolerance={tol:.6g}\n"
              f"        sum(u)-sum(v) = {gap:.6g}; floor |gap|/(m+n) = "
              f"{floor:.6g} ({worst / floor:.2g}x), row-exact bound |gap|/n = "
              f"{abs(gap) / v.size:.6g}")
    if tol > ABS_TOL + REL_TOL * float(np.abs(np.concatenate([u, v])).max()):
        detail += ("\n        the targets are inconsistent, so part of this "
                   "residual is theirs and cannot be solved away")
    return Result("SOLVER", f"Solver attained its margins ({label})",
                  _CITE_SOLVER, viol == 0, worst, viol, detail,
                  {"floor": floor, "tolerance": tol, "margin_imbalance": gap,
                   "max_row_dev": float(row_dev.max()),
                   "max_col_dev": float(col_dev.max())})


# ---------------------------------------------------------------------------
# SUT identities
# ---------------------------------------------------------------------------

def id01_product_balance(output_basic, imports, trade_margins, transport_margins,
                         taxes_on_products, subsidies_on_products,
                         intermediate_use, final_consumption,
                         capital_formation, exports):
    """ID-01 product balance, articulated form.

    output@basic + imports + trade margins + transport margins
                 + taxes on products - subsidies on products
      = intermediate use + final consumption + gross capital formation + exports

    Both sides must be on the same valuation basis; the identity is invalid
    otherwise (CORE_006 par. 9.06(b), p. 276).

    `subsidies_on_products` is passed POSITIVE and subtracted here, per the
    storage convention in C_canonical_data_model.md C.2.
    """
    supply = (np.asarray(output_basic, float) + np.asarray(imports, float)
              + np.asarray(trade_margins, float) + np.asarray(transport_margins, float)
              + np.asarray(taxes_on_products, float) - np.asarray(subsidies_on_products, float))
    use = (np.asarray(intermediate_use, float) + np.asarray(final_consumption, float)
           + np.asarray(capital_formation, float) + np.asarray(exports, float))
    ok, dev = _close(supply, use)
    return Result("ID-01", "Product balance (row identity)",
                  "CORE_003 par. 15.9-15.10, p. 481; CORE_006 par. 9.06(b), p. 276",
                  bool(ok.all()), float(dev.max()), int((~ok).sum()))


def id02_industry_identity(intermediate_consumption, gross_value_added, output):
    """ID-02  IC(j) + GVA(j) = output(j).

    Note the deliberate mixed valuation: output at basic prices, intermediate
    consumption at purchasers' prices (CORE_006 par. 9.31, p. 281).
    """
    ok, dev = _close(np.asarray(intermediate_consumption, float)
                     + np.asarray(gross_value_added, float),
                     np.asarray(output, float))
    return Result("ID-02", "Industry identity (column identity)",
                  "CORE_003 par. 15.23, p. 483; CORE_006 par. 9.06(a), p. 276",
                  bool(ok.all()), float(dev.max()), int((~ok).sum()))


def id03_value_added_decomposition(gva, components):
    """ID-03  GVA(j) = sum of the generation-of-income components.

    `components` is a sequence of vectors. SNA form: remuneration of employees,
    other taxes less subsidies on production, gross operating surplus, gross
    mixed income. ESA form substitutes net operating surplus/mixed income plus
    consumption of fixed capital. Both are accepted; the caller chooses.
    """
    total = np.sum([np.asarray(c, float) for c in components], axis=0)
    ok, dev = _close(total, np.asarray(gva, float))
    return Result("ID-03", "Value-added decomposition",
                  "CORE_003 par. 15.136, p. 502; CORE_006 par. 9.06(c), p. 276",
                  bool(ok.all()), float(dev.max()), int((~ok).sum()))


def id06_gdp_three_approaches(gdp_production, gdp_expenditure, gdp_income=None):
    """ID-06  the three approaches must converge after balancing.

    A single estimate of GDP at market prices is derived only when the supply
    and use tables are balanced (CORE_006 par. 9.16, p. 279).
    """
    vals = [("production", gdp_production), ("expenditure", gdp_expenditure)]
    if gdp_income is not None:
        vals.append(("income", gdp_income))
    nums = np.array([v for _, v in vals], dtype=float)
    dev = float(nums.max() - nums.min())
    scale = float(np.abs(nums).max())
    passed = dev <= (ABS_TOL + REL_TOL * scale)
    detail = "  ".join(f"{k}={v:,.4f}" for k, v in vals)
    return Result("ID-06", "Three approaches to GDP converge",
                  "CORE_003 par. 15.15, p. 482; CORE_006 par. 9.16, p. 279",
                  passed, dev, 0 if passed else 1, detail)


def id07_supply_totals(V, q=None, g=None):
    """ID-07  q = row sums of V, g = column sums of V, and sum(q) = sum(g)."""
    V = np.asarray(V, float)
    rows, cols = V.sum(1), V.sum(0)
    viol, worst = 0, 0.0
    if q is not None:
        ok, dev = _close(rows, q)
        viol += int((~ok).sum()); worst = max(worst, float(dev.max()))
    if g is not None:
        ok, dev = _close(cols, g)
        viol += int((~ok).sum()); worst = max(worst, float(dev.max()))
    tot_dev = abs(rows.sum() - cols.sum())
    worst = max(worst, tot_dev)
    scale = max(abs(rows.sum()), 1.0)
    passed = viol == 0 and tot_dev <= (ABS_TOL + REL_TOL * scale)
    return Result("ID-07", "Product output q and industry output g from V",
                  "CORE_003 par. 15.130, p. 501",
                  passed, worst, viol,
                  f"sum(q)={rows.sum():,.4f}  sum(g)={cols.sum():,.4f}")


def id08_margins_sum_to_zero(trade_margins, transport_margins=None):
    """ID-08  trade and transport margins each sum to zero economy-wide.

    Positive additions to the goods rows are matched by offsetting negative
    entries in the rows of the margin industries (CORE_006 par. 9.06(b),
    p. 276; CORE_003 par. 15.56, p. 488).

    This identity is the origin of the structurally negative cells that make a
    sign-agnostic balancing method necessary.
    """
    parts, worst, viol = [], 0.0, 0
    for label, vec in (("trade", trade_margins), ("transport", transport_margins)):
        if vec is None:
            continue
        s = float(np.asarray(vec, float).sum())
        scale = float(np.abs(np.asarray(vec, float)).sum())
        parts.append(f"sum({label})={s:,.6g}")
        worst = max(worst, abs(s))
        if abs(s) > (ABS_TOL + REL_TOL * scale):
            viol += 1
    return Result("ID-08", "Margins sum to zero across products",
                  "CORE_006 par. 9.06(b), p. 276; CORE_003 par. 15.56, p. 488",
                  viol == 0, worst, viol, "  ".join(parts))


def id10_cif_fob_sums_to_zero(adj_goods, adj_services,
                              total_imports_cif=None, total_imports_fob=None):
    """ID-10  the CIF/FOB adjustment entries sum to zero, and both import
    totals agree (CORE_003 par. 15.69, p. 490; par. 15.71, p. 490)."""
    s = float(adj_goods) + float(adj_services)
    worst = abs(s)
    viol = 1 if worst > ABS_TOL else 0
    detail = f"goods={adj_goods:,.6g}  services={adj_services:,.6g}  sum={s:,.6g}"
    if total_imports_cif is not None and total_imports_fob is not None:
        d = abs(float(total_imports_cif) - float(total_imports_fob))
        worst = max(worst, d)
        if d > (ABS_TOL + REL_TOL * abs(float(total_imports_cif))):
            viol += 1
        detail += f"  |CIF-FOB totals|={d:,.6g}"
    return Result("ID-10", "CIF/FOB adjustment sums to zero",
                  "CORE_003 par. 15.69, par. 15.71, p. 490",
                  viol == 0, worst, viol, detail)


def id19_margin_column_sums_to_zero(margin_column, service_rows=None,
                                    label="trade"):
    """ID-19  a margin column of the supply table sums to zero down the products.

    CORE_010 par. 7.19, p. 211 describes the trade and transport margin columns
    as carrying "positive entries (+) in the rows of the traded and transported
    products and negative entries (-) in the rows of trade services and
    transport services", and states that their column totals "are always zero".

    WHY THIS ONE IS DIFFERENT FROM EVERY OTHER IDENTITY HERE
    -------------------------------------------------------
    It is the only check in this file for which NEGATIVE ENTRIES ARE MANDATORY
    rather than merely permitted. A margin column with no negative in the
    service rows has not reallocated anything -- it has invented margin from
    nowhere -- and the zero total would then have to come from somewhere else.
    So a passing total is not on its own evidence of a correct column, and the
    sign pattern is checked separately and reported.

    `service_rows` are the indices of the trade or transport SERVICE product
    rows, where the offsetting negatives must sit. Pass None to check only the
    total, which is what a table that does not identify those rows allows.
    """
    m = np.asarray(margin_column, float).ravel()
    total = float(m.sum())
    scale = float(np.abs(m).sum())
    viol = 1 if abs(total) > (ABS_TOL + REL_TOL * scale) else 0
    detail = f"sum={total:,.6g}  gross={scale:,.6g}"
    if service_rows is not None and scale > 0:
        idx = list(service_rows)
        svc = m[idx]
        others = np.delete(m, idx)
        detail += (f"  service rows {idx}: {np.array2string(svc, precision=4)}"
                   f"  min elsewhere={others.min() if others.size else 0:,.6g}")
        # The service rows GIVE UP the margin, so their sum must be strictly
        # negative in a column that reallocates anything, and none of them may
        # be positive. Testing only "not positive" would pass a column whose
        # service row is zero and whose zero total was produced by a negative
        # somewhere it does not belong -- which is the case this check exists
        # to catch, and which it originally let through.
        if svc.size and svc.sum() >= 0:
            viol += 1
            detail += "  [service rows do not give up any margin]"
        if svc.size and (svc > 0).any():
            viol += 1
            detail += "  [a service row is positive]"
        # CORE_010 par. 7.19, p. 211: positive entries in the rows of the traded
        # and transported products.
        if others.size and (others < 0).any():
            viol += 1
            detail += "  [a traded-product row is negative]"
    return Result("ID-19", f"{label} margin column sums to zero",
                  "CORE_010 par. 7.19, p. 211", viol == 0, abs(total), viol,
                  detail)


def id14_intermediate_totals(U, ic_by_industry=None):
    """ID-14  total intermediate demand = total intermediate consumption
    (CORE_006 par. 9.06(b), p. 276)."""
    U = np.asarray(U, float)
    row_total, col_total = U.sum(), U.sum()
    worst = 0.0
    viol = 0
    detail = f"sum(U)={U.sum():,.4f}"
    if ic_by_industry is not None:
        d = abs(U.sum() - float(np.asarray(ic_by_industry, float).sum()))
        worst = d
        if d > (ABS_TOL + REL_TOL * abs(U.sum())):
            viol = 1
        detail += f"  sum(IC)={float(np.sum(ic_by_industry)):,.4f}"
    return Result("ID-14", "Total intermediate demand = total intermediate consumption",
                  "CORE_006 par. 9.06(b), p. 276", viol == 0, worst, viol, detail)


# ---------------------------------------------------------------------------
# IOT identities
# ---------------------------------------------------------------------------

def id11_iot_balance(Z, final_use, value_added, output):
    """ID-11  in an input-output table the row total equals the column total
    for every index (CORE_005 par. 36.30, p. 1015).

    row(i) = sum_j Z(i,j) + final use(i)
    col(i) = sum_k Z(k,i) + value added(i)
    both must equal output(i).
    """
    Z = np.asarray(Z, float)
    row = Z.sum(1) + np.asarray(final_use, float)
    col = Z.sum(0) + np.asarray(value_added, float)
    ok_r, dev_r = _close(row, np.asarray(output, float))
    ok_c, dev_c = _close(col, np.asarray(output, float))
    ok_rc, dev_rc = _close(row, col)
    worst = float(max(dev_r.max(), dev_c.max(), dev_rc.max()))
    viol = int((~ok_r).sum() + (~ok_c).sum() + (~ok_rc).sum())
    return Result("ID-11", "IOT row total = column total = output",
                  "CORE_005 par. 36.30, p. 1015",
                  viol == 0, worst, viol)


def id12_leontief(Z, output, final_use, check_series_terms: int = 40):
    """ID-12  the Leontief system.

        A x + y = x ;  (I - A) x = y ;  x = (I - A)^-1 y
        (CORE_005 par. 36.36-36.37, p. 1015)

    A is defined as each entry of the inter-industry table divided by the
    output at the foot of its own column (CORE_005 par. 36.36, p. 1015).

    NOTE on the series expansion. CORE_005 par. 36.39, p. 1016 as extracted
    prints "(I-A)^-1 ... can be written as A+A^2+A^3+A^4 etc.", i.e. without
    the leading identity term. The only expansion consistent with
    x = (I - A)^-1 y, stated in par. 36.36 of the same source, is
    I + A + A^2 + ... This function implements and verifies the form WITH the
    leading I, and reports the discrepancy against the printed form.
    See D_open_questions.md OQ-A-01.
    """
    Z = np.asarray(Z, float)
    x = np.asarray(output, float)
    y = np.asarray(final_use, float)
    n = Z.shape[0]

    with np.errstate(divide="ignore", invalid="ignore"):
        A = np.where(x != 0, Z / x[None, :], 0.0)

    I = np.eye(n)
    resid_axy = np.abs(A @ x + y - x)
    L = np.linalg.inv(I - A)
    resid_inv = np.abs((I - A) @ L - I)
    resid_xly = np.abs(L @ y - x)

    # Neumann series with the leading identity term.
    S, term = np.zeros((n, n)), I.copy()
    for _ in range(check_series_terms):
        S += term
        term = term @ A
    series_gap_with_I = float(np.abs(S - L).max())
    series_gap_without_I = float(np.abs((S - I) - L).max())

    worst = float(max(resid_axy.max(), resid_inv.max(), resid_xly.max()))
    scale = float(np.abs(x).max())
    passed = worst <= (1e-6 + 1e-9 * scale)

    detail = (f"max|Ax+y-x|={resid_axy.max():.6g}  "
              f"max|(I-A)L-I|={resid_inv.max():.6g}  "
              f"max|Ly-x|={resid_xly.max():.6g}\n"
              f"        Neumann {check_series_terms} terms: "
              f"gap WITH leading I = {series_gap_with_I:.6g}, "
              f"gap WITHOUT it = {series_gap_without_I:.6g}  "
              f"(see OQ-A-01)")
    return Result("ID-12", "Leontief system",
                  "CORE_005 par. 36.36-36.39, pp. 1015-1016",
                  passed, worst, 0 if passed else 1, detail,
                  {"A": A, "L": L})


def id13_value_added_preserved(W_before, W_after, table_type: str):
    """ID-13  value added preservation under transformation.

    For an INDUSTRY-BY-INDUSTRY transformation the value-added block is
    unaltered and column totals of the intermediate matrix do not change
    (CORE_005 par. 36.50, p. 1017): only composition changes, by moving
    entries BETWEEN ROWS.

    For a PRODUCT-BY-PRODUCT transformation entries move BETWEEN COLUMNS
    within fixed row totals and the final-use quadrant is unaltered
    (CORE_005 par. 36.49, p. 1017); the value-added block DOES change, but
    its total must be preserved.
    """
    a, b = np.asarray(W_before, float), np.asarray(W_after, float)
    if table_type.upper() in ("IOT_IXI", "IXI", "INDUSTRY"):
        ok, dev = _close(a, b)
        return Result("ID-13", "Value-added block unchanged (industry x industry)",
                      "CORE_005 par. 36.50, p. 1017",
                      bool(ok.all()), float(dev.max()), int((~ok).sum()))
    d = abs(a.sum() - b.sum())
    passed = d <= (ABS_TOL + REL_TOL * abs(a.sum()))
    return Result("ID-13", "Value-added total preserved (product x product)",
                  "CORE_005 par. 36.49, p. 1017; par. 36.17, p. 1009",
                  passed, d, 0 if passed else 1,
                  f"before={a.sum():,.4f}  after={b.sum():,.4f}")


# ---------------------------------------------------------------------------
# Structural checks that are NOT identities but are required by the spec
# ---------------------------------------------------------------------------

def negative_census(**arrays):
    """Report where negatives occur. Negatives are NOT errors in this
    framework -- see A_core_accounting_spec.md A.8.1 for the cited list of
    cells that are legitimately negative. This function exists so that a
    balancing routine can be told what it must tolerate, and so that a
    negative appearing somewhere the spec does not permit is visible.
    """
    out = {}
    for name, arr in arrays.items():
        a = np.asarray(arr, float)
        neg = a < 0
        out[name] = {
            "n_negative": int(neg.sum()),
            "share": float(neg.mean()) if a.size else 0.0,
            "min": float(a.min()) if a.size else 0.0,
            "sum_negative": float(a[neg].sum()) if neg.any() else 0.0,
        }
    return out


def structural_zero_check(block, name, citation):
    """Assert that a block that must be zero by construction is zero.

    Chief case: the lower-right quadrant of the use table, which is empty
    (CORE_003 par. 15.95, p. 495; par. 15.179, p. 509).
    """
    a = np.asarray(block, float)
    worst = float(np.abs(a).max()) if a.size else 0.0
    viol = int((np.abs(a) > ABS_TOL).sum())
    return Result("SZ", f"Structural zero: {name}", citation,
                  viol == 0, worst, viol)
