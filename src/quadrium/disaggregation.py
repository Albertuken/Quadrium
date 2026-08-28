"""
The disaggregation engine: one aggregate sector -> N subsectors.

MVP_0.1 §6. Proportional splitting of the row, the column, final demand and
value added, plus the double-proportionality estimate of the internal block —
which is the piece with the most methodological judgement in the whole MVP and
is labelled as an estimate everywhere it appears.

Nothing here balances. The output is a SEED matrix whose margins do not yet
hold; `balancing.py` closes it.
"""

from __future__ import annotations

import numpy as np

from .classification import check_split
from .models import CellLabel, IOTable, Scenario, SplitSpec


class DisaggregationError(ValueError):
    pass


def _weights(scenario: Scenario, keys: dict, block: str, fallback: str,
             k: int, spec: SplitSpec | None = None
             ) -> tuple[np.ndarray, str, bool]:
    """Weights for a block, and whether the block CHOSE that key or inherited it.

    Precedence: the split's own key, then the scenario's key for that block,
    then either's key for `fallback` (always "output"). A split that names
    nothing inherits the scenario entirely, which is how the single-split case
    stays as terse as before.

    THE THIRD RETURN VALUE EXISTS BECAUSE THE FALLBACK WAS INVISIBLE.
    A block that inherited the output key looked, in the report, exactly like a
    block the analyst had deliberately assigned that key: same row, same id,
    same weights. An inherited default presented as a decision is the quiet
    kind of wrong this project keeps finding in itself (2026-08-10). It is now
    returned, recorded and printed.
    """
    def _pick(block_name):
        if spec is not None and spec.keys_by_block.get(block_name):
            return spec.keys_by_block[block_name]
        return scenario.key_for(block_name)

    own = _pick(block)
    key_id = own or _pick(fallback)
    inherited = own is None
    if key_id is None:
        raise DisaggregationError(
            f"scenario {scenario.scenario_id!r} has no allocation key for "
            f"block {block!r} and no {fallback!r} key to fall back on")
    if key_id not in keys:
        raise DisaggregationError(
            f"scenario {scenario.scenario_id!r} names key {key_id!r} for block "
            f"{block!r}, which is not among the loaded keys: "
            f"{', '.join(sorted(keys))}")
    key = keys[key_id]
    if len(key.weights) != k:
        raise DisaggregationError(
            f"key {key_id!r} has {len(key.weights)} weights for {k} subsectors")
    return key.w, key_id, inherited


def profile_level_shift(table: IOTable, sector_code: str, new_codes: list[str],
                        w_col, profiles: dict) -> dict:
    """How far a profile moves each subsector's TOTAL purchases. OQ-B-13.

    A profile is meant to say *what* a subsector buys, not *how much* — the
    amount is already fixed by the allocation key. But `_column_shares`
    normalises per SUPPLIER, which is what keeps each supplier's total sales to
    the group unchanged, and nothing then holds each subsector's total where the
    key put it. So a profile moves the level as a side effect of describing the
    composition, and the engine never said so.

    Usually the internal block absorbs it. When the parent barely trades with
    itself it cannot: product 36 of the Spanish table has a diagonal of 154.9
    against an input column of 49,604, and a raw profile there moved 428 —
    nearly three times the whole internal block — which made the scenario
    infeasible twice before the cause was understood.

    So the shift is measured against the room available, and reported.
    """
    p = table.index_of(sector_code)
    col = np.asarray(table.Z, float)[:, p].copy()
    diagonal = float(col[p])
    col[p] = 0.0
    shares = _column_shares(table, p, new_codes, np.asarray(w_col, float),
                            profiles or {}, strict=False)
    got = col @ shares
    want = np.asarray(w_col, float) * col.sum()
    shift = got - want
    worst = float(np.abs(shift).max()) if shift.size else 0.0
    return {"by_subsector": {c: float(s) for c, s in zip(new_codes, shift)},
            "max_abs": worst,
            "internal_block": diagonal,
            "share_of_internal_block": (worst / abs(diagonal)
                                        if abs(diagonal) > 1e-12
                                        else float("inf")),
            "neutral": worst <= 1e-6 * max(abs(col.sum()), 1.0)}


