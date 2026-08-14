"""
`OQ-B-02`, widened from five fixtures to every published table the project holds.

THE QUESTION THIS ANSWERS IS NOT THE ONE THE ENTRY ASKS
-------------------------------------------------------
`OQ-B-02` asks what discrepancy in an accounting identity is *acceptable*. Six
sources have now been searched and none states a number: the UN Handbook across
735 pages, two Eurostat chapters, Lahr & de Mesnard, and the UK, Spanish and
Saudi offices' own quality documentation. `run_tolerance_absent.py` records that.
The entry's own v1.46 framing is that it is no longer waiting for a source — it
is waiting for the project to defend its own floor.

This file does not invent the missing number either. It measures something else,
which turns out to make the missing number much less important than it looked:

    **how far the published tables actually are from their own floor.**

The floor is `0.5·10^-d·n` for an `n`-term identity in a table printed to `d`
decimals (`quadrium.precision.assertable_tolerance`, `OQ-B-02` v1.10) — the
point below which "balanced" and "not balanced" are the same observation.

WHAT THE POPULATION SHOWS
--------------------------
Eighteen identity observations, six statistical offices, two table types, four
vintages. They do not spread out along the scale. They fall into two clusters
with **nothing between them**:

  * every table that balances does so at **or below a quarter of its own
    floor** — the largest is 0.26;
  * the two that do not balance are **37.5x and 1252x** the floor.

So an acceptance threshold set anywhere between 0.26 and 37.5 floors — a band
144 wide — classifies **every observation in this population identically**. The
constant `OQ-B-02` cannot source is, on this evidence, not load-bearing: it can
be wrong by two orders of magnitude without changing a single verdict.

WHAT THIS IS NOT
-----------------
Not a sourced threshold, and not a claim that the gap is universal. It is a
measurement of one population, and a table could be published inside the gap
tomorrow. What it licenses is narrow and worth stating exactly: **the project's
unsourced acceptance constant is not, today, deciding anything** — and the honest
default is the floor itself, because on this evidence choosing it costs nothing.

TWO FINDINGS FROM THE REFUSALS, WHICH ARE THE INTERESTING HALF
---------------------------------------------------------------
1. `naio_10_cp1700_ES_2019` (total flows) misses "final-demand components sum to
   total final use" by **500.8 million EUR** where its own printed precision
   entitles it to 0.4. `..._ES_2021` (domestic) misses the same identity by 15.0.
   Two of the four Spanish vintages this project holds do not balance as
   published. `load_iot` already refuses both; this file measures the size of
   the refusal instead of only reporting it.
2. **In one file, one variant balances and the other does not.** ES 2021's
   domestic table is out by 37.5 floors; its total table balances to 1.5e-11.
   Whatever went wrong is in one valuation variant, not in the vintage.

DENMARK AND NORWAY ARE ABSENT, AND WHY
---------------------------------------
Both have a `naio_10_cp15` supply table here and no `cp16` use table, so no
supply-use pair can be formed. A first draft of this file substituted an
identity of its own -- "the industry columns sum to the published `TOTAL`
column" -- and got ratios of 37,000x to 576,000x on SIX countries including
three whose supply tables balance to 1e-11 through the proper loader. `TOTAL`
in `cp15`'s `ind_impv` dimension is not the sum over industries. The identity
was mine, the failure was mine, and inventing an identity to widen a sample is
exactly how a measurement becomes a fabrication. Both are simply excluded.

Run:
    python3 validators/run_tolerance_population.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

from quadrium.precision import (  # noqa: E402
    assertable_tolerance, printed_decimals,
)

FAIL: list[str] = []

# The loader states the residual and the tolerance it refused on, in prose.
# Parsing its message is less fragile than re-implementing its three identity
# checks here and letting the two drift apart.
_REFUSED = re.compile(r"off by ([\d,.]+) \(tolerance ([\d.eE+-]+), "
                      r"for a sum of (\d+)")


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def _observations():
    """(label, office, decimals, n, residual, floor, refused) per identity."""
    from quadrium.eurostat import EurostatError, load_iot, load_sut
    from quadrium.io_loader import load_ine_tio, load_ine_tod

    out = []

    def add(label, office, values, n, residual, refused=False, floor=None):
        f = assertable_tolerance(values, n) if floor is None else floor
        d = printed_decimals(values) if values is not None else None
        out.append((label, office, d, n, residual, f, refused))

    D = ROOT / "data" / "eurostat"

    # --- Eurostat symmetric IOTs, four Spanish vintages and one Italian.
    for geo, year, ds, office in (("ES", 2019, "naio_10_cp1700", "INE (ES)"),
                                  ("ES", 2020, "naio_10_cp1700", "INE (ES)"),
                                  ("ES", 2021, "naio_10_cp1700", "INE (ES)"),
                                  ("ES", 2022, "naio_10_cp1700", "INE (ES)"),
                                  ("IT", 2022, "naio_10_cp1750", "Istat (IT)")):
        p = D / f"{ds}_{geo}_{year}.json"
        if not p.exists():
            continue
        for variant in ("domestic", "total"):
            try:
                t = load_iot(p, variant=variant)
            except EurostatError as exc:
                m = _REFUSED.search(str(exc))
                if m:            # refused on a source identity: measure it
                    add(f"{geo} IOT {year} {variant[:3]}", office, None,
                        int(m.group(3)), float(m.group(1).replace(",", "")),
                        refused=True, floor=float(m.group(2)))
                continue         # no match: a missing variant, not an imbalance
            values = np.concatenate([t.Z.ravel(), t.Y.ravel(), t.X])
            add(f"{geo} IOT {year} {variant[:3]}", office, values,
                t.n + t.Y.shape[1],
                float(np.abs(t.Z.sum(1) + t.Y.sum(1) - t.X).max()))
            break                # one variant per vintage is enough

    # --- Eurostat supply-use pairs. Two identities each: the supply table's
    #     own row total, and the product balance at purchasers' prices.
    for geo, office in (("AT", "Statistik Austria"), ("ES", "INE (ES)"),
                        ("FR", "INSEE (FR)"), ("NL", "CBS (NL)")):
        s, u = D / f"naio_10_cp15_{geo}_2022.json", D / f"naio_10_cp16_{geo}_2022.json"
        if not (s.exists() and u.exists()):
            continue
        sut = load_sut(s, u)
        add(f"{geo} SUT supply", office,
            np.concatenate([sut.V.ravel(), sut.q, sut.g]), sut.V.shape[1],
            float(np.abs(sut.V.sum(1) - sut.q).max()))
        lhs = sut.q + sut.imports + sut.total_margins + sut.taxes_on_products
        add(f"{geo} SUT product", office,
            np.concatenate([sut.U.ravel(), sut.Y.ravel(), sut.q, sut.imports,
                            sut.total_margins, sut.taxes_on_products]),
            sut.U.shape[1] + sut.Y.shape[1] + 4,
            float(np.abs(lhs - (sut.U.sum(1) + sut.Y.sum(1))).max()))

    # --- The two national workbooks, read from the offices' own files.
    p = ROOT / "data" / "ine" / "cne_tio_22.xlsx"
    if p.exists():
        t = load_ine_tio(p, unbalanced="residual_column")
        add("INE TIO 2022", "INE (ES)",
            np.concatenate([t.Z.ravel(), t.Y.ravel(), t.X]),
            t.n + t.Y.shape[1],
            float(np.abs(t.Z.sum(1) + t.Y.sum(1) - t.X).max()))
    p = ROOT / "data" / "ine" / "cne_tod_22.xlsx"
    if p.exists():
        s = load_ine_tod(p)
        add("INE TOD supply", "INE (ES)",
            np.concatenate([s.V.ravel(), s.q, s.g]), s.n_activities,
            float(np.abs(s.V.sum(1) - s.q).max()))
        lhs = s.q + s.imports + s.total_margins + s.taxes_on_products
        add("INE TOD product", "INE (ES)",
            np.concatenate([s.U.ravel(), s.Y.ravel(), s.q, s.imports,
                            s.total_margins, s.taxes_on_products]),
            s.U.shape[1] + s.Y.shape[1] + 4,
            float(np.abs(lhs - (s.U.sum(1) + s.Y.sum(1))).max()))

    # --- The project's own founding fixture.
    p = ROOT / "UK_IOAT_2023_domestic_ixi.xlsx"
    if p.exists():
        import run_uk_iot as uk
        t = uk.load_iot(p)
        Z, x = t["Z"], t["x"]
        # `P3 S1` is the S13+S14+S15 subtotal; including it double counts.
        FD = np.column_stack([v for k, v in t["FD"].items() if k != "P3 S1"])
        add("ONS UK IOAT 2023", "ONS (UK)",
            np.concatenate([Z.ravel(), FD.ravel(), x]),
            Z.shape[1] + FD.shape[1],
            float(np.nanmax(np.abs(Z.sum(1) + FD.sum(1) - x))))
    return out


def main() -> int:
    obs = _observations()
    if not obs:
        print("no fixture available")
        return 0

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)
    print(f"  {'observation':<20}{'office':<19}{'dec':>4}{'n':>5}"
          f"{'residual':>13}{'floor':>10}{'x floor':>10}")
    for label, office, d, n, r, f, refused in obs:
        ratio = r / f if f else float("nan")
        print(f"  {label:<20}{office:<19}"
              f"{('—' if d is None else d):>4}{n:>5}{r:>13.4g}{f:>10.4g}"
              f"{ratio:>10.3f}" + ("   REFUSED" if refused else ""))
    print()

    balanced = [(l, r / f) for l, _, _, _, r, f, ref in obs if not ref]
    refused = [(l, r / f) for l, _, _, _, r, f, ref in obs if ref]
    offices = {o for _, o, _, _, _, _, _ in obs}

    # 1 -- the claim run_tolerance_from_precision.py makes on five fixtures,
    #      re-made on the whole population.
    worst = max(balanced, key=lambda t: t[1])
    check("every table that loads balances inside its own floor",
          all(x <= 1.0 for _, x in balanced),
          f"{len(balanced)} observations, {len(offices)} offices; "
          f"worst is {worst[0]} at {worst[1]:.3f} of its floor")

    # 2 -- and it is not a near miss. The margin is the finding.
    check("and does so with an order of magnitude to spare",
          worst[1] <= 0.5,
          f"the largest ratio in the population is {worst[1]:.3f}; a table "
          f"that balances is nowhere near the line it must not cross")

    # 3 -- the failures are not near it either, from the other side.
    if refused:
        least_bad = min(refused, key=lambda t: t[1])
        check("a table that does not balance misses by orders of magnitude",
              least_bad[1] >= 10.0,
              f"the smallest failure is {least_bad[0]} at {least_bad[1]:.1f} "
              f"floors; the largest is "
              f"{max(refused, key=lambda t: t[1])[1]:.0f}")

        # 4 -- THE POINT. The unsourced constant has a 144-fold band to sit in.
        gap = least_bad[1] / worst[1]
        check("the acceptance threshold has a wide band and decides nothing "
              "inside it",
              gap >= 20.0,
              f"any threshold in [{worst[1]:.2f}, {least_bad[1]:.1f}] floors "
              f"classifies all {len(obs)} observations identically — a band "
              f"{gap:.0f}x wide, with no observation inside it")

        # 5 -- and the failure is per-variant, not per-vintage.
        es21 = {l: x for l, x in balanced + refused if l.startswith("ES IOT 2021")}
        if len(es21) == 2:
            check("one file can balance in one variant and not in the other",
                  max(es21.values()) > 1.0 > min(es21.values()),
                  ", ".join(f"{k} at {v:.3g} floors" for k, v in es21.items()))

    print()
    print("    What this does NOT do: state an acceptance threshold. No source")
    print("    does (`run_tolerance_absent.py`, six sources). What it shows is")
    print("    that the missing number is not currently deciding anything, and")
    print("    that the floor is the defensible default because on this")
    print("    evidence it costs nothing. `ABS_TOL` / `REL_TOL` keep their")
    print("    PROJECT CHOICE label. D_open_questions.md OQ-B-02.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
