"""
A key an analyst could actually get, scored against the answer.

WHAT WAS MEASURED BEFORE, AND ON HOW MUCH
-------------------------------------------
`OQ-S-05` measured one allocation key, for one sector, in one country: Spain's
accommodation share of hospitality output is 23.95 %, the pilot's production key
said 33.73 %, and **the key with the best conceptual match was the third worst
of seven while the loosest — employment — was the best**. That is a striking
lesson and it rests on a single split.

`run_split_backtest.py` then measured what a split costs with the key exactly
RIGHT: 7.8 % median error in the subsectors' multipliers. Nobody had measured
what a real key costs, at scale.

Eurostat's structural business statistics (`sbs_ovw_act`) publish ten variables
at full NACE detail — output value, turnover, value added, persons employed,
employees, FTE, wages, purchases, gross operating surplus, enterprises — the
same set the Spanish pilot registered. Against the symmetric tables that publish
both the parent and its parts, that gives **39 splits x up to 10 published
proxies in 3 countries**, each scored against the office's own answer.

HOW WRONG IS A REAL KEY
-------------------------
Largest error in a subsector's share, in percentage points:

    proxy                    n    median    worst    within 5 pp
    value of output         37     5.2       58.1      16 of 37
    net turnover            37     5.1       54.6      16 of 37
    wages and salaries      37     7.1       32.8      11 of 37
    purchases               37     7.1       43.4      16 of 37
    value added             37     7.2       66.8      13 of 37
    gross operating surplus 34     8.0       70.2       9 of 34
    persons employed        38     8.4       42.1      12 of 38
    FTE employees           38     8.6       40.3      13 of 38
    employees               38     9.1       43.3      12 of 38
    number of enterprises   39    11.7       50.2      10 of 39

Over every proxy and split: **median 7.9 points, p90 28.8, worst 70.2.**

NO PROXY IS RELIABLY BEST, AND THE PILOT'S LESSON DOES NOT GENERALISE
-----------------------------------------------------------------------
Output value has the best median — and wins outright in **1 split of 39**. The
per-split winner is scattered across every proxy on the list: purchases 10, GOS
7, wages 5, enterprises 3, FTE 3, value added 3, turnover 3, employed 2,
employees 2, output 1. Head to head, output value beats employment in **20 of
37** — a coin flip.

So output has the best median because it is rarely terrible, not because it is
usually right. Neither "use the closest conceptual match" nor `OQ-S-05`'s
inversion of it survives contact with 39 splits.

**And Spain's hospitality is an outlier.** Its production key is 9.8 points out.
The same key on the same sector elsewhere:

                        ES     FR     BE     HU
    production        +9.8   +3.9   +3.2   +2.3
    employment        -2.7   -4.1   +0.6   -6.7

The pilot picked an unusually bad case for its chosen key, which is why the
lesson looked so sharp.

**Nor is there a systematic sign.** `run_key_bias.py` found all seven Spanish
keys overstating accommodation and explained it by the enterprise/product
mismatch — the survey counts a hotel's restaurant as accommodation. The
mechanism is real and it does not produce a general lean: across 39 splits the
output-value key is a median +0.6 points with 22 of 37 positive, and employment
+0.7 with 21 of 38. Balanced. The Spanish case is a strong instance, not the
rule.

AND THE OBVIOUS PROXY IS NOT AVAILABLE AT ALL
-----------------------------------------------
National accounts employment (`nama_10_a64_e`) is the first thing an analyst
would reach for, and it is published at **exactly the aggregation of the table
being split** — it carries `I`, not `I55` and `I56`. Checked against all 15
parents: zero have their children covered. The detail only exists in structural
business statistics, which are enterprise-basis where the table is
product-basis. That mismatch is not a shortcut anyone took; it is the only road
there is.

WHAT THIS MEANS FOR A RESULT
------------------------------
Roughly 5 to 8 points of key error is the realistic case, with a long tail.

The multiplier is **not moved by it at all** — not approximately: running these
same 372 keys through the engine gives multipliers identical to the ones the
published answer gives, in 372 of 372, because the key cancels out of the
multiplier recursion. That is an identity, and `run_key_invariance.py` proves
it and checks it; this file used to assert it in prose with nothing behind it.
The multiplier's own error, a median 7.8 %, is structural and is measured
separately (`run_split_backtest.py`).

What the key does move is **size**, and a point of share error costs more than
a point of subsector. The error is relative to a part that may be small, so it
is amplified by a median factor of 3.8: at these key errors the worst part's
output is out by a median **31 %**, and only 45 of the 372 keys put every
subsector within 10 % of its true size.

It also supports what the report already does. Since no proxy is reliably best,
the spread across the proxies a user registers is the honest thing to print —
and `run_key_bias.py`'s finding stands: that spread is a **lower bound** on
uncertainty, not a confidence interval.

Run:
    python3 validators/run_real_key.py
"""