def neutralise_profile(table: IOTable, sector_code: str, new_codes: list[str],
                       w_col, profiles: dict, max_iter: int = 2000,
                       tol: float = 1e-12) -> dict:
    """Rescale a profile so it changes composition and not level.

    Each subsector's named intensities are scaled by a single factor, which puts
    its total purchases back where the allocation key had them.

    WHAT SURVIVES AND WHAT CANNOT.
    It preserves each subsector's COMPOSITION exactly — the ratios among the
    suppliers it names, which is what "a restaurant buys food and a hotel rents
    premises" actually asserts. It does **not** preserve the ratio between
    subsectors for a given supplier, and no method could: saying that one
    subsector buys 1.6x the average of everything named and another 0.5x IS a
    statement about their relative size, and size is what the allocation key
    already fixed. The level and the between-subsector pattern are the same
    information, so removing one removes the other.

    If the between-subsector comparison is the evidence, it does not belong in a
    profile — it belongs in the `intermediate_cols` key, where the engine treats
    it as size and the report shows it as such.

    THE CORRECTION HAS TO LIVE ON THE NAMED SUPPLIERS ALONE. Every supplier the
    profile does not name stays at 1.00, so scaling a whole vector and then
    writing back only the named entries leaves the level uncorrected. The
    Spanish pilot made exactly that mistake: it cut the shift from 915 to 428,
    which still overran an internal block of 155 by nearly three times, and the
    scenario was refused a second time.

    Raises rather than returning something almost neutral: a profile that
    quietly moves subsector size is what this exists to prevent.
    """
    p = table.index_of(sector_code)
    w = np.asarray(w_col, float)
    col = np.asarray(table.Z, float)[:, p].copy()
    col[p] = 0.0
    target = w * col.sum()
    named = {c: dict(v) for c, v in (profiles or {}).items() if c in new_codes}
    if not named:
        return {"profiles": dict(profiles or {}), "scale": {}, "iterations": 0,
                "shift_before": 0.0, "shift_after": 0.0}

    before = profile_level_shift(table, sector_code, new_codes, w,
                                 profiles)["max_abs"]
    scale = {c: 1.0 for c in named}
    got = target
    for it in range(1, max_iter + 1):
        scaled = {c: {s: v * scale[c] for s, v in d.items()}
                  for c, d in named.items()}
        shares = _column_shares(table, p, new_codes, w, scaled, strict=False)
        got = col @ shares
        if np.abs(got - target).max() < tol * max(abs(col.sum()), 1.0):
            break
        for a, c in enumerate(new_codes):
            if c in scale and got[a] > 1e-12:
                scale[c] *= (target[a] / got[a]) ** 0.5
    else:
        raise DisaggregationError(
            f"could not make the input profile for {sector_code!r} "
            f"level-neutral: subsector purchases are still off by "
            f"{float(np.abs(got - target).max()):,.6f}. Returning it would move "
            f"subsector size while claiming only to describe composition.")

    out = dict(profiles or {})
    out.update({c: {s: v * scale[c] for s, v in d.items()}
                for c, d in named.items()})
    after = profile_level_shift(table, sector_code, new_codes, w, out)["max_abs"]
    return {"profiles": out, "scale": scale, "iterations": it,
            "shift_before": before, "shift_after": after}


