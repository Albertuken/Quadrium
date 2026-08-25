"""
How tightly a published table can be asked to balance.

`OQ-B-02` has been open since v1.1 asking what discrepancy in an accounting
identity is acceptable. No loaded source says, and three candidates have been
examined and refused — all of them convergence thresholds on dimensionless
multipliers, or stopping rules for an iteration, which is a different kind of
quantity from a residual in the table's own currency unit.

This module does not answer that question. It answers the one underneath it,
which turns out to be answerable without any source saying anything:

    **What discrepancy is DETECTABLE?**

A table published to `d` decimals states each cell as a value that stands for a
true figure somewhere in a band of width `10^-d` around it. An identity that
sums `n` such cells therefore cannot be checked more tightly than `0.5·10^-d·n`,
**even when the unrounded table balances exactly**. Below that, "balanced" and
"not balanced" are the same observation, and any tolerance tighter than it is
measuring the publisher's rounding rather than the accounts.

This is not a judgement about acceptable error. It is a floor that no acceptance
criterion may go below, and it is arithmetic on the source's own stated
precision rather than a project choice. The acceptance threshold ABOVE that
floor is still unsourced and still a project choice — the two must not share a
constant, for the same reason the handover threshold does not (`M-039`).

CORE_012 SUPPORTS THE PRINCIPLE, WITHOUT STATING THE RULE
---------------------------------------------------------
The chapter's balanced worked example (Tables A11.6–A11.10, pp. 358 ff.) prints
an **empty Check column throughout** — that is, it asserts equality *at the
one-decimal precision of its own tables*. `OQ-B-02` recorded that at v1.1 as
evidence that "the target is exact equality", and it is: exact equality at the
precision the source prints. That is this construct, in the source's own hands.

WHAT THE MEASUREMENT SHOWED, ACROSS EVERY FIXTURE THE PROJECT HOLDS
-------------------------------------------------------------------
    source              decimals   n    residual    floor
    ONS UK 2022         see below  113  1.16e-10    5.7e-06   float64
    INE TIO ES 2022     1           72  2.91e-11    3.6
    INE TOD ES 2022     1           81  7.28e-11    4.05
    Eurostat ES 2022    1           72  2.91e-11    3.6
    Eurostat IT 2022    2           73  0.08        0.365

**Corrected 2026-08-25.** The first line read `unrounded` and it is wrong. The
ONS table is not published to one precision: its intermediate block is full
precision and its final demand, output and total use are **all integers**, in
every edition from 2019 to 2023. Pooling 105 unrounded cells with 10 rounded
ones gives 99.1 % unrounded, `printed_decimals` correctly answers `None` for
the pool, and the identity is then judged at float64 accumulation — 5.7e-06
where what the file can distinguish is **5.0**. See
`assertable_tolerance_mixed`, which measures each block separately, and
`../validators/run_uk_editions.py`, which measures all six editions.

Three things follow, and the third is the one worth carrying.

1. The project's flat `ABS_TOL = 1e-6` is right for four of the five, and it is
   right BY ACCIDENT — a wider accident than this file thought. It survived
   because the ONS's rounded margins happen to be mutually consistent in four
   editions of six, not because the table is unrounded.

2. It is wrong for Italy, and Italy is not at fault: 0.08 across 73 cells
   rounded to two decimals is well inside what that source can distinguish.

3. **Whether a published table balances at its own printed precision is a
   property of the office, not of the framework.** Spain and Italy publish the
   same dataset, under the same regulation, on the same methodology. Spain's
   balances to 1e-11 — the INE balanced the rounded figures themselves. Italy's
   balances only to rounding. Nothing in ESA 2010 requires either.
"""

from __future__ import annotations

import numpy as np

# The share of a source's values that must actually USE a precision level
# before that level is accepted as the source's own. PROJECT CHOICE, and the
# only one in this file.
#
# Measured across the 46 Eurostat cubes the project holds: 45 of them classify
# IDENTICALLY at every threshold from 0.02 to 0.50 — a 25-fold band — and the
# forty-sixth (`naio_10_cp15_FR_2022`) differs only below 0.02. The choice is
# unobservable across that band, which is the same argument `OQ-B-02` made for
# the acceptance threshold itself.
_LEVEL_SHARE = 0.05