from __future__ import annotations

import collections
import itertools
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "eurostat"
COARSE = "naio_10_cp1700_ES_2022.json"
CASES = (("FR", 2021, "naio_10_cp1700_FR_2021.json"),
         ("BE", 2022, "naio_10_cp1700_BE_2022.json"),
         ("HU", 2022, "naio_10_cp1700_HU_2022.json"))
PROXIES = (("VAL_OUT_MEUR", "value of output"), ("NETTUR_MEUR", "net turnover"),
           ("WAGE_MEUR", "wages and salaries"), ("PUR_MEUR", "purchases"),
           ("AV_MEUR", "value added"), ("GOS_MEUR", "gross operating surplus"),
           ("EMP_NR", "persons employed"), ("SAL_FTE_NR", "FTE employees"),
           ("SAL_NR", "employees"), ("ENT_NR", "number of enterprises"))
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def reader(path: Path):
    """Random access into a JSON-stat cube, by dimension value."""
    d = json.loads(path.read_text())
    ids, size = d["id"], d["size"]
    idx = {k: d["dimension"][k]["category"]["index"] for k in ids}
    stride = [1] * len(size)
    for i in range(len(size) - 2, -1, -1):
        stride[i] = stride[i + 1] * size[i + 1]

    def at(**kw):
        pos = 0
        for i, k in enumerate(ids):
            v = kw.get(k) if kw.get(k) is not None else (
                next(iter(idx[k])) if len(idx[k]) == 1 else None)
            j = idx[k].get(v) if v is not None else None
            if j is None:
                return None
            pos += j * stride[i]
        return d["value"].get(str(pos))
    return at, idx