def _va_columns(table: IOTable, p: int, k: int, w_va: np.ndarray,
                keys: dict, spec: SplitSpec | None):
    """The value-added block of the split sector, row by row where evidence
    exists for a row.

    WHY THIS IS NOT JUST `VA[:, p] * w_va[a]`, WHICH IS WHAT IT USED TO BE.
    That gave every row of the block the same ratio — imported intermediate
    inputs, taxes on products, compensation of employees, operating surplus, all
    divided alike. It is the only defensible thing to do when nothing is known
    row by row, and it was quietly wrong the moment something was: the Spanish
    structural business survey gives accommodation 55.19 % of gross operating
    surplus, 32.76 % of compensation and 29.80 % of imported inputs, against a
    flat 39.84 %. On product 36 that misplaced 6,441 million EUR of operating
    surplus. The column still balanced, because the errors offset. See OQ-B-12.

    THE SHAPE OF THE FIX, AND WHY THE OBVIOUS ONE DOES NOT WORK.
    Simply splitting each row by its own key breaks nothing in the accounts —
    every row still sums back to its parent — but it moves the block's COLUMN
    total, and the column total is what is left over for intermediate purchases.
    On the Spanish pilot the fully row-driven split leaves accommodation needing
    to buy -8,470 from its siblings, which is worse than the flat key's -4,755.
    Evidence that is right about rows can still be wrong about the column.

    So the block total per subsector stays governed by `w_va`, the rows that have
    keys take them exactly, and **one named row absorbs the difference**. That
    row is `spec.va_residual_row` and the caller has to name it: in the accounts
    the residual item is operating surplus, but which row plays that part is an
    economic judgement, not something to infer from the data.

    Every row still sums back to the parent exactly, including the residual —
    that falls out of `w_va` summing to one — so reaggregation is untouched.
    """
    VA_p = np.asarray(table.VA, float)[:, p]
    out = np.outer(VA_p, np.asarray(w_va, float))
    info = {"pinned": {}, "residual_row": None, "residual_shares": None}
    row_keys = dict(getattr(spec, "va_row_keys", {}) or {})
    if not row_keys:
        return out, info

    labels = list(table.VA_labels)
    residual = getattr(spec, "va_residual_row", None)

    def _row(name):
        if name not in labels:
            raise DisaggregationError(
                f"value-added row {name!r} is not in this table. Available: "
                + "; ".join(repr(x) for x in labels))
        return labels.index(name)

    r_res = _row(residual)
    for name, key_id in row_keys.items():
        r = _row(name)
        key = keys.get(key_id)
        if key is None:
            raise DisaggregationError(
                f"va_row_keys names key {key_id!r} for row {name!r}, which is "
                f"not among the loaded keys: {', '.join(sorted(keys))}")
        w = np.asarray(key.w, float)
        if w.size != k:
            raise DisaggregationError(
                f"key {key_id!r} has {w.size} weights for {k} subsectors")
        out[r, :] = VA_p[r] * w
        info["pinned"][name] = key_id

    pinned_rows = [_row(n) for n in row_keys]
    others = [r for r in range(len(labels))
              if r != r_res and r not in pinned_rows]
    total = VA_p.sum() * np.asarray(w_va, float)
    taken = out[pinned_rows, :].sum(axis=0) if pinned_rows else np.zeros(k)
    if others:
        taken = taken + out[others, :].sum(axis=0)
    out[r_res, :] = total - taken

    share = (out[r_res, :] / VA_p[r_res]) if abs(VA_p[r_res]) > 1e-12 \
        else np.full(k, np.nan)
    info["residual_row"] = residual
    info["residual_shares"] = [float(s) for s in share]
    bad = [(i, float(s)) for i, s in enumerate(share)
           if not (-1e-9 <= s <= 1 + 1e-9)]
    if bad:
        raise DisaggregationError(
            f"the value-added rows you pinned leave {residual!r} an impossible "
            f"share: "
            + ", ".join(f"subsector {i} would take {s:.1%}" for i, s in bad)
            + f". A residual row cannot take less than none of its parent row "
              f"({VA_p[r_res]:,.1f}) or more than all of it. The pinned rows "
              f"claim more of the block than the block key {list(np.round(w_va, 4))} "
              f"leaves for them. Either pin fewer rows, choose a different "
              f"residual row, or drive `value_added` with a key that matches "
              f"the evidence you are pinning.")
    return out, info


def _column_shares(table: IOTable, p: int, new_codes: list[str],
                   w_col: np.ndarray, profiles: dict,
                   strict: bool = True) -> np.ndarray:
    """Share of each supplier's sales to the parent that goes to each subsector.

    Returns an (n_original, k) array whose rows sum to 1.

        share[i, a] = w_col[a] * m[i, a] / sum_b (w_col[b] * m[i, b])

    where `m` is the relative intensity from `Scenario.input_profiles`,
    defaulting to 1. Normalising per supplier is what preserves that supplier's
    total sales to the group.

    A supplier that every subsector is given a zero multiplier for would have
    nowhere to sell; that is an analyst error, not a rounding issue, so it
    raises rather than silently falling back.
    """
    n, k = table.n, len(new_codes)
    m = np.ones((n, k))
    for code, per_supplier in (profiles or {}).items():
        if code not in new_codes:
            if not strict:
                continue          # belongs to another split of this scenario
            raise DisaggregationError(
                f"input_profiles names subsector {code!r}, which is not among "
                f"{new_codes}")
        a = new_codes.index(code)
        for supplier, mult in per_supplier.items():
            try:
                i = table.index_of(supplier)
            except KeyError:
                raise DisaggregationError(
                    f"input_profiles for {code!r} names supplier {supplier!r}, "
                    f"which is not a sector of the table") from None
            if mult < 0:
                raise DisaggregationError(
                    f"input intensity for {code!r} from {supplier!r} is "
                    f"{mult}; a relative intensity cannot be negative")
            m[i, a] = float(mult)

    raw = m * w_col[None, :]
    totals = raw.sum(axis=1)
    bad = np.flatnonzero(totals <= 0)
    if bad.size:
        raise DisaggregationError(
            f"suppliers {[table.sector_codes[i] for i in bad]} were given a "
            f"zero intensity for every subsector, so their sales to the group "
            f"have nowhere to go. Give at least one subsector a positive "
            f"intensity.")
    return raw / totals[:, None]


