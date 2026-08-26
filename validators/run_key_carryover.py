"""
Last year's published answer beats every proxy, and the clever version adds nothing.

WHAT THREE CONSECUTIVE YEARS MADE POSSIBLE
--------------------------------------------
`run_key_bias.py` asked whether a proxy's bias is stable enough to be worth
knowing, on one sector, one country and two years, and said so itself: "Two
observations are not a calibration and none is proposed here."

`run_source_pairs.py` swept Eurostat for every country-year that publishes an
89-product symmetric table AND structural business statistics, and found
Hungary publishes **2021, 2022 and 2023**. That is the same country's true
split, three years running, with ten downloadable proxies beside each — 316
(split, subsector, proxy) triples observed in all three years.

THE BIAS IS MODERATELY STABLE
-------------------------------
    drift in the bias across 2021-2023      median  2.07 pp   p90 7.04
    size of the bias itself                 median  4.97 pp
    drift as a fraction of the bias         median  0.37
    the true share's own movement           median  2.57 pp

So a bias is roughly a third as volatile as it is large. `run_key_bias.py`'s
other claim — that small biases are the stable ones — survives, weakly:
1.50 pp of drift below the median bias against 2.59 above it, r = +0.154.

WHICH MAKES AN OBVIOUS IDEA LOOK SPECTACULAR
----------------------------------------------
If the bias is stable, measure it on a year the office HAS published and
subtract it from the proxy in the year you need. Out of sample, all six ordered
pairs of years:

    raw proxy                    median 6.91 pp
    bias-corrected proxy         median 1.56 pp   better in 79 % to 90 %

A factor of four. **And it is an artefact.**

THE CONFOUND, WHICH ACCOUNTS FOR ALL OF IT
--------------------------------------------
Subtracting "proxy minus truth, measured in year A" from "proxy in year B"
leaves truth plus the proxy's own year-to-year movement. If the truth barely
moves — and it moves a median 2.57 points — then the arithmetic is a laundered
way of using year A's published answer. So the baseline is not the raw proxy.
It is **carrying the published answer over**:

    from -> to    raw proxy   carry-over   bias-corrected
    2021 -> 2022      7.02       1.39           1.41
    2021 -> 2023      7.16       2.41           1.85
    2022 -> 2021      6.57       1.39           1.42
    2022 -> 2023      7.16       0.97           1.42
    2023 -> 2021      6.57       2.41           1.85
    2023 -> 2022      7.02       0.97           1.42
    mean              6.91       1.59           1.56

**The correction beats plain carry-over in 54 % of splits.** A coin flip. The
proxy contributes nothing once the other year is in hand, and no calibration
is proposed here either.

WHAT IS WORTH KNOWING IS THE PLAIN VERSION
--------------------------------------------
If the office publishes the split for ANY nearby year, use that year's shares
and ignore the proxies:

    one year apart      1.18 pp
    two years apart     2.41 pp
    best real proxy     4.8 pp median, 27.4 at p90 (run_real_key.py)

The engine already refuses to hide a vintage mismatch — an `AllocationKey`
carries `source_year` and the run says when it differs from the table's. What
was missing was the size of the trade, and it is about four to one in favour of
an older answer over a current proxy.

HOW FAR THIS GOES, AND NOT FURTHER
------------------------------------
One country and three years, one of which (2021) is still pandemic-affected.
It says nothing about a five- or ten-year gap, and Eurostat's structural
business statistics do not reach before 2021, so nothing here can be widened
without another office's data. Two years apart already costs twice one year
apart, which is the shape to expect and not a law.

Run:
    python3 validators/run_key_carryover.py
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_real_key import COARSE, DATA, PROXIES, reader  # noqa: E402

GEO = "HU"
YEARS = (2021, 2022, 2023)
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}"
          + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    from quadrium.eurostat import _covers, load_iot

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    files = [(y, DATA / f"naio_10_cp1700_{GEO}_{y}.json",
              DATA / f"sbs_ovw_act_{GEO}_{y}.json") for y in YEARS]
    check("one country publishes its true split three years running, with proxies",
          all(a.exists() and b.exists() for _, a, b in files),
          f"{GEO} {', '.join(str(y) for y in YEARS)} — the only such run "
          f"Eurostat offers (run_source_pairs.py)")
    if not all(a.exists() and b.exists() for _, a, b in files):
        return 1

    coarse = load_iot(DATA / COARSE)
    rec: dict = {}
    for year, f, sbs in files:
        fine = load_iot(f)
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
                for a, kid in enumerate(kids):
                    rec.setdefault((parent, kid, label), {})[year] = \
                        (float(sh[a]), float(truth[a]))

    full = {k: v for k, v in rec.items() if len(v) == len(YEARS)}
    check("and enough of them are observable in every year",
          len(full) >= 200,
          f"{len(full)} (split, subsector, proxy) triples seen in all "
          f"{len(YEARS)} years, out of {len(rec)} seen in any")

    # 1 -- is the bias stable?
    bias = {k: {y: (v[y][0] - v[y][1]) * 100 for y in YEARS}
            for k, v in full.items()}
    drift = np.array([max(b.values()) - min(b.values()) for b in bias.values()])
    mag = np.array([np.mean([abs(x) for x in b.values()])
                    for b in bias.values()])
    moved = np.array([(max(v[y][1] for y in YEARS)
                       - min(v[y][1] for y in YEARS)) * 100
                      for v in full.values()])
    print()
    print(f"    {'drift in the bias across the three years':<44}"
          f"median {np.median(drift):>5.2f} pp")
    print(f"    {'size of the bias itself':<44}"
          f"median {np.median(mag):>5.2f} pp")
    print(f"    {'the true share moves too':<44}"
          f"median {np.median(moved):>5.2f} pp")
    check("a bias is roughly a third as volatile as it is large",
          0.15 < float(np.nanmedian(drift / np.where(mag == 0, np.nan, mag)))
          < 0.7,
          f"median ratio {np.nanmedian(drift / np.where(mag == 0, np.nan, mag)):.2f}"
          f" — stable enough to be tempting, which is the point of the rest of "
          f"this file")
    q = float(np.median(mag))
    check("and run_key_bias.py's 'small biases are the stable ones' survives, weakly",
          float(np.median(drift[mag <= q])) < float(np.median(drift[mag > q])),
          f"{np.median(drift[mag <= q]):.2f} pp of drift below the median bias "
          f"against {np.median(drift[mag > q]):.2f} above it, r = "
          f"{np.corrcoef(mag, drift)[0, 1]:+.3f} — real and not strong")

    # 2 -- the tempting idea, and the baseline it has to beat.
    per: dict = {}
    for (parent, kid, label), v in full.items():
        per.setdefault((parent, label), []).append(v)

    print()
    print(f"    {'from -> to':<16}{'raw proxy':>11}{'carry-over':>13}"
          f"{'bias-corrected':>17}")
    agg = []
    for src, tgt in itertools.permutations(YEARS, 2):
        raw, carry, cor = [], [], []
        for items in per.values():
            sh = np.array([v[tgt][0] for v in items])
            tr = np.array([v[tgt][1] for v in items])
            prev = np.array([v[src][1] for v in items])
            b = np.array([v[src][0] - v[src][1] for v in items])
            adj = np.clip(sh - b, 0, None)
            if adj.sum() <= 0 or prev.sum() <= 0:
                continue
            adj, prev = adj / adj.sum(), prev / prev.sum()
            raw.append(float(np.abs(sh - tr).max() * 100))
            carry.append(float(np.abs(prev - tr).max() * 100))
            cor.append(float(np.abs(adj - tr).max() * 100))
        raw, carry, cor = np.array(raw), np.array(carry), np.array(cor)
        agg.append((abs(src - tgt), np.median(raw), np.median(carry),
                    np.median(cor), float((cor < carry).mean())))
        print(f"    {src} -> {tgt}{'':<6}{np.median(raw):>11.2f}"
              f"{np.median(carry):>13.2f}{np.median(cor):>17.2f}")

    a = np.array(agg)
    print(f"    {'mean':<16}{a[:, 1].mean():>11.2f}{a[:, 2].mean():>13.2f}"
          f"{a[:, 3].mean():>17.2f}")

    check("carrying the published answer over beats every downloadable proxy",
          a[:, 2].mean() < a[:, 1].mean() / 3,
          f"{a[:, 2].mean():.2f} pp against {a[:, 1].mean():.2f} — a factor of "
          f"{a[:, 1].mean() / a[:, 2].mean():.1f}. The true split barely moves "
          f"between adjacent years")
    check("and correcting a proxy by its measured bias adds nothing to that",
          0.4 < a[:, 4].mean() < 0.65
          and abs(a[:, 3].mean() - a[:, 2].mean()) < 0.3,
          f"{a[:, 3].mean():.2f} pp against carry-over's {a[:, 2].mean():.2f}, "
          f"better in {a[:, 4].mean() * 100:.0f} % of splits — a coin flip. "
          f"Subtracting 'proxy minus truth in year A' from the proxy in year B "
          f"is a laundered way of using year A's answer, so the proxy "
          f"contributes nothing once that answer is in hand. No calibration is "
          f"proposed")

    one = a[a[:, 0] == 1]
    two = a[a[:, 0] == 2]
    print()
    print(f"    {'one year apart':<20}{one[:, 2].mean():>6.2f} pp")
    print(f"    {'two years apart':<20}{two[:, 2].mean():>6.2f} pp")
    check("and the cost grows with the gap, so this is not a free substitution",
          float(two[:, 2].mean()) > float(one[:, 2].mean()) * 1.5,
          f"{one[:, 2].mean():.2f} pp at one year against "
          f"{two[:, 2].mean():.2f} at two. One country and three years, one of "
          f"them still pandemic-affected — the shape to expect, not a law, and "
          f"SBS does not reach before 2021 so nothing here can widen it")

    print()
    print("    If the office publishes your split for any nearby year, use")
    print("    that year and ignore the proxies. The clever version of the")
    print("    same idea is the same idea with extra steps.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
