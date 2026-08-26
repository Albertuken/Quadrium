"""
The range across the keys you did not use: honest, and nearly uninformative.

WHAT THE REPORT TELLS EVERY USER, AND ON WHAT
-----------------------------------------------
`reporting.py` prints this beside every corroborated split:

    And this spread is a floor on your uncertainty, not a confidence interval.
    Keys drawn from one survey tend to err the same way, so the whole spread
    can sit on one side of the answer.

The evidence behind it is `run_key_bias.py`: **one sector, one country, two
years** — Spanish hospitality in 2021 and 2022, where all seven of the pilot's
keys overstate accommodation in the first year and the range misses the truth
by 0.6 points. That file says so itself: "Two observations are not a
calibration and none is proposed here."

There are now 65 splits across five country-years where the office publishes
both the parent and its parts AND structural business statistics publish up to
ten proxies for the same year — FR 2021, BE 2022 and HU 2021, 2022 and 2023.
That is 162 subsectors with an answer next to them.

THE COMMON LEAN IS THE EXCEPTION, NOT THE RULE
------------------------------------------------
    every available proxy on the same side of the answer   16.0 % of subsectors

So "keys drawn from one survey tend to err the same way" is false as a general
statement. Spanish hospitality is again the unusual case — as `run_real_key.py`
already found for the SIZE of its error, where 9.8 points sat against 2.3 to
3.9 for the same key and sector elsewhere.

THE CONCLUSION SURVIVES ANYWAY, FOR A DIFFERENT REASON
--------------------------------------------------------
    the range contains the truth        84.0 % of subsectors
    it contains every subsector at once 75.4 % of splits  (49 of 65)
    width of the range                  median 28.1 points

It misses one split in four. And when it does contain the answer, it does so
across a median of **28 points of share** — a range that wide excludes almost
nothing. It is not a confidence interval and it is not much of a floor either:
it is honest and nearly uninformative, and the report should say both.

AND THE WIDTH DOES NOT WARN YOU
---------------------------------
The obvious rescue — trust a narrow range, distrust a wide one — is backwards:

    splits where the range CONTAINS the truth   median width 27.8 points
    splits where it MISSES                                   38.6

The misses are the WIDER ones, so a wide range is not a flag you can act on;
it is simply a worse range. Nor is the verdict a property of the sector: of the
13 parents that appear in more than one country-year, the range agrees with
itself in only 7 — and three of the five country-years are Hungary in
consecutive years, so that is as much about years as about countries.

TRIMMING THE EXTREMES DOES NOT RESCUE IT EITHER
-------------------------------------------------
If width is the problem, drop the highest and lowest proxy and re-measure. On
the 159 subsectors with at least five proxies:

    full range           coverage 84.9 %   median width 20.5 points
    extremes dropped              59.7 %                12.2

It ends up missing 40 % of subsectors and is still 12 points wide — short of
being narrow and short of being right. Trading 25 points of coverage for 8.3
points of width does not cross the line between "wide and honest" and "narrow
and correct"; it lands outside both. No trimmed interval is proposed, and the
negative result is recorded here rather than left as an untried idea.

(Widths differ between the sections above because one is the widest subsector
in a split and the other is per subsector. Each section is internally
consistent; the comparisons are within a section, never across.)

Run:
    python3 validators/run_key_spread.py
"""
from __future__ import annotations

