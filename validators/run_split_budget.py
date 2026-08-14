"""
`OQ-S-02`: how many subsectors a table can support — the question, made countable.

No loaded source answers it. CORE_024 p. 17 offers a trade-off to be "thoroughly
weighted" by the analyst and no rule; CORE_031 gives none either. Checked tonight
and adding nothing: CORE_015 (data-scarce ESUTs) and CORE_017 (extended IOTs)
contain no guidance on the level of detail. `NOT SPECIFIED` stands.

WHAT THE TWO CHAPTERS READ TONIGHT DO SAY, WHICH IS A CEILING
--------------------------------------------------------------
CORE_008 ¶5.24, p. 136: "The general recommendation, however, is to work with as
much detail as possible". But ¶5.23, p. 136 says who sets the ceiling, and it is
not the compiler: "the way in which statistical units are defined and classified
in the business register and covered in basic statistics represents a real
constraint on the possible choices concerning industries in the SUTs", and those
options "are much more limited than the range of choices available when it comes
to deciding what product classification should be applied."

And CORE_009 ¶6.46, p. 166 says what happens past the frame: "Input structures of
small establishments that are not covered by the survey will probably be unlike
the structures found in the survey."

So: **more detail on the PRODUCT axis is cheap and more detail on the INDUSTRY
axis is not**, and pushing past the surveyed size classes has a bias of unknown
sign. That is not a number, but it is more than the entry had.

THE COUNTABLE PART
------------------
A split into `k` subsectors driven by one allocation key takes `k − 1`
independent numbers from the analyst — the weights, which sum to 1 — and writes
`2k(n−1) + k²` cells that did not exist before. Every one of those carries a
`PROXY_ESTIMATED` label, because the engine has nothing else to give them.

Measured below on the Spanish table, splitting one sector of 65:

    k = 2    1 fact      260 new cells     6.0 % of the table estimated
    k = 8    7 facts   1,088 new cells    21.0 % of the table estimated

The cells-per-fact ratio *improves* slightly with `k` (260 → 155) because each
extra subsector brings one more weight. What grows, linearly, is the share of the
published table that has stopped being observed. **Splitting one sector of
sixty-five into two already makes six per cent of the whole table an estimate.**

That is the answer this question can be given today: the arithmetic supports any
`k`; what degrades is measurable before you start, and it is not the split that
degrades — it is the table around it.

A SCREEN THAT IS *NOT* ZHAO'S COUNT, AND IS NOT PRESENTED AS ONE
-----------------------------------------------------------------
`M-053` records that Zhao had to allocate **6 of 41** supplying rows by hand,
"because their inputs are technology-specific". A statistical proxy for that —
rows both material to the parent's column (>1 %) and concentrated on it (>20 % of
the supplier's sales) — finds 0.8–2.0 % of rows in the UK, Spanish and Italian
tables, an order of magnitude below Zhao's 14.6 %.

**The two are not comparable and the thresholds were not tuned to make them so.**
Zhao's criterion is semantic — is this input specific to a technology — and his
nine subsectors sit at a far finer level than a 65-sector table, where
aggregation dilutes any supplier's concentration on one buyer. The screen is
reported for what it is: a list of rows where "allocate in proportion to size" is
a strong claim, useful for deciding where to look first, and not a count of the
judgements a split will actually need.

Run:
    python3 validators/run_split_budget.py
"""

from __future__ import annotations

import collections
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def judgement_rows(Z, material=0.01, concentrated=0.20):
    """Rows where proportional allocation is a strong claim. NOT Zhao's count."""
    sales, col = Z.sum(1), Z.sum(0)
    out = []
    for p in range(Z.shape[1]):
        if col[p] <= 0:
            continue
        mat = Z[:, p] / col[p]
        con = np.where(sales > 0, Z[:, p] / np.maximum(sales, 1e-12), 0.0)
        out.append((int(((mat > material) & (con > concentrated)).sum()),
                    int((Z[:, p] > 0).sum())))
    return out


