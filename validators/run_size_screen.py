"""
How wrong a subsector's SIZE will be, from one division you can do beforehand.

THE HALF NOTHING PREDICTED
----------------------------
`run_split_screen.py` ranks how badly a split will estimate its subsectors'
MULTIPLIERS, from two numbers in the analyst's own table. `run_key_invariance.py`
then showed that the allocation key cannot move a multiplier at all — the share
cancels out of the coefficients — so that screen was already independent of the
key, which is good.

But it left the other half unattended. What the key DOES move is size, and it
moves it hard: at the error a real downloadable proxy carries, the worst
subsector's output is out by a median **32 %**, and only 77 of 638 real keys put
every subsector within 10 %. Nothing predicted that.

WHAT DOES NOT WORK: A SECOND RANKING SCREEN
---------------------------------------------
The obvious move is to copy the multiplier screen — find signals, cut at their
medians, print bands. Two signals rank the size error on 638 pairs:

    log(1 / smallest share the proxy gives any part)   Spearman +0.442
    number of parts                                    Spearman +0.384

They are **not independent** (r = +0.671 — more parts is mechanically a smaller
smallest part), and the four-way band table does not transfer. Held out one
country at a time, Belgium inverts: its "small share, many parts" corner comes
in at 29.7 % against 47.8 % for "small share, few parts", the opposite of the
other two folds, and two of its cells hold one and six observations. **No
quadrant screen is proposed**, and this is recorded as the negative result it is
rather than fitted until it looks convincing.

WHAT DOES WORK IS NOT A RANKING AT ALL
----------------------------------------
The algebra says what the answer has to be. A proportional split gives part *i*
an output of `share_i x X_parent`, so an error of *e* POINTS in that share is an
error of `e / share_i` in the part's own size. Nothing to fit and no cut points:

    size error  ~=  key error in points  /  that part's share

Calibrated on 1,583 subsector-and-proxy pairs, using `run_real_key.py`'s own
distribution of key error:

    with the median key error (7.3 pp)   covers 64.3 %   real/predicted 0.65
    with the p90 key error   (27.4 pp)   covers 92.2 %

Held out one country at a time, the second row is 92.8 / 88.7 / 92.9 % for BE /
FR / HU, and the rank correlation is +0.33 to +0.44 in every fold. So the
median figure is a central estimate — the truth runs about 0.7 of it — and the
p90 figure is a band that holds better than nine times in ten.

WHY IT MATTERS MOST FOR THE SMALL PART
----------------------------------------
At a typical 7.3 points of key error:

    a part with 50 % of the parent   output out by   15 %
                25 %                                 29 %
                10 %                                 73 %
                 5 %                                146 %

This is why "my key is only a few points off" is not reassurance. A few points
is the whole of a small subsector.

HOW FAR IT GOES
-----------------
Five country-years across three countries, and the constant it needs — how many
points a key is typically out by — comes from those same tables. An office whose
business statistics match its product classification more closely than
Eurostat's would carry a smaller constant and the same formula.

Run:
    python3 validators/run_size_screen.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_real_key import CASES, COARSE, DATA, PROXIES, reader  # noqa: E402

KEY_MEDIAN = 7.3      # run_real_key.py, over every proxy and split
KEY_P90 = 27.4
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}"
          + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def spearman(a, b) -> float:
    """Rank correlation without a scipy dependency."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3:
        return float("nan")

    def rank(x):
        order = np.argsort(x, kind="mergesort")
        r = np.empty(len(x), float)
        r[order] = np.arange(len(x), dtype=float)
        # average ties, so a proxy that repeats a share is not ordered by luck
        _, first, counts = np.unique(x[order], return_index=True,
                                     return_counts=True)
        for f, c in zip(first, counts):
            if c > 1:
                r[order[f:f + c]] = r[order[f:f + c]].mean()
        return r
    ra, rb = rank(a), rank(b)
    return float(np.corrcoef(ra, rb)[0, 1])