def split_sector(table: IOTable, sector_code: str, new_codes: list[str],
                 new_labels: list[str], scenario: Scenario,
                 keys: dict, spec: SplitSpec | None = None) -> dict:
    """Expand `sector_code` into `new_codes`, returning the seed system.

    Returns a dict with the expanded Z, Y, VA, X, labels, the provenance matrix,
    the mapping new->original, and the weights actually used.

    The original table is never mutated (spec §5).
    """
    p = table.index_of(sector_code)
    n, k = table.n, len(new_codes)
    if k < 2:
        raise DisaggregationError("splitting into fewer than 2 subsectors is "
                                  "not a disaggregation")
    if len(new_labels) != k:
        raise DisaggregationError("new_labels and new_codes differ in length")

    w_out, key_out, inh_out = _weights(scenario, keys, "output", "output", k, spec)
    w_y, key_y, inh_y = _weights(scenario, keys, "final_demand", "output", k, spec)
    w_va, key_va, inh_va = _weights(scenario, keys, "value_added", "output", k, spec)
    w_row, key_row, inh_row = _weights(scenario, keys, "intermediate_rows",
                                       "output", k, spec)
    w_col, key_col, inh_col = _weights(scenario, keys, "intermediate_cols",
                                       "output", k, spec)

    for name, w in (("output", w_out), ("final_demand", w_y),
                    ("value_added", w_va)):
        if not np.isclose(w.sum(), 1.0):
            raise DisaggregationError(f"{name} weights sum to {w.sum()}, not 1")

    # Index bookkeeping: the split sector's single slot becomes k slots, in
    # place, so the surrounding sectors keep their relative order.
    new_n = n - 1 + k
    codes, labels, mapping = [], [], []
    for i in range(n):
        if i == p:
            codes.extend(new_codes)
            labels.extend(new_labels)
            mapping.extend([p] * k)
        else:
            codes.append(table.sector_codes[i])
            labels.append(table.sector_labels[i])
            mapping.append(i)
    new_pos = list(range(p, p + k))          # positions of the new subsectors
    old_to_new = {i: (i if i < p else i + k - 1) for i in range(n) if i != p}

    # ---- Z ---------------------------------------------------------------
    Z = np.zeros((new_n, new_n))
    prov = np.empty((new_n, new_n), dtype=object)
    prov[:, :] = CellLabel.OBSERVED

    # untouched block: copied exactly, so reaggregation must be exact there
    for i, ii in old_to_new.items():
        for j, jj in old_to_new.items():
            Z[ii, jj] = table.Z[i, j]

    # the split sector's ROW: what it sells to every other buyer (spec §6.1)
    for a, i_new in enumerate(new_pos):
        for j, jj in old_to_new.items():
            Z[i_new, jj] = table.Z[p, j] * w_row[a]
            prov[i_new, jj] = CellLabel.PROXY_ESTIMATED

    # the split sector's COLUMN: what every other seller sells to it.
    #
    # Each supplier's total sales to the group are preserved exactly -- the
    # shares below sum to 1 across subsectors for every supplier -- so this
    # redistributes within the group and never changes what leaves it. That is
    # what keeps reaggregation exact.
    #
    # With no input profile the share is just w_col[a], and every subsector gets
    # a scaled copy of the parent's input structure. With a profile, the
    # composition differs: restaurants can buy more food and bars more drink.
    # Precedence, and the reason the two levels are treated differently.
    # A profile on the SplitSpec is about this split and nothing else, so every
    # subsector it names must belong here — a typo should be an error.
    # A profile on the SCENARIO is a shared pool: with several splits in one
    # scenario it necessarily names other splits' subsectors too, so entries
    # that are not ours are simply not for us. That is what lets one scenario
    # say "profiled" and another "plain" over the same set of splits.
    if spec is not None and spec.input_profiles:
        profiles, strict = spec.input_profiles, True
    else:
        profiles = {c: v for c, v in (scenario.input_profiles or {}).items()
                    if c in new_codes}
        strict = False
    shares = _column_shares(table, p, new_codes, w_col, profiles, strict)
    for a, j_new in enumerate(new_pos):
        for i, ii in old_to_new.items():
            Z[ii, j_new] = table.Z[i, p] * shares[i, a]
            prov[ii, j_new] = CellLabel.PROXY_ESTIMATED

    # ---- the internal block (spec §6.3) ----------------------------------
    # CORE_031 eq. (14) is the outer product of the weights and eq. (15) says it
    # conserves the parent cell exactly. `alpha` lets an analyst concentrate the
    # block on its diagonal -- a subsector usually buys from itself more than
    # proportionality implies -- and the OFF-DIAGONAL now pays for it, so eq.
    # (15) still holds:
    #
    #     diagonal      alpha * w_row[a] * w_col[b] * z_pp
    #     off-diagonal  beta  * w_row[a] * w_col[b] * z_pp
    #     beta = (1 - alpha*d) / (1 - d),   d = sum_a w_row[a]*w_col[a]
    #
    # `d + o = (sum w_row)(sum w_col) = 1`, so at alpha = 1 this gives beta = 1
    # and reduces EXACTLY to eq. (14). It is a reparameterisation of Wolsky, not
    # a departure from him, and `beta = 0` at `alpha = 1/d` bounds it.
    #
    # THE OLD FORM SCALED THE DIAGONAL AND LEFT THE OFF-DIAGONAL AT 1.0, so it
    # broke eq. (15) and left the shortfall to a balancing step that knows
    # nothing about the block. The default was 0.5, which halved the diagonal;
    # measured on 1,403 sibling pairs in three published tables the diagonal is
    # about 1.5x the outer product, never below it. The default is now 1.0 --
    # the sourced rule -- and `alpha` is documented with that measurement so an
    # analyst can raise it deliberately. See OQ-S-04 and run_internal_block.py.
    z_pp = table.Z[p, p]
    alpha = scenario.internal_block_alpha
    d = float(sum(w_row[a] * w_col[a] for a in range(len(new_pos))))
    beta = 1.0 if abs(1.0 - d) < 1e-12 else (1.0 - alpha * d) / (1.0 - d)
    for a, i_new in enumerate(new_pos):
        for b, j_new in enumerate(new_pos):
            base = z_pp * w_row[a] * w_col[b]
            Z[i_new, j_new] = base * (alpha if a == b else beta)
            prov[i_new, j_new] = CellLabel.PROXY_ESTIMATED

    # ---- Y, VA, X --------------------------------------------------------
    Y = np.zeros((new_n, table.Y.shape[1]))
    VA = np.zeros((table.VA.shape[0], new_n))
    X = np.zeros(new_n)
    for i, ii in old_to_new.items():
        Y[ii, :] = table.Y[i, :]
        VA[:, ii] = table.VA[:, i]
        X[ii] = table.X[i]
    VA_new, va_rows = _va_columns(table, p, k, w_va, keys, spec)
    for a, i_new in enumerate(new_pos):
        Y[i_new, :] = table.Y[p, :] * w_y[a]
        VA[:, i_new] = VA_new[:, a]
        X[i_new] = table.X[p] * w_out[a]

    # ---- user constraints -------------------------------------------------
    # CORE_009 ¶6.36, p. 164 gives the compiler's order: "first, to estimate the
    # values for total intermediate consumption by industry; second, to enter in
    # the table known values of intermediate consumption by product and by
    # industry when available; and, third, to use additional information on cost
    # structures to estimate ALL OTHER VALUES in this part of the use table."
    #
    # THIS ENGINE HAD THE SECOND AND THIRD STEPS THE WRONG WAY ROUND. It filled
    # every cell from the structure against the FULL column total and then wrote
    # the known value on top, so the remaining cells absorbed nothing and the
    # column total moved by exactly the amount pinned away. Measured on the
    # Spanish table: pinning one cell of H51 at half its value took the column
    # from 4,280.520 to 3,904.200, a silent loss of 376.320 left for a balancer
    # that cannot know which cell was authoritative.
    #
    # The structure now applies to what is LEFT, which is what ¶6.36 says.
    constraints = {}
    for cell, value in (scenario.user_constraints or {}).items():
        i, j = (int(x) for x in cell.split(","))
        constraints.setdefault(j, {})[i] = float(value)

    for j, pinned in constraints.items():
        if not (0 <= j < new_n):
            raise ValueError(f"user constraint column {j} is outside the table")
        target = float(Z[:, j].sum())
        free = np.ones(new_n, bool)
        free[list(pinned)] = False
        for i, value in pinned.items():
            Z[i, j] = value
            prov[i, j] = CellLabel.USER_CONSTRAINT
        remaining = target - sum(pinned.values())
        free_sum = float(Z[free, j].sum())
        # Renormalise only where there is something to renormalise. A pin ABOVE
        # the column's own total is left alone deliberately: it is a real, tested
        # capability of this engine -- the analyst asserts a figure the key
        # disagrees with, the balancer reconciles it, and the provenance machinery
        # is required to stop calling the cell "pinned" once the solver has moved
        # it. Raising here would have removed that path; the first draft of this
        # fix did, and `test_a_pinned_cell_the_solver_moved_stops_claiming_to_be
        # _pinned` caught it. What ¶6.36 buys is the ordinary case, which is the
        # common one: a pin inside the total, with the structure applied to the
        # remainder instead of to the whole.
        if remaining > 0 and free_sum > 0:
            Z[free, j] *= remaining / free_sum
        prov[i, j] = CellLabel.USER_CONSTRAINT

    internal = Z[np.ix_(new_pos, new_pos)]
    return {
        "Z": Z, "Y": Y, "VA": VA, "X": X,
        "codes": codes, "labels": labels, "mapping": mapping,
        "new_positions": new_pos, "split_index": p,
        "provenance": prov,
        "keys_used": {"output": key_out, "final_demand": key_y,
                      "value_added": key_va, "intermediate_rows": key_row,
                      "intermediate_cols": key_col},
        # True where the block named no key of its own and took the output
        # key. The distinction matters to a reader and was invisible before.
        "keys_inherited": {"output": inh_out, "final_demand": inh_y,
                           "value_added": inh_va, "intermediate_rows": inh_row,
                           "intermediate_cols": inh_col},
        "weights": {"output": w_out, "final_demand": w_y, "value_added": w_va,
                    "intermediate_rows": w_row, "intermediate_cols": w_col},
        "va_rows": va_rows,
        "internal_block_sum": float(internal.sum()),
        "internal_block_share_pct": float(
            100.0 * abs(internal).sum() / max(abs(Z).sum(), 1e-12)),
        "original_diagonal": float(z_pp),
    }


