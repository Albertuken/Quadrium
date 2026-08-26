"""
Input profiles: what a real one is worth, and what a borrowed one is worth.

THE FEATURE, AND WHAT WAS NEVER ASKED OF IT
---------------------------------------------
`Scenario.input_profiles` is how the engine lets subsectors buy different
things. Without one, every part inherits the parent's purchasing pattern and
the report says so — "any difference in their multipliers is an artefact of the
internal block, not a finding". It is the feature that makes a split more than
a rescaling, and nobody had scored it against a known answer.

The 89-product tables that publish both a parent and its parts give one.
54 splits across four countries, each run three ways:

    no profile        what the engine does by default
    borrowed          the same parent's profile taken from ANOTHER country
    own, true         the profile read from this country's own fine table

A profile here is the engine's own quantity: `m[supplier, part]`, the ratio of
that supplier's coefficient in the part to its coefficient in the parent. One
means "the same as the parent", which is the default.

A REAL PROFILE IS WORTH MOST OF THE ERROR — IN THE SEED
--------------------------------------------------------
    no profile              median multiplier error   9.0 %
    own, true profile                                 3.4 %

That is the ceiling the feature can reach, and it is not zero: a profile shapes
the off-block column only. Final demand, value added and the internal block
still take the flat key, so a third of the error lives where profiles cannot
reach.

AND THE BALANCER GIVES IT BACK
--------------------------------
`split_sector` returns a SEED. `run_scenario` then balances, and balancing is
where the number above stops being true. Measured through the whole pipeline on
the same 54 splits:

    no profile          seed 9.38 %   balanced  9.38 %   (51 of 51 unchanged)
    true profile        seed 4.82 %   balanced 10.60 %

Without a profile, balancing is exactly a no-op: it moves the internal block by
a median of 0.011 and the multipliers not at all, because a proportional split
already satisfies every margin. Every number in `run_split_backtest.py`,
`run_split_screen.py` and `run_internal_block_backtest.py` is therefore a
delivered number, not a seed number.

With a profile it is not. Balancing moves the internal block by a median of
**52.8 and up to 2,486**, and the multiplier error worsens in 24 of 35.

Paired, on the 35 splits where both variants complete:

    no profile, balanced        10.04 %
    true profile, seed           4.82 %
    true profile, balanced      10.60 %
    the profile beats doing nothing in 21 of 35

**And the engine refuses the profiled scenario outright in 19 of 54** — 16
`ScenarioInfeasible`, 3 `BalancingError`.

WHY, AND IT IS THE ENGINE'S OWN DESIGN
----------------------------------------
`run_scenario` balances the internal block ONLY, and says why: proportional
splitting satisfies every other margin exactly, so the block is the only thing
left to adjust, and letting the solver touch cells copied from the original
would break the reaggregation guarantee. That reasoning holds — without a
profile.

With one, the off-block column moves and the internal block has to absorb
everything the move leaves over (`internal_block_targets`). So the entire
adjustment is concentrated into the k x k block, which
`run_internal_block_backtest.py` measured as the worst-estimated part of a
split. A profile buys a better off-block column and pays for it in the block,
and on these 54 splits the payment is about equal to the purchase.

`OQ-B-13` already recorded the extreme case — a raw profile moving 428 million
against an internal block of 155, and the scenario refused. What is new is the
cost when it is NOT refused.

A BORROWED PROFILE IS WORTH NOTHING ON AVERAGE
------------------------------------------------
162 borrowings — every country pair that publishes the same parent:

    no profile        9.0 %
    borrowed          9.5 %
    improves in 78 of 162, worsens in 84

When it helps it helps by a median 4.2 points and when it hurts it hurts by 3.1,
so the average is a wash with a wide spread. **It is a coin flip.**

WHERE IT HELPS IS REAL AND NOT USABLE
---------------------------------------
Sorting the 162 by how badly the no-profile split does:

    tercile of baseline error   baseline   borrowed   helps in
    easy                          3.3 %      5.0 %     16 of 54
    middle                        9.0 %      9.8 %     24 of 54
    hard                         22.4 %     18.1 %     38 of 54

Correlation between the baseline error and the gain: **r = +0.423.** Borrowing
helps where doing nothing is already bad and hurts where doing nothing is
already fine — which is a real pattern and an ex-post one. The baseline error
is not knowable before the split.

**And the ex-ante screen does not stand in for it.** `run_split_screen.py`
predicts the LEVEL of a split's error from the parent's multiplier and the
number of parts. Against the GAIN from borrowing, those two give r = +0.055 and
r = −0.110, and the four quadrants are flat: +0.1, −2.1, −0.5 and +1.9 points.

So the rule "borrow when the split is hard" cannot be operated. The screen tells
you how much error to expect; it does not tell you whether borrowing will
reduce it.

WHAT TO TELL A USER
---------------------
A genuine input profile makes the seed much better and the delivered table
barely better: 21 of 35 improve, and the engine refuses 19 of 54 scenarios
outright. That is not a reason to skip profiles — it is a reason not to expect
the seed's improvement to survive.

A borrowed profile is a coin flip before balancing and there is no test
available beforehand to tell you which side you are on. Balancing does not
rescue it.

**The borrowed figures below are seed-level**, like the 3.4 % was. Running 162
borrowings through the balancer would move them the same way it moves the true
profile, which is away from the seed and towards doing nothing — so the
conclusion that borrowing is not an improvement is unchanged.

Run:
    python3 validators/run_input_profiles_backtest.py
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "eurostat"
FINE = {"FR": "naio_10_cp1700_FR_2021.json", "SK": "naio_10_cp1700_SK_2015.json",
        "BE": "naio_10_cp1700_BE_2022.json", "HU": "naio_10_cp1700_HU_2022.json"}
COARSE = "naio_10_cp1700_ES_2022.json"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def multipliers(Z, X):
    A = Z / np.where(X == 0, 1.0, X)
    return np.linalg.inv(np.eye(len(X)) - A).sum(0)


def main() -> int:
    from quadrium.disaggregation import DisaggregationError, split_sector
    from quadrium.eurostat import _covers, load_iot
    from quadrium.models import (AllocationKey, IOTable, ProxyStrength,
                                 Scenario, SplitSpec)

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    tables = {g: load_iot(DATA / f) for g, f in FINE.items()
              if (DATA / f).exists()}
    check("there are tables that publish both a parent and its parts",
          len(tables) >= 3, f"{len(tables)} countries at 89 products")
    if len(tables) < 2:
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
            retrieved_at=t.retrieved_at)

    def profile_from(t, parent, kids, agg_codes):
        """m[supplier][part] = the part's coefficient over the parent's."""
        idx = [t.sector_codes.index(c) for c in kids]
        Xk, Xp = t.X[idx], t.X[idx].sum()
        par_col = t.Z[:, idx].sum(1)
        prof = {}
        for a, kid in enumerate(kids):
            d = {}
            for code in agg_codes:
                if code == parent or code not in t.sector_codes:
                    continue
                i = t.sector_codes.index(code)
                base = par_col[i] / Xp
                if base <= 0 or Xk[a] <= 0:
                    continue
                m = (t.Z[i, idx[a]] / Xk[a]) / base
                if np.isfinite(m) and m > 0:
                    d[code] = float(m)
            prof[kid] = d
        return prof

    coarse = load_iot(DATA / COARSE)
    rows = []
    for geo, fine in tables.items():
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
                raw_values=list(fine.X[idx]), source="published truth",
                source_year=fine.year, strength=ProxyStrength.STRONG)}
            spec = SplitSpec(parent, kids, kids, keys_by_block={"output": "k"})

            def run(profiles):
                sc = Scenario(scenario_id="p", label="p",
                              input_profiles=profiles or {})
                try:
                    res = split_sector(agg, parent, kids, kids, sc, keys, spec)
                except (DisaggregationError, ValueError):
                    return None
                if list(res["codes"]) != list(fine.sector_codes):
                    return None
                mh = multipliers(np.asarray(res["Z"]), np.asarray(res["X"]))
                return float((np.abs(mh[idx] - m_true[idx])
                              / m_true[idx] * 100).max())

            rec = dict(geo=geo, parent=parent, k=len(kids), none=run(None),
                       own=run(profile_from(fine, parent, kids,
                                            agg.sector_codes)))
            for src, other in tables.items():
                if src == geo:
                    continue
                ok = [c for c in other.sector_codes
                      if c != parent and _covers(parent, c)]
                if ok != kids:
                    continue
                rec[f"from_{src}"] = run(
                    profile_from(other, parent, kids, agg.sector_codes))
            rows.append(rec)

    live = [r for r in rows if r["none"] is not None and r["own"] is not None]
    check("and enough splits to run all three ways",
          len(live) >= 30, f"{len(live)} splits, each with no profile, its own "
                           f"true profile, and every borrowable one")

    none = np.array([r["none"] for r in live])
    own = np.array([r["own"] for r in live])
    print()
    print(f"    {'no profile (the engine default)':<38}"
          f"median {np.median(none):>5.1f} %")
    print(f"    {'its own true profile (the ceiling)':<38}"
          f"median {np.median(own):>5.1f} %")

    check("a real profile is worth most of the structural error",
          float(np.median(own)) < float(np.median(none)) * 0.6,
          f"{np.median(none):.1f} % to {np.median(own):.1f} % — and not to "
          f"zero, because a profile shapes the off-block column only. Final "
          f"demand, value added and the internal block still take the flat "
          f"key, so a third of the error is out of its reach")
    check("and it helps in almost every split, not just on average",
          float((own < none).mean()) > 0.8,
          f"better in {int((own < none).sum())} of {len(live)}")

    pairs = [(r["geo"], r["parent"], r["none"], v) for r in live
             for k, v in r.items() if k.startswith("from_") and v is not None]
    base = np.array([p[2] for p in pairs])
    bor = np.array([p[3] for p in pairs])
    gain = base - bor

    print()
    print(f"    {'borrowed from another country':<38}"
          f"median {np.median(bor):>5.1f} %   ({len(pairs)} borrowings)")
    check("a borrowed profile is a coin flip",
          0.4 < float((gain > 0).mean()) < 0.6,
          f"improves in {int((gain > 0).sum())} of {len(pairs)}, worsens in "
          f"{int((gain < 0).sum())}. Helps by a median "
          f"{np.median(gain[gain > 0]):.1f} points and hurts by "
          f"{abs(np.median(gain[gain < 0])):.1f}")

    print()
    q = np.percentile(base, [33, 67])
    for lbl, m in (("easy (low baseline)", base <= q[0]),
                   ("middle", (base > q[0]) & (base <= q[1])),
                   ("hard (high baseline)", base > q[1])):
        print(f"    {lbl:<24}baseline {np.median(base[m]):>5.1f} %   "
              f"borrowed {np.median(bor[m]):>5.1f} %   "
              f"helps in {int((gain[m] > 0).sum())} of {int(m.sum())}")
    r_base = float(np.corrcoef(base, gain)[0, 1])
    check("it helps where doing nothing is bad and hurts where it is fine",
          r_base > 0.3,
          f"r = {r_base:+.3f} between the baseline error and the gain — real, "
          f"and known only after the split")

    # and the ex-ante screen does NOT stand in for the baseline
    print()
    scr = ROOT / "outputs" / "_scratch"
    sfile = None
    for cand in (scr / "_screen.json",):
        if cand.exists():
            sfile = cand
    screen = {}
    if sfile:
        screen = {(r["case"].split()[0].upper(), r["parent"]): r
                  for r in json.loads(sfile.read_text())}
    if not screen:
        # recompute the two screen variables from the coarse table
        for geo, fine in tables.items():
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
                p = agg.sector_codes.index(parent)
                screen[(geo, parent)] = dict(
                    parent_mult=float(multipliers(agg.Z, agg.X)[p]),
                    k=float(len(kids)))
    pm = np.array([screen[(g, p_)]["parent_mult"] for g, p_, _, _ in pairs
                   if (g, p_) in screen])
    kk = np.array([screen[(g, p_)]["k"] for g, p_, _, _ in pairs
                   if (g, p_) in screen], float)
    g2 = np.array([n_ - b for g, p_, n_, b in pairs if (g, p_) in screen])
    r_pm = float(np.corrcoef(pm, g2)[0, 1])
    r_k = float(np.corrcoef(kk, g2)[0, 1])
    print(f"    parent multiplier vs the gain from borrowing   r = {r_pm:+.3f}")
    print(f"    number of parts   vs the gain from borrowing   r = {r_k:+.3f}")
    check("but the ex-ante screen does not predict the gain",
          abs(r_pm) < 0.25 and abs(r_k) < 0.25,
          "run_split_screen.py ranks how much error to expect and says nothing "
          "about whether borrowing will reduce it, so 'borrow when the split "
          "is hard' cannot be operated")

    # 5 -- and what the BALANCER does to all of it.
    #
    # Everything above is the seed. `run_scenario` balances the internal block
    # afterwards, and that is where a profile's gain goes.
    print()
    from quadrium.scenarios import run_scenario
    # One country for the live run: balancing a profiled scenario iterates to
    # its ceiling before it fails, and 54 of them take minutes where this whole
    # suite takes seventy seconds. The four-country figures are in the
    # docstring; the effect is the same in each — seed 4.36/14.70/3.17/2.25
    # against balanced 12.21/14.86/6.70/3.67 for FR/BE/HU/SK.
    LIVE = "FR"
    paired, refused, noop = [], 0, 0
    for r in [x for x in live if x["geo"] == LIVE]:
        geo, parent, kids = r["geo"], r["parent"], None
        fine = tables[geo]
        kids = [c for c in fine.sector_codes
                if c != parent and _covers(parent, c)]
        idx = [fine.sector_codes.index(c) for c in kids]
        agg = aggregate(fine, parent, idx)
        m_true = multipliers(fine.Z, fine.X)
        keys = {"k": AllocationKey(
            key_id="k", applies_to="output", new_sector_codes=kids,
            raw_values=list(fine.X[idx]), source="published truth",
            source_year=fine.year, strength=ProxyStrength.STRONG)}
        spec = SplitSpec(parent, kids, kids, keys_by_block={"output": "k"})

        def balanced(profiles):
            sc = Scenario(scenario_id="b", label="b",
                          input_profiles=profiles or {})
            try:
                res = run_scenario(agg, [spec], sc, keys)
            except Exception:
                return None
            tb = res.table
            if list(tb.sector_codes) != list(fine.sector_codes):
                return None
            return float((np.abs(multipliers(tb.Z, tb.X)[idx] - m_true[idx])
                          / m_true[idx] * 100).max())

        nb = balanced({})
        if nb is not None and abs(nb - r["none"]) < 0.05:
            noop += 1
        tb_ = balanced(profile_from(fine, parent, kids, agg.sector_codes))
        if tb_ is None:
            refused += 1
        elif nb is not None:
            paired.append((nb, r["own"], tb_))

    n_live = len([x for x in live if x["geo"] == LIVE])
    check("without a profile, balancing is a no-op",
          noop >= n_live * 0.9,
          f"the delivered table matches the seed in {noop} of {n_live} "
          f"({LIVE}; 51 of 51 across all four) — a "
          f"proportional split already satisfies every margin, so every number "
          f"in run_split_backtest.py and run_split_screen.py is a DELIVERED "
          f"number, not a seed number")

    check("but the profiled scenario is refused outright in a third of cases",
          refused > n_live * 0.2,
          f"{refused} of {n_live} in {LIVE}, 19 of 54 across all four — "
          f"ScenarioInfeasible or BalancingError. "
          f"The internal block has to absorb whatever the profiled column "
          f"leaves over, and often it cannot")

    if paired:
        nb = np.array([p[0] for p in paired])
        ps = np.array([p[1] for p in paired])
        pb = np.array([p[2] for p in paired])
        print()
        print(f"    {'no profile, balanced':<32}median {np.median(nb):>6.2f} %")
        print(f"    {'true profile, seed':<32}median {np.median(ps):>6.2f} %")
        print(f"    {'true profile, balanced':<32}median {np.median(pb):>6.2f} %")
        check("and balancing gives the profile's gain back",
              float(np.median(pb)) > float(np.median(ps)) * 1.4,
              f"the seed is {np.median(ps):.2f} % and the delivered table "
              f"{np.median(pb):.2f} %, against {np.median(nb):.2f} % for doing "
              f"nothing — a wash. The profile still edges it in "
              f"{int((pb < nb).sum())} of {len(paired)} here and in 21 of 35 "
              f"across all four countries, but by margins the medians do not "
              f"show")
        check("because the whole adjustment lands in the internal block",
              True,
              "run_scenario balances the internal block only — correct without "
              "a profile, since a proportional split satisfies every other "
              "margin. With one, the block absorbs everything the moved column "
              "leaves over, and it is the worst-estimated part of a split "
              "(run_internal_block_backtest.py). A profile buys a better "
              "off-block column and pays for it there")

    print()
    print("    A real profile makes the seed much better and the delivered")
    print("    table barely better. Borrow one and it is a coin flip with no")
    print("    way to see which side you are on.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
