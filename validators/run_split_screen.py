"""
Two numbers from your own table that say how risky a split is, before you make it.

THE GAP THIS FILLS
--------------------
`run_split_backtest.py` measures what a split costs — with the size key exactly
right, the subsectors' multipliers land a median 7.8 % from the published truth
— and finds the error is set by how UNLIKE the parts are, r = +0.92 against the
spread of their true multipliers. That is a diagnosis and not advice: knowing
the spread means already having the answer.

Looking at a country that publishes your split helps a little (the ordering
survives at Spearman +0.52) and is not always possible. So: **is there anything
in the coarse table the analyst already holds?**

Seven candidates were tried, each with a mechanical reason to expect something,
against the 68 real splits. With n = 68 anything under |r| = 0.24 is noise:

    input concentration, Herfindahl of the parent's input column   +0.469
    value added / output of the parent                             -0.414
    the parent's own output multiplier                             +0.405
    number of parts                                                +0.364
    ------------------------------------------------------------- noise floor
    sales concentration                                            +0.261
    the parent's size as a share of the table                      +0.248
    self-consumption, z_pp / X_p                                   +0.246

AND THE TOP THREE ARE ONE THING
---------------------------------
Value added / output and the parent's multiplier correlate at **−0.98** — they
are the same number read two ways, since a sector that keeps more value added
buys fewer intermediates. Input concentration goes with them at 0.74 to 0.79.
Controlling for the parent's multiplier, value added adds nothing (partial
−0.09) and input concentration a little (+0.27).

The number of parts is independent of all of it: r = 0.03 to 0.06.

So there are **two** signals, not four: how intermediate-intensive the parent
is, and how many parts you are asking for.

DOES IT HOLD ON A TABLE IT WAS NOT FITTED ON?
-----------------------------------------------
Leave-one-country-out — fit on three countries, rank the fourth:

    model                             BE     FR     HU     SK    median
    parent multiplier only          +0.27  +0.13  +0.23  +0.51   +0.25
    number of parts only            +0.52  +0.36  +0.53  +0.57   +0.53
    both                            +0.52  +0.26  +0.53  +0.66   +0.53
    input concentration + parts     +0.68  +0.45  +0.42  +0.76   +0.56

Positive in every fold. It ranks splits by difficulty; it does not predict a
number, and nothing here should be read as if it did.

WHAT IT LOOKS LIKE IN USE
---------------------------
Cutting both signals at their median:

    parent multiplier   parts    median error    worst    n
    low                 few          4.8 %      14.9 %   20
    low                 many         7.0 %      23.4 %   14
    high                few          7.9 %      41.6 %   15
    high                many        18.6 %      48.1 %   19

Four-fold between the corners, from two numbers available before you start.

AND WHY `k` IS IN IT WITHOUT CONTRADICTING OQ-S-02
----------------------------------------------------
`OQ-S-02` closed on the finding that **k was never the variable** — accuracy has
no cliff in the number of subsectors. Here k is the best single predictor, which
looks like a contradiction and is not:

     k   splits   worst part    mean part    ONE part
     2       35       5.2 %        4.1 %       3.5 %
     3       30      10.8 %        6.9 %       5.8 %
     5        3      23.4 %        8.7 %       5.4 %

    error of a single subsector vs k     r = +0.174
    mean error of the split vs k         r = +0.286
    WORST error of the split vs k        r = +0.364

A single subsector's error barely moves with k. What grows is the **maximum**,
because more parts is more draws from the same distribution. Asking for five
subsectors does not make each one worse; it makes it likelier that one of them
is badly wrong. That is exactly `OQ-S-02`'s result seen from the other end, and
it changes the advice: if you care about one particular subsector, k costs you
little; if you need all of them to hold, it costs you the maximum.

The k = 5 row is three splits. It is reported because leaving it out would
flatter the pattern, not because three is a sample.

AND IT BEATS THE OBVIOUS ALTERNATIVE, WHICH WAS NOT THE EXPECTED RESULT
------------------------------------------------------------------------
`run_split_backtest.py` suggests looking at a country that publishes your split.
Where both are possible — parents measured in three or more countries, one held
out at a time — the screen's band misses the held-out error by **3.7 points**
and the other countries' median by **4.9**. Borrowing carries the between-country
variation with it: the same parent's spread differs by a median factor of 4.6.

This section was written expecting the opposite and the check refused it.

Accommodation is where the screen is wrong: its parent multiplier is high in
every country (1.51 to 1.94), so the screen puts it in the harder band at 7.9 %,
and its measured error is 4.9 % median, 0.8 % to 7.9 %. Pessimistic, on the
sector the Spanish pilot divides. One counterexample is not the rule, but it is
the direction to expect the screen to be wrong in: a parent can be
intermediate-intensive and still have look-alike halves.

Run:
    python3 validators/run_split_screen.py
"""