def internal_block_targets(seed: dict, split: dict, tr, tc):
    """What one split's internal block must sum to, row-wise and column-wise.

    This is the constraint that actually binds, and it is tighter than
    `tr > 0`. The off-block part of each new subsector's row and column is
    already fixed by the proportional split, so the internal block has to
    absorb the remainder.

    Their sums are always equal, and always equal that sector's own diagonal,
    whatever weights are used:

        sum internal_tr = X_p - Y_p - (Zrow_p - z_pp) = z_pp
        sum internal_tc = X_p - VA_p - (Zcol_p - z_pp) = z_pp

    So neither multi-proxy splitting nor an input profile can ever break the
    ACCOUNTING consistency of the system — only the sign feasibility of an
    individual subsector.
    """
    pos = split["positions"]
    Z = seed["Z"]
    off = [i for i in range(len(seed["codes"])) if i not in pos]
    itr = np.asarray(tr)[pos] - Z[np.ix_(pos, off)].sum(axis=1)
    itc = np.asarray(tc)[pos] - Z[np.ix_(off, pos)].sum(axis=0)
    return itr, itc


def feasibility(table: IOTable, seed: dict, split: dict, tr, tc) -> dict:
    """Diagnose whether one split's weights describe a possible economy.

    Returns the binding quantities per subsector so the caller can explain the
    problem in the analyst's terms rather than as a solver row index.
    """
    itr, itc = internal_block_targets(seed, split, tr, tc)
    z_pp = float(split["original_diagonal"])
    # With a positive parent diagonal the internal block is all non-negative,
    # so each of its row and column totals must be non-negative too.
    want_positive = z_pp > 0
    problems = []
    for a, code in enumerate(split["new_codes"]):
        if want_positive and itr[a] < 0:
            problems.append((code, "sells", float(itr[a])))
        if want_positive and itc[a] < 0:
            problems.append((code, "buys", float(itc[a])))

    # How much room is left before some subsector's internal-block total goes
    # negative, as a share of the parent's own internal trade. This is the
    # budget that differentiated input profiles have to fit inside, and it can
    # be very small: a sector that barely trades with itself gives the analyst
    # almost no room to say its subsectors buy differently. Reported so the
    # limit is visible before it is hit rather than as an error afterwards.
    tightest = float(min(itr.min(), itc.min())) if len(itr) else 0.0
    headroom = 100.0 * tightest / z_pp if z_pp else float("nan")
    return {"internal_tr": itr, "internal_tc": itc, "z_pp": z_pp,
            "tightest_internal_total": tightest, "headroom_pct": headroom,
            "feasible": not problems, "problems": problems}


