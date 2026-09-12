"""Regionalising a national table with the location quotient family.

The method is `library/specs/B_method_cards/M-070_flq_regionalisation.md`, which
is the contract this module implements. Sources: `CORE_039` (Torój 2024) for the
family in one notation, `CORE_034` (Flegg & Tohmo) for the FLQ's calibration,
`CORE_033` (Szabó 2015) for the map.

WHAT THIS RETURNS BESIDES A MATRIX
------------------------------------
A `Regionalisation` carries the coefficients, the scaling factors actually
applied, the interregional imports the scaling implies, and **the measured cost
of the choices the caller did not make**. That last part is not decoration.
`CORE_036` p. 35 argues the ultimate responsibility for a table sits with the
analyst and that there should be no refuge in mechanically produced figures; a
function that returns a matrix and nothing else invites exactly that refuge.

The costs are measurements, not opinions, and each is checked by a validator:

    the whole family overstates local multipliers      SLQ +6.9 % to +20.0 %
                                                       (10 regions, 2 countries)
    using delta = 0.25 blind, against a fitted value   mean 2.2 points, worst 6.8
    cross-hauling the family does not reproduce        28.3 % of Catalonia's
                                                       interregional trade
    interregional spillover a single-region table      median 11.7 % of the
    cannot contain at all: the output an impulse       multiplier, 2.1 % to
    sets off in OTHER regions, of which the part       41.5 % (259 regions)
    returning to this one is a median 0.04 %           -- a LOWER bound: the
    (`run_wide_against_surveys.py`)                    archive it is measured
                                                       on holds 0.25 of the
                                                       surveyed trade with the
                                                       rest of the country;
                                                       moved to the surveys'
                                                       level, median 21.6 %

See `run_flq_delta.py`, `run_delta_across_regions.py` and
`run_regionalisation_crosshauling.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

METHODS = ("SLQ", "CILQ", "RLQ", "FLQ")

# Measured, not assumed. Sources named in the module docstring.
EVIDENCE = {
    "slq_multiplier_bias_pct": (6.9, 20.0),
    "blind_delta_cost_points": {"mean": 2.2, "median": 1.4, "worst": 6.8},
    "fitted_delta_range": (0.14, 0.60),
    "fitted_delta_median": 0.26,
    "regions_measured": 10,
    "countries_measured": 2,
    # What a SINGLE-REGION table cannot contain, measured on the European
    # MRIO's 272 regions: the share of the output multiplier that travels
    # through other regions and comes back. Every table this module produces
    # has it at zero by construction. `run_mrio_spillovers.py`.
    "spillover_share_pct": {"p10": 2.1, "median": 11.7, "p90": 41.5},
    "spillover_regions_measured": 259,
    # And how far that archive can be trusted on it. Where surveys record a
    # region's trade -- nine Austrian regions and Catalonia -- the archive
    # gives a region a quarter of the purchases from the rest of its country
    # that they record, and twice the purchases from itself, while the total
    # it buys is about right. So the spillover above is more likely too low
    # than too high; how much is `spillover_share_pct_survey` below. It holds
    # at the surveys' own year too: 0.23 in 2010 (`run_mrio_same_year.py`).
    # `run_mrio_against_surveys.py`.
    "mrio_vs_surveys": {"regions": 10, "lower_in": 10,
                        "rest_of_country_ratio": 0.25, "own_ratio": 2.06},
    # And how far below: the archive's trade with the rest of the country
    # multiplied by 4, its partners and every column total unchanged. A
    # counterfactual on the coefficients, not a corrected archive; the ten
    # surveyed regions, each on its own survey's split, all lose more.
    # `run_spillover_sensitivity.py`.
    "spillover_share_pct_survey": {"p10": 4.7, "median": 21.6, "p90": 61.4,
                                   "surveyed_higher": 10, "factor": 4.0},
    # The same question asked of the THREE-BLOCK table, on the nine Austrian
    # regions at 2010 against their own 2010 surveys. Two answers that pull in
    # opposite directions: the total an impulse sets off hardly moves when the
    # archive's home bias is corrected, but the line between "here" and "the
    # rest of the country" moves a lot, and always the same way. And what a
    # one-region table omits turns out to be production ELSEWHERE rather than
    # feedback returning home, which the engine used to call feedback.
    # `run_wide_against_surveys.py`.
    # The three-block table's own cross-check, and what the report's landing
    # table quotes: where an impulse lands read off three blocks, against the
    # same quantity read off all 2,720 units. `run_eu_mrio_wide.py`.
    "wide_lands_vs_full": {"regions": 7, "median_pts": 0.05, "max_pts": 1.7},
    "wide_vs_surveys": {"regions": 9, "rest_of_country_of_gain": 0.81,
                        "feedback_pct": 0.04, "total_move_pct": -0.09,
                        "here_pct": 88.9, "here_pct_survey": 72.7},
    # And whether any of it depends on the year. Across the deposit's eleven
    # years the archive's median stays put while a single region's figure
    # moves by several points; regions keep their order.
    # `run_spillover_years.py`.
    "spillover_by_year": {"median_min": 10.8, "median_max": 12.3,
                          "region_range_median_pts": 5.1,
                          "region_range_p90_pts": 9.8,
                          "rank_2008_2018": 0.86},
    # The same in jobs: Eurostat's employment for the 229 regions that have
    # it, weighting the full 2018 inverse. On the 2,200 units that have both
    # employment and trade; the output figure is on those same units, which
    # is why it is not the 11.7 above. `run_employment_spillovers.py`.
    "employment_spillover_pct": {"p10": 3.0, "median": 11.4, "p90": 45.0,
                                 "units": 2210,
                                 "output_median_same_units": 13.6,
                                 "median_if_surveyed": 20.7,
                                 "unmeasured_median_pct": 0.2,
                                 "unmeasured_p90_pct": 1.5},
    # Region by region, weighted by the final demand for its own products (the
    # five categories the loaded table carries, exports included): the share
    # of the output and of the jobs that demand sets off elsewhere.
    # Without exports the output median is 12.1. `run_demand_spillovers.py`.
    "demand_spillover_pct": {"output_regions": 259, "output_p10": 3.4,
                             "output_median": 10.5, "output_p90": 20.6,
                             "jobs_regions": 221, "jobs_p10": 5.2,
                             "jobs_median": 10.4, "jobs_p90": 20.0,
                             "output_median_if_surveyed": 19.8,
                             "jobs_median_if_surveyed": 19.4,
                             "output_median_without_exports": 12.1},
    # And by year, 2008 to 2018, with Eurostat's employment for each: the
    # archive's medians barely move, a region's weighted figure moves more
    # than its output figure does, and regions keep their order less well
    # (+0.71 against +0.86 for output). `run_employment_years.py`.
    # A guard, and what it found. Employment over output, region by region,
    # against the median region's: three regions stood at 25 to 40 times it on
    # 2026-09-11, and that turned out to be the archive's own labels naming
    # other regions (`run_mrio_labels.py`). With the labels corrected no region
    # passes ten times and the largest is 5.1, so the guard fires on nothing --
    # which is the point of keeping it. `run_demand_spillovers.py`.
    "implausible_output": {"regions": [],
                           "threshold_times_median": 10,
                           "largest_times_median": 5.1},
    "employment_by_year": {"unit_median_min": 10.4, "unit_median_max": 11.5,
                           "demand_median_min": 9.7,
                           "demand_median_max": 11.0,
                           "region_range_median_pts": 5.1,
                           "region_range_p90_pts": 12.1,
                           "rank_2008_2018": 0.72},
}


@dataclass
class Regionalisation:
    """The regional coefficients, and what the caller should know about them."""

    A: np.ndarray                       # regional domestic coefficients, n x n
    q: np.ndarray                       # the scaling factors applied
    method: str
    delta: Optional[float]
    lam: Optional[float]                # FLQ's lambda, None for the others
    slq: np.ndarray
    implicit_imports: np.ndarray        # by product, CORE_039 p. 292
    X: np.ndarray                       # the regional output the scaling used
    caveats: list[str] = field(default_factory=list)

    def _regional_satellites(self, national) -> tuple[dict, list]:
        """Carry the national accounts down to the region, scaled by output.

        WHY SCALED AND NOT DROPPED
        ----------------------------
        Dropping is safer and it is also silent, and silence is the failure
        this project keeps finding in itself: a user loads an employment
        account, regionalises, and the account vanishes with nothing saying
        so. Carrying it unchanged would be worse -- it would give the region
        the whole country's employment.

        So it is scaled by the region's share of national output, sector by
        sector, which is the same bargain a split makes: **the region is
        assumed to have the country's intensity**, the same jobs per euro, the
        same tonnes per euro. Every value comes out `estimated` and the caveat
        travels with the run.

        AND THE ASSUMPTION IS OF THE KIND THIS PROJECT HAS SEEN FAIL
        -------------------------------------------------------------
        Not for employment -- nothing here measured that. But there is one
        measurement of an intensity transported from a nation to one of its
        regions, and it went the wrong way.
        `run_charm_heterogeneity.py`: Spain against Catalonia, rank
        correlation **0.886**, so the ORDERING carries, while Catalonia's mean
        is **1.40x** Spain's and the national value under-predicts in **47 of
        63** products. A region trades more than its country, and nothing says
        it employs or emits exactly like it either.

        A different quantity, so this is the nearest measured case and not
        evidence about employment. What it establishes is that "carry the
        national intensity" is an assumption with a track record.
        """
        if national is None or not getattr(national, "satellites", None):
            return {}, []
        from .models import Satellite

        nat_X = np.asarray(national.X, float).ravel()
        share = np.where(nat_X > 0,
                         self.X / np.where(nat_X == 0, 1.0, nat_X), 0.0)
        undefined = int((nat_X <= 0).sum())

        out = {}
        for name, sat in national.satellites.items():
            vals = (np.asarray(sat.values, float) * share).tolist()
            out[name] = Satellite(
                name=sat.name, unit=sat.unit, values=vals,
                source=sat.source, source_year=sat.source_year,
                origin=["estimated"] * len(vals),
                notes=((sat.notes + " · " if sat.notes else "")
                       + "scaled from the national account by this region's "
                         "share of national output: the region is assumed to "
                         "have the country's intensity"))
        notes = [
            f"- the {len(out)} satellite account(s) are the national ones "
            f"scaled by this region's share of output, which assumes the "
            f"region has the country's intensity. Every value is an estimate; "
            f"if you hold the quantity FOR THIS REGION, that is the number to "
            f"use"]
        if undefined:
            notes.append(
                f"- {undefined} sector(s) have no national output, so their "
                f"share is undefined and their accounts come out zero rather "
                f"than scaled")
        return out, notes

    def to_table(self, *, sector_codes, sector_labels=None, country="XX-region",
                 year=0, unit="", classification="", source="",
                 national=None) -> "object":
        """The estimated region as an `IOTable`, so the rest of the engine can
        take it.

        Until v1.85 `--regionalise` produced a coefficient matrix and stopped:
        nothing downstream could diagnose it, split a sector of it, or export
        it. No new data is needed to go further --

            Z = A * diag(X)
            final demand and exports = X - Z.sum(1)     (row residual)
            value added and imports  = X - Z.sum(0)     (column residual)

        -- and both of IOTable's balance identities then hold BY CONSTRUCTION.
        That is arithmetic already implicit in what the method computes, not a
        new assumption.

        **One column and one row, deliberately.** The quotient says nothing
        about how a region's final demand splits between households and exports,
        or its value added between labour and capital. Returning several columns
        would imply a detail the method does not have, so it returns one and
        names it for what it is.
        """
        from .models import CellLabel, IOTable

        n = len(sector_codes)
        if n != len(self.X):
            raise ValueError(f"{n} sector codes for {len(self.X)} sectors")
        Z = self.A * self.X
        Y = (self.X - Z.sum(axis=1)).reshape(n, 1)
        VA = (self.X - Z.sum(axis=0)).reshape(1, n)
        note = None
        if float(Y.min()) < 0:
            k = int(np.argmin(Y))
            note = (f"the row residual is negative for {sector_codes[k]} "
                    f"({float(Y[k, 0]):,.4f}): its estimated intermediate sales "
                    f"exceed its output, which a row of A summing above 1 can "
                    f"do. Carried rather than clipped")
        sats, sat_notes = self._regional_satellites(national)

        # THE TYPE II CLOSURE CANNOT COME, and that is a fact about the object
        # rather than a limitation of the code. Its two settings name a
        # value-added ROW and a final-demand COLUMN of the national table; this
        # table has one of each and both are residuals, because the quotient
        # says nothing about how a region's value added splits between labour
        # and capital. There is no wages row to close on.
        #
        # Said, not dropped. A table that comes back type I where the user
        # configured type II shows multipliers a third smaller with nothing
        # explaining why -- the same silence the satellites had until today.
        if national is not None and getattr(national, "type_ii", None):
            sat_notes.append(
                "- the type II closure did NOT come with the region: it names "
                "a wages row and a household column of the national table, "
                "and a regionalised table has one value-added row and one "
                "final-demand column, both residuals. These multipliers are "
                "type I")

        return IOTable(
            table_id=f"regionalised_{self.method.lower()}",
            satellites=sats,
            country=country, year=year, unit=unit,
            classification=classification,
            sector_codes=list(sector_codes),
            sector_labels=list(sector_labels or sector_codes),
            Z=Z, Y=Y, Y_labels=["final demand and exports (residual)"],
            VA=VA, VA_labels=["value added and imports (residual)"],
            X=self.X.copy(), source=source or f"Quadrium {self.method}",
            notes=note,
            # EVERY CELL IS AN ESTIMATE, and the table has to say so itself.
            # `provenance=None` means "a publisher's table, every cell an
            # observation as far as this system can tell" -- which is what the
            # first version of this method returned, and it is exactly the
            # failure the field exists to prevent: read back, a regionalised
            # table would have handed a later split a matrix of estimates
            # wearing the status of measurements, and the audit trail would
            # have reset to zero at the file boundary.
            # np.full() infers a fixed-width string dtype from the enum and
            # silently truncates it to 'CellLabel.PROXY'; build the object
            # array first and fill it.
            provenance=_estimated(n),
            lineage=[f"regionalised from a national table with {self.method}"
                     + (f", delta = {self.delta:g}" if self.delta is not None
                        else "")]
            + [c.strip() for c in self.caveats if c.strip().startswith("-")]
            + sat_notes)

    def report(self) -> str:
        """The costs, as a block a caller can print beside the numbers."""
        return "\n".join(self.caveats)


def _estimated(n: int) -> np.ndarray:
    """An n x n provenance array in which every cell is a proxy estimate."""
    from .models import CellLabel

    out = np.empty((n, n), dtype=object)
    out[:] = CellLabel.PROXY_ESTIMATED
    return out


def _quotients(slq: np.ndarray, method: str, lam: float) -> np.ndarray:
    """CORE_039 eqs. (2)-(8). See M-070 for the numbering."""
    n = len(slq)
    if method == "SLQ":
        return np.minimum(slq, 1.0)[:, None] * np.ones((n, n))
    if method == "CILQ":
        raw = slq[:, None] / slq[None, :]
    elif method == "RLQ":
        raw = slq[:, None] / np.log2(1.0 + slq)[None, :]
    else:                                                   # FLQ
        raw = (slq[:, None] / slq[None, :]) * lam
    q = np.minimum(raw, 1.0)
    np.fill_diagonal(q, np.minimum(slq * (lam if method == "FLQ" else 1.0), 1.0))
    return q


def regionalise(A_national: np.ndarray,
                Q_region: np.ndarray,
                Q_national: np.ndarray,
                *,
                method: str = "FLQ",
                delta: Optional[float] = None,
                X_region: Optional[np.ndarray] = None) -> Regionalisation:
    """Estimate a region's domestic coefficients from the national table.

    `A_national` must be the **domestic** matrix. Feeding it a total-flow matrix
    regionalises the country's imports as though they were domestic supply, and
    nothing downstream catches it -- see M-070's DOMESTIC_IMPORT_TREATMENT and
    `run_regional_truth_survey.py`, which shows what that looks like when it
    happens.

    `X_region` is only needed for `implicit_imports`; it defaults to `Q_region`,
    which is right when activity is measured as output.
    """
    A_national = np.asarray(A_national, float)
    Q_region = np.asarray(Q_region, float).ravel()
    Q_national = np.asarray(Q_national, float).ravel()

    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}; expected one of "
                         f"{', '.join(METHODS)}")
    n = len(Q_region)
    if A_national.shape != (n, n):
        raise ValueError(f"A_national must be {n}x{n} to match the {n} sectors "
                         f"of Q_region, got {A_national.shape}")
    if len(Q_national) != n:
        raise ValueError(f"Q_national has {len(Q_national)} sectors against "
                         f"Q_region's {n}; align the classifications first, do "
                         f"not pad")
    if not np.isfinite(A_national).all():
        raise ValueError("A_national carries non-finite entries")
    neg = np.argwhere(A_national < 0)
    if neg.size:
        i, j = neg[0]
        raise ValueError(
            f"A_national[{i}, {j}] = {A_national[i, j]:.6g} is negative. The "
            f"quotient rule applies min(q, 1) to scale a coefficient DOWN, "
            f"which moves a negative one up; M-070 does not admit them")
    if Q_region.sum() <= 0 or Q_national.sum() <= 0:
        raise ValueError("regional and national activity must both be positive")
    bad = np.argwhere((Q_national <= 0) & (Q_region > 0))
    if bad.size:
        raise ValueError(
            f"sector {int(bad[0][0])} has positive regional activity and none "
            f"nationally, so its quotient is undefined. That is a "
            f"classification error upstream, not a value to substitute")

    if method == "FLQ":
        if delta is None:
            raise ValueError(
                "the FLQ needs a delta and there is no defensible default: "
                "measured across 10 regions in 2 countries it runs from "
                f"{EVIDENCE['fitted_delta_range'][0]} to "
                f"{EVIDENCE['fitted_delta_range'][1]} with a median of "
                f"{EVIDENCE['fitted_delta_median']}. Pass one and read the "
                "caveats, or choose CILQ and accept its bias. See OQ-R-02")
        if not 0.0 <= delta < 1.0:
            raise ValueError(f"delta must satisfy 0 <= delta < 1, got {delta}")
        lam = float(np.log2(1.0 + Q_region.sum() / Q_national.sum()) ** delta)
    else:
        lam = 1.0

    with np.errstate(divide="ignore", invalid="ignore"):
        slq = (Q_region / Q_region.sum()) / (Q_national / Q_national.sum())
    slq = np.where(np.isfinite(slq) & (slq > 0), slq, 0.0)

    q = _quotients(slq, method, lam)
    A = A_national * q
    x = Q_region if X_region is None else np.asarray(X_region, float).ravel()
    implicit = ((A_national - A) * x).sum(axis=1)

    lo, hi = EVIDENCE["slq_multiplier_bias_pct"]
    cost = EVIDENCE["blind_delta_cost_points"]
    caveats = [
        f"Measured on {EVIDENCE['regions_measured']} regions across "
        f"{EVIDENCE['countries_measured']} countries:",
        f"  - the quotient family overstates local output multipliers; SLQ by "
        f"{lo:.1f} % to {hi:.1f} %",
        f"  - cross-hauling is not reproduced in any amount anyone chose; it is "
        f"28.3 % of Catalonia's interregional trade",
        f"  - this is a SINGLE-REGION table: an impulse cannot leave it and "
        f"come back, and what it sets off elsewhere is not in it either. "
        f"Across {EVIDENCE['spillover_regions_measured']} European "
        f"regions that spillover is a median "
        f"{EVIDENCE['spillover_share_pct']['median']:.1f} % of the output "
        f"multiplier, and between "
        f"{EVIDENCE['spillover_share_pct']['p10']:.1f} % and "
        f"{EVIDENCE['spillover_share_pct']['p90']:.1f} % from the tenth "
        f"percentile to the ninetieth. Nothing in a region's own accounts "
        f"says which end it sits at. And it was measured on an archive that, "
        f"where {EVIDENCE['mrio_vs_surveys']['regions']} regional surveys can "
        f"check it, records {EVIDENCE['mrio_vs_surveys']['rest_of_country_ratio']:.2f} "
        f"times the trade a region has with the rest of its country, so the "
        f"true spillover is more likely higher: moved to what the surveys "
        f"record, the median is "
        f"{EVIDENCE['spillover_share_pct_survey']['median']:.1f} %, not "
        f"{EVIDENCE['spillover_share_pct']['median']:.1f} %",
    ]
    if method == "FLQ":
        caveats.insert(1, f"  - delta = {delta:g} was supplied, not derived. A "
                          f"blind 0.25 costs a mean {cost['mean']:.1f} points of "
                          f"multiplier bias, worst {cost['worst']:.1f}")
    else:
        caveats.insert(1, f"  - {method} has no calibration at all; the FLQ at a "
                          f"fitted delta is roughly an order of magnitude closer")
    return Regionalisation(A=A, q=q, method=method, delta=delta,
                           lam=lam if method == "FLQ" else None,
                           slq=slq, implicit_imports=implicit, X=x.copy(),
                           caveats=caveats)