import collections
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_real_key import CASES, COARSE, DATA, PROXIES, reader  # noqa: E402

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

    have = [c for c in CASES if (DATA / c[2]).exists()
            and (DATA / f"sbs_ovw_act_{c[0]}_{c[1]}.json").exists()]
    check("there are splits with both a published answer and published proxies",
          len(have) >= 2,
          f"{len(have)} country-years at 89 products with structural business "
          f"statistics for the same year")
    if len(have) < 2:
        return 1 if FAIL else 0

    coarse = load_iot(DATA / COARSE)
    splits = []
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
            shares = []
            for code, _ in PROXIES:
                v = [at(nace_r2=c, indic_sbs=code) for c in kids]
                if any(x is None for x in v):
                    continue
                v = np.array(v, float)
                if v.sum() <= 0 or (v < 0).any():
                    continue
                shares.append(v / v.sum())
            if len(shares) >= 3:
                splits.append((geo, parent, truth, np.array(shares)))

    check("and enough of them to say something the pilot could not",
          len(splits) >= 25,
          f"{len(splits)} splits, {sum(len(s[2]) for s in splits)} subsectors "
          f"with the office's own answer beside them — against the one sector, "
          f"one country and two years run_key_bias.py had")

    # 1 -- do the proxies lean together, as the report says they tend to?
    inside_sub, inside_split, one_side, width, verdict = [], [], [], [], []
    for geo, parent, truth, S in splits:
        lo, hi = S.min(0), S.max(0)
        ins = (truth >= lo - 1e-12) & (truth <= hi + 1e-12)
        inside_sub.extend(ins.tolist())
        inside_split.append(bool(ins.all()))
        one_side.extend((((S > truth).all(0)) | ((S < truth).all(0))).tolist())
        width.append(float((hi - lo).max() * 100))
        verdict.append((parent, bool(ins.all())))

    sub = np.array(inside_sub)
    spl = np.array(inside_split)
    lean = np.array(one_side)
    w = np.array(width)

    print()
    print(f"    {'every proxy on the same side of the answer':<44}"
          f"{lean.mean() * 100:>5.1f} % of subsectors")
    check("the common lean the report describes is the exception",
          float(lean.mean()) < 0.35,
          f"{lean.mean() * 100:.1f} % — 'keys drawn from one survey tend to err "
          f"the same way' does not hold in general. Spanish hospitality is the "
          f"unusual case again, as it was for the size of the error in "
          f"run_real_key.py")

    # 2 -- and the conclusion survives anyway, on the numbers that matter.
    print(f"    {'the range contains the truth':<44}"
          f"{sub.mean() * 100:>5.1f} % of subsectors")
    print(f"    {'it contains every subsector at once':<44}"
          f"{spl.mean() * 100:>5.1f} % of splits ({int(spl.sum())} of "
          f"{len(spl)})")
    print(f"    {'width of the range':<44}median {np.median(w):>5.1f} points")

    check("the range is not a confidence interval, and misses one split in four",
          float(spl.mean()) < 0.85,
          f"it contains every subsector in {int(spl.sum())} of {len(spl)} "
          f"splits. The report's conclusion is right; its stated reason is not")
    check("and where it does contain the answer, it barely constrains it",
          float(np.median(w)) > 15.0,
          f"a median {np.median(w):.1f} points of share. A range that wide "
          f"excludes almost nothing — honest, and nearly uninformative")

    # 3 -- can the width itself be used as a flag? No: backwards.
    print()
    print(f"    {'splits where the range CONTAINS the truth':<44}"
          f"median width {np.median(w[spl]):>5.1f}")
    print(f"    {'splits where it MISSES':<44}"
          f"{'':<13}{np.median(w[~spl]):>5.1f}")
    check("a narrow range is not a safer one",
          float(np.median(w[~spl])) >= float(np.median(w[spl])),
          f"the misses are the WIDER ranges ({np.median(w[~spl]):.1f} against "
          f"{np.median(w[spl]):.1f}), so 'narrow means trustworthy' is exactly "
          f"backwards and there is no flag here to act on")

    by = collections.defaultdict(set)
    for parent, ok in verdict:
        by[parent].add(ok)
    repeated = {p: v for p, v in by.items() if len(by[p]) or True}
    multi = [p for p in by
             if sum(1 for q, _ in verdict if q == p) > 1]
    agree = sum(1 for p in multi if len(by[p]) == 1)
    check("nor is the verdict a property of the sector",
          len(multi) >= 5 and agree < len(multi),
          f"of the {len(multi)} parents that appear in more than one "
          f"country-year, the range agrees with itself in {agree}. Whether it "
          f"covers the answer is not something the sector tells you — and "
          f"three of the five country-years are the same country in "
          f"consecutive years, so this is a statement about years as much as "
          f"about countries")
    _ = repeated

    # 4 -- trimming the extremes: the obvious rescue, measured and refused.
    full_c, trim_c, full_w, trim_w = [], [], [], []
    for geo, parent, truth, S in splits:
        if len(S) < 5:
            continue
        Ss = np.sort(S, axis=0)
        for lo, hi, cov, wid in ((S.min(0), S.max(0), full_c, full_w),
                                 (Ss[1], Ss[-2], trim_c, trim_w)):
            cov.extend(((truth >= lo - 1e-12)
                        & (truth <= hi + 1e-12)).tolist())
            wid.extend(((hi - lo) * 100).tolist())

    if len(full_c) >= 30:
        fc, tc = np.array(full_c), np.array(trim_c)
        fw, tw = np.array(full_w), np.array(trim_w)
        print()
        print(f"    on the {len(fc)} subsectors with at least five proxies:")
        print(f"      {'full range':<22}coverage {fc.mean() * 100:>5.1f} %   "
              f"median width {np.median(fw):>5.1f}")
        print(f"      {'extremes dropped':<22}coverage {tc.mean() * 100:>5.1f} "
              f"%   median width {np.median(tw):>5.1f}")
        check("and trimming the extremes does not buy a usable interval",
              float(tc.mean()) < 0.70 and float(np.median(tw)) > 10.0,
              f"it ends up missing {(1 - tc.mean()) * 100:.0f} % of subsectors "
              f"and is still {np.median(tw):.1f} points wide. Trading "
              f"{(fc.mean() - tc.mean()) * 100:.0f} points of coverage for "
              f"{np.median(fw) - np.median(tw):.1f} points of width does not "
              f"cross the line from 'wide and honest' to 'narrow and right' — "
              f"it lands short of both. No trimmed interval is proposed; this "
              f"is recorded as the negative result it is")

    print()
    print("    The range is honest about being uncertain and says almost")
    print("    nothing about where the answer is. Both halves belong in the")
    print("    report, and only one of them was in it.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