# The rule this replaced asked the opposite question: the smallest `d` at which
# 99.95 % of values are REPRESENTABLE. That reads a file's precision off its
# rarest cells rather than its bulk, and five of those 46 cubes are misread by
# it — Belgium's supply and use tables are 90.2 % one-decimal figures with
# **two** two-decimal cells in 2,829, and were judged as two-decimal files and
# therefore held ten times too tight. France and Spain's 2020 symmetric table
# are the same, at 14 cells each.
_COVERAGE = 0.9995     # kept for reference; no longer used to choose `d`

_MAX_DECIMALS = 6      # beyond this a source is treated as unrounded
_FLOAT_EPS = np.finfo(float).eps


def _decimals_needed(v: np.ndarray) -> np.ndarray:
    """How many decimals each value actually uses, `_MAX_DECIMALS + 1` if more."""
    out = np.full(v.shape, _MAX_DECIMALS + 1)
    for d in range(_MAX_DECIMALS + 1):
        m = ((out > _MAX_DECIMALS)
             & (np.abs(v - np.round(v, d)) < 1e-7 * np.maximum(1.0, np.abs(v))))
        out[m] = d
    return out


def printed_decimals(values, level_share: float = _LEVEL_SHARE) -> int | None:
    """The number of decimals a source publishes to, read off the values.

    **The finest level a meaningful share of the values actually use**, not the
    finest level that covers almost all of them. A file of one-decimal figures
    carrying two stray two-decimal cells is a one-decimal file; asking which
    precision *represents* 99.95 % of the values answers "two", because a
    one-decimal figure is representable at two decimals and the two anomalies
    are not representable at one.

    That distinction is not academic. It decided Belgium: 2,829 figures in its
    supply table, 2,553 of them one-decimal, 274 whole numbers, and **two** with
    a second decimal. Judged as a two-decimal file its supply-use pair was held
    to 0.465 and refused for a 0.8 discrepancy; judged as the one-decimal file
    it is, the bound is 4.65 and the pair loads.

    Returns `None` when the values are not rounded at all — the ONS
    intermediate block is like this, and it is why a flat tolerance in currency
    units appeared to work for as long as it did. "Unrounded" is treated as one
    more level and tested by the same rule, so a table with a scattering of
    whole numbers in an otherwise full-precision block is not mistaken for an
    integer table.

    Read off the data rather than taken from the documentation because the
    documentation does not say, and because it varies **within one dataset**:
    Eurostat serves Spain at one decimal and Italy at two, from the same
    `naio_10_*` family under the same regulation. It also varies **within one
    table**: the ONS publishes an unrounded interior and integer margins.
    """
    v = np.asarray(values, float).ravel()
    v = v[np.isfinite(v)]
    v = v[v != 0.0]
    if v.size == 0:
        return None
    nd = _decimals_needed(v)
    if float((nd > _MAX_DECIMALS).mean()) >= level_share:
        return None
    for d in range(_MAX_DECIMALS, -1, -1):
        if float((nd == d).mean()) >= level_share:
            return d
    return None


def assertable_tolerance(values, n_terms: int) -> float:
    """The tightest residual an identity over `n_terms` cells can be held to.

    Two regimes, because there are two different limits and only one of them is
    about rounding:

      * the source rounds — the limit is the rounding itself, `0.5·10^-d·n`;
      * the source does not — the limit is float64 accumulation over `n` terms
        at the magnitude actually present, `n·eps·max|v|`.

    Both are floors on what can be OBSERVED, not statements about what is
    acceptable. A residual below the floor means the identity holds as tightly
    as this source permits anyone to check; it does not mean the underlying
    accounts are exact, and nothing here should be read as saying so.
    """
    d = printed_decimals(values)
    if d is not None:
        return 0.5 * 10.0 ** -d * n_terms
    v = np.asarray(values, float).ravel()
    v = v[np.isfinite(v)]
    # `n*eps*sum|x|`, the textbook bound for accumulating `n` floats -- NOT
    # `n*eps*max|x|`, which the first version used and which is too tight by
    # roughly the ratio of the sum to its largest term. It bit immediately:
    # GRAS refused a synthetic fixture whose margins summed to 12 and 12 with a
    # difference of 2.7e-14, against a floor of 1.2e-14. The margins there are
    # themselves column sums, so they arrive carrying accumulated error of their
    # own before this comparison adds more, and a bound on the last operation
    # alone cannot cover that.
    scale = float(np.abs(v).sum()) if v.size else 1.0
    return max(n_terms * _FLOAT_EPS * scale, np.finfo(float).tiny)


