"""
Splitting a sector back, against the office's own published answer.

WHAT HAD AND HAD NOT BEEN TESTED
----------------------------------
Disaggregation is the operation this engine exists for, and it had never been
scored against a known answer on real data. `run_split_depth.py` measures it on
a synthetic economy — Dirichlet draws, no zeros, no block structure — and says
so in as many words: *"no absolute level here transfers to a real split"*.
`OQ-S-05` measured how wrong one allocation KEY was, which is a different
quantity.

Eurostat makes the real test possible. Several countries publish a symmetric
table at 89 products where the classification nests: `I` beside `I55` and
`I56`, `C10-12` beside `C10`, `C11` and `C12`, and twelve more. So the office
publishes both the parent and its parts, and the engine can be asked to
reproduce the parts.

The experiment, one parent at a time: take the published fine table, sum a
parent's children into the parent, hand the result to `split_sector` with the
**true output shares as the key**, and compare what comes back with the fine
table it came from. A perfect key isolates the METHOD's error from the key's.

    68 splits, 14 parents, 4 countries, 5 tables

WHAT IT COSTS, WITH THE KEY EXACTLY RIGHT
-------------------------------------------
    cell error in the touched rows and columns   median 41.6 %   max 112.2 %
    output multiplier error of the subsectors    median  7.8 %   max  48.1 %
    splits whose multipliers land within 5 %     21 of 68
    splits whose multipliers are out by over 15 %  15 of 68

The size key being exactly right does not make the split right. The parts get
the parent's average input structure, and they do not have it.

THE ERROR IS PREDICTED BY ONE THING, AND IT IS NOT THE OBVIOUS ONE
--------------------------------------------------------------------
Against the spread of the subsectors' TRUE multipliers,
`(max − min) / mean`:

    multiplier error vs that spread          r = +0.920,  ratio ~0.69
    multiplier error vs cell error           r = -0.014
    multiplier error vs number of parts      r = +0.364

The first is mechanical once seen: proportional splitting hands every part the
parent's average, so each part's error is its distance from that average and
the worst is about two-thirds of the spread.

**The second is the one worth acting on.** How much of the table the split had
to estimate says NOTHING about whether the multipliers are right — the
correlation is zero. A split can be 112 % wrong cell by cell and land its
multipliers inside 4 %, or be tidy in the cells and 40 % out in the
multipliers. The report prints cell provenance prominently, and a reader who
takes a heavily-estimated block as a warning about the multiplier is reading
something the data does not support.

The third confirms `OQ-S-02` — "k was never the variable" — on real data, where
the synthetic study said its own levels would not transfer.

CAN YOU TELL BEFOREHAND? PARTLY
---------------------------------
The spread is not observable before the split: knowing it means having the
answer. The obvious workaround is to look at a country that publishes the
split. It does not give a number — for the same parent, the largest country
spread is a median **4.6x** the smallest and up to 10.3x — but the ORDERING
partly survives, Spearman +0.52 between countries and +0.80 between two years
of the same country.

So it supports "this sector tends to divide cleanly" and not "expect 6 %":

    consistently safe        J59_60 2.4 %, Q87_88 5.9 %, I 6.2 %, J62_63 6.2 %
    consistently expensive   C10-12 26.5 %, B 35.0 %, N80-82 23.7 %, F 20.5 %
                             (median across countries)

`I`, accommodation and food service, sits in the safe third in all five tables.
That is the sector the Spanish pilot divides, and it is a fair thing to know
about it: the two halves of hospitality have unusually similar input
structures, so the pilot's 9.8-point key error moves the sizes and barely
touches the multipliers.

Run:
    python3 validators/run_split_backtest.py
"""

from __future__ import annotations

import collections
import itertools
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "eurostat"
FINE = ("naio_10_cp1700_FR_2021.json", "naio_10_cp1700_SK_2015.json",
        "naio_10_cp1700_BE_2022.json", "naio_10_cp1700_HU_2022.json",
        "naio_10_cp1700_HU_2020.json")
COARSE = "naio_10_cp1700_ES_2022.json"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def multipliers(Z, X):
    A = Z / np.where(X == 0, 1.0, X)
    return np.linalg.inv(np.eye(len(X)) - A).sum(0)


