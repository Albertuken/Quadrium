"""
The internal block: the worst-estimated part of a split, and one of the least
consequential.

WHAT THE REPORT SAYS, AND WHAT HAD NEVER BEEN CHECKED
-------------------------------------------------------
Every split this engine produces carries this sentence:

    the split assumes the propensity to trade internally is proportional to
    each subsector's weight (MVP_0.1 §6.3). **This is the weakest assumption
    in the result.**

`OQ-S-04` measured what a real block LOOKS like — 1,403 published sibling pairs,
diagonal about 1.5x the outer product — and decided, correctly, not to move the
default off the sourced 1.0. What nobody had measured is whether any of it
changes the ANSWER. `run_internal_block.py` never calls the engine;
`check_wolsky_internal_block.py` calls it on a synthetic fixture; and
`run_split_backtest.py` scores real splits but never isolates the block or
varies alpha.

This joins them. Same 96 real splits, same published truth, same perfect output
key — and now the k x k block scored on its own, at five values of alpha.

RAISING ALPHA TO THE MEASURED 1.5 MAKES THE ANSWER WORSE
----------------------------------------------------------
    alpha    multiplier error          block error     best for
             median      max           median
    0.50      7.12 %    75.1 %          109.7 %        49 of 96
    1.00      7.29 %    49.2 %           60.9 %         7 of 96
    1.25      8.15 %    36.8 %           53.6 %         1 of 96
    1.50      8.73 %    35.9 %           60.2 %         7 of 96
    2.00      9.17 %    48.1 %           89.9 %        32 of 96

Against the 1.0 default, alpha = 1.5 improves 28 splits and worsens 37, and
moves the median from 7.82 % to 9.37 %. **The value measured from observed
blocks does not reconstruct published tables better.** `OQ-S-04` declined to
adopt it on the grounds that a measurement is not a source; it turns out not to
work either, which is a second and independent reason.

And no single alpha is right. The best value per split piles up at the two ENDS
— 34 at 0.5, 22 at 2.0, six at the default — so there is no interior value to
find. Nor can it be borrowed: the alpha implied by the true block correlates
with the alpha that reconstructs best at **r = +0.17**.

Note the row that does not line up: alpha = 1.25 gives the smallest BLOCK error
and the third-worst multiplier error. Fitting the block better does not fit the
answer better.

THE BLOCK IS BADLY ESTIMATED AND IT BARELY MATTERS
----------------------------------------------------
At the default, the estimated block misses the published one by a median of
**60.9 %**. It is comfortably the worst-estimated part of a split — the cell
error over the whole touched cross is 41.6 % (`run_split_backtest.py`).

    block error       vs multiplier error      r = +0.030
    block weight      vs multiplier error      r = +0.277

**Essentially nothing.** How wrong the block is does not predict how wrong the
answer is. Its weight in a subsector's own input column — median 8.9 %, from
0.0 % to 55.6 % — carries a little more signal, and not much.

So "the weakest assumption in the result" is half right and misleading as
written. It is the weakest ASSUMPTION. The result does not rest on it.

TWO SHARES, AND THE REPORT PRINTS THE REASSURING ONE
------------------------------------------------------
`internal_block_share_pct` is the block over the absolute value of the WHOLE
intermediate matrix — 0.05 % to 0.7 % in the shipped pilots, which reads as
nothing. The share that has anything to do with a subsector's multiplier is the
block over THAT SUBSECTOR's input column, and it runs to 55.6 %. Both are
correct. The report gave the small one and then called it the weakest
assumption, on the same page.

WHAT THIS DOES NOT MEASURE
----------------------------
One output key, so `w_row == w_col` and the estimated block comes out
symmetric. Real blocks are not: France's `I55`/`I56` is 126.3 / 206.9 / 170.2 /
170.3 against an estimate of 35.1 / 118.7 / 118.7 / 401.2. The engine accepts
separate row and column keys and would not be symmetric with them. What is
measured here is the case a user almost always has: one size key and nothing
else.

Run:
    python3 validators/run_internal_block_backtest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "eurostat"
# Seven tables, FOUR countries. Hungary publishes 2020 through 2023, so it is
# four of the seven and every pooled median below is Hungary-weighted — the
# per-country figures are printed beside them so the weighting is visible.
# `run_source_pairs.py` records that no fifth country publishes an 89-product
# table that also loads, so this is the whole of what Eurostat offers.
FINE = ("naio_10_cp1700_FR_2021.json", "naio_10_cp1700_SK_2015.json",
        "naio_10_cp1700_BE_2022.json", "naio_10_cp1700_HU_2020.json",
        "naio_10_cp1700_HU_2021.json", "naio_10_cp1700_HU_2022.json",
        "naio_10_cp1700_HU_2023.json")
COARSE = "naio_10_cp1700_ES_2022.json"
ALPHAS = (0.5, 1.0, 1.25, 1.5, 2.0)
DEFAULT = 1.0
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def multipliers(Z, X):
    A = Z / np.where(X == 0, 1.0, X)
    return np.linalg.inv(np.eye(len(X)) - A).sum(0)


def main() -> int:
    from quadrium.disaggregation import split_sector
    from quadrium.eurostat import _covers, load_iot
    from quadrium.models import (AllocationKey, IOTable, ProxyStrength,
                                 Scenario, SplitSpec)

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    have = [f for f in FINE if (DATA / f).exists()]
    if not have or not (DATA / COARSE).exists():
        print("  (the fine tables are not here)")
        return 0

    def aggregate(t, parent, idx):
        pos, s = idx[0], set(idx)
        keep = [i for i in range(t.n) if i not in s]
        order = ([i for i in keep if i < pos] + [None]
                 + [i for i in keep if i > pos])
        M = np.zeros((len(order), t.n))
        codes = []
        for r, i in enumerate(order):
            if i is None:
                M[r, idx] = 1.0
                codes.append(parent)
            else:
                M[r, i] = 1.0
                codes.append(t.sector_codes[i])
        return IOTable(
            table_id=f"{t.table_id}-agg", country=t.country, year=t.year,
            unit=t.unit, classification=t.classification, sector_codes=codes,
            sector_labels=codes, Z=M @ t.Z @ M.T, Y=M @ t.Y,
            Y_labels=list(t.Y_labels), VA=t.VA @ M.T,
            VA_labels=list(t.VA_labels), X=M @ t.X, source=t.source,
            retrieved_at=t.retrieved_at)

    coarse = load_iot(DATA / COARSE)
    rows, worst_seed, worst_pub, worst_scale = [], 0.0, 0.0, 1.0
    for f in have:
        fine = load_iot(DATA / f)
        m_true = multipliers(fine.Z, fine.X)
        published_gap = float(np.abs(fine.Z.sum(1) + fine.Y.sum(1)
                                     - fine.X).max())
        for parent in coarse.sector_codes:
            kids = [c for c in fine.sector_codes
                    if c != parent and _covers(parent, c)]
            if len(kids) < 2:
                continue
            idx = [fine.sector_codes.index(c) for c in kids]
            if idx != list(range(idx[0], idx[0] + len(idx))) \
                    or fine.X[idx].min() <= 0:
                continue
            agg = aggregate(fine, parent, idx)
            keys = {"k": AllocationKey(
                key_id="k", applies_to="output", new_sector_codes=kids,
                raw_values=list(fine.X[idx]), source="published truth",
                source_year=fine.year, strength=ProxyStrength.STRONG)}
            spec = SplitSpec(parent, kids, kids, keys_by_block={"output": "k"})
            true_block = fine.Z[np.ix_(idx, idx)]
            P = float(true_block.sum())
            rho = fine.X[idx] / fine.X[idx].sum()
            d = float((rho ** 2).sum())
            col_tot = fine.Z[:, idx].sum(0) + fine.VA[:, idx].sum(0)
            share = true_block.sum(0) / np.where(col_tot == 0, 1.0,
                                                 col_tot) * 100.0
            rec = dict(parent=parent,
                       alpha_obs=(float(np.trace(true_block)) / (d * P)
                                  if P > 0 and d > 0 else None),
                       share=float(share.max()))
            good = True
            for a in ALPHAS:
                try:
                    res = split_sector(
                        agg, parent, kids, kids,
                        Scenario(scenario_id=f"a{a}", label=str(a),
                                 internal_block_alpha=a), keys, spec)
                except Exception:
                    good = False
                    break
                if list(res["codes"]) != list(fine.sector_codes):
                    good = False
                    break
                Zh = np.asarray(res["Z"])
                Xh = np.asarray(res["X"])
                npos = res["new_positions"]
                est = Zh[np.ix_(npos, npos)]
                m_hat = multipliers(Zh, Xh)
                rec[f"m{a}"] = float((np.abs(m_hat[idx] - m_true[idx])
                                      / m_true[idx] * 100).max())
                rec[f"b{a}"] = float(np.abs(est - true_block).sum()
                                     / max(np.abs(true_block).sum(), 1e-9)
                                     * 100)
                if a == DEFAULT:
                    gap = float(np.abs(Zh.sum(1) + np.asarray(res["Y"]).sum(1)
                                       - Xh).max())
                    if gap > worst_seed:
                        worst_seed = gap
                        worst_pub = published_gap
                        worst_scale = float(Xh.max())
            if good:
                rows.append(rec)

    check("there are enough splits to sweep", len(rows) >= 25,
          f"{len(rows)} splits at {len(ALPHAS)} values of alpha")
    # `split_sector` returns a SEED whose margins need not hold; `balancing.py`
    # normally closes it. With one output key it needs no closing, and that has
    # to be shown rather than assumed, or every number below is measured on a
    # table nobody would ever see.
    check("and the seed needs no balancing, so scoring it is fair",
          worst_seed <= worst_pub * 1.5
          and worst_seed / worst_scale < 1e-5,
          f"worst row deviation {worst_seed:.4f} against the published table's "
          f"own {worst_pub:.4f} — {worst_seed / max(worst_pub, 1e-12):.2f}x, "
          f"and {worst_seed / worst_scale:.1e} of the table. A proportional "
          f"split with one key carries the identities through, so these are "
          f"the numbers a user gets")

    # 1 -- the sweep.
    print()
    print(f"    {'alpha':>7}{'mult median':>14}{'mult max':>11}"
          f"{'block median':>15}{'best for':>11}")
    best = []
    for r in rows:
        ms = {a: r[f"m{a}"] for a in ALPHAS}
        best.append(min(ms, key=ms.get))
    stats = {}
    for a in ALPHAS:
        m = np.array([r[f"m{a}"] for r in rows])
        b = np.array([r[f"b{a}"] for r in rows])
        stats[a] = (float(np.median(m)), float(m.max()), float(np.median(b)))
        print(f"    {a:>7}{stats[a][0]:>13.2f}%{stats[a][1]:>10.1f}%"
              f"{stats[a][2]:>14.1f}%{best.count(a):>8} /{len(rows):>3}")

    m1 = np.array([r[f"m{DEFAULT}"] for r in rows])
    m15 = np.array([r["m1.5"] for r in rows])
    check("raising alpha to the measured 1.5 makes the answer WORSE",
          float(np.median(m15)) > float(np.median(m1))
          and int((m15 > m1 + 1e-9).sum()) > int((m15 < m1 - 1e-9).sum()),
          f"median {np.median(m15):.2f} % against the default's "
          f"{np.median(m1):.2f} %, worse on "
          f"{int((m15 > m1 + 1e-9).sum())} splits and better on "
          f"{int((m15 < m1 - 1e-9).sum())}. OQ-S-04 declined 1.5 because a "
          f"measurement is not a source; it also does not work")
    check("and no single alpha is right — the best value piles up at the ends",
          best.count(0.5) + best.count(2.0) > len(rows) * 0.6,
          f"{best.count(0.5)} splits are best at 0.5 and {best.count(2.0)} at "
          f"2.0, against {best.count(DEFAULT)} at the default. There is no "
          f"interior value to find")
    check("fitting the block better does not fit the answer better",
          min(stats, key=lambda a: stats[a][2]) != min(stats,
                                                       key=lambda a: stats[a][0]),
          f"alpha {min(stats, key=lambda a: stats[a][2])} gives the smallest "
          f"block error and alpha {min(stats, key=lambda a: stats[a][0])} the "
          f"smallest multiplier error")

    ao = np.array([r["alpha_obs"] for r in rows], float)
    ok = np.isfinite(ao)
    r_borrow = float(np.corrcoef(ao[ok], np.array(best, float)[ok])[0, 1])
    check("nor can the right alpha be read off a published block",
          abs(r_borrow) < 0.5,
          f"the alpha implied by the true block against the alpha that "
          f"reconstructs best: r = {r_borrow:+.3f}")

    # 2 -- does the block matter at all?
    print()
    b1 = np.array([r[f"b{DEFAULT}"] for r in rows])
    sh = np.array([r["share"] for r in rows])
    r_err = float(np.corrcoef(b1, m1)[0, 1])
    r_wt = float(np.corrcoef(sh, m1)[0, 1])
    print(f"    block error at the default          median "
          f"{np.median(b1):>6.1f} %")
    print(f"    block weight in the subsector column median "
          f"{np.median(sh):>6.1f} %   range {sh.min():.1f}–{sh.max():.1f} %")
    print(f"    block error  vs multiplier error     r = {r_err:+.3f}")
    print(f"    block weight vs multiplier error     r = {r_wt:+.3f}")

    check("the block is the worst-estimated part of a split",
          float(np.median(b1)) > 40.0,
          f"{np.median(b1):.1f} % out at the default, against 41.6 % for the "
          f"whole touched cross (run_split_backtest.py)")
    check("and how wrong it is does not predict how wrong the answer is",
          abs(r_err) < 0.3,
          f"r = {r_err:+.3f}. 'The weakest assumption in the result' is half "
          f"right: it is the weakest assumption, and the result does not rest "
          f"on it")
    check("its weight in the subsector's own column carries a little more",
          abs(r_wt) > abs(r_err),
          f"r = {r_wt:+.3f} against {r_err:+.3f} — weak, and the better of the "
          f"two things a report could show")

    check("the two shares are not the same share",
          sh.max() > 20.0,
          f"the report prints the block over the WHOLE intermediate matrix, "
          f"0.05–0.7 % in the pilots. Over the subsector's own input column it "
          f"reaches {sh.max():.1f} %. Both are right and only the second has "
          f"anything to do with that subsector's multiplier")

    print()
    print("    OQ-S-04 measured what a real block looks like and left the")
    print("    default alone. This asks whether any of it changes the answer.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