def assertable_tolerance_mixed(*populations) -> float:
    """The floor for an identity whose terms are NOT all printed alike.

    Each argument is a `(values, n_terms)` pair naming one population of terms
    in the identity. The floor of a sum is the sum of the floors, so the
    populations are measured separately and added.

    WHY THIS EXISTS, AND WHY THE ONE FIXTURE THAT MOTIVATED THIS MODULE NEEDS IT
    -----------------------------------------------------------------------------
    The docstring above records `ONS UK 2022  unrounded  113  1.16e-10  5.7e-06`
    and says the project's flat `ABS_TOL = 1e-6` "survived because the founding
    fixture is the ONS table, which is published unrounded."

    **The ONS table is not published unrounded.** Measured across every edition
    from 2019 to 2023: the intermediate block is full precision — under 0.6 % of
    its cells are whole numbers — and **final demand, output and total use are
    every one of them integers**, in all six files. The interior is unrounded
    and the margins are rounded to whole millions.

    Pooling them hides it. 105 unrounded cells against 10 rounded ones is
    99.1 % unrounded, well past this module's 99.95 %-coverage rule in the other
    direction, so `printed_decimals` correctly answers `None` for the pool and
    the whole identity is then judged at float64 accumulation, **about 5.7e-06
    where what it can actually distinguish is 5.0** — nine final-demand
    integers and one output integer, half a unit each. Six orders of magnitude
    too tight, on the fixture this module was written around.

    It went unnoticed because the ONS's rounded margins happen to be mutually
    consistent in four editions of six. In the 2022 revised tables two rows are
    a single unit out and cancel — `CPA_G46` at −1 and `CPA_G47` at +1 — which
    is one rounding unit doing exactly what rounding units do, and the pooled
    bound called it a table that does not balance.

    The 2021 tables are refused either way: 83 of 105 rows disagree with their
    own printed total and `CPA_D351` is out by **259**, which is 259 rounding
    units and not rounding.
    """
    return float(sum(assertable_tolerance(v, n) for v, n in populations))


def infeasibility_floor(u, v) -> float:
    """The tightest residual a solver's OWN OUTPUT can be held to.

    `assertable_tolerance` above is about a table someone else published, and
    its limit is that publisher's rounding. This is the other half of `OQ-B-02`
    and it has a different cause: a solver asked to hit row totals `u` and
    column totals `v` is being asked for a table whose cells sum to `Σu` and to
    `Σv` at once. When those differ, **no table exists**, and the residual is
    not the solver's error — it is the constraints', and it cannot be removed.

    Writing `R_i` for a row residual and `C_j` for a column one, `ΣR − ΣC =
    Σv − Σu`, so `|ΣR| + |ΣC| ≥ |Σu − Σv|` and

        max residual ≥ |Σu − Σv| / (m + n)

    however the solver distributes it. A run that meets the rows exactly, which
    is what GRAS does, faces the tighter `|Σu − Σv| / n` on the columns.

    THIS IS NOT HYPOTHETICAL, AND THE PROJECT'S OWN FIXTURE FAILS ON IT
    -------------------------------------------------------------------
    UNH_18 Box 18.2, p. 568 publishes margins that sum to 866,987.032 against
    866,987.000 — `OQ-B-06`. GRAS reproduces every printed intermediate of the
    chapter's own iterations and still leaves a column total 1.01e-02 out,
    because 0.032 has to land somewhere. Judged by `identities.ABS_TOL = 1e-6`
    that verified-correct result is a failure by four orders of magnitude.
    Judged by this floor — 0.004, which on that fixture is set by the margins'
    own three printed decimals rather than by the 0.00246 infeasibility bound —
    it is 2.5x, and 1.58x the row-exact `|Σu − Σv| / n`: the right answer.

    Returns a floor, never an acceptance criterion. Consistent constraints fall
    through to the float64 accumulation limit, which is what remains when the
    arithmetic is the only source of error left.
    """
    u = np.asarray(u, float).ravel()
    v = np.asarray(v, float).ravel()
    gap = abs(float(u.sum()) - float(v.sum()))
    combined = np.concatenate([u, v])
    noise = assertable_tolerance(combined, max(u.size, v.size))
    return max(gap / (u.size + v.size), noise)
