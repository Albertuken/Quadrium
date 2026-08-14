"""
Balancing diagnostics from CORE_012 (UN Handbook on SUT and IOT 2018, ch. 11,
"Balancing the supply and use tables", publication pages 319-368).

Specified by library/specs/B_method_cards/M-030 (diagnostic battery), M-037
(negative triage), M-038 (implied tax rates), M-039 (handover threshold), and
identities ID-15, ID-16, ID-17 in library/specs/A_core_accounting_spec.md A.6.

Design rules, unchanged from identities.py:
  * numerical checks only; never selects a method, repairs data or relabels a
    value's status;
  * every check carries its citation;
  * a check that cannot run reports NOT APPLICABLE. It never passes vacuously.

TWO THINGS THIS MODULE DOES NOT DO, BECAUSE THE SOURCE DOES NOT SPECIFY THEM:

  1. It does not supply a sourced numerical tolerance. CORE_012 contains no
     absolute tolerance, no relative tolerance, no convergence criterion and no
     definition of "small", "large" or "significant" -- all of which it uses as
     operative terms (par. 11.105, pp. 342-343; par. 11.114, p. 345; par. 11.124,
     p. 348; Annex A11.6, p. 351). Every constant below is prefixed PROJECT_ and
     is a project choice. See D_open_questions.md OQ-B-02.

  2. It does not decide whether a negative is "unwanted" in the sense of
     par. 11.66, pp. 333-334. The chapter gives the rule and not the test. The
     triage below applies the CITED block list from A_core_accounting_spec.md
     A.8.1 first, and escalates the remainder as UNCLASSIFIED rather than
     zeroing it. See D_open_questions.md OQ-B-04.

A DIAGNOSTIC IS ADVISORY. CORE_012's own phrasing is preserved deliberately:
"this indicates that there may be something wrong in the data and further
investigation is advisable" (par. 11.19, p. 323). Nothing here authorises an
automatic correction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# ---------------------------------------------------------------------------
# Thresholds. ALL OF THESE ARE PROJECT CHOICES. No loaded CORE source gives one.
# ---------------------------------------------------------------------------

# Identity-level closeness reuses identities.py ABS_TOL/REL_TOL. The constants
# below are a DIFFERENT quantity: how large a residual may be and still be handed
# to an automated procedure (CORE_012 par. 11.105, pp. 342-343; A11.6, p. 351).
# The two must not share a value -- the handover threshold is far the larger.
PROJECT_HANDOVER_ABS = 1.0        # table units, e.g. GBP million
PROJECT_HANDOVER_REL = 1e-3       # share of the row/column gross scale

# "Outlier" and "deviates significantly" are undefined in CORE_012 par. 11.21,
# p. 323 and par. 11.38, p. 327.
PROJECT_OUTLIER_MAD = 5.0         # median absolute deviations
PROJECT_RATIO_JUMP = 0.10         # change in a credibility ratio vs t-1

# Denominator guard for ratio and index diagnostics. CORE_012's own Table A11.2,
# p. 354 prints a price index of 568.8 and one of -100.0 because it does not
# apply one. See M-035 NEGATIVE_VALUES.
PROJECT_MIN_BASE = 1e-9


PASS = "PASS"
FLAG = "FLAG"                     # soft diagnostic fired; investigate, do not fix
FAIL = "FAIL"                     # hard constraint violated
NA = "NOT APPLICABLE"             # inputs absent; never reported as PASS


@dataclass
class Check:
    check_id: str
    name: str
    citation: str
    status: str
    n_flagged: int = 0
    worst: float = 0.0
    detail: str = ""
    info: dict = field(default_factory=dict)

    def __str__(self) -> str:
        s = (f"[{self.status:>14s}] {self.check_id}  {self.name}\n"
             f"                 flagged = {self.n_flagged}   worst = {self.worst:.6g}\n"
             f"                 {self.citation}")
        if self.detail:
            for line in self.detail.splitlines():
                s += f"\n                 {line}"
        return s


def not_applicable(check_id: str, name: str, citation: str, reason: str) -> Check:
    return Check(check_id, name, citation, NA, detail=reason)


def _safe_ratio(num, den, min_base=PROJECT_MIN_BASE):
    """Ratio that returns NaN rather than a number where the base is too small.

    Sign-safe by construction: a negative base is allowed (subsidies, margin
    rows), but a base whose magnitude is below min_base is not, because the
    resulting ratio carries no information. A.8.1 lists the cells that are
    legitimately negative.
    """
    num = np.asarray(num, dtype=float)
    den = np.asarray(den, dtype=float)
    out = np.full(np.broadcast(num, den).shape, np.nan)
    ok = np.abs(den) > min_base
    np.divide(num, den, out=out, where=ok)
    return out


# ---------------------------------------------------------------------------
# ID-15 / ID-16 / ID-17 -- identities added to A.6 from CORE_012
# ---------------------------------------------------------------------------

def id15_margin_supply_vs_valuation_matrix(supply_column, valuation_matrix,
                                           label="TTM", abs_tol=1e-6, rel_tol=1e-9):
    """ID-15  per product, the supply-table margin/tax column equals the total
    of the corresponding valuation matrix over users.

    "for each product, the trade and transport margins in the supply table have
    to be equal to the sum by columns of the relevant valuation matrices"
    (CORE_012 par. 11.16, p. 323). The annex states the same for taxes less
    subsidies and calls the same quantity a ROW total (A11.5, p. 351); the
    orientation wording differs in the source, the quantity does not. This
    project stores valuation matrices as product x user, so it is a row sum.

    Balancing breaks this identity as a side effect and it must be re-imposed
    (CORE_012 par. 11.75, p. 336; method card M-038).
    """
    col = np.asarray(supply_column, dtype=float)
    mat = np.asarray(valuation_matrix, dtype=float)
    if mat.ndim != 2 or mat.shape[0] != col.shape[0]:
        return not_applicable("ID-15", f"{label} supply column vs valuation matrix",
                              "CORE_012 par. 11.16, p. 323; A11.5, p. 351",
                              "valuation matrix absent or wrongly shaped")
    tot = mat.sum(axis=1)
    dev = np.abs(col - tot)
    scale = np.abs(mat).sum(axis=1)          # gross scale: the row sums to ~0
    ok = dev <= (abs_tol + rel_tol * scale)
    return Check("ID-15", f"{label} supply column = valuation-matrix totals by product",
                 "CORE_012 par. 11.16, p. 323; Annex A11.5, p. 351",
                 PASS if ok.all() else FAIL, int((~ok).sum()), float(dev.max()))


def id16_six_pack(v_t_current, v_t_prev_prices, v_tm1_current,
                  labels=None, abs_tol=1e-6):
    """ID-16  value index = price index x volume index / 100, from the six-pack.

    Three stored values per entry (CORE_012 par. 11.29, p. 325; Figure 11.2,
    p. 325):
        v[t, p_t]        value for year t at current prices
        v[t, p_{t-1}]    value for year t in prices of t-1
        v[t-1, p_{t-1}]  value in current prices for year t-1

    The chapter's own worked figures, 525 / 510 / 500, give 102.9 / 102.0 / 105.0.

    PRECONDITION, and it is hard: the identities hold in volume terms only under
    "the combination of the Laspeyres volume index and Paasche price index
    formula" (par. 11.17, p. 323). This function cannot verify that; the caller
    must.

    Indices are suppressed (NaN) where a base is below PROJECT_MIN_BASE. That is
    a project rule forced by CORE_012's own Table A11.2, p. 354, which prints
    568.8 and -100.0 because it applies no such guard.
    """
    a = np.asarray(v_t_current, dtype=float)
    b = np.asarray(v_t_prev_prices, dtype=float)
    c = np.asarray(v_tm1_current, dtype=float)

    price = 100.0 * _safe_ratio(a, b)
    volume = 100.0 * _safe_ratio(b, c)
    value = 100.0 * _safe_ratio(a, c)

    defined = ~(np.isnan(price) | np.isnan(volume) | np.isnan(value))
    if not defined.any():
        return not_applicable("ID-16", "value index = price index x volume index / 100",
                              "CORE_012 par. 11.17, p. 323; Figure 11.2, p. 325",
                              "no cell has all three six-pack values on a usable base")

    dev = np.zeros_like(value)
    dev[defined] = np.abs(value[defined] - price[defined] * volume[defined] / 100.0)
    bad = defined & (dev > abs_tol)
    n_sup = int((~defined).sum())
    return Check("ID-16", "value index = price index x volume index / 100",
                 "CORE_012 par. 11.17, p. 323; Figure 11.2, p. 325",
                 PASS if not bad.any() else FAIL,
                 int(bad.sum()), float(dev[defined].max()),
                 f"{int(defined.sum())} cells tested, {n_sup} suppressed "
                 f"(base below PROJECT_MIN_BASE or negative-base index)",
                 {"price": price, "volume": volume, "value": value})


def id17_income_approach_gva(gva_production, gross_operating_surplus,
                             compensation_of_employees,
                             other_taxes_on_production,
                             other_subsidies_on_production=None,
                             components_independently_sourced=False,
                             abs_tol=1e-6, rel_tol=1e-9):
    """ID-17  income-approach GVA by industry, MINIMUM form.

    "the minimum that should be incorporated in the SUTs compilation and
    balancing process":
        gross operating surplus
      + compensation of employees
      + other taxes on production and imports
      - other subsidies on production
      = GVA at basic prices (income approach)
    (CORE_012 par. 11.96, p. 340)

    Balanced against the production approach per industry (par. 11.93, p. 339).

    CIRCULARITY. Where net operating surplus was itself used as the balancing
    item -- which CORE_012 A11.5, p. 351 says is the general practice -- this
    identity holds by construction and tests nothing. CORE_006 par. 9.17, p. 279
    states the same caveat. The caller must declare whether the components are
    independently sourced; if not, the result is reported but marked.
    """
    gos = np.asarray(gross_operating_surplus, dtype=float)
    coe = np.asarray(compensation_of_employees, dtype=float)
    otp = np.asarray(other_taxes_on_production, dtype=float)
    total = gos + coe + otp
    if other_subsidies_on_production is not None:
        total = total - np.asarray(other_subsidies_on_production, dtype=float)

    gvp = np.asarray(gva_production, dtype=float)
    dev = np.abs(total - gvp)
    scale = np.maximum(np.abs(total), np.abs(gvp))
    ok = dev <= (abs_tol + rel_tol * scale)

    note = ("components are NOT independently sourced -- this identity is "
            "circular here and tests nothing (CORE_006 par. 9.17, p. 279; "
            "CORE_012 A11.5, p. 351)")
    return Check("ID-17", "Income-approach GVA by industry (minimum form)",
                 "CORE_012 par. 11.93, p. 339; par. 11.96, p. 340",
                 PASS if ok.all() else FAIL, int((~ok).sum()), float(dev.max()),
                 "" if components_independently_sourced else note)


# ---------------------------------------------------------------------------
# M-030 -- the diagnostic battery
# ---------------------------------------------------------------------------

def d2_credibility_ratios(gva=None, output=None,
                          taxes_on_products=None, supply=None,
                          margins=None,
                          prior=None):
    """D2  the credibility ratios CORE_012 par. 11.38, p. 327 lists verbatim:

        GVA to total output ratios, "while recognizing that activities such as
            processing require careful consideration"
        changes in the composition of GVA weights
        taxes on products, trade and transport margins as a proportion of the
            supply and use of products

    `prior` is the same dict from t-1, for the change test. NO THRESHOLD IS
    GIVEN for any of these; PROJECT_RATIO_JUMP and PROJECT_OUTLIER_MAD are
    project choices.

    Returns a list of Check records, one per ratio that could be computed.
    """
    out = []
    cite = "CORE_012 par. 11.38, p. 327"

    def _outliers(name, ratio, check_id):
        r = np.asarray(ratio, dtype=float)
        fin = r[np.isfinite(r)]
        if fin.size == 0:
            return not_applicable(check_id, name, cite, "ratio undefined everywhere")
        med = float(np.median(fin))
        mad = float(np.median(np.abs(fin - med))) or float("inf")
        z = np.abs(r - med) / mad
        flag = np.isfinite(z) & (z > PROJECT_OUTLIER_MAD)
        detail = (f"median={med:.4f}  MAD={mad:.4f}  "
                  f"defined on {int(np.isfinite(r).sum())} of {r.size}  "
                  f"threshold {PROJECT_OUTLIER_MAD} MAD is a PROJECT CHOICE")
        return Check(check_id, name, cite,
                     FLAG if flag.any() else PASS,
                     int(flag.sum()), float(np.nanmax(z[np.isfinite(z)]) if np.isfinite(z).any() else 0.0),
                     detail, {"ratio": r, "flagged": flag})

    if gva is not None and output is not None:
        out.append(_outliers("GVA / output by industry",
                             _safe_ratio(gva, output), "D2a"))
    else:
        out.append(not_applicable("D2a", "GVA / output by industry", cite,
                                  "gva or output not supplied"))

    if taxes_on_products is not None and supply is not None:
        out.append(_outliers("taxes on products / supply of product",
                             _safe_ratio(taxes_on_products, supply), "D2b"))
    else:
        out.append(not_applicable("D2b", "taxes on products / supply of product", cite,
                                  "taxes on products or supply not supplied"))

    if margins is not None and supply is not None:
        out.append(_outliers("trade and transport margins / supply of product",
                             _safe_ratio(margins, supply), "D2c"))
    else:
        out.append(not_applicable("D2c", "trade and transport margins / supply of product",
                                  cite, "margin column not supplied -- an analytical "
                                        "IOT at basic prices has none"))

    if prior and gva is not None and output is not None \
            and prior.get("gva") is not None and prior.get("output") is not None:
        now = _safe_ratio(gva, output)
        before = _safe_ratio(prior["gva"], prior["output"])
        d = np.abs(now - before)
        flag = np.isfinite(d) & (d > PROJECT_RATIO_JUMP)
        out.append(Check("D2d", "change in GVA/output ratio vs t-1", cite,
                         FLAG if flag.any() else PASS, int(flag.sum()),
                         float(np.nanmax(d)) if np.isfinite(d).any() else 0.0,
                         f"threshold {PROJECT_RATIO_JUMP} is a PROJECT CHOICE"))
    else:
        out.append(not_applicable("D2d", "change in GVA/output ratio vs t-1", cite,
                                  "no t-1 data supplied"))
    return out


def d3_volume_change_coherence(volume_index_output, volume_index_intermediate,
                               is_service=None, tol=None):
    """D3  "the volume change of production is very similar to the volume change
    of intermediate consumption. This relation is stronger for the output goods
    and input of raw materials than for services. Nevertheless, when there is a
    large difference between the two volume changes, this indicates that there
    may be something wrong in the data and further investigation is advisable"
    (CORE_012 par. 11.19, p. 323).

    "Large" is not defined. `tol` is a project choice; the service exception is
    the source's, and services are flagged separately rather than exempted.
    """
    a = np.asarray(volume_index_output, dtype=float)
    b = np.asarray(volume_index_intermediate, dtype=float)
    if a.size == 0 or b.size == 0:
        return not_applicable("D3", "volume change of output vs intermediate consumption",
                              "CORE_012 par. 11.19, p. 323",
                              "no volume indices supplied -- needs the six-pack")
    t = 5.0 if tol is None else float(tol)      # index points; PROJECT CHOICE
    d = np.abs(a - b)
    flag = d > t
    n_serv = 0 if is_service is None else int(np.asarray(is_service, bool)[flag].sum())
    return Check("D3", "volume change of output vs intermediate consumption",
                 "CORE_012 par. 11.19, p. 323",
                 FLAG if flag.any() else PASS, int(flag.sum()), float(d.max()),
                 f"tolerance {t} index points is a PROJECT CHOICE; "
                 f"{n_serv} of the flagged industries are services, where the "
                 f"source says the relation is weaker")


def d4_labour_productivity(volume_gva, labour_input, prior_ratio=None):
    """D4  "labour productivity is expected to rise gradually every year (except
    for periods such as the start of a recession). A decrease or a high growth
    of productivity can also indicate possible mistakes in the data"
    (CORE_012 par. 11.20, p. 323).

    "the labour data should be calculated on the same basis (for example, using
    the same statistical unit) as the economic data" -- the caller is
    responsible for that; the function cannot check it.
    """
    if volume_gva is None or labour_input is None:
        return not_applicable("D4", "labour productivity", "CORE_012 par. 11.20, p. 323",
                              "volume GVA or labour input not supplied")
    r = _safe_ratio(volume_gva, labour_input)
    if prior_ratio is None:
        return not_applicable("D4", "labour productivity", "CORE_012 par. 11.20, p. 323",
                              "no t-1 productivity supplied; level alone carries no signal")
    growth = _safe_ratio(r, np.asarray(prior_ratio, dtype=float)) - 1.0
    flag = np.isfinite(growth) & ((growth < 0.0) | (growth > 0.10))
    return Check("D4", "labour productivity growth", "CORE_012 par. 11.20, p. 323",
                 FLAG if flag.any() else PASS, int(flag.sum()),
                 float(np.nanmax(np.abs(growth))) if np.isfinite(growth).any() else 0.0,
                 "upper bound 10% is a PROJECT CHOICE; the source says only "
                 "'a decrease or a high growth'")


def d5_price_dispersion(price_index_by_user, exclude=None):
    """D5  "it is expected that price changes should be more or less the same for
    all economic agents (except for areas like foreign trade). If the price
    change of a certain user deviates significantly from the average, this may
    indicate that something is wrong" (CORE_012 par. 11.21, p. 323).

    `exclude` names the user columns to leave out -- exports and imports, per the
    source's own foreign-trade exception.
    """
    p = np.asarray(price_index_by_user, dtype=float)
    if p.size == 0 or not np.isfinite(p).any():
        return not_applicable("D5", "price change dispersion across users",
                              "CORE_012 par. 11.21, p. 323", "no price indices supplied")
    mask = np.ones(p.shape, bool)
    if exclude is not None:
        mask[..., np.asarray(exclude)] = False
    vals = p[mask & np.isfinite(p)]
    med = float(np.median(vals))
    mad = float(np.median(np.abs(vals - med))) or float("inf")
    z = np.abs(p - med) / mad
    flag = mask & np.isfinite(z) & (z > PROJECT_OUTLIER_MAD)
    return Check("D5", "price change dispersion across users",
                 "CORE_012 par. 11.21, p. 323",
                 FLAG if flag.any() else PASS, int(flag.sum()),
                 float(np.nanmax(z[np.isfinite(z)])) if np.isfinite(z).any() else 0.0,
                 "foreign-trade columns excluded per the source's own exception")


# ---------------------------------------------------------------------------
# M-038 -- second-order effects
# ---------------------------------------------------------------------------

def s4_implied_tax_rate(tax, base, legal_rate, name="VAT"):
    """S4  "One important final check is to ensure that the resulting effective
    (and implied) tax rates do not exceed the legal rates, for example, the
    standard rate of VAT" (CORE_012 par. 11.77, p. 336).

    A HARD inequality, in Box 11.3's "strong constraints ... upper and lower
    boundaries" class (p. 346), not a plausibility flag.

    Apply to the TAX component, not to taxes-less-subsidies netted: subsidies are
    negative taxes (CORE_003 par. 15.93, p. 495) and a dominant subsidy produces
    a meaningless negative 'rate'.
    """
    if tax is None or base is None or legal_rate is None:
        return not_applicable("S4", f"implied {name} rate <= legal rate",
                              "CORE_012 par. 11.77, p. 336",
                              "tax block, base or legal-rate table not supplied")
    r = _safe_ratio(tax, base)
    lim = np.asarray(legal_rate, dtype=float)
    over = np.isfinite(r) & (r > lim + 1e-12)
    return Check("S4", f"implied {name} rate <= legal rate",
                 "CORE_012 par. 11.77, p. 336",
                 PASS if not over.any() else FAIL, int(over.sum()),
                 float(np.nanmax(r - lim)) if np.isfinite(r).any() else 0.0)


# ---------------------------------------------------------------------------
# M-039 -- handover triage
# ---------------------------------------------------------------------------

def discrepancy_triage(residuals, scale, diagnostics_firing=None):
    """T1/T2  separate the discrepancies "needing further research" from "those
    which can be resolved using automated procedures" (CORE_012 par. 11.105,
    pp. 342-343).

    Note the second clause, which the implementation must honour: "In general,
    large inconsistencies require more attention than smaller ones BUT such
    indicators as time series, revision analyses, input-output ratios and labour
    productivity can also point to serious problems in the data." Size is
    explicitly not sufficient. A11.6, p. 351 says the same: large discrepancies
    "or implausible input-output ratios in volume terms or implausible movements
    in the price changes on a row" require research first.

    So `diagnostics_firing` -- a boolean per residual, true if any soft
    diagnostic fired on it -- forces MANUAL regardless of magnitude.

    THE THRESHOLDS ARE PROJECT CHOICES. CORE_012 gives none.
    """
    r = np.abs(np.asarray(residuals, dtype=float))
    s = np.abs(np.asarray(scale, dtype=float))
    small = r <= (PROJECT_HANDOVER_ABS + PROJECT_HANDOVER_REL * s)
    if diagnostics_firing is None:
        clean = np.ones(r.shape, bool)
        note = "no diagnostic profile supplied -- size used alone, which the source forbids"
    else:
        clean = ~np.asarray(diagnostics_firing, bool)
        note = ""
    automatable = small & clean
    manual = ~automatable
    detail = (f"automatable = {int(automatable.sum())}   manual = {int(manual.sum())}\n"
              f"of the manual set, {int((small & ~clean).sum())} are small but have a "
              f"diagnostic firing (par. 11.105 forces these to manual)\n"
              f"thresholds PROJECT_HANDOVER_ABS={PROJECT_HANDOVER_ABS}, "
              f"PROJECT_HANDOVER_REL={PROJECT_HANDOVER_REL} are PROJECT CHOICES")
    if note:
        detail += f"\nWARNING: {note}"
    return Check("T1", "handover triage: manual vs automatable",
                 "CORE_012 par. 11.105, pp. 342-343; Annex A11.6, p. 351",
                 PASS, int(manual.sum()), float(r.max()) if r.size else 0.0,
                 detail, {"automatable": automatable, "manual": manual})


# ---------------------------------------------------------------------------
# M-037 -- negative triage
# ---------------------------------------------------------------------------

# The cited blocks from A_core_accounting_spec.md A.8.1, as DATA so that each
# carries its citation and the map can be extended when a source justifies it.
# CORE_012 par. 11.66, pp. 333-334 names only two of these (inventories, exports
# of goods e.g. merchanting); it is rank 2 and does not narrow the rank-1 list.
LEGITIMATE_NEGATIVE_BLOCKS = {
    "trade_transport_margin_rows": "CORE_003 par. 15.56, p. 488; par. 15.180, p. 509; CORE_006 par. 9.06(b), p. 276",
    "subsidies_on_products": "CORE_003 par. 15.93, p. 495",
    "taxes_less_subsidies_on_products": "CORE_003 par. 15.93, p. 495; Table 15.12 row 17, p. 512",
    "other_taxes_less_subsidies_on_production": "CORE_003 Table 15.12 row 17, p. 512",
    "cif_fob_adjustment_services": "CORE_003 par. 15.70, p. 490; Table 15.4, p. 491",
    "changes_in_inventories": "CORE_003 Table 15.8, p. 499; CORE_012 par. 11.66, p. 334",
    "gross_capital_formation": "CORE_003 par. 15.120, p. 499",
    "acquisitions_less_disposals_of_valuables": "CORE_003 par. 15.111, p. 498; par. 15.124, p. 500",
    "supply_of_existing_goods": "CORE_003 par. 15.115, p. 499; CORE_006 par. 9.47, p. 286",
    "domestic_purchases_by_non_residents": "CORE_003 Table 15.7, p. 498",
    "merchanting_acquisitions_as_negative_exports": "CORE_003 par. 15.84, p. 493; CORE_012 par. 11.66, p. 334",
    "product_technology_iot_cells": "CORE_005 par. 36.56, p. 1018",
    "fixed_industry_sales_iot_cells": "CORE_005 par. 36.61, p. 1019",
}


def negative_triage(blocks: dict, block_map: dict | None = None):
    """M-037  classify every negative cell, block by block.

    `blocks`      : {name: array}
    `block_map`   : {name: key into LEGITIMATE_NEGATIVE_BLOCKS}. A block whose
                    name is already a key needs no entry.

    Classes:
      LEGITIMATE_CITED : the block is on the A.8.1 list. PIN IT. A rank-2 source
                         does not narrow a rank-1 citation.
      UNCLASSIFIED     : negative, and no loaded source permits it here.
                         ESCALATE (M-031). DO NOT ZERO IT.

    The UNWANTED class of CORE_012 par. 11.66, pp. 333-334 is NOT produced here.
    Deciding it requires tracing the valuation deduction, which needs the
    valuation matrices; and the chapter gives no test even then. See OQ-B-04.
    """
    block_map = block_map or {}
    rows, n_cited, n_unclass = [], 0, 0
    for name, arr in blocks.items():
        a = np.asarray(arr, dtype=float)
        neg = a < 0
        if not neg.any():
            continue
        key = block_map.get(name, name)
        cited = key in LEGITIMATE_NEGATIVE_BLOCKS
        cls = "LEGITIMATE_CITED" if cited else "UNCLASSIFIED"
        if cited:
            n_cited += 1
        else:
            n_unclass += 1
        rows.append({
            "block": name,
            "classification": cls,
            "citation": LEGITIMATE_NEGATIVE_BLOCKS.get(key, "-- none in any loaded source --"),
            "n_negative": int(neg.sum()),
            "min": float(a.min()),
            "sum_negative": float(a[neg].sum()),
        })

    detail = (f"{n_cited} block(s) LEGITIMATE_CITED (pin them)   "
              f"{n_unclass} block(s) UNCLASSIFIED (escalate, do not zero)\n"
              "the UNWANTED class of par. 11.66 is not produced -- no loaded "
              "source gives a test for it (OQ-B-04)")
    return Check("NEG", "negative-entry triage",
                 "CORE_012 par. 11.66, pp. 333-334; A_core_accounting_spec.md A.8.1",
                 FLAG if n_unclass else PASS, n_unclass,
                 min((r["min"] for r in rows), default=0.0),
                 detail, {"rows": rows})