def main() -> int:
    from quadrium.eurostat import _covers, load_iot

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    coarse = load_iot(DATA / COARSE)
    per_sub, per_split = [], []
    for geo, year, f in CASES:
        sbs = DATA / f"sbs_ovw_act_{geo}_{year}.json"
        if not (DATA / f).exists() or not sbs.exists():
            continue
        fine = load_iot(DATA / f)
        at, _ = reader(sbs)
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
                v = [at(nace_r2=c, indic_sbs=code) for c in kids]
                if any(x is None for x in v):
                    continue
                v = np.array(v, float)
                if v.sum() <= 0 or (v < 0).any():
                    continue
                sh = v / v.sum()
                worst = float((np.abs(sh - truth) / truth * 100).max())
                per_split.append((geo, float(sh.min()), float(len(kids)),
                                  worst))
                for a in range(len(kids)):
                    if sh[a] <= 0:
                        continue
                    per_sub.append((geo, float(sh[a]),
                                    float(abs(sh[a] - truth[a])
                                          / truth[a] * 100)))

    check("there are real keys with the office's own answer beside them",
          len(per_sub) >= 800,
          f"{len(per_sub)} subsector-and-proxy pairs over {len(per_split)} "
          f"key-and-split pairs, {len(CASES)} country-years")
    if len(per_sub) < 800:
        return 1 if FAIL else 0

    # 1 -- the ranking screen that does NOT survive being held out.
    g_s = np.array([r[0] for r in per_split])
    small = np.array([np.log(1.0 / max(r[1], 1e-6)) for r in per_split])
    k = np.array([r[2] for r in per_split])
    worst = np.array([r[3] for r in per_split])

    print()
    print(f"    {'log(1 / smallest share the proxy gives)':<44}"
          f"Spearman {spearman(small, worst):+.3f}")
    print(f"    {'number of parts':<44}"
          f"Spearman {spearman(k, worst):+.3f}")
    collinear = float(np.corrcoef(small, k)[0, 1])
    check("the two candidate signals are not independent",
          collinear > 0.5,
          f"r = {collinear:+.3f} — more parts is mechanically a smaller "
          f"smallest part, so this is one signal wearing two hats, unlike the "
          f"multiplier screen's pair (r = 0.03)")

    inverts = []
    for held in sorted(set(g_s)):
        tr, te = g_s != held, g_s == held
        cm, ck = float(np.median(small[tr])), float(np.median(k[tr]))
        few = worst[te][(small[te] > cm) & (k[te] <= ck)]
        many = worst[te][(small[te] > cm) & (k[te] > ck)]
        if len(few) and len(many):
            inverts.append((held, float(np.median(few)),
                            float(np.median(many))))
    print()
    for held, few, many in inverts:
        print(f"    held out {held}: small share + few parts {few:>6.1f} %   "
              f"+ many parts {many:>6.1f} %")
    signs = {f < m for _, f, m in inverts}
    check("and the four-way band table does not transfer between countries",
          len(signs) > 1,
          "one fold ranks its corners the opposite way round from the others, "
          "on cells holding as few as one observation. No quadrant screen is "
          "proposed — recorded as a negative result rather than fitted until "
          "it convinces")

    # 2 -- the thing that does work, and it is the algebra rather than a fit.
    g_u = np.array([r[0] for r in per_sub])
    share = np.array([r[1] for r in per_sub])
    actual = np.array([r[2] for r in per_sub])

    print()
    for kp, tag in ((KEY_MEDIAN, "median key error"), (KEY_P90, "p90")):
        pred = kp / (share * 100) * 100
        cov = float((actual <= pred).mean())
        print(f"    {tag + f' ({kp} pp)':<28}covers {cov * 100:>5.1f} %   "
              f"real/predicted median "
              f"{np.median(actual / np.where(pred == 0, np.nan, pred)):.2f}")

    pred_med = KEY_MEDIAN / (share * 100) * 100
    ratio = float(np.median(actual / np.where(pred_med == 0, np.nan, pred_med)))
    check("the median key error gives a central estimate, not a bound",
          0.5 < ratio < 1.0,
          f"the truth runs {ratio:.2f} of it. `size error = key error in "
          f"points / that part's share` needs no fitting and no cut points — "
          f"it is what a proportional split does, calibrated")

    pred_hi = KEY_P90 / (share * 100) * 100
    folds = []
    for held in sorted(set(g_u)):
        m = g_u == held
        folds.append((held, float((actual[m] <= pred_hi[m]).mean()),
                      spearman(pred_hi[m], actual[m])))
    print()
    for held, cov, sp in folds:
        print(f"    held out {held}: p90 band covers {cov * 100:>5.1f} %   "
              f"Spearman {sp:+.3f}")
    check("and the p90 key error gives a band that holds in every country",
          all(c > 0.85 for _, c, _ in folds)
          and all(s > 0.25 for _, _, s in folds),
          f"{', '.join(f'{h} {c * 100:.1f} %' for h, c, _ in folds)} — better "
          f"than nine times in ten, with the rank order preserved in each "
          f"({', '.join(f'{s:+.2f}' for _, _, s in folds)})")

    print()
    print(f"    at {KEY_MEDIAN} points of key error, a part holding:")
    for s in (0.50, 0.25, 0.10, 0.05):
        print(f"      {s * 100:>4.0f} % of the parent   output out by "
              f"{KEY_MEDIAN / (s * 100) * 100:>5.0f} %")
    check("which is why a key being 'only a few points off' is not reassurance",
          True,
          "a few points is the whole of a small subsector, and the split "
          "screen's multiplier bands say nothing about it because the key "
          "cannot reach a multiplier (run_key_invariance.py)")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