def targets(Y: np.ndarray, VA: np.ndarray, X: np.ndarray):
    """Row and column totals the balanced Z must hit.

        row_i = X_i - final demand_i        (total intermediate sales)
        col_j = X_j - value added_j         (total intermediate purchases)

    Both sum to the same grand total whenever the expanded system preserves
    sum(Y) == sum(VA), which proportional splitting does.
    """
    return X - Y.sum(axis=1), X - VA.sum(axis=0)


def split_sectors(table: IOTable, specs: list[SplitSpec], scenario: Scenario,
                  keys: dict) -> dict:
    """Divide several sectors in one pass.

    Applied sequentially: each split runs on the table the previous one
    produced. That is sound because a split changes only its own sector's row
    and column — every other cell is copied — so the splits do not interfere.
    In particular each supplier's total sales to a group are preserved, so
    splitting B leaves A's row totals untouched, and the internal blocks of
    different splits are disjoint and can be balanced independently.

    ORDER. With no input profiles the result does not depend on the order of
    `specs`; `tests/test_engine.py` asserts it. It CAN depend on the order if a
    later split's `input_profiles` names an earlier split's new subsectors as
    suppliers, because those rows do not exist until the earlier split has run.
    That is a deliberate capability, not an accident: it lets an analyst say
    "beverage serving buys from restaurants, not from catering". Use it
    knowingly.

    Each `spec.sector_code` must name a sector of the ORIGINAL table and no
    sector may be split twice; splitting a subsector further is a different
    operation and is not supported here.
    """
    if not specs:
        raise DisaggregationError("no splits requested")
    seen = set()
    for spec in specs:
        if spec.sector_code in seen:
            raise DisaggregationError(
                f"{spec.sector_code!r} is listed twice; a sector can only be "
                f"split once per scenario")
        seen.add(spec.sector_code)
        table.index_of(spec.sector_code)          # raises if absent
    # Are these codes a legitimate subdivision, or just a list? Checked here so
    # every path gets it -- workbook, script or generated configuration alike.
    # Unrecognised codes are NOT an error: see classification.py.
    code_checks = {}
    for spec in specs:
        chk = check_split(spec.sector_code, spec.new_codes)
        code_checks[spec.sector_code] = chk
        if not chk.ok:
            raise DisaggregationError(
                f"the proposed subdivision of {spec.sector_code!r} is not valid "
                f"in its classification:\n  " + "\n  ".join(chk.problems)
                + f"\n\nSee B_method_cards/M-049. Note what was NOT checked: "
                + "; ".join(chk.unchecked))

    introduced = {c for s in specs for c in s.new_codes}
    clash = introduced & set(table.sector_codes)
    if clash:
        raise DisaggregationError(
            f"new subsector code(s) {sorted(clash)} already exist in the table")
    # A SECOND CHECK USED TO SIT HERE and could never fire. It asked whether a
    # new code repeats the code of a sector being split -- but `seen` is built
    # only from codes `table.index_of` accepted, so `seen` is a subset of the
    # table's own codes and `introduced & seen` is a subset of `clash` above.
    # The line three above always caught it first.
    #
    # Removed rather than left looking like a guard: PROVENANCE.md states the
    # rule for the public tree ("a validator that could not run was removed
    # rather than left to pass vacuously") and it holds for a refusal too.
    # Found by run_refusal_coverage.py, which could not reach it with any
    # input -- the difference between untested and unreachable.

    current = table
    mapping = list(range(table.n))          # current index -> ORIGINAL index
    splits: list[dict] = []

    for spec in specs:
        seed = split_sector(current, spec.sector_code, spec.new_codes,
                            spec.new_labels, scenario, keys, spec)
        p, k = seed["split_index"], len(spec.new_codes)
        # positions recorded by earlier splits shift right of the new slots
        for earlier in splits:
            earlier["positions"] = [q if q < p else q + k - 1
                                    for q in earlier["positions"]]
        mapping = [mapping[i] for i in seed["mapping"]]
        prof_used = (spec.input_profiles or
                     {c: v for c, v in (scenario.input_profiles or {}).items()
                      if c in spec.new_codes})
        prov_meta = spec.profile_provenance or scenario.profile_provenance
        prov_meta = ({"source": prov_meta.source,
                      "source_year": prov_meta.source_year,
                      "strength": getattr(prov_meta.strength, "value",
                                          str(prov_meta.strength)),
                      "notes": prov_meta.notes,
                      "level_shift_before": prov_meta.level_shift_before}
                     if prov_meta else None)
        splits.append({
            "sector_code": spec.sector_code,
            "new_codes": list(spec.new_codes),
            "positions": list(seed["new_positions"]),
            "original_index": table.index_of(spec.sector_code),
            "keys_used": seed["keys_used"],
            "keys_inherited": seed["keys_inherited"],
            "va_rows": seed.get("va_rows", {}),
            "profile_shift": (
                profile_level_shift(table, spec.sector_code, spec.new_codes,
                                    seed["weights"]["intermediate_cols"],
                                    prof_used)
                if prof_used else None),
            "profile_provenance": prov_meta,
            "weights": seed["weights"],
            "original_diagonal": seed["original_diagonal"],
            "internal_block_share_pct": seed["internal_block_share_pct"],
            "code_check": code_checks[spec.sector_code],
            "profiled": bool(spec.input_profiles
                             or any(c in spec.new_codes
                                    for c in (scenario.input_profiles or {}))),
        })
        current = IOTable(
            table_id=current.table_id, country=current.country,
            year=current.year, unit=current.unit,
            classification=current.classification,
            sector_codes=seed["codes"], sector_labels=seed["labels"],
            Z=seed["Z"], Y=seed["Y"], Y_labels=current.Y_labels,
            VA=seed["VA"], VA_labels=current.VA_labels, X=seed["X"],
            source=current.source, notes=current.notes)

    # Provenance is recomputed rather than merged across the splits of THIS
    # run: a cell is estimated exactly when its row or its column belongs to
    # some split's new subsectors.
    #
    # But it is INHERITED from the table that came in. A table this engine
    # produced and wrote out can be read back and split again, and its earlier
    # estimates have to survive that: a cell no split of this run touches is
    # not thereby an observation, it is whatever it already was. Starting every
    # cell at OBSERVED, as this did until 2026-08-25, let the audit trail reset
    # to zero each time a result was written to disk and reopened -- and the
    # reset was invisible, because a derived table balances exactly as well as
    # a published one.
    n = current.n
    prov = np.empty((n, n), dtype=object)
    if table.provenance is None:
        prov[:, :] = CellLabel.OBSERVED
    else:
        inherited = table.provenance
        for i in range(n):
            for j in range(n):
                prov[i, j] = inherited[mapping[i], mapping[j]]
    touched = sorted({q for s in splits for q in s["positions"]})
    prov[touched, :] = CellLabel.PROXY_ESTIMATED
    prov[:, touched] = CellLabel.PROXY_ESTIMATED
    for cell, value in (scenario.user_constraints or {}).items():
        i, j = (int(x) for x in cell.split(","))
        current.Z[i, j] = value
        prov[i, j] = CellLabel.USER_CONSTRAINT

    return {
        "Z": current.Z, "Y": current.Y, "VA": current.VA, "X": current.X,
        "codes": current.sector_codes, "labels": current.sector_labels,
        "mapping": mapping, "provenance": prov, "splits": splits,
        "code_checks": code_checks,
        "touched_positions": touched,
        "new_positions": [q for s in splits for q in s["positions"]],
    }