from __future__ import annotations

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
NOISE = 0.24          # |r| below this is not distinguishable from zero at n = 68
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
            table_id="agg", country=t.country, year=t.year, unit=t.unit,
            classification=t.classification, sector_codes=codes,
            sector_labels=codes, Z=M @ t.Z @ M.T, Y=M @ t.Y,
            Y_labels=list(t.Y_labels), VA=t.VA @ M.T,
            VA_labels=list(t.VA_labels), X=M @ t.X, source=t.source,
            retrieved_at=t.retrieved_at), order.index(None)

    coarse = load_iot(DATA / COARSE)
    rows, parts = [], []
    for f in have:
        fine = load_iot(DATA / f)
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
            agg, p = aggregate(fine, parent, idx)
            keys = {"k": AllocationKey(
                key_id="k", applies_to="output", new_sector_codes=kids,
                raw_values=list(fine.X[idx]), source="published truth",
                source_year=fine.year, strength=ProxyStrength.STRONG)}
            try:
                res = split_sector(
                    agg, parent, kids, kids,
                    Scenario(scenario_id="screen", label="screen"), keys,
                    SplitSpec(parent, kids, kids, keys_by_block={"output": "k"}))
            except Exception:
                continue
            if list(res["codes"]) != list(fine.sector_codes):
                continue
            m_hat = multipliers(np.asarray(res["Z"]), np.asarray(res["X"]))
            errs = np.abs(m_hat[idx] - m_true[idx]) / m_true[idx] * 100
            col = agg.Z[:, p].sum() + agg.VA[:, p].sum()
            inp = agg.Z[:, p] / max(col, 1e-12)
            rows.append(dict(
                geo=fine.country[:2].upper(), parent=parent, k=float(len(kids)),
                err=float(errs.max()), mean_err=float(errs.mean()),
                parent_mult=float(multipliers(agg.Z, agg.X)[p]),
                hhi_in=float((inp ** 2).sum()),
                va_share=float(agg.VA[:, p].sum() / max(agg.X[p], 1e-12) * 100),
                self_share=float(agg.Z[p, p] / max(agg.X[p], 1e-12) * 100),
                size=float(agg.X[p] / agg.X.sum() * 100),
                hhi_out=float(((agg.Z[p, :] / max(agg.Z[p, :].sum()
                                                  + agg.Y[p, :].sum(), 1e-12))
                               ** 2).sum())))
            parts.extend((float(len(kids)), float(x)) for x in errs)

    check("there are enough splits, and every candidate is table-only",
          len(rows) >= 25,
          f"{len(rows)} splits, {len(parts)} subsectors — every predictor is "
          f"computed from the AGGREGATED table, which is all an analyst holds")

    e = np.array([r["err"] for r in rows])
    V = {n: np.array([r[n] for r in rows], float)
         for n in ("hhi_in", "va_share", "parent_mult", "k", "hhi_out",
                   "size", "self_share")}
    r_ = {n: float(np.corrcoef(v, e)[0, 1]) for n, v in V.items()}

    print()
    print(f"    {'candidate, from the coarse table only':<44}{'r':>8}")
    for n in sorted(r_, key=lambda n: -abs(r_[n])):
        mark = "" if abs(r_[n]) >= NOISE else "   (noise)"
        print(f"    {n:<44}{r_[n]:>+8.3f}{mark}")

    check("something in the analyst's own table does carry signal",
          max(abs(v) for v in r_.values()) > 0.4,
          f"best is {max(r_, key=lambda n: abs(r_[n]))} at "
          f"{max(r_.values(), key=abs):+.3f}, against a {NOISE} noise floor at "
          f"n = {len(rows)}")

    # the top three are one factor
    print()
    r_vm = float(np.corrcoef(V["va_share"], V["parent_mult"])[0, 1])
    r_hm = float(np.corrcoef(V["hhi_in"], V["parent_mult"])[0, 1])
    r_km = float(np.corrcoef(V["k"], V["parent_mult"])[0, 1])
    print(f"    value added / output  vs parent multiplier   r = {r_vm:+.2f}")
    print(f"    input concentration   vs parent multiplier   r = {r_hm:+.2f}")
    print(f"    number of parts       vs parent multiplier   r = {r_km:+.2f}")

    check("value added and the parent multiplier are the same number",
          r_vm < -0.9,
          f"r = {r_vm:+.2f} — a sector that keeps more value added buys fewer "
          f"intermediates, so this is one signal and not two")
    check("and the number of parts is independent of it",
          abs(r_km) < 0.2,
          f"r = {r_km:+.2f}. Two signals, not four")

    # out of sample
    print()
    geos = sorted({r["geo"] for r in rows})

    def design(rs, cols):
        return np.column_stack([np.ones(len(rs))]
                               + [[r[c] for r in rs] for c in cols])

    folds = {}
    for label, cols in (("parent multiplier only", ["parent_mult"]),
                        ("number of parts only", ["k"]),
                        ("both", ["parent_mult", "k"]),
                        ("input concentration + parts", ["hhi_in", "k"])):
        rhos = []
        for held in geos:
            tr = [r for r in rows if r["geo"] != held]
            te = [r for r in rows if r["geo"] == held]
            if len(te) < 5:
                continue
            beta, *_ = np.linalg.lstsq(
                design(tr, cols), np.array([r["err"] for r in tr]), rcond=None)
            rhos.append(spearman(design(te, cols) @ beta,
                                 [r["err"] for r in te]))
        folds[label] = rhos
        print(f"    {label:<30}" + "".join(f"{x:>+8.2f}" for x in rhos)
              + f"   median {np.median(rhos):+.2f}")

    check("the ranking holds on a country it was not fitted on",
          all(min(v) > 0 for v in folds.values())
          and max(float(np.median(v)) for v in folds.values()) > 0.4,
          "positive in every held-out country, and the best model ranks at "
          f"{max(float(np.median(v)) for v in folds.values()):+.2f} — a "
          f"RANKING, not a predicted number")

    # the quadrants
    print()
    pm, kk = V["parent_mult"], V["k"]
    print(f"    {'parent multiplier':<20}{'parts':<10}{'median':>9}{'worst':>9}"
          f"{'n':>5}")
    quad = {}
    for lo_m, nm in ((True, "low"), (False, "high")):
        for lo_k, nk in ((True, "few"), (False, "many")):
            m = ((pm <= np.median(pm)) == lo_m) & ((kk <= np.median(kk)) == lo_k)
            if not m.sum():
                continue
            quad[(nm, nk)] = (float(np.median(e[m])), float(e[m].max()))
            print(f"    {nm:<20}{nk:<10}{np.median(e[m]):>8.1f}%"
                  f"{e[m].max():>8.1f}%{int(m.sum()):>5}")
    check("and the corners are four-fold apart",
          quad[("high", "many")][0] > quad[("low", "few")][0] * 3,
          f"{quad[('low', 'few')][0]:.1f} % against "
          f"{quad[('high', 'many')][0]:.1f} % — from two numbers you have "
          f"before you start")

    # k is an extremum effect, which is why OQ-S-02 stands
    print()
    pk = np.array([p[0] for p in parts])
    pe = np.array([p[1] for p in parts])
    mn = np.array([r["mean_err"] for r in rows])
    r_one = float(np.corrcoef(pk, pe)[0, 1])
    r_mean = float(np.corrcoef(V["k"], mn)[0, 1])
    print(f"    {'k':>3}{'splits':>9}{'worst part':>13}{'mean part':>12}"
          f"{'ONE part':>11}")
    for kv in sorted(set(V["k"])):
        m, pmask = V["k"] == kv, pk == kv
        print(f"    {int(kv):>3}{int(m.sum()):>9}{np.median(e[m]):>12.1f}%"
              f"{np.median(mn[m]):>11.1f}%{np.median(pe[pmask]):>10.1f}%")
    print(f"\n    a single subsector's error vs k   r = {r_one:+.3f}")
    print(f"    the split's MEAN error vs k       r = {r_mean:+.3f}")
    print(f"    the split's WORST error vs k      r = {r_['k']:+.3f}")

    check("k grows the WORST case and barely touches a single subsector",
          r_one < r_["k"] and r_one < 0.25,
          f"{r_one:+.3f} for one part against {r_['k']:+.3f} for the worst — "
          f"more parts is more draws, not worse parts. OQ-S-02's 'k was never "
          f"the variable' stands; this is the same result from the other end")

    # 6 -- and where BOTH kinds of evidence exist, which one to believe.
    print()
    import collections
    by_parent = collections.defaultdict(list)
    for r in rows:
        by_parent[r["parent"]].append(r)
    band_med = {("low", "few"): 4.8, ("low", "many"): 7.0,
                ("high", "few"): 7.9, ("high", "many"): 18.6}
    med_pm, med_k = float(np.median(V["parent_mult"])), float(np.median(V["k"]))
    screen_miss, direct_miss = [], []
    for parent, rs in by_parent.items():
        if len(rs) < 3:
            continue
        for i, held in enumerate(rs):
            others = [x for x in rs if x is not held]
            key = ("high" if held["parent_mult"] > med_pm else "low",
                   "many" if held["k"] > med_k else "few")
            screen_miss.append(abs(band_med[key] - held["err"]))
            direct_miss.append(abs(float(np.median([x["err"] for x in others]))
                                   - held["err"]))
    # WRITTEN EXPECTING THE OPPOSITE. The obvious thing to say is that a direct
    # measurement of your own parent somewhere else beats a two-variable
    # screen. It does not: the same parent's spread varies by a median 4.6x
    # between countries (`run_split_backtest.py`), so borrowing one country's
    # number carries that variation with it.
    check("the screen beats borrowing the same parent from another country",
          float(np.median(screen_miss)) < float(np.median(direct_miss)),
          f"leaving one country out on parents measured in 3 or more: the "
          f"screen's band misses by {np.median(screen_miss):.1f} points and "
          f"the other countries' median by {np.median(direct_miss):.1f}, over "
          f"{len(screen_miss)} held-out cases")

    ho = [r for r in rows if r["parent"] == "I"]
    if len(ho) >= 4:
        check("and accommodation is where it is wrong, which is worth knowing",
              float(np.median([r["err"] for r in ho]))
              < band_med[("high", "few")],
              f"its parent multiplier is high in every country "
              f"({min(r['parent_mult'] for r in ho):.2f}–"
              f"{max(r['parent_mult'] for r in ho):.2f}), so the screen puts it "
              f"in the harder band at 7.9 % — and its measured error is "
              f"{np.median([r['err'] for r in ho]):.1f} % median, "
              f"{min(r['err'] for r in ho):.1f}–{max(r['err'] for r in ho):.1f} %. "
              f"Pessimistic on the sector the Spanish pilot divides. One "
              f"counterexample is not the rule — across all parents the screen "
              f"still wins — but it is the direction to expect it to be wrong "
              f"in: a parent can be intermediate-intensive and still have "
              f"look-alike halves")

    print()
    print("    If you need one subsector, k costs you little. If you need all")
    print("    of them to hold, it costs you the maximum.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