def main() -> int:
    from quadrium.eurostat import _covers, load_iot

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    have = [c for c in CASES if (DATA / c[2]).exists()
            and (DATA / f"sbs_ovw_act_{c[0]}_{c[1]}.json").exists()]
    check("there are tables with both an answer and a published proxy",
          len(have) >= 2,
          f"{len(have)} country-years with a symmetric table at 89 products AND "
          f"structural business statistics for the same year")
    if not have:
        return 0

    coarse = load_iot(DATA / COARSE)
    rows = []
    for geo, year, f in have:
        fine = load_iot(DATA / f)
        at, _ = reader(DATA / f"sbs_ovw_act_{geo}_{year}.json")
        for parent in coarse.sector_codes:
            kids = [c for c in fine.sector_codes
                    if c != parent and _covers(parent, c)]
            if len(kids) < 2:
                continue
            i = [fine.sector_codes.index(c) for c in kids]
            if fine.X[i].min() <= 0:
                continue
            truth = fine.X[i] / fine.X[i].sum()
            for code, label in PROXIES:
                vals = [at(nace_r2=k, indic_sbs=code) for k in kids]
                if any(v is None for v in vals):
                    continue
                v = np.array(vals, float)
                if v.sum() <= 0 or (v < 0).any():
                    continue
                share = v / v.sum()
                rows.append(dict(geo=geo, parent=parent, proxy=code,
                                 label=label,
                                 err=float(np.abs(share - truth).max() * 100),
                                 signed=float((share - truth)[0] * 100)))

    splits = {(r["geo"], r["parent"]) for r in rows}
    check("and enough of them to say anything",
          len(splits) >= 25 and len(rows) >= 200,
          f"{len(splits)} splits x up to {len(PROXIES)} published proxies = "
          f"{len(rows)} scored keys")

    print()
    print(f"    {'proxy':<26}{'n':>4}{'median':>10}{'worst':>9}{'within 5 pp':>14}")
    med = {}
    for code, label in PROXIES:
        s = np.array([r["err"] for r in rows if r["proxy"] == code])
        if not s.size:
            continue
        med[label] = float(np.median(s))
        print(f"    {label:<26}{len(s):>4}{np.median(s):>9.1f}{s.max():>9.1f}"
              f"{int((s <= 5).sum()):>10} /{len(s):>3}")

    allv = np.array([r["err"] for r in rows])
    check("a real key is wrong by single-digit points, with a long tail",
          5.0 < float(np.median(allv)) < 15.0
          and float(np.percentile(allv, 90)) > 20.0,
          f"median {np.median(allv):.1f} pp over every proxy and split, "
          f"p90 {np.percentile(allv, 90):.1f}, worst {allv.max():.1f}")

    # which proxy actually wins, split by split
    print()
    wins = collections.Counter()
    for _, grp in itertools.groupby(
            sorted(rows, key=lambda r: (r["geo"], r["parent"])),
            key=lambda r: (r["geo"], r["parent"])):
        g = list(grp)
        wins[min(g, key=lambda r: r["err"])["label"]] += 1
    print("    proxy that wins each split:")
    for lbl, c in wins.most_common():
        print(f"      {lbl:<28}{c:>3}")

    best_med = min(med, key=med.get)
    check("the best median proxy almost never wins a split outright",
          wins[best_med] <= 3 and len(wins) >= 6,
          f"'{best_med}' has the best median at {med[best_med]:.1f} pp and wins "
          f"{wins[best_med]} of {sum(wins.values())} splits outright — best on "
          f"median because it is rarely terrible, not because it is usually "
          f"right. The winner is scattered over {len(wins)} different proxies")

    out = {(r["geo"], r["parent"]): r["err"]
           for r in rows if r["proxy"] == "VAL_OUT_MEUR"}
    emp = {(r["geo"], r["parent"]): r["err"]
           for r in rows if r["proxy"] == "EMP_NR"}
    both = [(out[k], emp[k]) for k in out if k in emp]
    w = sum(1 for a, b in both if a < b)
    check("and head to head with employment it is a coin flip",
          0.4 < w / len(both) < 0.7,
          f"output value beats employment in {w} of {len(both)}. Neither 'use "
          f"the closest conceptual match' nor OQ-S-05's inversion of it "
          f"survives 39 splits")

    # the Spanish case, and whether its sign generalises
    print()
    ho = {r["geo"]: r["signed"] for r in rows
          if r["parent"] == "I" and r["proxy"] == "VAL_OUT_MEUR"}
    if ho:
        print("    hospitality, production key, signed error on accommodation:")
        print("      ES  +9.8  (the pilot)   "
              + "   ".join(f"{g} {v:+.1f}" for g, v in sorted(ho.items())))
        check("Spain's hospitality is an unusually bad case for that key",
              all(abs(v) < 9.8 for v in ho.values()),
              f"the pilot's 9.8 points against "
              f"{min(ho.values()):+.1f} to {max(ho.values()):+.1f} elsewhere — "
              f"which is why the lesson looked so sharp")

    for code, label in (("VAL_OUT_MEUR", "output value"),
                        ("EMP_NR", "employment")):
        v = np.array([r["signed"] for r in rows if r["proxy"] == code])
        check(f"the {label} key has no systematic sign across sectors",
              abs(float(np.median(v))) < 2.0
              and 0.4 < float((v > 0).mean()) < 0.65,
              f"median {np.median(v):+.1f} pp, {int((v > 0).sum())} of "
              f"{len(v)} positive. run_key_bias.py found all seven Spanish "
              f"keys leaning one way and explained it by the "
              f"enterprise/product mismatch; the mechanism is real and it does "
              f"not produce a general lean")

    # the proxy an analyst reaches for first, which does not exist at this level
    print()
    na = DATA / "nama_10_a64_e_FR_2021.json"
    if na.exists():
        _, nidx = reader(na)
        codes = set(nidx["nace_r2"])
        covered = 0
        total = 0
        fine = load_iot(DATA / have[0][2])
        for parent in coarse.sector_codes:
            kids = [c for c in fine.sector_codes
                    if c != parent and _covers(parent, c)]
            if len(kids) < 2:
                continue
            total += 1
            covered += all(k in codes for k in kids)
        check("national-accounts employment cannot serve as a key at all",
              covered == 0,
              f"{covered} of {total} parents have their children in "
              f"nama_10_a64_e — it is published at exactly the aggregation of "
              f"the table you are splitting. The detail only exists in "
              f"business statistics, which are enterprise-basis where the "
              f"table is product-basis")

    print()
    print("    One key, one sector, one country made a sharp lesson. Thirty-")
    print("    nine splits make a duller and more usable one: pick for the")
    print("    concept, expect five to eight points, and print the spread.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