def main() -> int:
    fixture = ROOT / "data" / "eurostat" / "naio_10_cp1700_ES_2022.json"
    if not fixture.exists():
        print(f"fixture absent: {fixture.name}")
        return 0

    from quadrium.eurostat import load_iot
    from quadrium.models import (AllocationKey, ProxyStrength, Scenario,
                                  SplitSpec)
    from quadrium.disaggregation import split_sector

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    table = load_iot(fixture, variant="domestic")
    code = "H51"
    n = table.n
    rows = []
    for k in (2, 3, 4, 5, 8):
        new = [f"{code}{chr(97 + i)}" for i in range(k)]
        keys = {"k": AllocationKey(key_id="k", applies_to="output",
                                   new_sector_codes=new,
                                   raw_values=[100.0 - 10 * i for i in range(k)],
                                   source="test fixture", source_year=2022,
                                   strength=ProxyStrength.WEAK)}
        spec = SplitSpec(code, new, new, keys_by_block={"output": "k"})
        res = split_sector(table, code, new, new,
                           Scenario(scenario_id="S", label="s"), keys, spec)
        prov = res["provenance"]
        counts = collections.Counter(c.name for c in prov.ravel())
        est = sum(v for name, v in counts.items()
                  if "ESTIMATED" in name or "PROXY" in name)
        rows.append((k, k - 1, 2 * k * (n - 1) + k * k, est / prov.size))

    print(f"  splitting one sector of {n} on the Spanish table:")
    print(f"  {'k':>3}{'facts':>8}{'new cells':>12}{'cells/fact':>12}"
          f"{'table estimated':>18}")
    for k, facts, cells, share in rows:
        print(f"  {k:>3}{facts:>8}{cells:>12,}{cells / facts:>12,.0f}"
              f"{share:>17.1%}")
    print()

    check("one split of one sector already estimates a measurable share",
          rows[0][3] > 0.04,
          f"k = 2 makes {rows[0][3]:.1%} of the whole table an estimate, from "
          f"{rows[0][1]} independent number")
    check("and the estimated share grows with k, roughly linearly",
          rows[-1][3] > 3 * rows[0][3],
          f"{rows[0][3]:.1%} at k = 2 against {rows[-1][3]:.1%} at k = 8")
    check("while cells-per-fact FALLS, which is the trap",
          rows[-1][2] / rows[-1][1] < rows[0][2] / rows[0][1],
          f"{rows[0][2] / rows[0][1]:,.0f} at k = 2 down to "
          f"{rows[-1][2] / rows[-1][1]:,.0f} at k = 8 — the marginal fact looks "
          f"cheaper the finer you go, and the total keeps rising")

    # ---- v1.25: the same budget for any table size ------------------------
    # The counts above are engine-measured on one table of 65. The cost is a
    # function of table size too, and an analyst choosing a table wants it
    # before choosing a k.
    def budget(n_: int, k_: float) -> float:
        return (2 * k_ * (n_ - 1) + k_ * k_) / ((n_ - 1 + k_) ** 2)

    check("the closed form reproduces what the engine counted",
          all(abs(budget(n, k) - share) < 5e-3 for k, _, _, share in rows),
          "share(n, k) = [2k(n−1) + k²] / (n−1+k)² matches the engine's own "
          "provenance counts on all five values of k, so it can be trusted "
          "off this fixture")

    print()
    print("    the same split, on tables of different size:")
    print(f"    {'n':>5}" + "".join(f"{'k=' + str(k):>9}" for k in (2, 4, 8)))
    for n_ in (30, 65, 104, 180):
        print(f"    {n_:>5}"
              + "".join(f"{budget(n_, k):>8.1%}" for k in (2, 4, 8)))

    sizes = (30, 65, 104, 180)
    check("a bigger table absorbs a split better — strictly, at every k",
          all(budget(a, k) > budget(b, k)
              for a, b in zip(sizes, sizes[1:]) for k in (2, 4, 8)),
          f"splitting one sector in two costs {budget(65, 2):.1%} of a "
          f"65-sector table and {budget(104, 2):.1%} of a 104-sector one. "
          f"The economics: disaggregation is cheapest where the classification "
          f"is already fine, which is the opposite of where the temptation is")
    # 2k/n as a rule of thumb, stated with the condition it actually needs.
    # It is always an overstatement — verified by exhaustion below — but the
    # margin grows with k/n, so it is only usable while the split is small
    # relative to the table.
    always_over = all(2 * k / n_ >= budget(n_, k)
                      for n_ in range(10, 400) for k in range(1, n_))
    worst = max(2 * k / n_ / budget(n_, k) - 1
                for n_ in range(20, 400) for k in range(1, max(2, n_ // 20 + 1)))
    check("2k/n is a safe rule of thumb — but only while k stays small "
          "against n",
          always_over and worst < 0.10,
          f"it never understates (checked for every n from 10 to 400 and "
          f"every k), and overstates by at most {worst:.0%} while k ≤ n/20. "
          f"Past that the margin runs away — at n = 30, k = 8 it says 53 % "
          f"where the truth is {budget(30, 8):.0%}, so use the formula, not "
          f"the shortcut, for a coarse table")

    # Solve share(n, k) = 1/2. With m = n−1 and x = k/m the n cancels:
    # (2x + x²)/(1+x)² = 1/2  →  x² + 2x − 1 = 0  →  x = √2 − 1.
    x = math.sqrt(2) - 1
    check("and half the table becomes an estimate at k/(n−1) = √2 − 1, for "
          "EVERY n",
          all(abs(budget(n_, x * (n_ - 1)) - 0.5) < 1e-9
              for n_ in (30, 65, 104, 180, 1000)),
          f"the table size cancels out of the algebra, leaving {x:.4f} exactly "
          f"— split one sector into more than ~41 % of the table's own size "
          f"and most of what you are left holding is PROXY_ESTIMATED, whether "
          f"the table has 30 sectors or 1,000")

    # The screen, labelled for what it is.
    print()
    import run_uk_iot as uk
    tables = {"Spain 65": table.Z}
    p = ROOT / "UK_IOAT_2023_domestic_ixi.xlsx"
    if p.exists():
        tables["UK 104"] = uk.load_iot(p)["Z"]
    p = ROOT / "data" / "eurostat" / "naio_10_cp1750_IT_2022.json"
    if p.exists():
        tables["Italy 65"] = load_iot(p, variant="domestic").Z
    print("    Rows where 'allocate in proportion to size' is a strong claim")
    print("    (>1 % of the parent's column AND >20 % of the supplier's sales):")
    shares = {}
    for label, Z in tables.items():
        r = judgement_rows(Z)
        cnt = np.array([x[0] for x in r])
        sup = np.array([x[1] for x in r])
        shares[label] = float(np.mean(cnt / np.maximum(sup, 1)))
        print(f"      {label:<11} median {np.median(cnt):>3.0f} per sector, "
              f"max {cnt.max():>3}, {shares[label]:.1%} of supplying rows")
    check("this screen is an order of magnitude below Zhao's 14.6 %, and is NOT "
          "presented as the same quantity",
          all(s < 0.05 for s in shares.values()),
          "Zhao's criterion is semantic and his nine subsectors sit far finer "
          "than 65 sectors, where aggregation dilutes concentration. The "
          "thresholds were NOT tuned to close the gap")

    print()
    print("    Still NOT SPECIFIED: any rule for k. What the sources give is a")
    print("    ceiling on the INDUSTRY axis — CORE_008 ¶5.23, p. 136, the")
    print("    business register 'represents a real constraint' — and a warning")
    print("    about going past the survey frame, CORE_009 ¶6.46, p. 166.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
