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

A REAL PROFILE IS WORTH MOST OF THE ERROR
-------------------------------------------
    no profile              median multiplier error   9.0 %
    own, true profile                                 3.4 %

That is the ceiling the feature can reach, and it is not zero: a profile shapes
the off-block column only. Final demand, value added and the internal block
still take the flat key, so a third of the error lives where profiles cannot
reach. Worth knowing before anyone spends a month sourcing one.

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
If you can source a genuine input profile for your subsectors, it is worth
about two thirds of the structural error. If you are thinking of borrowing one
from a country that publishes the split, the measurement says it is a coin flip
and there is no test available beforehand to tell you which side you are on.

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

    print()
    print("    Source a real profile and it is worth two thirds of the")
    print("    structural error. Borrow one and it is a coin flip with no")
    print("    way to see which side you are on.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