def spearman(a, b):
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def main() -> int:
    from quadrium.disaggregation import split_sector
    from quadrium.eurostat import _covers, load_iot
    from quadrium.models import (AllocationKey, IOTable, ProxyStrength,
                                 Scenario, SplitSpec)

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    have = [f for f in FINE if (DATA / f).exists()]
    check("there are fine tables to score against",
          len(have) >= 2 and (DATA / COARSE).exists(),
          f"{len(have)} table(s) at 89 products, and the 65-product list that "
          f"names the parents")

    def aggregate(t, parent, idx):
        """Sum the children into the parent, in the parent's place."""
        pos, s = idx[0], set(idx)
        keep = [i for i in range(t.n) if i not in s]
        order = ([i for i in keep if i < pos] + [None]
                 + [i for i in keep if i > pos])
        M = np.zeros((len(order), t.n))
        codes, labels = [], []
        for r, i in enumerate(order):
            if i is None:
                M[r, idx] = 1.0
                codes.append(parent)
                labels.append(parent)
            else:
                M[r, i] = 1.0
                codes.append(t.sector_codes[i])
                labels.append(t.sector_labels[i])
        return IOTable(
            table_id=f"{t.table_id}-agg-{parent}", country=t.country,
            year=t.year, unit=t.unit, classification=t.classification,
            sector_codes=codes, sector_labels=labels,
            Z=M @ t.Z @ M.T, Y=M @ t.Y, Y_labels=list(t.Y_labels),
            VA=t.VA @ M.T, VA_labels=list(t.VA_labels), X=M @ t.X,
            source=t.source, retrieved_at=t.retrieved_at)

    coarse = load_iot(DATA / COARSE)
    rows = []
    for f in have:
        fine = load_iot(DATA / f)
        tag = f"{fine.country[:2].upper()} {fine.year}"
        m_true = multipliers(fine.Z, fine.X)
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
                raw_values=list(fine.X[idx]),
                source=f"the office's own published {fine.year} table",
                source_year=fine.year, strength=ProxyStrength.STRONG)}
            try:
                res = split_sector(
                    agg, parent, kids, kids,
                    Scenario(scenario_id="back", label="back-test"), keys,
                    SplitSpec(parent, kids, kids, keys_by_block={"output": "k"}))
            except Exception:
                continue
            Zh, Xh = np.asarray(res["Z"]), np.asarray(res["X"])
            if list(res["codes"]) != list(fine.sector_codes):
                continue
            d = np.abs(Zh - fine.Z)
            tch = np.zeros_like(d, bool)
            tch[idx, :] = True
            tch[:, idx] = True
            m_hat = multipliers(Zh, Xh)
            err = np.abs(m_hat[idx] - m_true[idx]) / m_true[idx] * 100
            spread = float((m_true[idx].max() - m_true[idx].min())
                           / m_true[idx].mean() * 100)
            rows.append(dict(tag=tag, parent=parent, k=len(kids),
                             cell=float(d[tch].sum()
                                        / np.abs(fine.Z[tch]).sum() * 100),
                             mx=float(err.max()), spread=spread,
                             x_ok=float(np.abs(Xh - fine.X).max())))

    check("every split reproduces the parent's own output exactly",
          all(r["x_ok"] < 1e-6 for r in rows),
          "the sizes are the key's arithmetic and cannot be wrong when the "
          "key is right — the error measured below is all structure")
    check("there are enough real splits to say anything",
          len(rows) >= 25 and len({r["tag"] for r in rows}) >= 2,
          f"{len(rows)} splits, {len({r['parent'] for r in rows})} parents, "
          f"{len({r['tag'][:2] for r in rows})} countries")

    mx = np.array([r["mx"] for r in rows])
    sp = np.array([r["spread"] for r in rows])
    cell = np.array([r["cell"] for r in rows])
    kk = np.array([r["k"] for r in rows], float)

    print()
    print(f"    {'':32}{'median':>10}{'max':>10}")
    print(f"    {'cell error, touched block':<32}"
          f"{np.median(cell):>9.1f}%{cell.max():>9.1f}%")
    print(f"    {'multiplier error, subsectors':<32}"
          f"{np.median(mx):>9.1f}%{mx.max():>9.1f}%")

    check("a perfect size key does not buy a right answer",
          np.median(mx) > 3.0 and int((mx < 5).sum()) < len(rows) * 0.5,
          f"{int((mx < 5).sum())} of {len(rows)} land their multipliers "
          f"within 5 %, {int((mx > 15).sum())} are out by more than 15 % — "
          f"with the size key exactly right, so this is the method's own cost")

    print()
    r_spread = float(np.corrcoef(mx, sp)[0, 1])
    r_cell = float(np.corrcoef(mx, cell)[0, 1])
    r_k = float(np.corrcoef(mx, kk)[0, 1])
    print(f"    multiplier error vs spread of the true multipliers  "
          f"r = {r_spread:+.3f}")
    print(f"    multiplier error vs cell error                      "
          f"r = {r_cell:+.3f}")
    print(f"    multiplier error vs number of parts                 "
          f"r = {r_k:+.3f}")

    check("the error is the spread of what you are trying to separate",
          r_spread > 0.8,
          f"r = {r_spread:+.3f}, worst error about "
          f"{np.median(mx / sp):.2f} of the spread — proportional splitting "
          f"hands every part the parent's average, so each part's error is "
          f"its distance from that average")
    check("and how much of the table was ESTIMATED says nothing about it",
          abs(r_cell) < 0.3,
          f"r = {r_cell:+.3f}. A split can be {cell.max():.0f} % out cell by "
          f"cell and land its multipliers inside 4 %. The report prints cell "
          f"provenance prominently and it is not a warning about the "
          f"multiplier")
    check("the number of parts is barely in it, as OQ-S-02 found synthetically",
          abs(r_k) < 0.5,
          f"r = {r_k:+.3f} — measured here on published tables, where "
          f"run_split_depth.py said its own levels would not transfer")

    # Can the spread be borrowed from a country that publishes the split?
    print()
    by = collections.defaultdict(dict)
    for r in rows:
        by[r["tag"]][r["parent"]] = r["spread"]
    ratios, rhos = [], []
    for x, y in itertools.combinations(sorted(by), 2):
        common = sorted(set(by[x]) & set(by[y]))
        if len(common) < 6:
            continue
        rhos.append(spearman([by[x][p] for p in common],
                             [by[y][p] for p in common]))
    per_parent = collections.defaultdict(list)
    for r in rows:
        per_parent[r["parent"]].append(r["spread"])
    for vals in per_parent.values():
        if len(vals) >= 2 and min(vals) > 0:
            ratios.append(max(vals) / min(vals))

    if rhos and ratios:
        check("the spread cannot be borrowed from another country as a NUMBER",
              float(np.median(ratios)) > 2.0,
              f"for the same parent the largest country spread is a median "
              f"{np.median(ratios):.1f}x the smallest, up to "
              f"{max(ratios):.1f}x")
        check("but the ordering partly survives, which is what to use it for",
              0.3 < float(np.median(rhos)) < 0.95,
              f"Spearman {np.median(rhos):+.2f} between countries — enough for "
              f"'this sector tends to divide cleanly', not for 'expect 6 %'")

    print()
    med = {p: float(np.median(v)) for p, v in per_parent.items()}
    order = sorted(med, key=med.get)
    print("    parents by median spread across countries — safe first:")
    for p in order:
        vals = per_parent[p]
        print(f"      {p:<9}{med[p]:>7.1f}%   range {min(vals):>5.1f}"
              f"–{max(vals):<5.1f}%   ({len(vals)} table(s))")

    if "I" in med:
        check("accommodation and food service is in the safe third",
              order.index("I") < len(order) / 3,
              f"median spread {med['I']:.1f} %, rank {order.index('I') + 1} of "
              f"{len(order)} — the sector the Spanish pilot divides, and its "
              f"two halves have unusually similar input structures")

    print()
    print("    Verified against a synthetic economy since v1.57, and against")
    print("    a published answer for the first time today.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
